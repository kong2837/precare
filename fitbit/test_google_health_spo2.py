from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from fitbit.google_health.daily_data.spo2 import (
    KST, SpO2FetchError, fetch_spo2, get_spo2, spo2_minutes_for_date,
)


MODULE = "fitbit.google_health.daily_data.spo2"


def response(data=None, status=200, headers=None):
    result = Mock(status_code=status, headers={} if headers is None else headers)
    result.json.return_value = {} if data is None else data
    return result


def point(timestamp, value=97):
    return {
        "oxygenSaturation": {
            "sampleTime": {"physicalTime": timestamp},
            "percentage": value,
        }
    }


class GoogleHealthSpO2Tests(SimpleTestCase):
    def setUp(self):
        self.account = SimpleNamespace(access_token="test-token", user_id=111)

    def test_latest_sample_wins_even_if_api_pages_are_in_reverse_time_order(self):
        minutes, matched, invalid = spo2_minutes_for_date([
            point("2026-11-15T00:00:50Z", 98),
            point("2026-11-15T00:00:04Z", 94),
            point("2026-11-15T00:00:20Z", float("nan")),
            point("2026-11-15T00:01:00Z", 101),
            point("not-a-date", 97),
        ], "2026-11-15")
        self.assertEqual(matched, 2)
        self.assertEqual(invalid, 3)
        self.assertEqual(minutes, {datetime(2026, 11, 15, 9, 0): (datetime(2026, 11, 15, 9, 0, 50), 98)})

    @patch(f"{MODULE}.FitbitMinuteMetric.objects.get_or_create", return_value=(Mock(), True))
    @patch(f"{MODULE}.requests.get")
    def test_auto_sync_excludes_measurements_outside_the_enrollment_window(self, get, store):
        self.account.join_date = datetime(2026, 11, 15, 9, 0, 30, tzinfo=KST)
        self.account.end_date = datetime(2026, 11, 15, 9, 2, tzinfo=KST)
        get.return_value = response({"dataPoints": [
            point("2026-11-15T00:00:40Z"), point("2026-11-15T00:01:04Z"),
            point("2026-11-15T00:02:00Z"),
        ]})
        get_spo2("2026-11-15", self.account)
        store.assert_called_once_with(
            account=self.account, timestamp=datetime(2026, 11, 15, 9, 1), defaults={"spo2": 97},
        )

    @patch(f"{MODULE}.requests.get")
    @patch(f"{MODULE}.FitbitMinuteMetric.objects.get_or_create")
    def test_requested_days_use_kst_midnight_boundaries_without_measurement_writes(self, store, get):
        get.return_value = response()
        for day in (15, 16, 17):
            with self.subTest(day=day):
                result = fetch_spo2(f"2026-11-{day}", self.account)
                self.assertEqual(
                    get.call_args.kwargs["params"]["filter"],
                    f'oxygen_saturation.sample_time.physical_time >= "2026-11-{day-1}T15:00:00Z" '
                    f'AND oxygen_saturation.sample_time.physical_time < "2026-11-{day}T15:00:00Z"',
                )
                self.assertEqual(result["page_count"], 1)
                self.assertEqual(result["dataPoints"], [])
        store.assert_not_called()

    @patch(f"{MODULE}.requests.get")
    def test_more_than_one_thousand_points_are_fetched(self, get):
        first = [point("2026-11-14T16:00:00Z")] * 1000
        last = point("2026-11-15T14:59:00Z", 98)
        get.side_effect = [
            response({"dataPoints": first, "nextPageToken": "second"}),
            response({"dataPoints": [last]}),
        ]
        result = fetch_spo2("2026-11-15", self.account)
        self.assertEqual(result["api_point_count"], 1001)
        self.assertEqual(result["page_count"], 2)
        self.assertEqual(result["dataPoints"][-1], last)
        first_params = get.call_args_list[0].kwargs["params"]
        second_params = get.call_args_list[1].kwargs["params"]
        self.assertNotIn("pageToken", first_params)
        self.assertEqual(second_params, {**first_params, "pageToken": "second"})
        self.assertEqual(get.call_args.kwargs["timeout"], 20)

    @patch(f"{MODULE}.requests.get")
    def test_empty_page_with_next_token_does_not_end_query(self, get):
        get.side_effect = [
            response({"nextPageToken": "second"}),
            response({"dataPoints": [point("2026-11-15T00:00:00Z")]}),
        ]
        result = fetch_spo2("2026-11-15", self.account)
        self.assertEqual(result["api_point_count"], 1)
        self.assertEqual(result["page_count"], 2)

    @patch(f"{MODULE}.refresh_google_health_token")
    @patch(f"{MODULE}.requests.get")
    def test_expired_token_on_second_page_retries_that_page_with_new_token(self, get, refresh):
        def renew(account):
            account.access_token = "new-test-token"
            return True

        refresh.side_effect = renew
        get.side_effect = [
            response({"dataPoints": [point("2026-11-15T00:00:00Z")], "nextPageToken": "second"}),
            response(status=401),
            response({"dataPoints": [point("2026-11-15T00:01:00Z")]}),
        ]
        result = fetch_spo2("2026-11-15", self.account)
        self.assertEqual(result["api_point_count"], 2)
        self.assertEqual(result["page_count"], 2)
        refresh.assert_called_once_with(self.account)
        self.assertEqual(get.call_args_list[1].kwargs["params"], get.call_args_list[2].kwargs["params"])
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer new-test-token")

    @patch(f"{MODULE}.refresh_google_health_token", return_value=True)
    @patch(f"{MODULE}.requests.get")
    def test_repeated_unauthorized_response_does_not_refresh_forever(self, get, refresh):
        get.return_value = response(status=401)
        with self.assertRaisesMessage(SpO2FetchError, "HTTP 401"):
            fetch_spo2("2026-11-15", self.account)
        self.assertEqual(get.call_count, 2)
        refresh.assert_called_once()

    @patch(f"{MODULE}.refresh_google_health_token")
    @patch(f"{MODULE}.requests.get")
    def test_read_only_fetch_does_not_refresh_credentials(self, get, refresh):
        get.return_value = response(status=401)
        with self.assertRaisesMessage(SpO2FetchError, "HTTP 401"):
            fetch_spo2("2026-11-15", self.account, allow_token_refresh=False)
        get.assert_called_once()
        refresh.assert_not_called()

    @patch(f"{MODULE}.time.sleep")
    @patch(f"{MODULE}.random.uniform", return_value=0)
    @patch(f"{MODULE}.requests.get")
    def test_rate_limit_respects_retry_after_seconds(self, get, jitter, sleep):
        get.side_effect = [
            response(status=429, headers={"Retry-After": "5"}),
            response({"dataPoints": [point("2026-11-15T00:00:00Z")]}),
        ]
        result = fetch_spo2("2026-11-15", self.account)
        sleep.assert_called_once_with(5)
        self.assertEqual(result["api_point_count"], 1)
        self.assertEqual(result["page_count"], 1)
        self.assertEqual(get.call_args_list[0].kwargs["params"], get.call_args_list[1].kwargs["params"])

    @patch(f"{MODULE}.time.sleep")
    @patch(f"{MODULE}.random.uniform", side_effect=[0.25, 0.5, 0.75])
    @patch(f"{MODULE}.FitbitMinuteMetric.objects.get_or_create")
    @patch(f"{MODULE}.requests.get")
    def test_rate_limit_backoff_is_bounded_and_does_not_save_failed_results(self, get, store, jitter, sleep):
        get.return_value = response(status=429)
        self.assertIsNone(get_spo2("2026-11-15", self.account))
        self.assertEqual(get.call_count, 4)
        self.assertEqual(sleep.call_args_list, [call(2.25), call(4.5), call(8.75)])
        store.assert_not_called()

    @patch(f"{MODULE}.time.sleep")
    @patch(f"{MODULE}.random.uniform", return_value=0)
    @patch(f"{MODULE}.requests.get")
    def test_rate_limit_respects_http_date_retry_after(self, get, jitter, sleep):
        now = datetime(2026, 11, 20, tzinfo=timezone.utc)

        class FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return now

        get.side_effect = [
            response(status=429, headers={"Retry-After": format_datetime(now + timedelta(seconds=12), usegmt=True)}),
            response(),
        ]
        with patch(f"{MODULE}.datetime", FixedDatetime):
            fetch_spo2("2026-11-15", self.account)
        sleep.assert_called_once_with(12)

    @patch(f"{MODULE}.time.sleep")
    @patch(f"{MODULE}.random.uniform", return_value=0)
    @patch(f"{MODULE}.requests.get")
    def test_malformed_retry_after_falls_back_to_backoff(self, get, jitter, sleep):
        for header in ("invalid", "-1", "NaN"):
            with self.subTest(header=header):
                get.side_effect = [response(status=429, headers={"Retry-After": header}), response()]
                sleep.reset_mock()
                fetch_spo2("2026-11-15", self.account)
                sleep.assert_called_once_with(2)

    @patch(f"{MODULE}.time.sleep")
    @patch(f"{MODULE}.random.uniform", return_value=0)
    @patch(f"{MODULE}.requests.get")
    def test_rate_limit_on_second_page_keeps_the_first_page_and_retries_only_the_second(self, get, jitter, sleep):
        get.side_effect = [
            response({"dataPoints": [point("2026-11-15T00:00:00Z")], "nextPageToken": "second"}),
            response(status=429, headers={"Retry-After": "4"}),
            response({"dataPoints": [point("2026-11-15T00:01:00Z")]}),
        ]
        result = fetch_spo2("2026-11-15", self.account)
        self.assertEqual(result["api_point_count"], 2)
        self.assertEqual(result["page_count"], 2)
        self.assertEqual(get.call_args_list[1].kwargs["params"], get.call_args_list[2].kwargs["params"])
        self.assertEqual(get.call_args.kwargs["params"]["pageToken"], "second")
        sleep.assert_called_once_with(4)

    @patch(f"{MODULE}.time.sleep")
    @patch(f"{MODULE}.random.uniform", return_value=0)
    @patch(f"{MODULE}.requests.get")
    def test_each_page_has_a_separate_retry_budget(self, get, jitter, sleep):
        limited = response(status=429)
        get.side_effect = [limited, limited, limited, response({"nextPageToken": "second"}),
                           limited, limited, limited, response()]
        result = fetch_spo2("2026-11-15", self.account)
        self.assertEqual(result["page_count"], 2)
        self.assertEqual(get.call_count, 8)
        self.assertEqual(sleep.call_args_list, [call(2), call(4), call(8), call(2), call(4), call(8)])

    @patch(f"{MODULE}.time.sleep")
    @patch(f"{MODULE}.random.uniform", return_value=0)
    @patch(f"{MODULE}.requests.get")
    def test_long_retry_after_defers_the_account_without_retrying_early_on_the_next_day(self, get, jitter, sleep):
        get.return_value = response(status=429, headers={"Retry-After": "120"})
        with self.assertRaisesMessage(SpO2FetchError, "60초"):
            fetch_spo2("2026-11-15", self.account)
        with self.assertRaisesMessage(SpO2FetchError, "대기 중"):
            fetch_spo2("2026-11-16", self.account)
        get.assert_called_once()
        sleep.assert_not_called()

    @patch(f"{MODULE}.time.sleep")
    @patch(f"{MODULE}.random.uniform", return_value=0)
    @patch(f"{MODULE}.FitbitMinuteMetric.objects.get_or_create")
    @patch(f"{MODULE}.requests.get")
    def test_exhausted_second_page_retries_do_not_save_the_first_page(self, get, store, jitter, sleep):
        get.side_effect = [
            response({"dataPoints": [point("2026-11-15T00:00:00Z")], "nextPageToken": "second"}),
            response(status=429), response(status=429), response(status=429), response(status=429),
        ]
        self.assertIsNone(get_spo2("2026-11-15", self.account))
        self.assertEqual(get.call_count, 5)
        store.assert_not_called()

    @patch(f"{MODULE}.requests.get")
    def test_expired_account_cooldown_does_not_permanently_block_collection(self, get):
        self.account._spo2_retry_at = datetime(2020, 1, 1, tzinfo=timezone.utc)
        get.return_value = response()
        result = fetch_spo2("2026-11-15", self.account)
        self.assertEqual(result["page_count"], 1)
        get.assert_called_once()

    @patch(f"{MODULE}.requests.get")
    def test_repeated_page_token_is_an_error(self, get):
        get.return_value = response({"nextPageToken": "repeated"})
        with self.assertRaisesMessage(SpO2FetchError, "반복"):
            fetch_spo2("2026-11-15", self.account)
        self.assertEqual(get.call_count, 2)

    @patch(f"{MODULE}.requests.get")
    def test_invalid_date_does_not_make_a_request(self, get):
        with self.assertRaises(SpO2FetchError):
            fetch_spo2("2026-11-31", self.account)
        get.assert_not_called()

    @patch(f"{MODULE}.requests.get", side_effect=requests.Timeout("test timeout"))
    def test_network_error_is_reported_as_fetch_failure(self, get):
        with self.assertRaisesMessage(SpO2FetchError, "네트워크"):
            fetch_spo2("2026-11-15", self.account)

    @patch(f"{MODULE}.requests.get")
    def test_invalid_json_is_not_treated_as_no_data(self, get):
        get.return_value = response()
        get.return_value.json.side_effect = ValueError("invalid json")
        with self.assertRaisesMessage(SpO2FetchError, "JSON"):
            fetch_spo2("2026-11-15", self.account)

    @patch(f"{MODULE}.FitbitMinuteMetric.objects.get_or_create")
    @patch(f"{MODULE}.requests.get")
    def test_second_page_failure_does_not_save_partial_results(self, get, store):
        get.side_effect = [
            response({"dataPoints": [point("2026-11-15T00:00:00Z")], "nextPageToken": "second"}),
            response(status=503),
        ]
        self.assertIsNone(get_spo2("2026-11-15", self.account))
        store.assert_not_called()

    @patch(f"{MODULE}.FitbitMinuteMetric.objects.get_or_create")
    @patch(f"{MODULE}.requests.get")
    def test_both_pages_are_saved_only_inside_requested_kst_day(self, get, store):
        existing = SimpleNamespace(spo2=95, save=Mock())
        store.side_effect = [(Mock(), True), (existing, False)]
        get.side_effect = [
            response({
                "dataPoints": [point("2026-11-14T14:59:59Z"), point("2026-11-14T15:00:00Z")],
                "nextPageToken": "second",
            }),
            response({"dataPoints": [point("2026-11-15T14:59:59Z", 98), point("2026-11-15T15:00:00Z")]}),
        ]
        result = get_spo2("2026-11-15", self.account)
        self.assertEqual(result["page_count"], 2)
        self.assertEqual(store.call_args_list, [
            call(account=self.account, timestamp=datetime(2026, 11, 15, 0, 0), defaults={"spo2": 97}),
            call(account=self.account, timestamp=datetime(2026, 11, 15, 23, 59), defaults={"spo2": 98}),
        ])
        self.assertEqual(existing.spo2, 98)
        existing.save.assert_called_once_with(update_fields=["spo2"])


