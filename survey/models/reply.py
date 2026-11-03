from django.db import models


class Reply(models.Model):
    """Reply 모델 클래스
    UserSurvey와 SurveyQuestion에 대한 유저 응답
    """    
    user_survey = models.ForeignKey("UserSurvey", on_delete=models.CASCADE, related_name="replies")
    survey_question = models.ForeignKey("SurveyQuestion", on_delete=models.CASCADE, related_name="replies")
    content = models.CharField(
        db_column="content",
        db_comment="reply to question",
        null=False,
        blank=True,
        help_text="답변",
        max_length=255,
    )
    score = models.IntegerField(
        null=True,
        blank=True,
        help_text="제출 당시 선택한 응답의 점수",
    )

    @property
    def title(self) -> str:
        return self.survey_question.question.title

    @property
    def order(self) -> int:
        return self.survey_question.order

    class Meta:
        db_table = "reply"
        verbose_name = "답변"
        verbose_name_plural = "답변"
        ordering = ["user_survey"]


