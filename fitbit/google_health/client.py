import datetime
from django.utils.dateparse import parse_datetime


KST = datetime.timezone(datetime.timedelta(hours=9))


def google_time_to_kst_naive(iso_time):
    dt = parse_datetime(iso_time)

    if dt is None:
        return None

    if dt.tzinfo is None:
        return dt

    return dt.astimezone(KST).replace(tzinfo=None)


def google_date_dict_to_str(date_dict):
    return f"{date_dict['year']:04d}-{date_dict['month']:02d}-{date_dict['day']:02d}"