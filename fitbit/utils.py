import datetime as dt
from django.utils.timezone import make_aware, is_aware

def normalize_to_minute(dt):
    # 그냥 초, 마이크로초 제거만
    return dt.replace(second=0, microsecond=0)
