from django import forms
from django.contrib import messages
from django.core import signing
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponse
from django.utils import timezone
from django.views import View

from fitbit.models import FitbitAccount
from fitbit.participants import replace_participant
from accounts.views import RealResearchDataBlockedForTacMixin, SuperuserRequiredMixin


class ReplacementForm(forms.Form):
    name = forms.CharField(label="새 참여자 이름", max_length=100,
                           widget=forms.TextInput(attrs={"class": "form-control"}))
    effective_at = forms.DateTimeField(
        label="교체 일시 (한국 시간)",
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"],
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local", "class": "form-control"}),
    )

    def clean_name(self):
        value = self.cleaned_data["name"]
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise forms.ValidationError("이름에 줄바꿈이나 제어 문자를 입력할 수 없습니다.")
        return value

    def clean_effective_at(self):
        value = self.cleaned_data["effective_at"]
        if value.second or value.microsecond:
            raise forms.ValidationError("건강 데이터 저장 단위에 맞춰 교체 일시는 분 단위로 입력해주세요.")
        if value > timezone.now():
            raise forms.ValidationError("교체 일시는 현재보다 미래일 수 없습니다.")
        return value


class FitbitParticipantReplaceView(RealResearchDataBlockedForTacMixin, SuperuserRequiredMixin, View):
    def account(self, pk):
        return get_object_or_404(FitbitAccount.objects.select_related("user"), user_id=pk,
                                 user__is_superuser=False, user__is_staff=False, user__huami__isnull=True)

    def get(self, request, pk):
        account = self.account(pk)
        if account.participant_ended_at:
            return HttpResponse("이미 교체된 참여자입니다.", status=409)
        return render(request, "accounts/fitbit_replace.html", {
            "account": account, "form": ReplacementForm(initial={"effective_at": timezone.localtime().replace(second=0, microsecond=0)}),
        })

    def post(self, request, pk):
        account = self.account(pk)
        if account.participant_ended_at:
            return HttpResponse("이미 교체된 참여자입니다. 목록을 새로고침해주세요.", status=409)
        token = request.POST.get("confirmation")
        if token:
            try:
                data = signing.loads(token, salt="fitbit-replacement", max_age=600)
                if data["actor"] != request.user.pk or data["account"] != account.pk or data["old_name"] != account.full_name:
                    raise signing.BadSignature()
            except (signing.BadSignature, KeyError):
                return HttpResponse("확인 정보가 만료되었거나 변경되었습니다. 다시 입력해주세요.", status=400)
            form = ReplacementForm(data)
        else:
            form = ReplacementForm(request.POST)
        if form.is_valid():
            boundary = form.cleaned_data["effective_at"]
            if account.participant_started_at and boundary <= account.participant_started_at:
                form.add_error("effective_at", "이전 교체 일시보다 늦은 시각을 입력해주세요.")
            elif token:
                try:
                    new = replace_participant(account.pk, form.cleaned_data["name"], boundary, request.user, expected_name=data["old_name"])
                except ValidationError as exc:
                    form.add_error(None, exc)
                else:
                    messages.success(request, f"참여자를 교체했습니다. 새 시스템 사용자 ID: {new.user_id}. 기존 참여자는 목록에서 계속 조회할 수 있습니다.")
                    return redirect("accounts:fitbitUserManage")
            else:
                confirmation = signing.dumps({
                    "actor": request.user.pk, "account": account.pk, "old_name": account.full_name,
                    "name": form.cleaned_data["name"],
                    "effective_at": timezone.localtime(boundary).strftime("%Y-%m-%dT%H:%M:%S"),
                }, salt="fitbit-replacement")
                return render(request, "accounts/fitbit_replace_confirm.html", {
                    "account": account, "new_name": form.cleaned_data["name"],
                    "effective_at": boundary, "confirmation": confirmation,
                })
        return render(request, "accounts/fitbit_replace.html", {"account": account, "form": form}, status=400)
