from django.apps import AppConfig

class JobsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'jobs'

    def ready(self):
        import atexit
        import threading
        import time
        import traceback
        from apscheduler.schedulers.background import BackgroundScheduler
        from django_apscheduler.jobstores import DjangoJobStore

        try:
            scheduler = BackgroundScheduler(timezone='Asia/Seoul')
            scheduler.add_jobstore(DjangoJobStore(), "default")
            scheduler.start()
            print("🌀 스케줄러 시작됨")

            atexit.register(lambda: scheduler.shutdown())

            def add_jobs():
                try:
                    time.sleep(1)
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
                except Exception:
                    print("❌ add_jobs 내부 에러 발생:")
                    traceback.print_exc()

            threading.Thread(target=add_jobs).start()

        except Exception:
            print("❌ ready() 에서 에러 발생:")
            traceback.print_exc()

