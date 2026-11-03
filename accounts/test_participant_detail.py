from datetime import datetime
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import UserClickLog
from fitbit.models import FitbitAccount
from huami.models import HuamiAccount


@override_settings(ALLOWED_HOSTS=["testserver"])
class ParticipantDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser("detail-admin", "", "test")
        cls.user = get_user_model().objects.create_user("detail-user")
        cls.other = get_user_model().objects.create_user("other-detail")
        cls.fitbit = FitbitAccount.objects.create(
            user=cls.user, fitbit_user_id="detail-id", expires_at=timezone.now(),
            access_token="test", refresh_token="test", scope="", full_name="테스트 대상자", note="Fitbit 메모",
        )
        cls.huami = HuamiAccount.objects.create(user=cls.user, email="detail@example.com", password="test", note="Huami 메모")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_both_detail_pages_show_charts_profile_and_compact_note(self):
        for kind, route in [("fitbit", "fitbit_info"), ("huami", "info")]:
            response = self.client.get(f"/accounts/{route}/{self.user.pk}/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["profile_kind"], kind)
            self.assertEqual(len(response.context["survey_charts"]), 4)
            self.assertContains(response, 'class="participant-chart-grid"')
            self.assertContains(response, 'id="epdsWeekly"')
            self.assertContains(response, 'offcanvas offcanvas-end')
            self.assertContains(response, 'data-all-range="monthly"')
            self.assertContains(response, "participant_detail.js")

    def test_note_updates_the_selected_profile_and_preserves_other_profile(self):
        response = self.client.post(f"/accounts/{self.user.pk}/updateNote/", {"note": "수정한 Fitbit 메모", "profile_kind": "fitbit"})
        self.assertRedirects(response, f"/accounts/fitbit_info/{self.user.pk}/")
        self.fitbit.refresh_from_db()
        self.huami.refresh_from_db()
        self.assertEqual(self.fitbit.note, "수정한 Fitbit 메모")
        self.assertEqual(self.huami.note, "Huami 메모")

    def test_log_filter_counts_and_timezone_date_boundaries(self):
        one = UserClickLog.objects.create(user=self.user, log_type="survey_click", detail="K-EPDS")
        two = UserClickLog.objects.create(user=self.user, log_type="survey_click", detail="K-EPDS older")
        UserClickLog.objects.filter(pk=one.pk).update(created_at=datetime(2026, 11, 3, 0, 10, tzinfo=ZoneInfo("Asia/Seoul")))
        UserClickLog.objects.filter(pk=two.pk).update(created_at=datetime(2026, 11, 2, 23, 50, tzinfo=ZoneInfo("Asia/Seoul")))
        UserClickLog.objects.create(user=self.other, log_type="survey_click", detail="K-EPDS")
        UserClickLog.objects.create(user=self.user, log_type="mother_fetus_info_click", detail="태아 정보")
        response = self.client.get(f"/accounts/user/{self.user.pk}/click-logs/", {
            "search": "EPDS", "log_type": "survey_click", "start_date": "2026-11-03", "end_date": "2026-11-03",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["logs"]), [one])
        self.assertEqual(response.context["summary"], {"total": 1, "survey": 1, "information": 0})

    def test_log_pagination_preserves_search_and_stable_order(self):
        UserClickLog.objects.bulk_create([UserClickLog(user=self.user, log_type="survey_click", detail="A&B") for _ in range(35)])
        response = self.client.get(f"/accounts/user/{self.user.pk}/click-logs/", {"search": "A&B", "page": 2})
        self.assertEqual(response.context["page_obj"].paginator.count, 35)
        self.assertEqual(len(response.context["logs"]), 5)
        self.assertContains(response, "search=A%26B")
        self.assertEqual(response.context["page_obj"].number, 2)

    def test_invalid_log_dates_and_types_are_reported(self):
        for filters in ({"start_date": "not-a-date"}, {"start_date": "2026-11-04", "end_date": "2026-11-03"}, {"log_type": "invalid"}):
            response = self.client.get(f"/accounts/user/{self.user.pk}/click-logs/", filters)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["filter_form"].errors)
            self.assertEqual(response.context["summary"]["total"], 0)

    def test_participant_cannot_read_logs_detail_or_edit_notes(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f"/accounts/user/{self.user.pk}/click-logs/").status_code, 403)
        self.assertEqual(self.client.get(f"/accounts/fitbit_info/{self.user.pk}/").status_code, 403)
        self.assertEqual(self.client.post(f"/accounts/{self.user.pk}/updateNote/", {"note": "blocked"}).status_code, 403)
