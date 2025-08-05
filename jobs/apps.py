from django.apps import AppConfig

class JobsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'jobs'

    def ready(self):
        import atexit
        import threading
        import time
        from apscheduler.schedulers.background import BackgroundScheduler
        from django_apscheduler.jobstores import DjangoJobStore

        # 스케줄러 먼저 실행
        scheduler = BackgroundScheduler(timezone='Asia/Seoul')
        scheduler.add_jobstore(DjangoJobStore(), "default")
        scheduler.start()
        print("🌀 스케줄러 시작됨")

        # atexit 등록
        atexit.register(lambda: scheduler.shutdown())

        # add_job은 별도 스레드에서 실행 (약간의 시간 딜레이)
        def add_jobs():
            time.sleep(1)  # 1초 후 실행 (DB 접근 시간 확보)
            from datetime import datetime, timedelta
            from apscheduler.triggers.interval import IntervalTrigger
            from jobs.tasks import sync_intra_data

            scheduler.add_job(
                sync_intra_data,
                trigger=IntervalTrigger(minutes=10),
                id="sync_heart_rate_every_10_minutes",
                replace_existing=True,
                next_run_time=datetime.now() + timedelta(minutes=10),
            )
            print("🔁 심박수 자동 동기화 작업 등록됨")

        threading.Thread(target=add_jobs).start()
