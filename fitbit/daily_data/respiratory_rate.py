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

    # if r.status_code == 200:
    #     data = r.json()
    #     blocks = data.get("br", [])
    #     if not blocks:
    #         print(f"ℹ️ {account.user.username} | {date} | 호흡수 데이터 없음.")
    #         update_last_synced(account)
    #         return None

    #     # 보통 blocks[0] 안에 minutes 배열이 있음 (구조 변형 대비하여 두 경우 모두 처리)
    #     minutes = []
    #     if isinstance(blocks[0], dict):
    #         # 케이스 A: {"dateTime": "...", "minutes": [ {"minute": "HH:MM", "value": float}, ... ]}
    #         if "minutes" in blocks[0]:
    #             minutes = blocks[0].get("minutes", [])
    #         # 케이스 B: {"dateTime":"...", "value":{"minutes":[...]}}
    #         elif "value" in blocks[0] and isinstance(blocks[0]["value"], dict):
    #             minutes = blocks[0]["value"].get("minutes", [])

    #     if not minutes:
    #         print(f"ℹ️ {account.user.username} | {date} | 호흡수 minutes 없음.")
    #         update_last_synced(account)
    #         return None

    #     saved = 0
    #     for m in minutes:
    #         minute_str = m.get("minute")  # "HH:MM"
    #         value = m.get("value")
    #         if minute_str is None or value is None:
    #             continue

    #         # ✅ naive datetime → normalize_to_minute()
    #         dt_raw = datetime.datetime.strptime(f"{date} {minute_str}:00", "%Y-%m-%d %H:%M:%S")
    #         ts = normalize_to_minute(dt_raw)

    #         obj, created = FitbitMinuteMetric.objects.get_or_create(
    #             account=account,
    #             timestamp=ts,
    #             defaults={"respiratory_rate": value},
    #         )
    #         if not created:
    #             if obj.respiratory_rate != value:
    #                 obj.respiratory_rate = value
    #                 obj.save(update_fields=["respiratory_rate"])
    #                 saved += 1
    #         else:
    #             saved += 1

        # print(f"✅ {account.user.username} | {date} | 호흡수 {saved}건 저장/업데이트 완료.")
        # update_last_synced(account)
        # return data


    if r.status_code == 200:
        data = r.json()
        br_list = data.get("br", [])
        
        if not br_list:
            print(f"ℹ️ {account.user.username} | {date} | 호흡수 데이터(br) 없음.")
            update_last_synced(account)
            return None

        # 요약값(fullSleepSummary) 추출
        val_block = br_list[0].get("value", {})
        summary_value = val_block.get("fullSleepSummary", {}).get("breathingRate")

        if not summary_value:
            print(f"ℹ️ {account.user.username} | {date} | 호흡수 요약값(breathingRate)이 존재하지 않음.")
            update_last_synced(account)
            return None

        # 이미 DB에 저장된 해당 날짜의 '수면 단계' 데이터를 찾아서 그 시간대에 요약값을 채워넣음
        # 수면 중 호흡수이므로, sleep_stage 데이터가 있는 행을 기준으로 업데이트합니다.
        target_date = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        sleep_metrics = FitbitMinuteMetric.objects.filter(
            account=account,
            timestamp__date=target_date,
            sleep_stage__isnull=False  # 수면 단계 기록이 있는 행들만 선택
        )

        saved = 0
        if sleep_metrics.exists():
            for obj in sleep_metrics:
                obj.respiratory_rate = summary_value
                obj.save(update_fields=["respiratory_rate"])
                saved += 1
            print(f"✅ {account.user.username} | {date} | 호흡수 요약값({summary_value})을 수면 시간({saved}분)에 채움 완료.")
        else:
            print(f"⚠️ {date} | DB에 저장된 수면 데이터가 없어 호흡수를 채울 수 없습니다. (수면 데이터를 먼저 수집해야 합니다.)")

        update_last_synced(account)
        return data

    elif r.status_code == 401:
        print(f"⚠️ {account.user.username} | Access token 만료. 갱신 시도...")
        if refresh_token(account):
            return get_respiratory_rate_intraday(date, account)
        print("❌ 토큰 갱신 실패. 요청 중단. respiratory_rate")
        return None

    else:
        print(f"❌ 요청 실패: {r.status_code}")
        print(r.text)
        return None
