from datetime import datetime
import pytz

# def update_last_synced(account):
#     seoul_tz = pytz.timezone("Asia/Seoul")
#     now_kst = datetime.now(seoul_tz)
#     account.last_synced = now_kst
#     account.save(update_fields=["last_synced"])

from django.utils import timezone
from zoneinfo import ZoneInfo


def update_last_synced(account, synced_at):
    
    if synced_at is None:
        return

    # KST naive datetime → timezone-aware datetime
    if timezone.is_naive(synced_at):
        synced_at = timezone.make_aware(
            synced_at,
            ZoneInfo("Asia/Seoul")
        )

    if (
        account.last_synced is None
        or synced_at > account.last_synced
    ):
        account.last_synced = synced_at
        account.save(update_fields=["last_synced"])