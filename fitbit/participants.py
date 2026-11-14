"""Fitbit account reuse: source credentials and time-bound system users."""
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Max
from django.utils import timezone

from fitbit.models import FitbitAccount, FitbitMinuteMetric


def source_for(account):
    return account.source_account_id or account.pk


def participants(source):
    root_id = source_for(source)
    return FitbitAccount.objects.filter(Q(pk=root_id) | Q(source_account_id=root_id))


def participant_at(source, measured_at, lock=False):
    if timezone.is_naive(measured_at):
        measured_at = timezone.make_aware(measured_at, ZoneInfo("Asia/Seoul"))
    queryset = participants(source)
    if lock:
        queryset = queryset.select_for_update()
    return queryset.filter(
        Q(participant_started_at__isnull=True) | Q(participant_started_at__lte=measured_at),
    ).filter(
        Q(participant_ended_at__isnull=True) | Q(participant_ended_at__gt=measured_at),
    ).get()


def active_participant(account):
    return participants(account).get(participant_ended_at__isnull=True)


@transaction.atomic
def replace_participant(account_id, name, boundary, actor, expected_name=None):
    from accounts.models import UserClickLog
    from survey.models import UserSurvey
    from fitbit.models.account import ParticipantReplacement

    initial = FitbitAccount.objects.get(pk=account_id)
    source = FitbitAccount.objects.select_for_update().get(pk=source_for(initial))
    old = participants(source).select_for_update().get(pk=account_id)
    if expected_name is not None and old.full_name != expected_name:
        raise ValidationError("기존 이름이 변경되었습니다. 다시 확인해주세요.")
    if old.participant_ended_at is not None:
        raise ValidationError("이미 교체된 참여자입니다. 목록을 새로고침해주세요.")
    if old.user.is_staff or old.user.is_superuser or hasattr(old.user, "huami"):
        raise ValidationError("Fitbit 전용 일반 참여자만 교체할 수 있습니다.")
    if not name or len(name) > 100 or any(ord(c) < 32 or ord(c) == 127 for c in name):
        raise ValidationError("이름은 줄바꿈 없이 1~100자로 입력해주세요.")
    if boundary.second or boundary.microsecond:
        raise ValidationError("교체 일시는 분 단위로 입력해주세요.")
    if boundary > timezone.now():
        raise ValidationError("교체 일시는 현재보다 미래일 수 없습니다.")
    if old.participant_started_at and boundary <= old.participant_started_at:
        raise ValidationError("교체 일시는 이전 교체 일시보다 늦어야 합니다.")

    user = get_user_model().objects.create_user(
        username="fitbit_participant_" + uuid4().hex, first_name=name,
        email=old.user.email,
    )
    new = FitbitAccount.objects.create(
        user=user, fitbit_user_id=source.fitbit_user_id, source_account=source,
        participant_started_at=boundary, full_name=name, join_date=boundary,
        access_token=source.access_token, refresh_token=source.refresh_token,
        expires_at=source.expires_at, scope=source.scope, token_type=source.token_type,
    )
    old.participant_ended_at = boundary
    old.save(update_fields=["participant_ended_at"])
    FitbitMinuteMetric.objects.filter(account=old, timestamp__gte=boundary).update(account=new)
    UserSurvey.objects.filter(user=old.user, create_at__gte=boundary).update(user=user)
    UserClickLog.objects.filter(user=old.user, created_at__gte=boundary).update(user=user)
    for item in (old, new):
        item.last_synced = item.minute_metrics.filter(heart_rate__isnull=False).aggregate(latest=Max("timestamp"))["latest"]
        item.save(update_fields=["last_synced"])
    ParticipantReplacement.objects.create(
        previous=old, replacement=new, effective_at=boundary,
        changed_by=actor, previous_name=old.full_name or old.user.username,
        replacement_name=name,
    )
    return new


def save_for_participant(instance, save, *args, **kwargs):
    """Route new survey/log writes even if a request began before replacement."""
    if not instance._state.adding or not instance.user_id:
        return save(*args, **kwargs)
    account = FitbitAccount.objects.filter(user_id=instance.user_id).first()
    if account is None or hasattr(account.user, "huami"):
        return save(*args, **kwargs)
    with transaction.atomic():
        source = FitbitAccount.objects.select_for_update().get(pk=source_for(account))
        instance.user = participant_at(source, timezone.now(), lock=True).user
        return save(*args, **kwargs)
