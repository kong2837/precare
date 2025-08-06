from datetime import datetime

def normalize_to_minute(dt: datetime) -> datetime:
    """
    datetime 객체에서 초(second)와 마이크로초(microsecond)만 제거한다.
    시간대(aware/naive)는 그대로 유지한다.
    """
    return dt.replace(second=0, microsecond=0)
