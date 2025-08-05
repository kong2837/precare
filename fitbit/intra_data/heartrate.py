import requests
from datetime import datetime
from django.utils.timezone import make_aware

from fitbit.sync.sync import update_last_synced
from fitbit.token.refresh import refresh_token
from fitbit.models import FitbitMinuteMetric


def get_heart_rate_intraday(date, account):
    """
    FitbitAccount 인스턴스를 기반으로 심박수 데이터를 요청 및 저장.
    만료된 토큰이면 자동으로 갱신 후 재시도함.
    """
    headers = {
        "Authorization": f"Bearer {account.access_token}"
    }

    url = f"https://api.fitbit.com/1/user/-/activities/heart/date/{date}/1d/1min.json"
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        dataset = data.get("activities-heart-intraday", {}).get("dataset", [])
        date_str = data.get("activities-heart", [{}])[0].get("dateTime", date)  # 예: '2025-06-26'

        if not dataset:
            print("ℹ️ 데이터가 없습니다.")
            update_last_synced(account)
            return None

        saved_count = 0
        for item in dataset:
            time_str = item["time"]  # 예: "12:01:00"
            bpm = item["value"]

            # datetime 생성 (UTC aware)
            dt = make_aware(datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S"))

            # upsert: account + timestamp 기준으로 저장
            obj, created = FitbitMinuteMetric.objects.get_or_create(
                account=account,
                timestamp=dt,
                defaults={"heart_rate": bpm}
            )

            if not created:
                obj.heart_rate = bpm
                obj.save(update_fields=["heart_rate"])

            saved_count += 1

        print(f"✅ 심박수 {saved_count}건 저장 완료.")
        update_last_synced(account)
        return data

    elif response.status_code == 401:
        print("⚠️ Access token 만료. 다시 갱신 시도 중...")
        if refresh_token(account):
            return get_heart_rate_intraday(date, account)
        else:
            print("❌ 토큰 갱신 실패. 요청 중단.")
            return None

    else:
        print("❌ 요청 실패:", response.status_code)
        print(response.text)
        return None
