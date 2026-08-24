import csv
import re
import urllib.parse
import json

from tempfile import NamedTemporaryFile
from typing import Any

from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db.models.query import QuerySet
from django.core.exceptions import FieldError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic.detail import DetailView
from django.views.generic.edit import ProcessFormView
from django.views.generic.list import ListView

from openpyxl import Workbook

import survey.utils as utils

from accounts.views import SuperuserRequiredMixin
from survey.models import (
    Survey,
    Question,
    UserSurvey,
    Reply,
    SurveyQuestion,
    Answer,
    ActionFeedback,
)


# ============================================================
# Login Required Mixin
# ============================================================

class MyLoginRequiredMixin(LoginRequiredMixin):
    login_url = "/accounts/login/"
    redirect_field_name = "redirect_to"


# ============================================================
# Survey List
# ============================================================

class SurveyListView(MyLoginRequiredMixin, ListView):
    """참여 가능한 설문 목록을 제공하는 클래스 기반 뷰"""

    template_name = "survey/survey_list.html"
    model = Survey

    def get_queryset(self):
        custom_order = [
            "[연구시작시]연구 참여자 기초 건강 설문",
            "[상시]QUIPP",
            "[상시]조기진통위험 10문항",
            "[상시]임신스트레스 10문항",
            "[연구종료시]만족도 조사",
        ]

        surveys = Survey.objects.exclude(
            title__in=[
                "[상시]QUIPP 유증상",
                "[상시]QUIPP 무증상",
            ]
        )

        surveys_sorted = sorted(
            surveys,
            key=lambda s: (
                custom_order.index(s.title)
                if s.title in custom_order
                else 999
            ),
        )

        return surveys_sorted


# ============================================================
# Survey Detail
# ============================================================

class SurveyDetailView(MyLoginRequiredMixin, DetailView):
    """설문에 대한 구체적인 정보를 제공하는 클래스 기반 뷰"""

    template_name = "survey/survey_detail.html"
    model = Survey


# ============================================================
# Admin - User Survey List
# ============================================================

class UserSurveyListAdminView(SuperuserRequiredMixin, ListView):
    """다른 유저가 작성한 설문 결과들을 제공하는 클래스 기반 뷰"""

    template_name = "survey/user_survey_list.html"
    paginate_by = 5
    model = UserSurvey

    def get_queryset(self):
        queryset = UserSurvey.objects.filter(
            user__pk=self.kwargs["user_pk"],
            survey__pk=self.kwargs["survey_pk"],
        ).order_by("create_at")

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["survey"] = Survey.objects.get(
            pk=self.kwargs["survey_pk"]
        )

        return context


# ============================================================
# Admin - Survey List
# ============================================================

class SurveyListAdminView(SuperuserRequiredMixin, ListView):
    """다른 유저가 작성한 설문들을 제공하는 클래스 기반 뷰"""

    template_name = "survey/user_survey_list_admin.html"
    paginate_by = 5
    model = Survey

    def get_queryset(self) -> QuerySet[Survey]:
        queryset = Survey.objects.filter(
            users__pk=self.kwargs.get("pk")
        ).distinct()

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["user"] = get_user_model().objects.get(
            pk=self.kwargs.get("pk")
        )

        return context


# ============================================================
# CSV Download
# ============================================================

