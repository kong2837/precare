import datetime
import requests

from django.utils import timezone

from fitbit.sync.sync import update_last_synced
from fitbit.google_health.token import refresh_google_health_token
from fitbit.google_health.client import google_time_to_kst_naive
from fitbit.models import FitbitMinuteMetric
from fitbit.utils import normalize_to_minute


def get_heart_rate(date, account):
    """
    지정한 날짜(KST 기준)의 심박수 데이터를 Google Health에서 가져와
    1분 단위로 FitbitMinuteMetric에 저장한다.

    - API 요청 단계에서 날짜 범위를 필터링
    - nextPageToken을 이용해 모든 페이지 조회
    - 같은 분에 여러 심박수가 있으면 가장 최근 측정값 사용
    - 과거 날짜 백필 시 last_synced를 과거로 되돌리지 않음
    """

    try:
        target_date = datetime.datetime.strptime(
            date,
            "%Y-%m-%d"
        ).date()
    except ValueError:
        print(f"❌ 잘못된 날짜 형식: {date}")
        return None

    next_date = target_date + datetime.timedelta(days=1)

    headers = {
        "Authorization": f"Bearer {account.access_token}",
        "Accept": "application/json",
    }

    url = (
        "https://health.googleapis.com/v4/users/me/"
        "dataTypes/heart-rate/dataPoints"
    )

    # Google Health API의 sample civil time 기준 날짜 필터
    filter_expr = (
        f'heart_rate.sample_time.civil_time >= "{target_date.isoformat()}" '
        f'AND heart_rate.sample_time.civil_time < "{next_date.isoformat()}"'
    )

    page_token = None

    # key: 분 단위 timestamp
    # value: (실제 측정 시각, bpm)
    minute_values = {}

    latest_hr_dt = None
    api_point_count = 0
    page_count = 0

    while True:
        params = {
            "pageSize": 10000,
            "filter": filter_expr,
        }

        if page_token:
            params["pageToken"] = page_token

        try:
            response = requests.get(
                url,
                headers=headers,
                params=params,
                timeout=20,
            )

        except requests.RequestException as e:
            print(
                f"❌ {account.user.username} | {date} | "
                f"심박수 API 요청 오류: {e}"
            )
            return None

        # Access token 만료
        if response.status_code == 401:
            print(
                f"⚠️ {account.user.username} | "
                "Google Health 토큰 만료. 갱신 시도 중..."
            )

            if refresh_google_health_token(account):
                return get_heart_rate(date, account)

            print("❌ 토큰 갱신 실패. 요청 중단. heart rate")
            return None

        # 그 외 오류
        if response.status_code != 200:
            print(
                f"❌ Google Health 심박수 요청 실패: "
                f"{response.status_code}"
            )
            print(response.text)
            return None

        data = response.json()
        datapoints = data.get("dataPoints", [])

        page_count += 1
        api_point_count += len(datapoints)

        for point in datapoints:
            hr = point.get("heartRate", {})

            sample_time = hr.get("sampleTime", {})
            physical_time = sample_time.get("physicalTime")
            bpm = hr.get("beatsPerMinute")

            if not physical_time or bpm is None:
                continue

            dt_raw = google_time_to_kst_naive(physical_time)

            if dt_raw is None:
                continue

            # API filter가 있더라도 안전하게 날짜 재검증
            if dt_raw.date() != target_date:
                continue

            try:
                bpm = int(bpm)
            except (TypeError, ValueError):
                continue

            # DB에는 분 단위로 저장
            dt = normalize_to_minute(dt_raw)

            # 같은 분에 여러 심박 데이터가 있으면
            # 가장 최근에 측정된 값을 사용
            existing = minute_values.get(dt)

            if existing is None or dt_raw > existing[0]:
                minute_values[dt] = (dt_raw, bpm)

            if latest_hr_dt is None or dt_raw > latest_hr_dt:
                latest_hr_dt = dt_raw

        page_token = data.get("nextPageToken")

        if not page_token:
            break

    if not minute_values:
        print(
            f"ℹ️ {account.user.username} | {date} | "
            f"심박수 데이터 없음. "
            f"(API 원본 {api_point_count}건 / {page_count}페이지)"
        )
        return None

    saved_count = 0
    created_count = 0
    updated_count = 0

    for dt, (_, bpm) in minute_values.items():

        obj, created = FitbitMinuteMetric.objects.get_or_create(
            account=account,
            timestamp=dt,
            defaults={
                "heart_rate": bpm,
            },
        )

        if created:
            created_count += 1
            saved_count += 1

        elif obj.heart_rate != bpm:
            obj.heart_rate = bpm
            obj.save(update_fields=["heart_rate"])

            updated_count += 1
            saved_count += 1

    # 실시간(오늘) 데이터일 때만 last_synced 갱신.
    # 10/6 같은 과거 백필로 last_synced가 과거로 돌아가는 것 방지.
    if (
        latest_hr_dt is not None
        and target_date == timezone.localdate()
    ):
        update_last_synced(account, latest_hr_dt)

    print(
        f"✅ {account.user.username} | {date} | 심박수 처리 완료\n"
        f"   API 원본: {api_point_count}건 / {page_count}페이지\n"
        f"   분 단위 데이터: {len(minute_values)}건\n"
        f"   신규 저장: {created_count}건\n"
        f"   기존 갱신: {updated_count}건\n"
        f"   DB 변경 합계: {saved_count}건"
    )

    return {
        "api_point_count": api_point_count,
        "minute_count": len(minute_values),
        "created_count": created_count,
        "updated_count": updated_count,
        "latest_hr_dt": latest_hr_dt,
    }