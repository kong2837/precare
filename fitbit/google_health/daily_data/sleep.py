import requests
import datetime

from fitbit.sync.sync import update_last_synced
from fitbit.google_health.token import refresh_google_health_token
from fitbit.google_health.client import google_time_to_kst_naive
from fitbit.models import FitbitMinuteMetric
from fitbit.utils import normalize_to_minute


STAGE_MAP = {
    "AWAKE": "wake",
    "LIGHT": "light",
    "DEEP": "deep",
    "REM": "rem",
    "ASLEEP": "asleep",
}


def get_sleep_stage(date, account):
    headers = {
        "Authorization": f"Bearer {account.access_token}",
        "Accept": "application/json",
    }

    url = "https://health.googleapis.com/v4/users/me/dataTypes/sleep/dataPoints?pageSize=100"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        sessions = data.get("dataPoints", [])

        if not sessions:
            print(f"ℹ️ {account.user.username} | {date} | 수면 세션 없음.")
            update_last_synced(account)
            return None

        saved_stage_count = 0

        for point in sessions:
            sleep = point.get("sleep", {})
            stages = sleep.get("stages", [])

            if not stages:
                continue

            for stage_item in stages:
                raw_stage = stage_item.get("type")
                stage = STAGE_MAP.get(raw_stage)

                if not stage:
                    continue

                start_time = google_time_to_kst_naive(stage_item.get("startTime"))
                end_time = google_time_to_kst_naive(stage_item.get("endTime"))

                if not start_time or not end_time:
                    continue

                # 수면은 전날 밤~다음날 아침이라 start 날짜가 다를 수 있음
                # date 기준으로 저장 대상 날짜에 걸치는 분만 저장
                delta_sec = (end_time - start_time).total_seconds()
                duration_minutes = max(0, int(delta_sec // 60))

                for i in range(duration_minutes):
                    current_dt = start_time + datetime.timedelta(minutes=i)

                    if current_dt.date().isoformat() != date:
                        continue

                    minute_ts = normalize_to_minute(current_dt)

                    obj, created = FitbitMinuteMetric.objects.get_or_create(
                        account=account,
                        timestamp=minute_ts,
                        defaults={"sleep_stage": stage},
                    )

                    if created:
                        saved_stage_count += 1
                    else:
                        if obj.sleep_stage != stage:
                            obj.sleep_stage = stage
                            obj.save(update_fields=["sleep_stage"])
                            saved_stage_count += 1

        print(f"✅ {account.user.username} | {date} | 수면 단계 {saved_stage_count}건 저장 완료.")
        update_last_synced(account)
        return data

    elif response.status_code == 401:
        print(f"⚠️ {account.user.username} | Google Health 토큰 만료. 갱신 시도 중... sleep")
        if refresh_google_health_token(account):
            return get_sleep_stage(date, account)
        print("❌ 토큰 갱신 실패. 요청 중단. sleep")
        return None

    else:
        print(f"❌ Google Health 수면 요청 실패: {response.status_code}")
        print(response.text)
        return None