class UserSurveyCsvView(SuperuserRequiredMixin, View):

    def get(self, request, *args, **kwargs):
        user_pk = self.kwargs.get("user_pk")
        survey_pk = self.kwargs.get("survey_pk")

        user = get_user_model().objects.get(pk=user_pk)
        survey = Survey.objects.get(pk=survey_pk)

        user_surveys = UserSurvey.objects.filter(
            user_id=user_pk,
            survey_id=survey_pk,
        ).order_by("create_at")

        # 사용자 이름 결정
        try:
            name = user.huami.fullname
        except Exception:
            try:
                name = user.fitbit.full_name
            except Exception:
                # Google Health 사용자 등 huami / fitbit 객체가 없는 경우
                name = user.username

        filename = f"{name}-{survey.title}"

        response = HttpResponse(
            content_type="text/csv; charset=utf-8"
        )

        response["Content-Disposition"] = (
            "attachment; filename*=UTF-8''"
            f"{urllib.parse.quote(filename)}.csv"
        )

        # 한글 Excel 깨짐 방지
        response.write("\ufeff")

        writer = csv.writer(response)

        questions = list(
            survey.questions.order_by(
                "surveyquestion__order"
            )
        )

        writer.writerow(
            [
                "pk",
                "작성시간",
                *[question.title for question in questions],
            ]
        )

        for user_survey in user_surveys:
            reply_dict = {
                reply.survey_question.question_id: reply.content
                for reply in user_survey.replies.select_related(
                    "survey_question__question"
                )
            }

            writer.writerow(
                [
                    user_survey.pk,
                    user_survey.create_at.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                    *[
                        reply_dict.get(question.id, "")
                        for question in questions
                    ],
                ]
            )

        return response


# ============================================================
# User Survey Result List
# ============================================================

class UserSurveyListView(MyLoginRequiredMixin, ListView):
    """현재 로그인 사용자가 작성한 설문 결과 목록"""

    template_name = "survey/user_survey_list.html"
    paginate_by = 5

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        context["survey"] = Survey.objects.get(
            **self.kwargs
        )

        return context

    def get_queryset(self) -> QuerySet[UserSurvey]:
        survey = Survey.objects.get(
            **self.kwargs
        )

        queryset = UserSurvey.objects.filter(
            user=self.request.user,
            survey=survey,
        ).order_by("create_at")

        return queryset


# ============================================================
# Survey Form
# ============================================================

