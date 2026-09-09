import requests

from fitbit.sync.sync import update_last_synced
from fitbit.google_health.token import refresh_google_health_token
from fitbit.google_health.client import google_time_to_kst_naive
from fitbit.models import FitbitMinuteMetric
from fitbit.utils import normalize_to_minute


def get_step_count(date, account):
    headers = {
        "Authorization": f"Bearer {account.access_token}",
        "Accept": "application/json",
    }

    url = "https://health.googleapis.com/v4/users/me/dataTypes/steps/dataPoints?pageSize=1000"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        datapoints = data.get("dataPoints", [])

        if not datapoints:
            print(f"ℹ️ {account.user.username} | {date} | 걸음수 데이터 없음.")
            return None

        saved_count = 0

        for point in datapoints:
            steps_data = point.get("steps", {})
            interval = steps_data.get("interval", {})
            start_time = interval.get("startTime")
            steps = steps_data.get("count")

            if not start_time or steps is None:
                continue

            steps = int(steps)
            if steps == 0:
                continue

            dt_raw = google_time_to_kst_naive(start_time)
            if dt_raw is None or dt_raw.date().isoformat() != date:
                continue

            dt = normalize_to_minute(dt_raw)

            obj, created = FitbitMinuteMetric.objects.get_or_create(
                account=account,
                timestamp=dt,
                defaults={"step_count": steps},
            )

            if not created:
                if obj.step_count != steps:
                    obj.step_count = steps
                    obj.save(update_fields=["step_count"])
                    saved_count += 1
            else:
                saved_count += 1

        print(f"✅ {account.user.username} | {date} | 걸음수 {saved_count}건 저장 완료.")
        return data

    elif response.status_code == 401:
        print(f"⚠️ {account.user.username} | Google Health 토큰 만료. 갱신 시도 중...")
        if refresh_google_health_token(account):
            return get_step_count(date, account)
        print("❌ 토큰 갱신 실패. 요청 중단. steps")
        return None

    else:
        print(f"❌ Google Health 걸음수 요청 실패: {response.status_code}")
        print(response.text)
        return None