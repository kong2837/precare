from datetime import timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.utils import timezone

from fitbit.models import FitbitAccount


from fitbit.google_health.daily_data.respiratory_rate import get_respiratory_rate
from fitbit.google_health.daily_data.sleep import get_sleep_stage
from fitbit.google_health.daily_data.spo2 import get_spo2
from fitbit.google_health.daily_data.skin_temperature import get_skin_temperature
from fitbit.google_health.intra_data.steps import get_step_count
from fitbit.google_health.intra_data.heartrate import get_heart_rate


def sync_accounts():
    # Older installations have no participant replacement fields yet.
    try:
        FitbitAccount._meta.get_field("source_account")
    except FieldDoesNotExist:
        return FitbitAccount.objects.all()
    return FitbitAccount.objects.filter(source_account__isnull=True)


def sync_intra_data():
    today = timezone.localdate(timezone=ZoneInfo("Asia/Seoul")).isoformat()

    for account in sync_accounts():
        print(f"🩺 {account.user.username}의 실시간 데이터 동기화 중...")
        get_heart_rate(today, account)
        get_step_count(today,account)


def sync_daily_data():
    date = timezone.localdate(timezone=ZoneInfo("Asia/Seoul"))
    today = date.isoformat()
    yesterday = (date - timedelta(days=1)).isoformat()

    for account in sync_accounts():
        print(f"🩺 {account.user.username}의 실시간 데이터 동기화 중...")
        get_sleep_stage(today, account)
        get_respiratory_rate(today, account)
        # Re-read recent days to pick up measurements synced after midnight.
        for spo2_date in spo2_sync_dates(account, date):
            get_spo2(spo2_date, account)
        get_skin_temperature(yesterday, account)


def spo2_sync_dates(account, today):
    lookback = max(1, int(getattr(settings, "GOOGLE_HEALTH_SPO2_LOOKBACK_DAYS", 7)))
    first = today - timedelta(days=lookback - 1)
    joined_at = account.join_date
    if joined_at is None:
        # Without an enrollment boundary, do not import a previous wearer's history.
        first = today
    else:
        if timezone.is_aware(joined_at):
            joined_at = timezone.localtime(joined_at, ZoneInfo("Asia/Seoul"))
        first = max(first, joined_at.date())
    # Prefer today's data, then recover prior dates. No future enrollment dates.
    return [(today - timedelta(days=offset)).isoformat()
            for offset in range(max(0, (today - first).days + 1))]