class SurveyFormView(MyLoginRequiredMixin, ProcessFormView):
    """설문조사 입력 및 저장"""

    def _create_replies(self, user_survey, post_data):
        """사용자가 입력한 설문 응답을 Reply 객체로 생성"""

        for key in post_data.keys():

            # csrfmiddlewaretoken,
            # other_text_x 등의 값은 제외
            if not key.isdigit():
                continue

            question = Question.objects.get(
                pk=int(key)
            )

            survey_question = SurveyQuestion.objects.get(
                survey=user_survey.survey,
                question=question,
            )

            answer_content_list = post_data.getlist(
                key
            )

            answer_content = None

            # ------------------------------------------------
            # 기타 옵션 처리
            # ------------------------------------------------

            if "other" in answer_content_list:
                other_text_key = f"other_text_{key}"
                other_text = post_data.get(
                    other_text_key
                )

                if other_text:
                    answer_content = other_text
                else:
                    answer_content = ""

            # ------------------------------------------------
            # 일반 답변 처리
            # ------------------------------------------------

            if answer_content is None or answer_content == "":
                answer_content = ",".join(
                    [
                        item
                        for item in answer_content_list
                        if item != "other"
                    ]
                )

            Reply.objects.create(
                user_survey=user_survey,
                survey_question=survey_question,
                content=answer_content,
            )

    # --------------------------------------------------------
    # GET
    # --------------------------------------------------------

    def get(self, request, *args, **kwargs):
        """설문 입력 화면"""

        survey = Survey.objects.get(
            pk=kwargs["pk"]
        )

        questions = SurveyQuestion.objects.filter(
            survey=survey
        ).order_by("order")

        context = {
            "object": survey,
            "survey_questions": questions,
        }

        return render(
            request,
            "survey/user_survey_form.html",
            context,
        )

    # --------------------------------------------------------
    # POST
    # --------------------------------------------------------

    def post(self, request, *args, **kwargs):
        """설문 제출 처리"""

        survey = Survey.objects.get(
            pk=kwargs["pk"]
        )

        # ----------------------------------------------------
        # UserSurvey 생성
        # ----------------------------------------------------

        user_survey = UserSurvey.objects.create(
            user=request.user,
            survey=survey,
        )

        # ----------------------------------------------------
        # 각 질문 답변 저장
        # ----------------------------------------------------

        self._create_replies(
            user_survey,
            request.POST,
        )

        # ----------------------------------------------------
        # 결과 기본값
        #
        # 중요:
        # 점수가 없는 설문에서도 아래 render에서
        # result_html 변수를 사용하므로 반드시 미리 선언해야 함.
        # ----------------------------------------------------

        total_score = None
        action_code = None
        result_html = None

        survey_name = user_survey.survey_name

        # ----------------------------------------------------
        # 점수 계산 대상 설문
        # ----------------------------------------------------

        is_stress_survey = (
            "임신스트레스 10문항"
            in survey_name
        )

        is_pbras_survey = (
            "조기진통위험 10문항"
            in survey_name
        )

        if is_stress_survey or is_pbras_survey:

            replies = Reply.objects.filter(
                user_survey=user_survey
            ).order_by(
                "survey_question__order"
            )

            scores = []

            # ------------------------------------------------
            # Answer.value를 이용하여 점수 계산
            # ------------------------------------------------

            for reply in replies:

                answer = Answer.objects.filter(
                    description=reply.content
                ).get()

                scores.append(
                    answer.value
                )

            # ------------------------------------------------
            # 총점
            # ------------------------------------------------

            total_score = sum(scores)

            user_survey.score = total_score
            user_survey.save()

            # ------------------------------------------------
            # 설문 종류별 결과 처리
            # ------------------------------------------------

            if is_stress_survey:
                result_data = utils.stress_result(
                    tuple(scores)
                )

            else:
                result_data = utils.pbras_result(
                    tuple(scores)
                )

            # 기존 코드에서는 여기서 무조건
            # stress_result()를 다시 호출하고 있었음.
            # 해당 코드는 삭제함.

            result_html = result_data.get(
                "html"
            )

            action_code = result_data.get(
                "action_code"
            )

            # ------------------------------------------------
            # 행동 수행 여부 저장
            # ------------------------------------------------

            ActionFeedback.objects.create(
                user_survey=user_survey,
                action_code=action_code,
                performed=False,
            )

        # ----------------------------------------------------
        # 설문 완료 페이지
        #
        # 점수 없는 설문:
        # result_html = None
        # action_code = None
        # total_score = None
        #
        # 따라서 정상적으로 완료 페이지를 보여줄 수 있음.
        # ----------------------------------------------------

        return render(
            request,
            "survey/survey_complete.html",
            {
                "result": result_html,
                "action_code": action_code,
                "action_message": utils.ACTION_MESSAGES.get(
                    action_code
                ),
                "user_survey_id": user_survey.id,
                "total_score": total_score,
            },
        )

    # --------------------------------------------------------
    # PUT
    # --------------------------------------------------------

    def put(self, request, *args, **kwargs):
        """작성된 설문 수정 화면"""

        return render(
            request,
            "survey/survey_complete.html",
        )


# ============================================================
# XLSX Download
# ============================================================