COMMAND = "fitbit.management.commands.check_spo2"


class CheckSpO2CommandTests(SimpleTestCase):
    @patch(f"{COMMAND}.connection")
    @patch(f"{COMMAND}.FitbitAccount.objects.only")
    @patch(f"{COMMAND}.fetch_spo2")
    @patch(f"{MODULE}.FitbitMinuteMetric.objects.get_or_create")
    def test_command_checks_all_requested_dates_without_writes_or_secret_output(self, store, fetch, only, connection):
        # No source_account_id in an older schema must still permit diagnosis.
        connection.introspection.get_table_description.return_value = []
        account = SimpleNamespace(
            pk=32, access_token="secret-test-token", refresh_token="secret-refresh-token",
            scope="https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
            save=Mock(),
        )
        only.return_value.get.return_value = account
        fetch.return_value = {"dataPoints": [], "api_point_count": 0, "page_count": 1, "query_filter": "test-filter"}
        output = StringIO()
        call_command(
            "check_spo2", user_id=111, start_date="2026-11-15", end_date="2026-11-17", stdout=output,
        )
        self.assertEqual(fetch.call_args_list, [
            call("2026-11-15", account, allow_token_refresh=False),
            call("2026-11-16", account, allow_token_refresh=False),
            call("2026-11-17", account, allow_token_refresh=False),
        ])
        store.assert_not_called()
        account.save.assert_not_called()
        self.assertEqual(output.getvalue().count("HTTP 200"), 3)
        self.assertNotIn(account.access_token, output.getvalue())
        self.assertNotIn(account.refresh_token, output.getvalue())

    @patch(f"{COMMAND}.connection")
    @patch(f"{COMMAND}.FitbitAccount.objects.only")
    @patch(f"{COMMAND}.fetch_spo2")
    def test_command_does_not_mistake_api_failure_for_empty_data(self, fetch, only, connection):
        connection.introspection.get_table_description.return_value = []
        only.return_value.get.return_value = SimpleNamespace(
            pk=32, scope="https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
        )
        fetch.side_effect = SpO2FetchError("HTTP 403")
        output = StringIO()
        with self.assertRaises(CommandError):
            call_command(
                "check_spo2", user_id=111, start_date="2026-11-15", end_date="2026-11-17", stdout=output,
            )
        self.assertEqual(fetch.call_count, 3)
        self.assertNotIn("HTTP 200", output.getvalue())
        self.assertEqual(output.getvalue().count("HTTP 403"), 3)

    @patch(f"{COMMAND}.connection")
    def test_reversed_date_range_is_rejected_before_database_access(self, connection):
        with self.assertRaisesMessage(CommandError, "종료일"):
            call_command("check_spo2", user_id=111, start_date="2026-11-17", end_date="2026-11-15")
        connection.cursor.assert_not_called()
