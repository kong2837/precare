import datetime
import requests

from fitbit.google_health.token import refresh_google_health_token
from fitbit.google_health.client import google_time_to_kst_naive
from fitbit.models import FitbitMinuteMetric
from fitbit.utils import normalize_to_minute


def get_step_count(date, account):
    """
    지정한 날짜(KST 기준)의 걸음수 데이터를 Google Health에서 가져와
    FitbitMinuteMetric에 저장한다.

    - API 요청 단계에서 날짜 범위를 필터링
    - nextPageToken을 이용해 모든 페이지 조회
    - requests timeout 적용
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
        "dataTypes/steps/dataPoints"
    )

    # Google Health API의 interval civil start time 기준 날짜 필터
    filter_expr = (
        f'steps.interval.civil_start_time >= "{target_date.isoformat()}" '
        f'AND steps.interval.civil_start_time < "{next_date.isoformat()}"'
    )

    page_token = None

    api_point_count = 0
    page_count = 0

    saved_count = 0
    created_count = 0
    updated_count = 0

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
                f"걸음수 API 요청 오류: {e}"
            )
            return None

        # Access token 만료
        if response.status_code == 401:
            print(
                f"⚠️ {account.user.username} | "
                "Google Health 토큰 만료. 갱신 시도 중..."
            )

            if refresh_google_health_token(account):
                return get_step_count(date, account)

            print("❌ 토큰 갱신 실패. 요청 중단. steps")
            return None

        # 그 외 오류
        if response.status_code != 200:
            print(
                f"❌ Google Health 걸음수 요청 실패: "
                f"{response.status_code}"
            )
            print(response.text)
            return None

        data = response.json()
        datapoints = data.get("dataPoints", [])

        page_count += 1
        api_point_count += len(datapoints)

        for point in datapoints:

            steps_data = point.get("steps", {})
            interval = steps_data.get("interval", {})

            start_time = interval.get("startTime")
            steps = steps_data.get("count")

            if not start_time or steps is None:
                continue

            try:
                steps = int(steps)
            except (TypeError, ValueError):
                continue

            # 기존 로직 유지:
            # 0걸음 데이터는 저장하지 않음
            if steps == 0:
                continue

            dt_raw = google_time_to_kst_naive(start_time)

            if dt_raw is None:
                continue

            # API filter 외에 한 번 더 날짜 검증
            if dt_raw.date() != target_date:
                continue

            dt = normalize_to_minute(dt_raw)

            obj, created = FitbitMinuteMetric.objects.get_or_create(
                account=account,
                timestamp=dt,
                defaults={
                    "step_count": steps,
                },
            )

            if created:
                created_count += 1
                saved_count += 1

            elif obj.step_count != steps:
                obj.step_count = steps
                obj.save(update_fields=["step_count"])

                updated_count += 1
                saved_count += 1

        page_token = data.get("nextPageToken")

        if not page_token:
            break

    if api_point_count == 0:
        print(
            f"ℹ️ {account.user.username} | "
            f"{date} | 걸음수 데이터 없음."
        )
        return None

    print(
        f"✅ {account.user.username} | {date} | 걸음수 처리 완료\n"
        f"   API 원본: {api_point_count}건 / {page_count}페이지\n"
        f"   신규 저장: {created_count}건\n"
        f"   기존 갱신: {updated_count}건\n"
        f"   DB 변경 합계: {saved_count}건"
    )

    return {
        "api_point_count": api_point_count,
        "created_count": created_count,
        "updated_count": updated_count,
    }