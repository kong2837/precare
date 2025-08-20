from datetime import datetime

from fitbit.intra_data.steps import get_step_count_intraday
from fitbit.models import FitbitAccount
from fitbit.intra_data.heartrate import get_heart_rate_intraday  # 방금 작성한 함수

def sync_intra_data():
    today = datetime.today().strftime("%Y-%m-%d")

    for account in FitbitAccount.objects.all():
        print(f"🩺 {account.user.username}의 실시간 데이터 동기화 중...")
        get_heart_rate_intraday(today, account)
        get_step_count_intraday(today,account)