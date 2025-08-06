from datetime import datetime, timezone as stdlib_timezone
from django.utils.timezone import is_aware, make_aware


def ensure_utc_aware(dt: datetime) -> datetime:
    """
    주어진 datetime이 naive이면 UTC aware로 변환한다.
    이미 aware면 그대로 반환.
    """
    if is_aware(dt):
        return dt
    return make_aware(dt, timezone=stdlib_timezone.utc)


def normalize_to_minute(dt: datetime) -> datetime:
    """
    datetime을 UTC 기준으로 분 단위로 정규화한다 (초 및 마이크로초 제거).
    """
    dt = ensure_utc_aware(dt)
    return dt.replace(second=0, microsecond=0)