# jobs/scheduler.py

import os
import django
import sys

sys.path.append("/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apop2.settings")  # ⚠️ 프로젝트 이름에 맞게 수정
django.setup()

import time
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from django_apscheduler.jobstores import DjangoJobStore
import atexit
import traceback
from jobs.tasks import sync_intra_data  # ⚠️ 실제 등록된 작업 함수

def main():
    try:
        scheduler = BackgroundScheduler(timezone='Asia/Seoul')
        scheduler.add_jobstore(DjangoJobStore(), "default")
        scheduler.start()
        print("🌀 스케줄러 시작됨")

        scheduler.add_job(
            sync_intra_data,
            trigger=IntervalTrigger(minutes=2),
            id="sync_heart_rate_every_10_minutes",
            replace_existing=True,
            next_run_time=datetime.now() + timedelta(minutes=10),
        )
        print("🔁 심박수 자동 동기화 작업 등록됨")

        atexit.register(lambda: scheduler.shutdown())
        while True:
            time.sleep(1)

    except Exception:
        print("❌ 스케줄러 실행 중 에러 발생:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
