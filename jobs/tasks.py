from datetime import datetime, timedelta

from fitbit.models import FitbitAccount


from fitbit.google_health.daily_data.respiratory_rate import get_respiratory_rate
from fitbit.google_health.daily_data.sleep import get_sleep_stage
from fitbit.google_health.daily_data.spo2 import get_spo2
from fitbit.google_health.daily_data.skin_temperature import get_skin_temperature
from fitbit.google_health.intra_data.steps import get_step_count
from fitbit.google_health.intra_data.heartrate import get_heart_rate

def sync_intra_data():
    today = datetime.today().strftime("%Y-%m-%d")

    for account in FitbitAccount.objects.all():
        print(f"🩺 {account.user.username}의 실시간 데이터 동기화 중...")
        get_heart_rate(today, account)
        get_step_count(today,account)


def sync_daily_data():
    today = datetime.today().strftime("%Y-%m-%d")
    yesterday = (datetime.today() - timedelta(days=1)).strftime("%Y-%m-%d")  # skin temp는 수면 후 다음날 생성되지만 '어젯밤 데이터'라서 어제 날짜로 조회해야 함

    for account in FitbitAccount.objects.all():
        print(f"🩺 {account.user.username}의 실시간 데이터 동기화 중...")
        get_sleep_stage(today, account)
        get_respiratory_rate(today, account)
        get_spo2(today, account)
        get_skin_temperature(yesterday, account)