import requests
import datetime
from fitbit.sync.sync import update_last_synced
from fitbit.token.refresh import refresh_token
from fitbit.models import FitbitMinuteMetric
from fitbit.utils import normalize_to_minute  # ✅ KST 기준 정규화

def get_respiratory_rate_intraday(date, account):
    """
    호흡수(Breathing Rate) 인트라데이 조회 후
    'YYYY-MM-DD' + 'HH:MM' → naive datetime → normalize_to_minute() → upsert
    - endpoint: /1/user/-/br/date/{date}/all.json
    - 주로 수면 중 구간에서 제공
    """
    headers = {"Authorization": f"Bearer {account.access_token}"}
    url = f"https://api.fitbit.com/1/user/-/br/date/{date}/all.json"

    r = requests.get(url, headers=headers)

    if r.status_code == 200:
        data = r.json()
        blocks = data.get("br", [])
        if not blocks:
            print(f"ℹ️ {account.user.username} | {date} | 호흡수 데이터 없음.")
            update_last_synced(account)
            return None

        # 보통 blocks[0] 안에 minutes 배열이 있음 (구조 변형 대비하여 두 경우 모두 처리)
        minutes = []
        if isinstance(blocks[0], dict):
            # 케이스 A: {"dateTime": "...", "minutes": [ {"minute": "HH:MM", "value": float}, ... ]}
            if "minutes" in blocks[0]:
                minutes = blocks[0].get("minutes", [])
            # 케이스 B: {"dateTime":"...", "value":{"minutes":[...]}}
            elif "value" in blocks[0] and isinstance(blocks[0]["value"], dict):
                minutes = blocks[0]["value"].get("minutes", [])

        if not minutes:
            print(f"ℹ️ {account.user.username} | {date} | 호흡수 minutes 없음.")
            update_last_synced(account)
            return None

        saved = 0
        for m in minutes:
            minute_str = m.get("minute")  # "HH:MM"
            value = m.get("value")
            if minute_str is None or value is None:
                continue

            # ✅ naive datetime → normalize_to_minute()
            dt_raw = datetime.datetime.strptime(f"{date} {minute_str}:00", "%Y-%m-%d %H:%M:%S")
            ts = normalize_to_minute(dt_raw)

            obj, created = FitbitMinuteMetric.objects.get_or_create(
                account=account,
                timestamp=ts,
                defaults={"respiratory_rate": value},
            )
            if not created:
                if obj.respiratory_rate != value:
                    obj.respiratory_rate = value
                    obj.save(update_fields=["respiratory_rate"])
                    saved += 1
            else:
                saved += 1

        print(f"✅ {account.user.username} | {date} | 호흡수 {saved}건 저장/업데이트 완료.")
        update_last_synced(account)
        return data

    elif r.status_code == 401:
        print(f"⚠️ {account.user.username} | Access token 만료. 갱신 시도...")
        if refresh_token(account):
            return get_respiratory_rate_intraday(date, account)
        print("❌ 토큰 갱신 실패. 요청 중단.")
        return None

    else:
        print(f"❌ 요청 실패: {r.status_code}")
        print(r.text)
        return None
