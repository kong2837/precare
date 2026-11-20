from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import math
import random
import time

import requests

from fitbit.google_health.token import refresh_google_health_token
from fitbit.google_health.client import google_time_to_kst_naive
from fitbit.models import FitbitMinuteMetric
from fitbit.utils import normalize_to_minute


KST = timezone(timedelta(hours=9))
MAX_RATE_LIMIT_RETRIES = 3
MAX_RATE_LIMIT_WAIT = 60


class SpO2FetchError(RuntimeError):
    """The requested day's complete API response could not be obtained."""


def _retry_after_seconds(response):
    """Accept both Retry-After formats without trusting malformed headers."""
    header = response.headers.get("Retry-After")
    if not isinstance(header, str) or not header.strip():
        return None
    header = header.strip()
    try:
        if header.isdigit():
            return int(header)
        retry_at = parsedate_to_datetime(header)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0, (retry_at - datetime.now(timezone.utc)).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return None


def _defer_rate_limited_account(account, seconds):
    # Transient state only: do not save this field or touch authentication data.
    try:
        account._spo2_retry_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
    except OverflowError:
        account._spo2_retry_at = datetime.max.replace(tzinfo=timezone.utc)


def fetch_spo2(date, account, *, allow_token_refresh=True):
    """Fetch all pages for one KST day without writing health measurements.

    A 401 can refresh and save the authentication token once, unless disabled.
    Physical-time filters match the KST conversion used when saving data.
    See https://developers.google.com/health/reference/rest/v4/users.dataTypes.dataPoints/list
    """
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except (TypeError, ValueError) as exc:
        raise SpO2FetchError("날짜는 YYYY-MM-DD 형식이어야 합니다.") from exc

    retry_at = getattr(account, "_spo2_retry_at", None)
    if retry_at is not None and retry_at > datetime.now(timezone.utc):
        raise SpO2FetchError("HTTP 429 대기 중인 계정입니다. 이후 수집에서 다시 시도합니다.")

    start = datetime.combine(target_date, datetime.min.time(), tzinfo=KST)
    end = start + timedelta(days=1)
    start_utc = start.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    end_utc = end.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    filter_expr = (
        f'oxygen_saturation.sample_time.physical_time >= "{start_utc}" '
        f'AND oxygen_saturation.sample_time.physical_time < "{end_utc}"'
    )

    url = "https://health.googleapis.com/v4/users/me/dataTypes/oxygen-saturation/dataPoints"
    params = {"pageSize": 1000, "filter": filter_expr}
    datapoints = []
    page_count = 0
    seen_tokens = set()
    refreshed = False
    rate_limit_retries = 0

    while True:
        headers = {
            "Authorization": f"Bearer {account.access_token}",
            "Accept": "application/json",
        }
        try:
            response = requests.get(url, headers=headers, params=params.copy(), timeout=20)
        except requests.RequestException as exc:
            # Do not include request objects, tokens or response bodies in logs.
            raise SpO2FetchError("SpO₂ API 네트워크 요청에 실패했습니다.") from exc

        if response.status_code == 429:
            retry_after = _retry_after_seconds(response)
            if rate_limit_retries >= MAX_RATE_LIMIT_RETRIES:
                _defer_rate_limited_account(account, max(retry_after or 0, MAX_RATE_LIMIT_WAIT))
                raise SpO2FetchError("SpO₂ API HTTP 429: 3회 재시도 후에도 호출 제한이 지속됩니다.")
            delay = max(2 ** (rate_limit_retries + 1) + random.uniform(0, 1), retry_after or 0)
            if delay > MAX_RATE_LIMIT_WAIT:
                # Do not shorten the server's requested wait and retry too early.
                _defer_rate_limited_account(account, delay)
                raise SpO2FetchError("SpO₂ API HTTP 429: 요구 대기 시간이 60초를 초과하여 수집을 미룹니다.")
            rate_limit_retries += 1
            print(
                f"⚠️ user_id={account.user_id} | {date} | HTTP 429 | "
                f"{delay:.1f}초 대기 후 같은 페이지 재시도 "
                f"{rate_limit_retries}/{MAX_RATE_LIMIT_RETRIES}"
            )
            time.sleep(delay)
            continue

        if response.status_code == 401 and allow_token_refresh and not refreshed:
            refreshed = True
            try:
                token_refreshed = refresh_google_health_token(account)
            except requests.RequestException as exc:
                raise SpO2FetchError("Google Health 토큰 갱신 요청에 실패했습니다.") from exc
            if token_refreshed:
                continue
            raise SpO2FetchError("Google Health 토큰 갱신에 실패했습니다.")

        if response.status_code != 200:
            raise SpO2FetchError(f"SpO₂ API 요청 실패: HTTP {response.status_code}")

        try:
            data = response.json()
        except ValueError as exc:
            raise SpO2FetchError("SpO₂ API 응답이 올바른 JSON이 아닙니다.") from exc
        if not isinstance(data, dict) or not isinstance(data.get("dataPoints", []), list):
            raise SpO2FetchError("SpO₂ API 응답의 dataPoints 형식이 올바르지 않습니다.")

        datapoints.extend(data.get("dataPoints", []))
        page_count += 1
        rate_limit_retries = 0
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        if not isinstance(page_token, str) or page_token in seen_tokens:
            raise SpO2FetchError("SpO₂ API의 다음 페이지 토큰이 잘못되었거나 반복됩니다.")
        seen_tokens.add(page_token)
        params["pageToken"] = page_token

    return {
        "dataPoints": datapoints,
        "api_point_count": len(datapoints),
        "page_count": page_count,
        "query_filter": filter_expr,
    }


