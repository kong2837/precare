from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings

from huami.models import HuamiAccount, HealthData


def update_health():
    users = HuamiAccount.objects.filter(research_status='ongoing')
    for user in users:
        HealthData.create_from_sync_data(user)


# Create your views here.
def start():
    scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
    scheduler.add_job(func=update_health, trigger=CronTrigger(hour="02", minute="00"))
    scheduler.start()
