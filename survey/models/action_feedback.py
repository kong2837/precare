from django.db import models

class ActionFeedback(models.Model):
    """
    설문 결과 행동 수행 여부
    """
    user_survey = models.OneToOneField(
        to='UserSurvey',
        on_delete=models.CASCADE,
        related_name='action_feedback',
        db_comment='user survey id'
    )

    action_code = models.CharField(
        max_length=50,
        help_text='행동 코드 (DRINK_WATER, BED_REST 등)'
    )

    performed = models.BooleanField(
        null=True,
        help_text='행동 수행 여부 (예/아니오)'
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='행동 기록 생성 시간'
    )

    class Meta:
        db_table = 'action_feedback'
        verbose_name = '행동 수행 여부'
        verbose_name_plural = '행동 수행 여부'
