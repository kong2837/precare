from django.db import models
from django.conf import settings

# Create your models here.
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

"""인증번호 저장을 위한 profile model 생성
    """
class Profile(models.Model):
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    verification_code = models.CharField(max_length=8, blank=True, null=True)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()
    
# 사용 로그 저장 모델
class UserClickLog(models.Model):
    LOG_TYPE_CHOICES = (
        ("survey_click", "설문조사 클릭"),
        ("mother_fetus_info_click", "산모 및 태아 정보 클릭"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="click_logs"
    )

    log_type = models.CharField(max_length=50, choices=LOG_TYPE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]