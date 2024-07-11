from django.db import models
from django.conf import settings

""" Status에 관련된 model 생성
"""
class Status(models.Model):
    memo = models.CharField(
        db_column='memo',
        db_comment='memo of status',
        max_length=100,
        null=False,
        blank=False,
        help_text='상태 입력 내용입니다.'
    )

    start_datetime = models.DateTimeField(
        db_column='start_datetime',
        db_comment='status start datetime',

        null=False,
        help_text='상태 변화 시작한 시간과 날짜입니다.'
    )

    # end_datetime = models.DateTimeField(
    #         db_column='end_datetime',
    #         db_comment='status end datetime',
    #         null=False,
    #         help_text='상태 변화 끝난 시간과 날짜입니다.'
    #     )

    user = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='user_id',
        db_comment='user id',
        null=False,
        blank=False,
        help_text='유저 id',
    )




# Create your models here.
