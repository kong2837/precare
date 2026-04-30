import requests
import datetime

from fitbit.token.refresh import refresh_token
from fitbit.sync.sync import update_last_synced
from fitbit.models import FitbitMinuteMetric
from fitbit.utils import normalize_to_minute


def get_skin_temperature(date, account):
    """
    Fitbit API를 통해 skin temperature (nightlyRelative)를 가져와
    minute 테이블에 1건으로 저장 (00:00 기준)

    - sleep 기반 daily 데이터
    - minute 구조 유지 위해 00:00에 매핑
    """

    headers = {"Authorization": f"Bearer {account.access_token}"}
    url = f"https://api.fitbit.com/1/user/-/temp/skin/date/{date}.json"

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        temp_list = data.get("tempSkin", [])

        if not temp_list:
            print(f"ℹ️ {account.user.username} | {date} | skin temp 데이터 없음.")
            update_last_synced(account)
            return None

        try:
            value = temp_list[0]["value"]["nightlyRelative"]
        except (KeyError, IndexError, TypeError):
            print(f"⚠️ {account.user.username} | {date} | skin temp 파싱 실패.")
            update_last_synced(account)
            return None

        # 👉 날짜 기준 00:00 timestamp 생성
        base_dt = datetime.datetime.strptime(date, "%Y-%m-%d")
        minute_ts = normalize_to_minute(base_dt)

        # 👉 upsert (sleep_stage 코드 스타일 맞춤)
        obj, created = FitbitMinuteMetric.objects.get_or_create(
            account=account,
            timestamp=minute_ts,
            defaults={"skin_temperature": value},
        )

        if created:
            saved_count = 1
        else:
            saved_count = 0
            if obj.skin_temperature != value:
                obj.skin_temperature = value
                obj.save(update_fields=["skin_temperature"])
                saved_count = 1

        print(f"✅ {account.user.username} | {date} | skin temp {saved_count}건 저장 완료. ({value})")

        update_last_synced(account)
        return data

    elif response.status_code == 401:
        print(f"⚠️ {account.user.username} | 액세스 토큰 만료. 다시 갱신 시도 중... (skin temp)")
        if refresh_token(account):
            return get_skin_temperature(date, account)

        print("❌ 토큰 갱신 실패. 요청 중단. skin temp")
        return None

    else:
        print(f"❌ 요청 실패 (skin temp): {response.status_code}")
        print(response.text)
        return None