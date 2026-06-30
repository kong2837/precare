import requests
import datetime

from fitbit.sync.sync import update_last_synced
from fitbit.google_health.token import refresh_google_health_token
from fitbit.google_health.client import google_date_dict_to_str
from fitbit.models import FitbitMinuteMetric
from fitbit.utils import normalize_to_minute


def get_skin_temperature(date, account):
    headers = {
        "Authorization": f"Bearer {account.access_token}",
        "Accept": "application/json",
    }

    url = "https://health.googleapis.com/v4/users/me/dataTypes/daily-sleep-temperature-derivations/dataPoints?pageSize=1000"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        datapoints = data.get("dataPoints", [])

        if not datapoints:
            print(f"ℹ️ {account.user.username} | {date} | skin temp 데이터 없음.")
            update_last_synced(account)
            return None

        target = None

        for point in datapoints:
            temp_data = point.get("dailySleepTemperatureDerivations", {})
            date_dict = temp_data.get("date")

            if not date_dict:
                continue

            if google_date_dict_to_str(date_dict) == date:
                target = temp_data
                break

        if not target:
            print(f"ℹ️ {account.user.username} | {date} | skin temp 해당 날짜 데이터 없음.")
            update_last_synced(account)
            return None

        value = target.get("nightlyTemperatureCelsius")

        if value is None or value == "NaN":
            print(f"ℹ️ {account.user.username} | {date} | skin temp 값 없음.")
            update_last_synced(account)
            return None

        base_dt = datetime.datetime.strptime(date, "%Y-%m-%d")
        minute_ts = normalize_to_minute(base_dt)

        obj, created = FitbitMinuteMetric.objects.get_or_create(
            account=account,
            timestamp=minute_ts,
            defaults={"skin_temperature": value},
        )

        saved_count = 0
        if created:
            saved_count = 1
        else:
            if obj.skin_temperature != value:
                obj.skin_temperature = value
                obj.save(update_fields=["skin_temperature"])
                saved_count = 1

        print(f"✅ {account.user.username} | {date} | skin temp {saved_count}건 저장 완료. ({value})")
        update_last_synced(account)
        return data

    elif response.status_code == 401:
        print(f"⚠️ {account.user.username} | Google Health 토큰 만료. 갱신 시도 중... skin temp")
        if refresh_google_health_token(account):
            return get_skin_temperature(date, account)
        print("❌ 토큰 갱신 실패. 요청 중단. skin temp")
        return None

    else:
        print(f"❌ Google Health skin temp 요청 실패: {response.status_code}")
        print(response.text)
        return None