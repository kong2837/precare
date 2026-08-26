import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.http import HttpResponse
from django.test import SimpleTestCase, RequestFactory

from survey import utils
from survey.models import Answer
from survey.views import SurveyFormView, update_action_feedback


# ============================================================
# Utility 함수 테스트
# ============================================================

class StressResultTests(SimpleTestCase):
    """
    임신스트레스 점수 → 결과 코멘트 / action_code 테스트
    """

    def test_score_below_6(self):
        result = utils.stress_result(
            (0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        )

        self.assertIsNone(result["action_code"])

        self.assertIn(
            "스트레스 점수가 낮습니다",
            result["html"],
        )

    def test_score_6(self):
        result = utils.stress_result(
            (6, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        )

        self.assertEqual(
            result["action_code"],
            "SIT_AND_BREATH",
        )

        self.assertIn(
            "하던 일을 멈추고",
            result["html"],
        )

    def test_score_9(self):
        result = utils.stress_result(
            (9, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        )

        self.assertEqual(
            result["action_code"],
            "SIT_AND_BREATH",
        )

        self.assertIn(
            "하던 일을 멈추고",
            result["html"],
        )

    def test_score_10(self):
        result = utils.stress_result(
            (10, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        )

        self.assertEqual(
            result["action_code"],
            "SIT_AND_BREATH",
        )

        self.assertIn(
            "오늘 힘드셨군요",
            result["html"],
        )

    def test_score_15(self):
        result = utils.stress_result(
            (15, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        )

        self.assertEqual(
            result["action_code"],
            "SIT_AND_BREATH",
        )

        self.assertIn(
            "오늘 힘드셨군요",
            result["html"],
        )

    def test_score_16(self):
        result = utils.stress_result(
            (16, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        )

        self.assertEqual(
            result["action_code"],
            "MUSIC",
        )

        self.assertIn(
            "음악",
            result["html"],
        )

    def test_high_score(self):
        result = utils.stress_result(
            (30, 0, 0, 0, 0, 0, 0, 0, 0, 0)
        )

        self.assertEqual(
            result["action_code"],
            "MUSIC",
        )

        self.assertIn(
            "음악",
            result["html"],
        )


# ============================================================
# 조기진통위험 결과 테스트
# ============================================================

class PbrasResultTests(SimpleTestCase):
    """
    조기진통위험 10문항의 각 조건별
    코멘트/action_code 테스트
    """

    def test_no_risk(self):
        scores = (
            0, 0, 0, 0, 0,
            0, 0, 0, 0, 0,
        )

        result = utils.pbras_result(scores)

        self.assertIsNone(
            result["action_code"]
        )

        self.assertIn(
            "지금처럼",
            result["html"],
        )

    def test_mon1_score_3_or_more(self):
        # mon1 = scores[0] + scores[1] + scores[6]
        scores = (
            1, 1,
            0, 0,
            0, 0,
            1,
            0,
            0, 0,
        )

        result = utils.pbras_result(scores)

        self.assertEqual(
            result["action_code"],
            "BED_REST",
        )

        self.assertIn(
            "증상이 계속되면",
            result["html"],
        )

    def test_mon1_score_2(self):
        scores = (
            1, 1,
            0, 0,
            0, 0,
            0,
            0,
            0, 0,
        )

        result = utils.pbras_result(scores)

        self.assertEqual(
            result["action_code"],
            "BED_REST",
        )

        self.assertIn(
            "침상에 누워",
            result["html"],
        )

    def test_mon2_score_2_or_more(self):
        # mon2 = scores[2] + scores[3] + scores[7]
        scores = (
            0, 0,
            1, 1,
            0, 0,
            0,
            0,
            0, 0,
        )

        result = utils.pbras_result(scores)

        self.assertEqual(
            result["action_code"],
            "DRINK_WATER",
        )

        self.assertIn(
            "물을 한잔",
            result["html"],
        )

    def test_mon3_score_3_or_more(self):
        # mon3 = scores[4] + scores[5]
        scores = (
            0, 0,
            0, 0,
            2, 1,
            0,
            0,
            0, 0,
        )

        result = utils.pbras_result(scores)

        self.assertEqual(
            result["action_code"],
            "DRINK_WATER_OFTEN",
        )

        self.assertIn(
            "틈틈이",
            result["html"],
        )

    def test_mon4_score_3_or_more(self):
        # mon4 = scores[8] + scores[9]
        scores = (
            0, 0,
            0, 0,
            0, 0,
            0,
            0,
            2, 1,
        )

        result = utils.pbras_result(scores)

        self.assertEqual(
            result["action_code"],
            "SIT_AND_DRINK_WATER",
        )

        self.assertIn(
            "심호흡",
            result["html"],
        )

    def test_mon4_score_2(self):
        scores = (
            0, 0,
            0, 0,
            0, 0,
            0,
            0,
            1, 1,
        )

        result = utils.pbras_result(scores)

        self.assertEqual(
            result["action_code"],
            "MUSIC",
        )

        self.assertIn(
            "음악",
            result["html"],
        )

    def test_priority_mon1_over_other_groups(self):
        """
        여러 조건을 동시에 만족하면
        코드상 가장 먼저 검사하는 mon1이 우선되어야 함.
        """

        scores = (
            1, 1,
            0, 0,
            0, 0,
            1,
            0,
            2, 2,
        )

        result = utils.pbras_result(scores)

        self.assertEqual(
            result["action_code"],
            "BED_REST",
        )

        self.assertIn(
            "증상이 계속되면",
            result["html"],
        )


# ============================================================
# ACTION_MESSAGES 연결 테스트
# ============================================================

class ActionMessageTests(SimpleTestCase):

    def test_all_used_action_codes_have_message(self):
        action_codes = [
            "BED_REST",
            "DRINK_WATER",
            "DRINK_WATER_OFTEN",
            "SIT_AND_BREATH",
            "SIT_AND_DRINK_WATER",
            "MUSIC",
        ]

        for action_code in action_codes:

            with self.subTest(
                action_code=action_code
            ):

                self.assertIn(
                    action_code,
                    utils.ACTION_MESSAGES,
                )

                self.assertTrue(
                    utils.ACTION_MESSAGES[action_code]
                )


# ============================================================
# SurveyFormView 테스트
# ============================================================

class SurveyFormViewTests(SimpleTestCase):

    def setUp(self):

        self.factory = RequestFactory()

        self.user = SimpleNamespace(
            id=1,
            pk=1,
            username="test-user",
            is_authenticated=True,
        )

    def _run_post(
        self,
        survey_name,
        scores,
        survey_id=999,
    ):
        """
        실제 DB를 건드리지 않고 SurveyFormView.post()를 실행한다.

        scores:
            각 Reply에 대응되는 Answer.value
        """

        survey = SimpleNamespace(
            id=survey_id,
            pk=survey_id,
            title=survey_name,
        )

        user_survey = MagicMock()

        user_survey.id = 100
        user_survey.pk = 100

        user_survey.survey = survey
        user_survey.survey_name = survey_name

        user_survey.score = None

        # ---------------------------------------------
        # Reply mock 생성
        #
        # question.answers.get() 방식과
        # 기존 Answer.objects.filter() 방식 모두
        # 테스트할 수 있도록 구성
        # ---------------------------------------------

        replies = []

        score_map = {}

        for index, score in enumerate(scores):

            content = f"answer-{index}"

            score_map[content] = score

            question = MagicMock()

            question.answers.get.return_value = (
                SimpleNamespace(
                    value=score
                )
            )

            survey_question = SimpleNamespace(
                question=question,
                order=index + 1,
            )

            reply = SimpleNamespace(
                content=content,
                survey_question=survey_question,
            )

            replies.append(reply)

        reply_queryset = MagicMock()

        reply_queryset.order_by.return_value = replies

        def answer_filter_side_effect(**kwargs):

            content = kwargs.get(
                "description"
            )

            queryset = MagicMock()

            queryset.get.return_value = (
                SimpleNamespace(
                    value=score_map[content]
                )
            )

            return queryset

        request = self.factory.post(
            f"/survey/{survey_id}",
            data={},
        )

        request.user = self.user

        view = SurveyFormView()

        with patch(
            "survey.views.Survey.objects.get",
            return_value=survey,
        ), patch(
            "survey.views.UserSurvey.objects.create",
            return_value=user_survey,
        ), patch(
            "survey.views.Reply.objects.filter",
            return_value=reply_queryset,
        ) as mock_reply_filter, patch(
            "survey.views.Answer.objects.filter",
            side_effect=answer_filter_side_effect,
        ) as mock_answer_filter, patch(
            "survey.views.ActionFeedback.objects.create"
        ) as mock_feedback_create, patch(
            "survey.views.render",
            return_value=HttpResponse(
                "OK",
                status=200,
            ),
        ) as mock_render, patch.object(
            view,
            "_create_replies",
        ) as mock_create_replies:

            response = view.post(
                request,
                pk=survey_id,
            )

        context = (
            mock_render.call_args.args[2]
        )

        return {
            "response": response,
            "context": context,
            "user_survey": user_survey,
            "reply_filter": mock_reply_filter,
            "answer_filter": mock_answer_filter,
            "feedback_create": mock_feedback_create,
            "create_replies": mock_create_replies,
        }

    # --------------------------------------------------------
    # 일반 설문
    # --------------------------------------------------------

    def test_non_scored_survey_returns_200(self):

        result = self._run_post(
            "[연구시작시]연구 참여자 기초 건강 설문",
            scores=[],
            survey_id=6,
        )

        self.assertEqual(
            result["response"].status_code,
            200,
        )

        self.assertIsNone(
            result["context"]["result"]
        )

        self.assertIsNone(
            result["context"]["action_code"]
        )

        self.assertIsNone(
            result["context"]["total_score"]
        )

        result[
            "feedback_create"
        ].assert_not_called()

    # --------------------------------------------------------
    # 임신스트레스 낮은 점수
    # --------------------------------------------------------

    def test_low_stress_score_does_not_create_action_feedback(self):
        """
        매우 중요.

        stress_result()에서 action_code=None이면
        ActionFeedback을 만들면 안 된다.

        현재 ActionFeedback.action_code는 null=False이므로
        None으로 INSERT하면 실제 DB에서 500이 날 수 있다.
        """

        result = self._run_post(
            "[상시]임신스트레스 10문항",
            scores=[
                0, 0, 0, 0, 0,
                0, 0, 0, 0, 0,
            ],
            survey_id=4,
        )

        self.assertEqual(
            result["response"].status_code,
            200,
        )

        self.assertEqual(
            result["context"]["total_score"],
            0,
        )

        self.assertIsNone(
            result["context"]["action_code"]
        )

        self.assertIn(
            "스트레스 점수가 낮습니다",
            result["context"]["result"],
        )

        # action_code=None이면
        # Feedback row를 만들지 않는 것이 정상
        result[
            "feedback_create"
        ].assert_not_called()

    # --------------------------------------------------------
    # 스트레스 점수와 코멘트 일치
    # --------------------------------------------------------

    def test_stress_score_and_comment_match(self):

        result = self._run_post(
            "[상시]임신스트레스 10문항",
            scores=[
                2, 2, 2, 2, 2,
                2, 2, 2, 0, 0,
            ],
            survey_id=4,
        )

        # 총점 16
        self.assertEqual(
            result["context"]["total_score"],
            16,
        )

        self.assertEqual(
            result["context"]["action_code"],
            "MUSIC",
        )

        self.assertIn(
            "음악",
            result["context"]["result"],
        )

        self.assertEqual(
            result["context"]["action_message"],
            utils.ACTION_MESSAGES["MUSIC"],
        )

        self.assertEqual(
            result["user_survey"].score,
            16,
        )

        result[
            "user_survey"
        ].save.assert_called()

    # --------------------------------------------------------
    # 조기진통 결과가 stress_result로 덮어써지지 않는지
    # --------------------------------------------------------

    def test_pbras_result_is_not_overwritten_by_stress_result(self):
        """
        기존 views.py에는 pbras_result() 실행 후
        다시 stress_result()를 호출하는 버그가 있었음.

        이 테스트는 그 문제가 다시 생기지 않게 한다.
        """

        # mon2 = 1 + 1 + 0 = 2
        # 기대 결과 = DRINK_WATER
        scores = [
            0, 0,
            1, 1,
            0, 0,
            0,
            0,
            0, 0,
        ]

        result = self._run_post(
            "[상시]조기진통위험 10문항",
            scores=scores,
            survey_id=5,
        )

        self.assertEqual(
            result["context"]["total_score"],
            2,
        )

        self.assertEqual(
            result["context"]["action_code"],
            "DRINK_WATER",
        )

        self.assertIn(
            "물을 한잔",
            result["context"]["result"],
        )

        self.assertEqual(
            result["context"]["action_message"],
            utils.ACTION_MESSAGES[
                "DRINK_WATER"
            ],
        )

    # --------------------------------------------------------
    # 같은 답변 문구가 여러 질문에 있어도 안전해야 함
    # --------------------------------------------------------

    def test_answer_lookup_is_scoped_to_question(self):
        """
        '전혀 없음' 같은 description이 여러 Answer에 존재해도
        현재 질문에 연결된 Answer만 조회해야 한다.

        올바른 코드 예:

            reply.survey_question.question.answers.get(
                description=reply.content
            )

        기존 코드:

            Answer.objects.filter(
                description=reply.content
            ).get()

        는 MultipleObjectsReturned 위험이 있음.
        """

        survey = SimpleNamespace(
            id=5,
            pk=5,
            title="[상시]조기진통위험 10문항",
        )

        user_survey = MagicMock()

        user_survey.id = 100
        user_survey.pk = 100
        user_survey.survey = survey
        user_survey.survey_name = survey.title

        replies = []

        for index in range(10):

            question = MagicMock()

            question.answers.get.return_value = (
                SimpleNamespace(
                    value=0
                )
            )

            survey_question = SimpleNamespace(
                question=question,
                order=index + 1,
            )

            replies.append(
                SimpleNamespace(
                    content="전혀 없음",
                    survey_question=survey_question,
                )
            )

        reply_queryset = MagicMock()

        reply_queryset.order_by.return_value = replies

        request = self.factory.post(
            "/survey/5",
            data={},
        )

        request.user = self.user

        view = SurveyFormView()

        with patch(
            "survey.views.Survey.objects.get",
            return_value=survey,
        ), patch(
            "survey.views.UserSurvey.objects.create",
            return_value=user_survey,
        ), patch(
            "survey.views.Reply.objects.filter",
            return_value=reply_queryset,
        ), patch(
            "survey.views.Answer.objects.filter",
            side_effect=Answer.MultipleObjectsReturned(
                "같은 description의 Answer가 여러 개 존재함"
            ),
        ), patch(
            "survey.views.ActionFeedback.objects.create"
        ), patch(
            "survey.views.render",
            return_value=HttpResponse(
                "OK",
                status=200,
            ),
        ), patch.object(
            view,
            "_create_replies",
        ):

            # 질문에 연결된 Answer를 조회하는 코드라면
            # Answer.objects.filter() 자체를 호출하지 않으므로
            # 여기서 정상적으로 200이 나와야 한다.
            response = view.post(
                request,
                pk=5,
            )

        self.assertEqual(
            response.status_code,
            200,
        )


# ============================================================
# ActionFeedback API
# ============================================================

class ActionFeedbackViewTests(SimpleTestCase):

    def setUp(self):

        self.factory = RequestFactory()

        self.user = SimpleNamespace(
            id=1,
            pk=1,
            username="test-user",
            is_authenticated=True,
        )

    def test_update_action_feedback(self):

        request = self.factory.post(
            "/survey/update-action-feedback/",
            data=json.dumps(
                {
                    "performed": True,
                    "user_survey_id": 123,
                }
            ),
            content_type="application/json",
        )

        request.user = self.user

        action_feedback = MagicMock()

        with patch(
            "survey.views.ActionFeedback.objects.get",
            return_value=action_feedback,
        ) as mock_get:

            response = update_action_feedback(
                request
            )

        self.assertEqual(
            response.status_code,
            200,
        )

        mock_get.assert_called_once_with(
            user_survey_id=123,
            user_survey__user=self.user,
        )

        self.assertTrue(
            action_feedback.performed
        )

        action_feedback.save.assert_called_once()