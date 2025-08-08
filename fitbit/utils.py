import datetime as dt
from django.utils.timezone import make_aware, is_aware

def normalize_to_minute(date_str: str, time_str: str):
    """
    Fitbit 응답의 date, time 문자열을 그대로 사용.
    타임존 변환 없이 초/마이크로초만 제거.
    """
    # Fitbit에서 오는 응답이 이미 KST라면 그대로 사용
    d = dt.datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M:%S")

    # timezone-aware가 필요하면 make_aware 하되, settings.TIME_ZONE 기준
    if not is_aware(d):
        from django.conf import settings
        from zoneinfo import ZoneInfo
        d = make_aware(d, ZoneInfo(settings.TIME_ZONE))

    return d.replace(second=0, microsecond=0)
