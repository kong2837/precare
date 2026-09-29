from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import date
from django.utils import timezone

from information.services.pregnancy_data import PREGNANCY_DATA
from accounts.utils import cal_gestational_week
from accounts.utils import cal_gestational_age_from_join


class MyLoginRequiredMixin(LoginRequiredMixin):
    login_url = "/accounts/login/"
    redirect_field_name = "redirect_to"


class HomeView(TemplateView, MyLoginRequiredMixin):
    template_name = 'main.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user

        # Fitbit / Huami 중 연결된 계정 선택
        target = None

        if hasattr(user, "fitbit"):
            target = user.fitbit
        elif hasattr(user, "huami"):
            target = user.huami

        current_week = None
        current_day = None

        if target is not None:
            join_date = target.join_date
            pregnancy_week_at_join = target.pregnancy_week_at_join
            pregnancy_day_at_join = target.pregnancy_day_at_join

            if (
                join_date is not None
                and pregnancy_week_at_join is not None
                and pregnancy_day_at_join is not None
            ):
                current_week, current_day = cal_gestational_age_from_join(
                    join_date,
                    pregnancy_week_at_join,
                    pregnancy_day_at_join,
                    timezone.localdate()
                )

        context["current_week"] = current_week
        context["current_day"] = current_day

        # 임신 정보 데이터는 기존처럼 "주"를 기준으로 가져옴
        context["info"] = (
            PREGNANCY_DATA.get(current_week)
            if current_week is not None
            else None
        )

        return context