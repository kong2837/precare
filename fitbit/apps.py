# jobs/apps.py

from django.apps import AppConfig
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django_apscheduler.jobstores import DjangoJobStore
import atexit

class JobsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'jobs'

    def ready(self):
        from jobs.tasks import sync_heart_rate

        scheduler = BackgroundScheduler(timezone='Asia/Seoul')
        scheduler.add_jobstore(DjangoJobStore(), "default")

        scheduler.add_job(
            sync_heart_rate,
            trigger=IntervalTrigger(minutes=10),
            id="sync_heart_rate_every_10_minutes",
            replace_existing=True,
        )

        print("🔁 심박수 자동 동기화 스케줄러 실행 중 (10분 간격)")
        scheduler.start()

        # 서버 종료 시 scheduler 종료
        atexit.register(lambda: scheduler.shutdown())
