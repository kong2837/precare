import requests
import datetime

from fitbit.sync.sync import update_last_synced
from fitbit.google_health.token import refresh_google_health_token
from fitbit.google_health.client import google_date_dict_to_str
from fitbit.models import FitbitMinuteMetric


def get_respiratory_rate(date, account):
    headers = {
        "Authorization": f"Bearer {account.access_token}",
        "Accept": "application/json",
    }

    url = "https://health.googleapis.com/v4/users/me/dataTypes/daily-respiratory-rate/dataPoints?pageSize=1000"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        datapoints = data.get("dataPoints", [])

        if not datapoints:
            print(f"ℹ️ {account.user.username} | {date} | 호흡수 데이터 없음.")
            update_last_synced(account)
            return None

        target_value = None

        for point in datapoints:
            rr_data = point.get("dailyRespiratoryRate", {})
            date_dict = rr_data.get("date")

            if not date_dict:
                continue

            if google_date_dict_to_str(date_dict) == date:
                target_value = rr_data.get("breathsPerMinute")
                break

        if target_value is None:
            print(f"ℹ️ {account.user.username} | {date} | 호흡수 해당 날짜 데이터 없음.")
            update_last_synced(account)
            return None

        target_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()

        sleep_metrics = FitbitMinuteMetric.objects.filter(
            account=account,
            timestamp__date=target_date,
            sleep_stage__isnull=False,
        )

        saved = 0

        if sleep_metrics.exists():
            for obj in sleep_metrics:
                obj.respiratory_rate = target_value
                obj.save(update_fields=["respiratory_rate"])
                saved += 1

            print(f"✅ {account.user.username} | {date} | 호흡수({target_value})를 수면 시간 {saved}분에 저장 완료.")
        else:
            print(f"⚠️ {date} | 수면 데이터가 없어 호흡수를 채울 수 없습니다. 수면 데이터를 먼저 수집하세요.")

        update_last_synced(account)
        return data

    elif response.status_code == 401:
        print(f"⚠️ {account.user.username} | Google Health 토큰 만료. 갱신 시도 중... respiratory_rate")
        if refresh_google_health_token(account):
            return get_respiratory_rate(date, account)
        print("❌ 토큰 갱신 실패. 요청 중단. respiratory_rate")
        return None

    else:
        print(f"❌ Google Health 호흡수 요청 실패: {response.status_code}")
        print(response.text)
        return None