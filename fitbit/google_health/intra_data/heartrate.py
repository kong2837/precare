import requests

from fitbit.sync.sync import update_last_synced
from fitbit.google_health.token import refresh_google_health_token
from fitbit.google_health.client import google_time_to_kst_naive
from fitbit.models import FitbitMinuteMetric
from fitbit.utils import normalize_to_minute


def get_heart_rate(date, account):
    headers = {
        "Authorization": f"Bearer {account.access_token}",
        "Accept": "application/json",
    }

    url = "https://health.googleapis.com/v4/users/me/dataTypes/heart-rate/dataPoints?pageSize=1000"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        datapoints = data.get("dataPoints", [])

        if not datapoints:
            print(f"ℹ️ {account.user.username} | {date} | 심박수 데이터 없음.")
            update_last_synced(account)
            return None

        saved_count = 0

        for point in datapoints:
            hr = point.get("heartRate", {})
            sample_time = hr.get("sampleTime", {})
            physical_time = sample_time.get("physicalTime")
            bpm = hr.get("beatsPerMinute")

            if not physical_time or bpm is None:
                continue

            dt_raw = google_time_to_kst_naive(physical_time)
            if dt_raw is None or dt_raw.date().isoformat() != date:
                continue

            dt = normalize_to_minute(dt_raw)
            bpm = int(bpm)

            obj, created = FitbitMinuteMetric.objects.get_or_create(
                account=account,
                timestamp=dt,
                defaults={"heart_rate": bpm},
            )

            if not created:
                if obj.heart_rate != bpm:
                    obj.heart_rate = bpm
                    obj.save(update_fields=["heart_rate"])
                    saved_count += 1
            else:
                saved_count += 1

        print(f"✅ {account.user.username} | {date} | 심박수 {saved_count}건 저장 완료.")
        update_last_synced(account)
        return data

    elif response.status_code == 401:
        print(f"⚠️ {account.user.username} | Google Health 토큰 만료. 갱신 시도 중...")
        if refresh_google_health_token(account):
            return get_heart_rate(date, account)
        print("❌ 토큰 갱신 실패. 요청 중단. heart rate")
        return None

    else:
        print(f"❌ Google Health 심박수 요청 실패: {response.status_code}")
        print(response.text)
        return None