class XlsxDownloadView(SuperuserRequiredMixin, View):

    def _create_workbook(
        self,
        user_surveys: QuerySet,
        user,
    ):
        wb = Workbook()
        ws = wb.active

        # ----------------------------------------------------
        # 대상정보 시트
        # ----------------------------------------------------

        ws.title = "대상정보"

        ws.append(
            [
                "이름",
                "ID",
            ]
        )

        # ----------------------------------------------------
        # 이름 결정
        #
        # Huami → Fitbit → username
        #
        # Google Health 사용자처럼 Huami/Fitbit relation이
        # 없는 경우 username 사용
        # ----------------------------------------------------

        if (
            hasattr(user, "huami")
            and user.huami
            and user.huami.fullname
        ):
            name = user.huami.fullname

        elif (
            hasattr(user, "fitbit")
            and user.fitbit
            and user.fitbit.full_name
        ):
            name = user.fitbit.full_name

        else:
            name = user.username

        ws.append(
            [
                name,
                user.username,
            ]
        )

        # ----------------------------------------------------
        # 설문별 점수 라벨
        # ----------------------------------------------------

        def score_label(title: str):

            if "임신스트레스 10문항" in title:
                return "스트레스 점수"

            if "조기진통위험 10문항" in title:
                return "조기진통 점수"

            if "QUIPP" in title:
                return "QUIPP 점수"

            return None

        # ----------------------------------------------------
        # Excel 시트명
        # ----------------------------------------------------

        def sheet_name_from(title: str):

            match = re.search(
                r"\[.*?\]\s*(.*)",
                title,
            )

            return (
                match.group(1)
                if match
                else title
            )

        # ----------------------------------------------------
        # 질문 제목
        # ----------------------------------------------------

        def question_titles(survey):

            qs = survey.questions.all()

            try:
                qs = qs.order_by(
                    "order"
                )

            except FieldError:
                qs = qs.order_by(
                    "id"
                )

            return list(
                qs.values_list(
                    "title",
                    flat=True,
                )
            )

        # ----------------------------------------------------
        # 설문 결과 작성
        # ----------------------------------------------------

        for user_survey in user_surveys:

            survey = user_survey.survey

            sheet_name = sheet_name_from(
                survey.title
            )

            titles = question_titles(
                survey
            )

            score_column_label = score_label(
                survey.title
            )

            # ------------------------------------------------
            # 시트가 없다면 생성
            # ------------------------------------------------

            if sheet_name not in wb.sheetnames:

                ws = wb.create_sheet(
                    title=sheet_name
                )

                header = [
                    "작성시간",
                    *titles,
                ]

                if score_column_label:
                    header.append(
                        score_column_label
                    )

                ws.append(
                    header
                )

            else:
                ws = wb[
                    sheet_name
                ]

            # ------------------------------------------------
            # 응답 매핑
            # ------------------------------------------------

            reply_dict = {
                reply.survey_question.question.title:
                    reply.content

                for reply
                in user_survey.replies.all()
            }

            created_at = timezone.localtime(
                user_survey.create_at
            ).replace(
                tzinfo=None
            )

            row = [
                created_at,
                *[
                    reply_dict.get(
                        title,
                        "",
                    )
                    for title
                    in titles
                ],
            ]

            if score_column_label:
                row.append(
                    user_survey.score
                )

            ws.append(
                row
            )

        return wb

    def get(
        self,
        request,
        user_id,
    ):

        user_surveys = UserSurvey.objects.filter(
            user_id=user_id
        ).order_by(
            "survey_id",
            "create_at",
        )

        user = get_user_model().objects.get(
            pk=user_id
        )

        wb = self._create_workbook(
            user_surveys,
            user,
        )

        with NamedTemporaryFile(
            suffix=".xlsx"
        ) as tmp:

            wb.save(
                tmp.name
            )

            tmp.seek(0)

            stream = tmp.read()

        # ----------------------------------------------------
        # 파일 이름
        # ----------------------------------------------------

        if (
            hasattr(user, "huami")
            and user.huami
            and user.huami.fullname
        ):
            name = user.huami.fullname

        elif (
            hasattr(user, "fitbit")
            and user.fitbit
            and user.fitbit.full_name
        ):
            name = user.fitbit.full_name

        else:
            name = user.username

        filename = urllib.parse.quote(
            f"{name} 설문결과"
        )

        response = HttpResponse(
            content=stream,
            content_type=(
                "application/vnd.openxmlformats-"
                "officedocument.spreadsheetml.sheet"
            ),
        )

        response["Content-Disposition"] = (
            f'attachment; filename="{filename}.xlsx"'
        )

        return response


# ============================================================
# Action Feedback
# ============================================================

@require_POST
@login_required
def update_action_feedback(request):
    """설문 완료 후 행동요령 수행 여부 저장"""

    data = json.loads(
        request.body
    )

    performed = data.get(
        "performed"
    )

    user_survey_id = data.get(
        "user_survey_id"
    )

    action_feedback = ActionFeedback.objects.get(
        user_survey_id=user_survey_id,
        user_survey__user=request.user,
    )

    action_feedback.performed = performed
    action_feedback.save()

    return JsonResponse(
        {
            "status": "ok"
        }
    )