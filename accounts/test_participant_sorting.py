import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone

from fitbit.models import FitbitAccount
from huami.models import HuamiAccount


@override_settings(ALLOWED_HOSTS=["testserver"])
class ParticipantSortingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser("sorting-admin", "", "test")
        for i in range(12):
            user = get_user_model().objects.create_user(f"sorting-{i:02d}")
            start = timezone.now() - timedelta(days=i)
            FitbitAccount.objects.create(
                user=user, fitbit_user_id=f"sorting-{i}", access_token="test", refresh_token="test",
                expires_at=timezone.now(), full_name=f"Participant {i:02d}", scope="",
                birthday=f"1990-01-{i+1:02d}", research_year=str(2023 + i % 3),
                join_date=start, end_date=start, pregnancy_start_date=start,
                pregnancy_week_at_join=i // 2, pregnancy_day_at_join=i % 2,
                note=f"Note {i:02d}", last_synced=start,
            )
            HuamiAccount.objects.create(
                user=user, email=f"sorting{i:02d}@example.com", password="test",
                name=f"Participant {i:02d}", age=20+i, note=f"Note {i:02d}",
                research_year=str(2023 + i % 3), join_date=start, end_date=start,
                pregnancy_start_date=start,
            )

    def view_queryset(self, profile, field, direction="asc", **params):
        from accounts.views import FitbitUserManageView, UserManageView
        view = FitbitUserManageView() if profile == "fitbit" else UserManageView()
        view.request = RequestFactory().get("/", {"order_by": field, "direction": direction, **params})
        return view.get_queryset()

    def test_name_sort_both_directions(self):
        for profile, field in [("fitbit", "full_name"), ("huami", "name")]:
            asc = list(self.view_queryset(profile, f"{profile}__{field}").values_list("username", flat=True))
            desc = list(self.view_queryset(profile, f"{profile}__{field}", "desc").values_list("username", flat=True))
            self.assertEqual(asc[0], "sorting-00")
            self.assertEqual(desc, list(reversed(asc)))

    def test_dates_year_and_numeric_sorts(self):
        for profile, fields in [("fitbit", ["birthday", "research_year", "join_date", "end_date", "pregnancy_start_date", "last_synced"]),
                                ("huami", ["age", "research_year", "join_date", "end_date", "pregnancy_start_date"])]:
            for field in fields:
                key = f"{profile}__{field}"
                for direction in ("asc", "desc"):
                    with self.subTest(key=key, direction=direction):
                        values = list(self.view_queryset(profile, key, direction).values_list(key, flat=True))
                        self.assertEqual(values, sorted(values, reverse=direction == "desc"))

    def test_pregnancy_week_sorts_days_as_secondary_value(self):
        asc = list(self.view_queryset("fitbit", "fitbit__pregnancy_week_at_join").values_list("username", flat=True))
        desc = list(self.view_queryset("fitbit", "fitbit__pregnancy_week_at_join", "desc").values_list("username", flat=True))
        self.assertEqual(asc[:2], ["sorting-00", "sorting-01"])
        self.assertEqual(desc, list(reversed(asc)))

    def test_unknown_field_falls_back_and_search_is_preserved(self):
        for profile in ("fitbit", "huami"):
            qs = self.view_queryset(profile, "password", search="Participant 01")
            self.assertEqual(list(qs.values_list("username", flat=True)), ["sorting-01"])
            self.assertEqual(qs.query.order_by[-1], "pk")

    def test_pages_use_real_fields_and_move_columns_and_cells_together(self):
        self.client.force_login(self.admin)
        for profile, url in [("fitbit", "/accounts/fitbit_manage/"), ("huami", "/accounts/manage/")]:
            response = self.client.get(url, {"order_by": f"{profile}__research_year", "direction": "desc", "page": 2})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.context["users"]), 2)
            html = response.content.decode()
            head = re.search(r"<thead>(.*?)</thead>", html, re.S)[1]
            columns = re.findall(r'data-column="([^"]+)"', head)
            self.assertEqual(columns[-2:], [f"{profile}__research_year", f"{profile}__pregnancy_start_date"])
            row = re.search(r'<tr data-href=.*?</tr>', html, re.S)[0]
            cells = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
            self.assertIn("research-year", cells[-2])
            self.assertIn("pregnancy_start_date", cells[-1])
            self.assertEqual(len(cells), head.count("<th "))
