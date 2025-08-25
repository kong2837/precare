from django.db import models
from django.conf import settings


class FitbitAccount(models.Model):
    
    RESEARCH_STATUS_CHOICES = (
        ('preparing', '준비'),
        ('ongoing', '진행 중'),
        ('completed', '완료'),
    )

    RESEARCH_YEAR_CHOICES = (
        ('none', '미확인'),
        ('2023', '2023'),
        ('2024', '2024'),
        ('2025', '2025'),
    )
    
    user = models.OneToOneField(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='fitbit',
        help_text="이 계정과 연결된 유저"
    )

    fitbit_user_id = models.CharField(
        max_length=128,
        unique=True,
        help_text="Fitbit에서 받은 고유 사용자 ID"
    )

    access_token = models.TextField(
        help_text="Fitbit API 접근용 액세스 토큰"
    )

    refresh_token = models.TextField(
        help_text="액세스 토큰 갱신용 리프레시 토큰"
    )

    expires_at = models.DateTimeField( #yyyy-mm-dd 형식의 string
        help_text="액세스 토큰 만료 시간"
    )

    scope = models.TextField(
        help_text="발급받은 권한 범위"
    )

    token_type = models.CharField(
        max_length=20,
        default='Bearer',
        help_text="토큰 타입 (보통 Bearer)"
    )

    full_name = models.CharField(
        max_length=100,
        null=True,
        help_text="Fitbit 프로필에서 가져온 이름"
    )

    gender = models.CharField(
        max_length=10,
        null=True,
        help_text="성별 (male/female/NA 등)"
    )

    birthday = models.DateField( #yyyy-mm-dd 형식의 string
        null=True,
        help_text="생년월일"
    )

    height = models.FloatField(
        null=True,
        help_text="신장 (cm 또는 m 단위, Fitbit API 단위에 따라 조정)"
    )

    weight = models.FloatField(
        null=True,
        help_text="몸무게 (kg)"
    )

    last_synced = models.DateTimeField( #yyyy-mm-dd 형식의 string
        null=True,
        help_text="마지막 데이터 동기화 시간"
    )
    
    pregnancy_start_date = models.DateTimeField( #yyyy-mm-dd 형식의 string
        db_column="pregnancy_start_date",
        db_comment="임신 시작일",
        null=True,
        blank=True,
        help_text="임신 시작일을 입력해주세요"
    )

    research_status = models.CharField(
        db_column="research_status",
        max_length=10,
        choices=RESEARCH_STATUS_CHOICES,
        default='preparing',  # 기본값 설정
    )

    research_year = models.CharField(
        db_column="research_year",
        max_length=6,
        choices=RESEARCH_YEAR_CHOICES,
        default='none',
    )
    
    join_date = models.DateTimeField(
        db_column="join_date",
        null=True,
        help_text="연구 시작일"
    )
    
    end_date = models.DateTimeField(
        db_column="end_date",
        null=True,
        help_text="연구 종료일"
    )
 
    note = models.TextField(
        db_column="note",
        db_comment="information of user",
        null=True,
        blank=True,
        help_text="사용자에 대한 간략한 설명",
        default="정보를 입력해주세요."
    )

    def __str__(self):
        return f"{self.user.username} - FitbitAccount"

    class Meta:
        verbose_name = "핏빗 계정"
        verbose_name_plural = "핏빗 계정"
