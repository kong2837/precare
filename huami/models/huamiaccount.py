from datetime import datetime

from django.db import models
from django.conf import settings
from requests import HTTPError

from huami.utils import HuamiAmazfit

default_sny_date = datetime(1970, 1, 1)

class HuamiAccount(models.Model):
    """HuamiAccount 모델 클래스
    """    
    user = models.OneToOneField(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column="user_id",
        db_comment="user id",
        null=False,
        blank=False,
        help_text="유저 id",
        related_name="huami",
    )
    email = models.EmailField(
        db_column="email",
        db_comment="huami account email address",
        null=False,
        blank=False,
        unique=True,
        help_text="화웨이 계정 이메일"
    )
    password = models.CharField(
        db_column="password",
        db_comment="huami account password address",
        max_length=100,
        null=False,
        blank=False,
        help_text="화웨이 계정 패스워드"
    )
    sync_date = models.DateTimeField(
        db_column="sync_date",
        db_comment="huami account sync date",
        null=False,
        blank=False,
        help_text="화웨이 계정 동기화 날짜",
        default=default_sny_date,
    )
    note = models.TextField(
        db_column="note",
        db_comment="information of user",
        null=True,
        blank=True,
        help_text="사용자에 대한 간략한 설명",
        default="정보를 입력해주세요."
    )
    
    @property
    def full_name(self) -> str:
        return f"{self.user.last_name} {self.user.first_name}"
    
    @property
    def last_health_info(self):
        return self.health.last()

    def __str__(self) -> str:
        """HuamiAccount 인스턴스 출력 메서드

        Returns:
            str: Huami 계정 이메일
        """        
        return self.email

    class Meta:
        db_table = "huami_account"
        verbose_name = "화웨이 계정"
        verbose_name_plural = "화웨이 계정"
        ordering = ["email", "sync_date"]

    def reset_sync_date(self) -> None:
        """동기화 시간 초기화
        """        
        self.sync_date = default_sny_date
        self.save()
        
    def get_data(self) -> dict:
        """현재 계정 정보로 데이터 수집

        Raises:
            HTTPError: 처리 과정 중 오류

        Returns:
            dict: 심박수, 스트레스, 걸음 수, 수면 질, SPO2, 무게, 키 에 대한 정보
        """        
        result = {}
        account = HuamiAmazfit(email=self.email, password=self.password)
        try:
            account.access()
            account.login()
            result['profile'] = account.profile()            
            result['band'] = account.band_data('2023-01-01', datetime.now().strftime('%Y-%m-%d'))
            result['stress'] = account.stress('2023-01-01', datetime.now().strftime('%Y-%m-%d'))
            result['blood'] = account.blood_oxygen('2023-01-01',datetime.now().strftime('%Y-%m-%d'))
            account.logout()
        except HTTPError as e:
            raise HTTPError("데이터를 받아오는 과정에서 오류가 발생하였습니다. 오류내용: "+e)
        self.sync_date = datetime.now()
        self.save()
        
        return result


# Create your models here.
