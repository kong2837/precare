import requests
from datetime import datetime, timedelta
from django.utils import timezone

from fitbit.token.refresh import refresh_token
from fitbit.sync.sync import update_last_synced
from fitbit.models import FitbitMinuteMetric


def get_sleep_stage(date, account):
    """
    Fitbit API를 통해 수면 단계 데이터를 요청하고,
    지속 시간(seconds)에 따라 분 단위로 FitbitMinuteMetric 모델에 저장한다.
    """
    headers = {
        "Authorization": f"Bearer {account.access_token}"
    }

    url = f"https://api.fitbit.com/1.2/user/-/sleep/date/{date}.json"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        sessions = data.get("sleep", [])

        if not sessions:
            print(f"ℹ️ {account.user.username} | {date} | 수면 세션 없음.")
            update_last_synced(account)
            return None

        saved_stage_count = 0

        for session in sessions:
            levels = session.get("levels", {}).get("data", [])

            if not levels:
                print(f"ℹ️ {account.user.username} | {date} | 수면 단계 데이터 없음.")
                continue

            for entry in levels:
                stage = entry["level"]
                if stage not in ("wake", "light", "deep", "rem"):
                    continue

                start_time = timezone.make_aware(
                    datetime.fromisoformat(entry["dateTime"]),
                    timezone=timezone.utc
                )

                duration_seconds = entry.get("seconds", 0)
                duration_minutes = duration_seconds // 60

                for i in range(duration_minutes):
                    minute_ts = start_time + timedelta(minutes=i)

                    obj, created = FitbitMinuteMetric.objects.get_or_create(
                        account=account,
                        timestamp=minute_ts,
                        defaults={"sleep_stage": stage}
                    )

                    if not created:
                        if obj.sleep_stage != stage:
                            obj.sleep_stage = stage
                            obj.save(update_fields=["sleep_stage"])
                            saved_stage_count += 1
                    else:
                        saved_stage_count += 1

        print(f"✅ {account.user.username} | {date} | 수면 단계 {saved_stage_count}건 저장 완료.")
        update_last_synced(account)
        return data

    elif response.status_code == 401:
        print(f"⚠️ {account.user.username} | Access token 만료. 다시 갱신 시도 중...")
        if refresh_token(account):
            return get_sleep_stage(date, account)
        else:
            print("❌ 토큰 갱신 실패. 요청 중단.")
            return None

    else:
        print(f"❌ 요청 실패: {response.status_code}")
        print(response.text)
        return None
