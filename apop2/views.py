from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from datetime import date

from information.services.pregnancy_data import PREGNANCY_DATA
from accounts.utils import cal_gestational_week


class MyLoginRequiredMixin(LoginRequiredMixin):
    login_url = "/accounts/login/"
    redirect_field_name = "redirect_to"


class HomeView(TemplateView, MyLoginRequiredMixin):
    template_name = 'main.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user

        if hasattr(user, "fitbit") and user.fitbit.pregnancy_start_date:
            pregnancy_start_date = user.fitbit.pregnancy_start_date.date()
        else:
            pregnancy_start_date = None

        current_week = cal_gestational_week(
            pregnancy_start_date,
            date.today()
        )

        context["current_week"] = current_week
        context["info"] = PREGNANCY_DATA.get(current_week)

        return context