import pytz
from datetime import datetime
from django.utils.timezone import is_aware, make_aware

KST = pytz.timezone("Asia/Seoul")

def normalize_to_minute(dt: datetime) -> datetime:
    """
    초 및 마이크로초 제거하고, KST timezone-aware datetime 반환.
    """
    if not is_aware(dt):
        dt = make_aware(dt, timezone=KST)
    return dt.replace(second=0, microsecond=0)
