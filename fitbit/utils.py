from datetime import datetime
from django.utils.timezone import is_aware, make_aware
import pytz

KST = pytz.timezone("Asia/Seoul")

def ensure_kst_aware(dt: datetime) -> datetime:
    """
    주어진 datetime이 naive이면 KST aware로 변환한다.
    이미 aware인데 KST가 아니면 경고 메시지를 출력한다.
    """
    if is_aware(dt):
        if dt.tzinfo != KST:
            print(f"⚠️ 경고: 입력 datetime이 aware지만 KST가 아님 → tzinfo={dt.tzinfo}")
        return dt
    return make_aware(dt, timezone=KST)

def normalize_to_minute(dt: datetime) -> datetime:
    """
    datetime을 한국시(KST) 기준으로 정규화한다.
    초 및 마이크로초를 제거한다.
    기존 코드와 사용법 동일하게 유지된다.
    """
    dt = ensure_kst_aware(dt)
    return dt.replace(second=0, microsecond=0)
