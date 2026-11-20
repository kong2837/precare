"""Fill missing SpO2 measurements for one participant, within their enrollment."""
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from fitbit.google_health.daily_data.spo2 import (
    KST, SpO2FetchError, fetch_spo2, spo2_minutes_for_date,
)
from fitbit.models import FitbitAccount, FitbitMinuteMetric


def as_kst(value):
    return value.replace(tzinfo=KST) if timezone.is_naive(value) else value.astimezone(KST)


def backfill_bounds(participant, start_date, end_date, now):
    """Keep old wearers' measurements outside this participant's recovery range."""
    starts = [as_kst(participant[key]) for key in ("join_date", "participant_started_at")
              if participant.get(key) is not None]
    if start_date is not None:
        starts.append(datetime.combine(start_date, datetime.min.time(), tzinfo=KST))
    if not starts:
        raise CommandError("참여 시작일이 없습니다. 확인된 시작일을 --start-date로 지정하세요.")
    ends = [as_kst(now), datetime.combine(end_date + timedelta(days=1), datetime.min.time(), tzinfo=KST)]
    ends.extend(as_kst(participant[key]) for key in ("end_date", "participant_ended_at")
                if participant.get(key) is not None)
    return max(starts), min(ends)


def fill_missing_minutes(account_id, minutes):
    """Never overwrite an existing value or change another sensor's field."""
    manager = FitbitMinuteMetric._base_manager
    created = filled = 0
    for timestamp, value in sorted(minutes.items()):
        obj, is_new = manager.get_or_create(
            account_id=account_id, timestamp=timestamp, defaults={"spo2": value},
        )
        if is_new:
            created += 1
        elif obj.spo2 is None:
            filled += manager.filter(pk=obj.pk, spo2__isnull=True).update(spo2=value)
    present = manager.filter(
        account_id=account_id, timestamp__in=minutes, spo2__isnull=False,
    ).count()
    if present != len(minutes):
        raise CommandError("저장 후 SpO₂ 검증에 실패했습니다. 해당 날짜의 변경을 되돌립니다.")
    return created, filled


class Command(BaseCommand):
    help = (
        "참여 시작일부터 오늘(KST)까지 한 사용자의 누락 SpO₂를 보완합니다. "
        "기존 SpO₂ 값과 다른 센서 데이터는 유지합니다."
    )
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, required=True)
        parser.add_argument("--start-date", help="YYYY-MM-DD, 생략하면 참여 시작일부터")
        parser.add_argument("--end-date", help="YYYY-MM-DD, 생략하면 오늘까지")
        parser.add_argument(
            "--dry-run", action="store_true",
            help="측정 데이터는 저장하지 않음. 만료된 인증 토큰은 갱신될 수 있음.",
        )

    def handle(self, *args, **options):
        now = as_kst(timezone.now())
        try:
            requested_start = (datetime.strptime(options["start_date"], "%Y-%m-%d").date()
                               if options["start_date"] else None)
            requested_end = (datetime.strptime(options["end_date"], "%Y-%m-%d").date()
                             if options["end_date"] else now.date())
        except ValueError as exc:
            raise CommandError("날짜는 YYYY-MM-DD 형식이어야 합니다.") from exc
        if requested_start is not None and requested_end < requested_start:
            raise CommandError("종료일은 시작일보다 빠를 수 없습니다.")

        with connection.cursor() as cursor:
            columns = {c.name for c in connection.introspection.get_table_description(
                cursor, FitbitAccount._meta.db_table,
            )}
        fields = ["id", "user_id", "join_date", "end_date"]
        fields.extend(key for key in ("source_account_id", "participant_started_at", "participant_ended_at")
                      if key in columns)
        participant = FitbitAccount.objects.filter(user_id=options["user_id"]).values(*fields).first()
        if participant is None:
            raise CommandError(f"user_id={options['user_id']}에 연결된 Fitbit 계정이 없습니다.")
        source_id = participant.get("source_account_id") or participant["id"]
        credentials = FitbitAccount.objects.only(
            "id", "user_id", "access_token", "refresh_token", "expires_at", "token_type", "scope",
        ).get(pk=source_id)
        scope = "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly"
        if scope not in credentials.scope.split():
            raise CommandError("Google Health health_metrics_and_measurements.readonly 권한이 없습니다.")

        start, end = backfill_bounds(participant, requested_start, requested_end, now)
        if start >= end:
            raise CommandError("참여 기간과 요청 기간이 겹치지 않아 저장할 범위가 없습니다.")
        self.stdout.write(
            f"user_id={options['user_id']} | account_id={participant['id']} | "
            f"KST {start.isoformat()} 이상 ~ {end.isoformat()} 미만 | "
            f"{'측정 데이터 저장 안 함' if options['dry_run'] else '누락 SpO₂만 저장'}"
        )

        failures = total_created = total_filled = 0
        date = start.date()
        while date <= end.date():
            if datetime.combine(date, datetime.min.time(), tzinfo=KST) >= end:
                break
            date_text = date.isoformat()
            try:
                data = fetch_spo2(date_text, credentials)
            except SpO2FetchError as exc:
                failures += 1
                self.stdout.write(f"{date_text} | 조회 실패 | {exc}")
                date += timedelta(days=1)
                continue
            parsed, matched, invalid = spo2_minutes_for_date(data["dataPoints"], date_text)
            wanted = {}
            for minute, (observed_at, value) in parsed.items():
                minute_kst = minute.replace(tzinfo=KST)
                if start <= observed_at.replace(tzinfo=KST) < end and start <= minute_kst < end:
                    key = minute_kst if settings.USE_TZ else minute
                    wanted[key] = value
            present = FitbitMinuteMetric._base_manager.filter(
                account_id=participant["id"], timestamp__in=wanted, spo2__isnull=False,
            ).count()
            created = filled = 0
            if not options["dry_run"] and wanted:
                with transaction.atomic():
                    # Same locking order as participant replacement: source, then participant.
                    FitbitAccount.objects.select_for_update().values("id").get(pk=source_id)
                    current = FitbitAccount.objects.select_for_update().values(*fields).get(pk=participant["id"])
                    if current != participant:
                        raise CommandError("참여 정보가 변경되었습니다. 복구를 중단합니다. 다시 실행하세요.")
                    created, filled = fill_missing_minutes(participant["id"], wanted)
            total_created += created
            total_filled += filled
            self.stdout.write(
                f"{date_text} | API={data['api_point_count']}건/{data['page_count']}페이지 | "
                f"대상={len(wanted)}분 | 기존={present}분 | "
                f"{'보완 예정=' + str(len(wanted) - present) + '분' if options['dry_run'] else '신규 행=' + str(created) + '건, 기존 행 보완=' + str(filled) + '건'} | "
                f"유효 표본={matched}건, 오류={invalid}건"
            )
            date += timedelta(days=1)

        self.stdout.write(f"합계: 신규 행={total_created}건 | 기존 행 SpO₂ 보완={total_filled}건 | 조회 실패={failures}일")
        if failures:
            raise CommandError("일부 날짜의 조회에 실패했습니다. 같은 명령을 다시 실행해 재시도할 수 있습니다.")
