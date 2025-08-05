from datetime import datetime
import pytz

def update_last_synced(account):
    seoul_tz = pytz.timezone("Asia/Seoul")
    now_kst = datetime.now(seoul_tz)
    account.last_synced = now_kst
    account.save(update_fields=["last_synced"])
