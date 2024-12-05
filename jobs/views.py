import logging

import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings

from huami.models import HuamiAccount, HealthData

logger = logging.getLogger(__name__)


def update_health():
    users = HuamiAccount.objects.filter(research_status='ongoing')
    for user in users:
        try:
            HealthData.create_from_sync_data(user)
        except requests.HTTPError as e:
            logger.error(e.response.reason)
            logger.warning(f"{user.name}님의 데이터 동기화에 문제가 발생했습니다.")
        except Exception as e:
            logger.error(e)
            logger.warning(f"{user.name}님의 데이터 동기화에 문제가 발생했습니다.")


# Create your views here.
def start():
    scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
    scheduler.add_job(func=update_health, trigger=CronTrigger(hour="02", minute="00"))
    scheduler.start()
