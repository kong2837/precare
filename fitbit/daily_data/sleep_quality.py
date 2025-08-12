import requests
import datetime

from fitbit.token.refresh import refresh_token
from fitbit.sync.sync import update_last_synced
from fitbit.models import FitbitMinuteMetric
from fitbit.utils import normalize_to_minute


def _parse_iso_naive(iso_str: str) -> datetime.datetime:
    """
    Fitbit ISO 시각 문자열을 naive datetime으로 변환.
    예: '2025-08-04T23:10:30.000' / '2025-08-04T23:10:30.000Z'
    -> 초 단위까지만 사용, timezone 표기는 버림.
    """
    s = iso_str.replace("Z", "")
    if "." in s:
        s = s.split(".")[0]  # 밀리초 제거
    # 'YYYY-MM-DDTHH:MM:SS'
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")


def get_sleep_stage(date, account):
    """
    Fitbit API를 통해 수면 단계 데이터를 요청하고,
    다음 단계의 시작 시간까지 같은 상태로 저장.
    모든 타임스탬프는 naive → normalize_to_minute() → DB 저장.
    """
    headers = {"Authorization": f"Bearer {account.access_token}"}
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

            session_end = _parse_iso_naive(session["endTime"])

            for idx, entry in enumerate(levels):
                stage = entry.get("level")
                if stage not in ("wake", "light", "deep", "rem"):
                    continue

                start_time = _parse_iso_naive(entry["dateTime"])

                if idx + 1 < len(levels):
                    next_time = _parse_iso_naive(levels[idx + 1]["dateTime"])
                else:
                    next_time = session_end

                # 분 단위 반복 저장
                delta_sec = (next_time - start_time).total_seconds()
                duration_minutes = max(0, int(delta_sec // 60))  # 둘 다 int

                for i in range(duration_minutes):
                    minute_ts = normalize_to_minute(start_time + datetime.timedelta(minutes=i))

                    obj, created = FitbitMinuteMetric.objects.get_or_create(
                        account=account,
                        timestamp=minute_ts,
                        defaults={"sleep_stage": stage},
                    )
                    if created:
                        saved_stage_count += 1
                    else:
                        if obj.sleep_stage != stage:
                            obj.sleep_stage = stage
                            obj.save(update_fields=["sleep_stage"])
                            saved_stage_count += 1

        print(f"✅ {account.user.username} | {date} | 수면 단계 {saved_stage_count}건 저장 완료.")
        update_last_synced(account)
        return data

    elif response.status_code == 401:
        print(f"⚠️ {account.user.username} | 액세스 토큰 만료. 다시 갱신 시도 중...")
        if refresh_token(account):
            return get_sleep_stage(date, account)
        print("❌ 토큰 갱신 실패. 요청 중단.")
        return None

    else:
        print(f"❌ 요청 실패: {response.status_code}")
        print(response.text)
        return None
