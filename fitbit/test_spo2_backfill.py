from datetime import datetime
from io import StringIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from fitbit.google_health.client import KST
from fitbit.google_health.daily_data.spo2 import SpO2FetchError
from fitbit.management.commands.backfill_spo2 import fill_missing_minutes
from fitbit.models import FitbitAccount, FitbitMinuteMetric


COMMAND = "fitbit.management.commands.backfill_spo2"
NOW = datetime(2026, 11, 19, 12, tzinfo=KST)
SCOPE = "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly"


def payload(*samples):
    points = [{"oxygenSaturation": {"sampleTime": {"physicalTime": time}, "percentage": value}}
              for time, value in samples]
    return {"dataPoints": points, "api_point_count": len(points), "page_count": 1}


class SpO2BackfillTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("spo2-participant")
        self.account = FitbitAccount.objects.create(
            user=self.user, fitbit_user_id="test-source", access_token="test", refresh_token="test",
            expires_at=NOW, scope=SCOPE, join_date=datetime(2026, 11, 15, tzinfo=KST),
        )
        self.output = StringIO()

    def run_backfill(self, **kwargs):
        options = {"user_id": self.user.pk, "start_date": "2026-11-15", "end_date": "2026-11-15"}
        options.update(kwargs)
        with patch(f"{COMMAND}.timezone.now", return_value=NOW):
            call_command("backfill_spo2", stdout=self.output, **options)

    @patch(f"{COMMAND}.fetch_spo2")
    def test_fills_missing_spo2_and_is_idempotent_without_changing_other_sensors(self, fetch):
        heart = FitbitMinuteMetric._base_manager.create(
            account=self.account, timestamp=datetime(2026, 11, 15, 9, tzinfo=KST),
            heart_rate=80, step_count=12,
        )
        existing = FitbitMinuteMetric._base_manager.create(
            account=self.account, timestamp=datetime(2026, 11, 15, 9, 1, tzinfo=KST), spo2=96,
        )
        fetch.return_value = payload(
            ("2026-11-15T00:00:04Z", 97), ("2026-11-15T00:01:04Z", 99),
            ("2026-11-15T00:02:04Z", 98),
        )
        self.run_backfill()
        heart.refresh_from_db()
        existing.refresh_from_db()
        self.assertEqual((heart.heart_rate, heart.step_count, heart.spo2), (80, 12, 97))
        self.assertEqual(existing.spo2, 96)
        self.assertEqual(self.account.minute_metrics.count(), 3)
        self.assertIn("신규 행=1건, 기존 행 보완=1건", self.output.getvalue())
        self.run_backfill()
        self.assertEqual(self.account.minute_metrics.count(), 3)
        self.assertIn("신규 행=0건, 기존 행 보완=0건", self.output.getvalue())

    @patch(f"{COMMAND}.fetch_spo2")
    def test_shared_credentials_do_not_import_another_participants_time_range(self, fetch):
        source = self.account
        source.participant_ended_at = datetime(2026, 11, 15, 12, tzinfo=KST)
        source.save(update_fields=["participant_ended_at"])
        new_user = get_user_model().objects.create_user("spo2-replacement")
        target = FitbitAccount.objects.create(
            user=new_user, fitbit_user_id="test-source", source_account=source,
            access_token="unused", refresh_token="unused", expires_at=NOW, scope=SCOPE,
            join_date=datetime(2026, 11, 15, 12, tzinfo=KST),
            participant_started_at=datetime(2026, 11, 15, 12, tzinfo=KST),
            participant_ended_at=datetime(2026, 11, 15, 18, tzinfo=KST),
        )
        fetch.return_value = payload(
            ("2026-11-15T02:59:00Z", 95), ("2026-11-15T03:00:04Z", 97),
            ("2026-11-15T09:00:00Z", 98),
        )
        self.run_backfill(user_id=new_user.pk, start_date="2026-11-01", end_date="2026-11-19")
        self.assertEqual(fetch.call_count, 1)
        self.assertEqual(fetch.call_args.args[1].pk, source.pk)
        self.assertEqual(list(target.minute_metrics.values_list("spo2", flat=True)), [97])
        self.assertFalse(source.minute_metrics.exists())

    @patch(f"{COMMAND}.fetch_spo2")
    def test_missing_enrollment_requires_an_explicit_start_date(self, fetch):
        self.account.join_date = None
        self.account.save(update_fields=["join_date"])
        with self.assertRaisesMessage(CommandError, "참여 시작일"):
            self.run_backfill(start_date=None)
        fetch.assert_not_called()

    @patch(f"{COMMAND}.fetch_spo2")
    def test_dry_run_does_not_write_measurements(self, fetch):
        fetch.return_value = payload(("2026-11-15T00:00:04Z", 97))
        self.run_backfill(dry_run=True)
        self.assertFalse(self.account.minute_metrics.exists())
        self.assertIn("보완 예정=1분", self.output.getvalue())

    @patch(f"{COMMAND}.fetch_spo2")
    def test_changed_enrollment_during_api_fetch_stops_before_writing(self, fetch):
        def change_enrollment(*args):
            FitbitAccount.objects.filter(pk=self.account.pk).update(
                join_date=datetime(2026, 11, 16, tzinfo=KST),
            )
            return payload(("2026-11-15T00:00:04Z", 97))

        fetch.side_effect = change_enrollment
        with self.assertRaisesMessage(CommandError, "참여 정보가 변경"):
            self.run_backfill()
        self.assertFalse(self.account.minute_metrics.exists())

    @patch(f"{COMMAND}.fetch_spo2", side_effect=SpO2FetchError("HTTP 503"))
    def test_failed_api_response_is_not_saved_or_reported_as_empty(self, fetch):
        with self.assertRaisesMessage(CommandError, "일부 날짜"):
            self.run_backfill()
        self.assertFalse(self.account.minute_metrics.exists())
        self.assertIn("조회 실패", self.output.getvalue())

    @patch(f"{COMMAND}.fetch_spo2")
    def test_day_is_rolled_back_when_storage_verification_fails(self, fetch):
        fetch.return_value = payload(("2026-11-15T00:00:04Z", 97))

        def fail_after_write(*args):
            fill_missing_minutes(*args)
            raise CommandError("검증 실패")

        with patch(f"{COMMAND}.fill_missing_minutes", side_effect=fail_after_write):
            with self.assertRaisesMessage(CommandError, "검증 실패"):
                self.run_backfill()
        self.assertFalse(self.account.minute_metrics.exists())

    @patch(f"{COMMAND}.fetch_spo2")
    def test_today_is_capped_at_current_time_and_future_days_are_not_fetched(self, fetch):
        self.account.join_date = datetime(2026, 11, 19, tzinfo=KST)
        self.account.save(update_fields=["join_date"])
        fetch.return_value = payload(("2026-11-19T02:59:00Z", 97), ("2026-11-19T03:00:00Z", 98))
        self.run_backfill(start_date=None, end_date="2026-12-01")
        fetch.assert_called_once()
        self.assertEqual(fetch.call_args.args[0], "2026-11-19")
        self.assertEqual(list(self.account.minute_metrics.values_list("spo2", flat=True)), [97])
