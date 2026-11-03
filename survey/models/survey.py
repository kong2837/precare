from django.db import models
from django.conf import settings


class Survey(models.Model):
    """Survey 모델 클래스
    설문에 대한 정보
    """    
    title = models.CharField(
        db_column="title",
        db_comment="survey title",
        null=False,
        blank=False,
        help_text="설문지 제목",
        max_length=40
    )
    description = models.TextField(
        db_column="description",
        db_comment="survey description",
        null=False,
        blank=False,
        help_text="설문지 설명",
        max_length=100
    )
    created_at = models.DateTimeField(
        db_column="created_at",
        db_comment="survey created time",
        auto_now_add=True,
        help_text="설문지 생성 시간"
    )
    updated_at = models.DateTimeField(
        db_column="updated_at",
        db_comment="survey updated time",
        auto_now=True,
        help_text="설문지 수정 시간"
    )
    questions = models.ManyToManyField(
        to="Question",
        through="SurveyQuestion",
        related_name="surveys",
    )
    users = models.ManyToManyField(
        to=settings.AUTH_USER_MODEL,
        through="UserSurvey",
        related_name="surveys",
    )

    def __str__(self) -> str:
        """Survey 인스턴스 출력 메서드

        Returns:
            str: Survey 제목
        """        
        return self.title

    @property
    def is_postpartum(self):
        from survey.scoring import is_epds
        return is_epds(self.title)

    class Meta:
        db_table = "survey"
        verbose_name = "설문조사"
        verbose_name_plural = "설문조사"
        ordering = ["title", "created_at"]
