from datetime import datetime
from fitbit.models import FitbitAccount
from fitbit.intra_data.heartrate import get_heart_rate_intraday  # 방금 작성한 함수

def sync_heart_rate():
    today = datetime.today().strftime("%Y-%m-%d")

    for account in FitbitAccount.objects.all():
        print(f"🩺 {account.user.username}의 심박수 데이터 동기화 중...")
        get_heart_rate_intraday(today, account)