import csv
import io
import json
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from fitbit.models import FitbitAccount, FitbitMinuteMetric
from huami.models import HuamiAccount
from survey.models import Answer, Question, QuestionAnswer, Reply, Survey, SurveyQuestion, UserSurvey


@override_settings(ALLOWED_HOSTS=["testserver"])
class EpdsFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.participant = get_user_model().objects.create_user("epds-participant")
        cls.other = get_user_model().objects.create_user("other-participant")
        cls.admin = get_user_model().objects.create_superuser("epds-admin", "", "test-password")
        cls.account = FitbitAccount.objects.create(
            user=cls.participant, fitbit_user_id="epds-test", access_token="test", refresh_token="test",
            expires_at=timezone.now(), scope="", full_name="Test participant",
        )
        cls.survey = Survey.objects.create(title="에딘비러 산후 우울 검사 (K-EPDS)", description="test")
        cls.payload = {}
        cls.expected = []
        # Create in reverse question order to catch exports that sort by question ID.
        for order in range(10, 0, -1):
            question = Question.objects.create(title=f"문항 {order}", type_filed=2)
            SurveyQuestion.objects.create(survey=cls.survey, question=question, order=order, mandatory=True)
            values = [0, 1, 2, 3] if order in (1, 2, 4) else [3, 2, 1, 0]
            for index, value in enumerate(values):
                answer = Answer.objects.create(description=f"선택 {index}", value=value)
                QuestionAnswer.objects.create(question=question, answer=answer, order=index + 1)
            cls.payload[str(question.pk)] = "선택 0"
        cls.expected = [0, 0, 3, 0, 3, 3, 3, 3, 3, 3]

    def setUp(self):
        self.client.force_login(self.participant)

    def submit(self, payload=None):
        return self.client.post(f"/survey/{self.survey.pk}", self.payload if payload is None else payload)

    def test_total_reverse_scoring_and_answer_snapshots(self):
        self.assertEqual(self.submit().status_code, 200)
        submission = UserSurvey.objects.get()
        self.assertEqual(submission.score, 21)
        replies = list(submission.replies.order_by("survey_question__order"))
        self.assertEqual([reply.score for reply in replies], self.expected)
        self.assertEqual([reply.content for reply in replies], ["선택 0"] * 10)
        Answer.objects.update(value=0)
        submission.refresh_from_db()
        self.assertEqual(submission.score, 21)
        self.assertEqual(list(submission.replies.order_by("survey_question__order").values_list("score", flat=True)), self.expected)

    def test_invalid_partial_duplicate_and_foreign_answers_create_nothing(self):
        key = next(iter(self.payload))
        cases = [
            {k: v for k, v in self.payload.items() if k != key},
            {**self.payload, key: ["선택 0", "선택 1"]},
            {**self.payload, key: "조작된 응답"},
            {**self.payload, "999999": "선택 0"},
        ]
        for payload in cases:
            with self.subTest(payload=payload):
                self.assertEqual(self.submit(payload).status_code, 400)
                self.assertEqual(UserSurvey.objects.count(), 0)
                self.assertEqual(Reply.objects.count(), 0)

    def test_unconfigured_score_does_not_create_submission(self):
        Answer.objects.update(value=None)
        self.assertEqual(self.submit().status_code, 400)
        self.assertFalse(UserSurvey.objects.exists())

    def test_atomic_write(self):
        with patch("survey.views.Reply.objects.bulk_create", side_effect=RuntimeError("write failed")):
            with self.assertRaises(RuntimeError):
                self.submit()
        self.assertFalse(UserSurvey.objects.exists())

    def test_zero_and_maximum_scores(self):
        for value, total in [(0, 0), (3, 30)]:
            Answer.objects.update(value=value)
            self.assertEqual(self.submit().status_code, 200)
            self.assertEqual(UserSurvey.objects.latest("pk").score, total)

    def test_weekly_monthly_and_history_access(self):
        self.submit()
        first = UserSurvey.objects.get()
        first_time = datetime(2026, 10, 1, 23, 30, tzinfo=ZoneInfo("Asia/Seoul"))
        UserSurvey.objects.filter(pk=first.pk).update(create_at=first_time)
        self.submit()
        UserSurvey.objects.filter(pk=UserSurvey.objects.latest("pk").pk).update(
            score=9, create_at=datetime(2026, 10, 2, 0, 30, tzinfo=ZoneInfo("Asia/Seoul"))
        )
        base = f"/accounts/{self.participant.pk}/stress-data/"
        weekly = self.client.get(base, {"metric": "epds", "range": "weekly"}).json()
        self.assertEqual(weekly["values"], [21])
        self.assertEqual(weekly["scale_max"], 30)
        monthly = self.client.get(base, {"metric": "epds", "range": "monthly"}).json()
        self.assertEqual(monthly["values"], [15.0])
        self.assertEqual(monthly["scale_max"], 30)
        self.assertEqual(monthly["periods"], [{"start": "2026-10-01", "end": "2026-10-31"}])
        detail = f"/accounts/charts/{self.participant.pk}/weekly-detail/"
        params = {"metric": "epds", "start": "2026-10-01", "end": "2026-10-31"}
        history = self.client.get(detail, params).json()["history"]
        self.assertEqual(len(history), 2)
        self.assertEqual(len(history[0]["answers"]), 10)
        self.assertEqual(history[1]["answers"][0]["score"], 0)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(base, {"metric": "epds"}).status_code, 403)
        self.assertEqual(self.client.get(detail, params).status_code, 403)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(base, {"metric": "epds"}).status_code, 200)
        self.assertEqual(self.client.get(detail, params).status_code, 200)

    def test_empty_graph_has_epds_scale(self):
        data = self.client.get(f"/accounts/{self.participant.pk}/stress-data/", {"metric": "epds"}).json()
        self.assertEqual(data["values"], [])
        self.assertEqual(data["scale_max"], 30)

    def test_home_axis_uses_actual_submission_dates_and_keeps_aggregations(self):
        for day, score in [("2026-10-01T23:30:00", 21), ("2026-10-02T00:30:00", 0), ("2026-12-01T10:00:00", 0)]:
            self.submit()
            UserSurvey.objects.filter(pk=UserSurvey.objects.latest("pk").pk).update(
                score=score, create_at=datetime.fromisoformat(day).replace(tzinfo=ZoneInfo("Asia/Seoul"))
            )
        url = f"/accounts/{self.participant.pk}/stress-data/"
        weekly = self.client.get(url, {"metric": "epds", "range": "weekly", "axis": "survey_date"}).json()
        self.assertEqual(weekly["labels"], ["2026.10.01", "2026.12.01"])
        self.assertEqual(weekly["values"], [21, 0])
        monthly = self.client.get(url, {"metric": "epds", "range": "monthly", "axis": "survey_date"}).json()
        self.assertEqual(monthly["labels"], ["2026.10.02", "2026.12.01"])
        self.assertEqual(monthly["values"], [10.5, 0.0])
        self.assertEqual(len(monthly["periods"]), 2)
        default = self.client.get(url, {"metric": "epds", "range": "monthly"}).json()
        self.assertEqual(default["values"], [10.5, None, 0.0])

    def test_month_without_epds_is_not_a_zero_score(self):
        self.submit()
        first = UserSurvey.objects.get()
        UserSurvey.objects.filter(pk=first.pk).update(
            create_at=datetime(2026, 8, 1, tzinfo=ZoneInfo("Asia/Seoul"))
        )
        self.submit()
        UserSurvey.objects.filter(pk=UserSurvey.objects.latest("pk").pk).update(
            create_at=datetime(2026, 10, 1, tzinfo=ZoneInfo("Asia/Seoul"))
        )
        data = self.client.get(f"/accounts/{self.participant.pk}/stress-data/", {
            "metric": "epds", "range": "monthly"
        }).json()
        self.assertEqual(data["values"], [21.0, None, 21.0])

    def csv_rows(self, url):
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        return list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))

    def test_fitbit_health_csv_contains_only_health_data(self):
        self.submit()
        self.submit()
        url = f"/accounts/{self.participant.pk}/fitbit_csvData/"
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.force_login(self.admin)
        # Survey submissions must not add rows or columns to health exports.
        rows = self.csv_rows(url)
        self.assertEqual(rows, [])
        FitbitMinuteMetric.objects.create(account=self.account, timestamp=timezone.now(), heart_rate=72)
        rows = self.csv_rows(url)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["heart_rate"], "72")
        self.assertEqual(list(rows[0]), ["timestamp", "heart_rate", "step_count", "sleep_stage", "spo2",
                                        "respiratory_rate", "skin_temperature", "weight_kg", "height_cm", "age_years"])
        self.assertTrue(all(None not in row for row in rows))

    def test_huami_health_csv_and_survey_exports(self):
        self.submit()
        HuamiAccount.objects.create(user=self.participant, email="test@example.com", password="test")
        self.client.force_login(self.admin)
        rows = self.csv_rows(f"/accounts/{self.participant.pk}/csvData/")
        self.assertEqual(rows, [])
        response = self.client.get(f"/accounts/{self.participant.pk}/csvData/")
        headers = next(csv.reader(io.StringIO(response.content.decode())))
        self.assertEqual(headers, ['week', 'year', 'month', 'day', 'hour', 'minute', 'age', 'height',
                                   'weight', 'bmi', 'heart', 'sleep', 'step', 'stress', 'spo2', 'note'])
        rows = self.csv_rows(f"/survey/{self.survey.pk}/user/{self.participant.pk}/csv/")
        self.assertEqual(rows[0]["K-EPDS 점수"], "21")
        self.assertEqual([rows[0][f"문항 {i}"] for i in range(1, 11)], ["선택 0"] * 10)
        from survey.views import XlsxDownloadView
        workbook = XlsxDownloadView()._create_workbook(UserSurvey.objects.all(), self.participant)
        sheet = workbook[self.survey.title]
        self.assertEqual([cell.value for cell in sheet[1]][1:11], [f"문항 {i}" for i in range(1, 11)])
        self.assertEqual(sheet.cell(1, 12).value, "K-EPDS 점수")
        self.assertEqual(sheet.cell(2, 12).value, 21)
        # Check the actual existing survey download button's endpoint, too.
        from openpyxl import load_workbook
        response = self.client.get(f"/accounts/user/{self.participant.pk}/surveys/")
        self.assertEqual(response.status_code, 200)
        download = load_workbook(io.BytesIO(response.content))
        self.assertEqual(download[self.survey.title].cell(2, 12).value, 21)

    def test_survey_results_view_shows_epds_answers_and_scores(self):
        self.submit()
        self.client.force_login(self.admin)
        response = self.client.get(f"/survey/user/{self.participant.pk}/")
        self.assertContains(response, self.survey.title)
        self.assertContains(response, f"/survey/{self.survey.pk}/user/{self.participant.pk}/")
        response = self.client.get(f"/survey/{self.survey.pk}/user/{self.participant.pk}/")
        self.assertContains(response, "총점: 21점")
        self.assertContains(response, "선택 0", count=10)
        self.assertContains(response, "(0점)", count=3)
        self.assertContains(response, "(3점)", count=7)
        html = response.content.decode()
        positions = [html.index(f'<h3 class="results-question">문항 {i}</h3>') for i in range(1, 11)]
        self.assertEqual(positions, sorted(positions))

    def test_participant_home_and_admin_pages_include_epds_graph(self):
        self.assertContains(self.client.get("/"), 'id="epdsChart"')
        self.assertEqual(self.client.get(f"/accounts/fitbit_info/{self.participant.pk}/").status_code, 403)
        self.client.force_login(self.admin)
        for path in ("info", "fitbit_info"):
            self.assertContains(self.client.get(f"/accounts/{path}/{self.participant.pk}/"), 'id="epdsWeekly"')

    def test_results_summary_counts_only_target_participant_and_keeps_zero_score(self):
        self.submit()
        self.submit()
        latest = UserSurvey.objects.latest("pk")
        UserSurvey.objects.filter(pk=latest.pk).update(score=0)
        UserSurvey.objects.create(user=self.other, survey=self.survey, score=30)
        self.client.force_login(self.admin)
        response = self.client.get(f"/survey/user/{self.participant.pk}/")
        self.assertEqual(response.context["user"].pk, self.admin.pk)
        self.assertEqual(response.context["participant"].pk, self.participant.pk)
        self.assertEqual(response.context["total_responses"], 2)
        self.assertEqual(response.context["paginator"].count, 1)
        summary = response.context["object_list"][0]
        self.assertEqual(summary.response_count, 2)
        self.assertEqual(summary.latest_score, 0)
        response = self.client.get(f"/survey/{self.survey.pk}/user/{self.participant.pk}/")
        self.assertEqual(response.context["object_list"][0].pk, latest.pk)

    def test_backfill_is_explicit_and_idempotent(self):
        self.submit()
        UserSurvey.objects.update(score=None)
        Reply.objects.update(score=None)
        call_command("backfill_epds_scores", stdout=io.StringIO())
        self.assertIsNone(UserSurvey.objects.get().score)
        call_command("backfill_epds_scores", apply=True, stdout=io.StringIO())
        self.assertEqual(UserSurvey.objects.get().score, 21)
        call_command("backfill_epds_scores", apply=True, stdout=io.StringIO())
        self.assertEqual(UserSurvey.objects.get().score, 21)
