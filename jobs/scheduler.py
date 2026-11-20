# jobs/scheduler.py

import os
import django
import sys

sys.path.append("/app")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apop2.settings")
django.setup()

import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger  # ✅ ADDED
from django_apscheduler.jobstores import DjangoJobStore
import atexit
import traceback
from jobs.tasks import sync_intra_data, sync_daily_data  # ✅ ADDED

def main():
    try:
        scheduler = BackgroundScheduler(timezone='Asia/Seoul')
        scheduler.add_jobstore(DjangoJobStore(), "default")
        scheduler.start()
        print("🌀 스케줄러 시작됨")

        # 매 2분마다 실시간(인트라데이) 동기화
        scheduler.add_job(
            sync_intra_data,
            trigger=IntervalTrigger(minutes=2, timezone="Asia/Seoul"),
            id="sync_intra_data_every_2_minutes",  # (선택) ID 명확히 변경
            replace_existing=True,
            next_run_time=datetime.now(ZoneInfo("Asia/Seoul")) + timedelta(minutes=1),
            coalesce=True,
            misfire_grace_time=300,
        )
        print("🔁 인트라데이 자동 동기화 작업 등록됨 (2분 간격)")

        # 매일 10:00, 22:00에 일일 배치 동기화
        scheduler.add_job(
            sync_daily_data,
            trigger=CronTrigger(hour="10,22", minute=0, timezone="Asia/Seoul"),
            id="sync_daily_data_10_22_kst",
            replace_existing=True,
            coalesce=True,  # 밀린 실행은 1회로 합치기
            misfire_grace_time=3600,  # 최대 1시간까지 지연 허용
        )
        print("🕙 일일 데이터 동기화 작업 등록됨 (매일 10:00/22:00 KST)")

        atexit.register(lambda: scheduler.shutdown())
        while True:
            time.sleep(1)

    except Exception:
        print("❌ 스케줄러 실행 중 에러 발생:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
