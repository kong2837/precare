import requests

from fitbit.sync.sync import update_last_synced
from fitbit.google_health.token import refresh_google_health_token
from fitbit.google_health.client import google_time_to_kst_naive
from fitbit.models import FitbitMinuteMetric
from fitbit.utils import normalize_to_minute


def get_spo2(date, account):
    headers = {
        "Authorization": f"Bearer {account.access_token}",
        "Accept": "application/json",
    }

    url = "https://health.googleapis.com/v4/users/me/dataTypes/oxygen-saturation/dataPoints?pageSize=1000"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        datapoints = data.get("dataPoints", [])

        if not datapoints:
            print(f"ℹ️ {account.user.username} | {date} | SpO₂ 데이터 없음.")
            update_last_synced(account)
            return None

        saved = 0

        for point in datapoints:
            spo2_data = point.get("oxygenSaturation", {})
            sample_time = spo2_data.get("sampleTime", {})
            physical_time = sample_time.get("physicalTime")
            value = spo2_data.get("percentage")

            if not physical_time or value is None:
                continue

            dt_raw = google_time_to_kst_naive(physical_time)
            if dt_raw is None or dt_raw.date().isoformat() != date:
                continue

            ts = normalize_to_minute(dt_raw)

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
            else:
                saved += 1

        print(f"✅ {account.user.username} | {date} | SpO₂ {saved}건 저장 완료.")
        update_last_synced(account)
        return data

    elif response.status_code == 401:
        print(f"⚠️ {account.user.username} | Google Health 토큰 만료. 갱신 시도 중...")
        if refresh_google_health_token(account):
            return get_spo2_intraday(date, account)
        print("❌ 토큰 갱신 실패. 요청 중단. spo2")
        return None

    else:
        print(f"❌ Google Health SpO₂ 요청 실패: {response.status_code}")
        print(response.text)
        return None