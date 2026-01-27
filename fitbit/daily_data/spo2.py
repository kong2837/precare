import requests
import datetime
from fitbit.sync.sync import update_last_synced
from fitbit.token.refresh import refresh_token
from fitbit.models import FitbitMinuteMetric
from fitbit.utils import normalize_to_minute  # ✅ KST 기준 정규화

def get_spo2_intraday(date, account):
    """
    SpO₂ 인트라데이(주로 5분 간격 EMA) 조회 후
    'YYYY-MM-DD' + 'HH:MM' → naive datetime → normalize_to_minute() → upsert
    """
    headers = {"Authorization": f"Bearer {account.access_token}"}
    url = f"https://api.fitbit.com/1/user/-/spo2/date/{date}/all.json"

    r = requests.get(url, headers=headers)

    # if r.status_code == 200:
    #     data = r.json()
    #     blocks = data.get("spo2", [])
    #     if not blocks:
    #         print(f"ℹ️ {account.user.username} | {date} | SpO₂ 데이터 없음.")
    #         update_last_synced(account)
    #         return None

    #     minutes = blocks[0].get("minutes", []) if blocks else []
    #     if not minutes:
    #         print(f"ℹ️ {account.user.username} | {date} | SpO₂ minutes 없음.")
    #         update_last_synced(account)
    #         return None

    #     saved = 0
    #     for m in minutes:
    #         minute_str = m.get("minute")  # "HH:MM"
    #         value = m.get("value")
    #         if minute_str is None or value is None:
    #             continue

    #         # ✅ naive datetime으로 만든 뒤 normalize_to_minute()만 호출
    #         dt_raw = datetime.datetime.strptime(f"{date} {minute_str}:00", "%Y-%m-%d %H:%M:%S")
    #         ts = normalize_to_minute(dt_raw)

    #         obj, created = FitbitMinuteMetric.objects.get_or_create(
    #             account=account,
    #             timestamp=ts,
    #             defaults={"spo2": value},
    #         )
    #         if not created:
    #             if obj.spo2 != value:
    #                 obj.spo2 = value
    #                 obj.save(update_fields=["spo2"])
    #                 saved += 1
    #         else:
    #             saved += 1
    if r.status_code == 200:
        data = r.json()

        minutes = data.get("minutes", [])
        
        if not minutes:
            print(f"ℹ️ {account.user.username} | {date} | SpO₂ 상세 데이터 없음.")
            return None

        saved = 0
        for m in minutes:
            # 핏빗 응답: "2026-01-27T03:27:36" (ISO 형식)
            minute_str = m.get("minute")
            value = m.get("value")
            
            if not minute_str or value is None: continue

            # T를 공백으로 바꾸고 초단위까지 파싱
            dt_raw = datetime.datetime.strptime(minute_str.replace('T', ' '), "%Y-%m-%d %H:%M:%S")
            ts = normalize_to_minute(dt_raw)

            # update_or_create로 기존 행(심박수 등)에 spo2 값만 추가
            obj, created = FitbitMinuteMetric.objects.update_or_create(
                account=account,
                timestamp=ts,
                defaults={"spo2": value}
            )
            saved += 1

        print(f"✅ {account.user.username} | {date} | SpO₂ {saved}건 저장/업데이트 완료.")
        update_last_synced(account)
        return data

    elif r.status_code == 401:
        print(f"⚠️ {account.user.username} | Access token 만료. 갱신 시도...")
        if refresh_token(account):
            return get_spo2_intraday(date, account)
        print("❌ 토큰 갱신 실패. 요청 중단. spo2")
        return None

    else:
        print(f"❌ 요청 실패: {r.status_code}")
        print(r.text)
        return None
