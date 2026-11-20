from datetime import date, datetime, timezone as dt_timezone
from types import SimpleNamespace
from unittest.mock import call, patch

from django.test import SimpleTestCase, override_settings
from django.core.exceptions import FieldDoesNotExist
from django.utils import timezone

from jobs.tasks import spo2_sync_dates, sync_accounts, sync_daily_data, sync_intra_data


class SpO2ScheduleTests(SimpleTestCase):
    @patch("jobs.tasks.FitbitAccount.objects.all")
    @patch("jobs.tasks.FitbitAccount._meta.get_field", side_effect=FieldDoesNotExist)
    def test_older_models_without_replacement_fields_can_still_sync(self, field, accounts):
        self.assertIs(sync_accounts(), accounts.return_value)
        accounts.assert_called_once()

    def test_lookback_includes_today_and_six_previous_days(self):
        account = SimpleNamespace(join_date=datetime(2026, 11, 5, tzinfo=dt_timezone.utc))
        self.assertEqual(spo2_sync_dates(account, date(2026, 11, 19)), [
            "2026-11-19", "2026-11-18", "2026-11-17", "2026-11-16",
            "2026-11-15", "2026-11-14", "2026-11-13",
        ])

    def test_lookback_never_precedes_enrollment_kst_date(self):
        account = SimpleNamespace(join_date=datetime(2026, 11, 17, 15, tzinfo=dt_timezone.utc))
        self.assertEqual(spo2_sync_dates(account, date(2026, 11, 19)), ["2026-11-19", "2026-11-18"])
        account.join_date = datetime(2026, 11, 20, tzinfo=dt_timezone.utc)
        self.assertEqual(spo2_sync_dates(account, date(2026, 11, 19)), [])

    def test_missing_enrollment_does_not_backfill_previous_wearer(self):
        self.assertEqual(spo2_sync_dates(SimpleNamespace(join_date=None), date(2026, 11, 19)), ["2026-11-19"])

    @override_settings(GOOGLE_HEALTH_SPO2_LOOKBACK_DAYS=3)
    def test_lookback_can_be_configured(self):
        account = SimpleNamespace(join_date=datetime(2026, 11, 1))
        self.assertEqual(spo2_sync_dates(account, date(2026, 11, 19)), ["2026-11-19", "2026-11-18", "2026-11-17"])

    @patch("jobs.tasks.FitbitAccount.objects.filter")
    @patch("jobs.tasks.get_skin_temperature")
    @patch("jobs.tasks.get_spo2")
    @patch("jobs.tasks.get_respiratory_rate")
    @patch("jobs.tasks.get_sleep_stage")
    def test_daily_job_uses_kst_even_when_current_timezone_is_utc(self, sleep, rr, spo2, skin, accounts):
        account = SimpleNamespace(join_date=datetime(2026, 11, 1), user=SimpleNamespace(username="test"))
        accounts.return_value = [account]
        with timezone.override("UTC"), patch("jobs.tasks.timezone.now", return_value=datetime(2026, 11, 18, 15, 30, tzinfo=dt_timezone.utc)):
            sync_daily_data()
        sleep.assert_called_once_with("2026-11-19", account)
        rr.assert_called_once_with("2026-11-19", account)
        skin.assert_called_once_with("2026-11-18", account)
        self.assertEqual(spo2.call_args_list, [call(day, account) for day in [
            "2026-11-19", "2026-11-18", "2026-11-17", "2026-11-16",
            "2026-11-15", "2026-11-14", "2026-11-13",
        ]])
        accounts.assert_called_once_with(source_account__isnull=True)

    @patch("jobs.tasks.FitbitAccount.objects.filter")
    @patch("jobs.tasks.get_step_count")
    @patch("jobs.tasks.get_heart_rate")
    def test_intraday_job_also_uses_kst_at_midnight(self, heart, steps, accounts):
        account = SimpleNamespace(user=SimpleNamespace(username="test"))
        accounts.return_value = [account]
        with timezone.override("UTC"), patch("jobs.tasks.timezone.now", return_value=datetime(2026, 11, 18, 15, 30, tzinfo=dt_timezone.utc)):
            sync_intra_data()
        heart.assert_called_once_with("2026-11-19", account)
        steps.assert_called_once_with("2026-11-19", account)