def get_spo2(date, account):
    try:
        data = fetch_spo2(date, account)
    except SpO2FetchError as exc:
        print(f"❌ user_id={account.user_id} | {date} | {exc}")
        return None

    datapoints = data["dataPoints"]
    if not datapoints:
        print(
            f"ℹ️ user_id={account.user_id} | {date} | SpO₂ 데이터 없음. "
            f"(API 원본 0건 / {data['page_count']}페이지)"
        )
        return None

    minutes, matched, invalid = spo2_minutes_for_date(datapoints, date)
    # A reused Google account can contain data preceding this research cohort.
    # Later replacements are routed by ParticipantMetricManager as before.
    joined_at = getattr(account, "join_date", None)
    if joined_at is not None and joined_at.tzinfo is not None:
        joined_at = joined_at.astimezone(KST).replace(tzinfo=None)
    ended_at = getattr(account, "end_date", None)
    # A replaced source's end_date must not cut off a later participant's data.
    if getattr(account, "participant_ended_at", None) is not None:
        ended_at = None
    if ended_at is not None and ended_at.tzinfo is not None:
        ended_at = ended_at.astimezone(KST).replace(tzinfo=None)

    saved = 0
    created_count = 0
    updated_count = 0
    for ts, (measured_at, value) in sorted(minutes.items()):
        if joined_at is not None and (measured_at < joined_at or ts < joined_at):
            continue
        if ended_at is not None and measured_at >= ended_at:
            continue

        obj, created = FitbitMinuteMetric.objects.get_or_create(
            account=account,
            timestamp=ts,
            defaults={"spo2": value},
        )

        if not created:
            if obj.spo2 != value:
                obj.spo2 = value
                obj.save(update_fields=["spo2"])
                saved += 1
                updated_count += 1
        else:
            saved += 1
            created_count += 1

    data.update(
        minute_count=len(minutes), matched_count=matched, invalid_count=invalid,
        created_count=created_count, updated_count=updated_count,
    )

    print(
        f"✅ user_id={account.user_id} | {date} | SpO₂ {saved}건 저장 완료. "
        f"(API 원본 {data['api_point_count']}건 / {data['page_count']}페이지 / "
        f"해당 날짜 {matched}건)"
    )
    return data


def spo2_minutes_for_date(datapoints, date):
    """Select the latest valid observation in each KST minute, independent of page order."""
    minutes = {}
    matched = 0
    invalid = 0
    for point in datapoints:
        try:
            sample = point["oxygenSaturation"]
            physical_time = sample["sampleTime"]["physicalTime"]
            value = sample["percentage"]
            if not physical_time or isinstance(value, bool):
                raise ValueError
            value = float(value)
            if not math.isfinite(value) or not 0 <= value <= 100:
                raise ValueError
            measured_at = google_time_to_kst_naive(physical_time)
            if measured_at is None:
                raise ValueError
        except (KeyError, TypeError, ValueError, AttributeError, OverflowError):
            invalid += 1
            continue
        if measured_at.date().isoformat() != date:
            continue
        matched += 1
        minute = normalize_to_minute(measured_at)
        previous = minutes.get(minute)
        if previous is None or measured_at > previous[0]:
            minutes[minute] = (measured_at, value)
    return minutes, matched, invalid
