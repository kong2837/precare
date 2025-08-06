from datetime import datetime
from django.utils.timezone import is_aware, make_aware
import pytz

KST = pytz.timezone("Asia/Seoul")

def ensure_kst_aware(dt: datetime) -> datetime:
    """
    주어진 datetime이 naive이면 KST aware로 변환한다.
    이미 aware면 그대로 반환한다.
    """
    if is_aware(dt):
        return dt
    return make_aware(dt, timezone=KST)

def normalize_to_minute_kst(dt: datetime) -> datetime:
    """
    datetime을 한국시(KST) 기준으로 분 단위 정규화한다.
    초 및 마이크로초를 제거한다.
    """
    dt = ensure_kst_aware(dt)
    return dt.replace(second=0, microsecond=0)
