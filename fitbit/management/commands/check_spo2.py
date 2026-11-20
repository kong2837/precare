"""Inspect complete Google Health SpO2 responses without saving measurements."""
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import connection

from fitbit.google_health.client import google_time_to_kst_naive
from fitbit.google_health.daily_data.spo2 import SpO2FetchError, fetch_spo2
from fitbit.models import FitbitAccount


class Command(BaseCommand):
    help = (
        "KST 날짜 범위와 전체 페이지를 지정해 Google Health SpO₂ 응답 건수를 확인합니다. "
        "헬스데이터는 저장하지 않으며, --refresh-token 지정 시에만 인증 토큰을 갱신할 수 있습니다."
    )
    # This diagnostic does not need URL checks, which currently query the DB.
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, required=True)
        parser.add_argument("--start-date", required=True, help="YYYY-MM-DD, KST 기준")
        parser.add_argument("--end-date", required=True, help="YYYY-MM-DD, 해당 날짜 포함")
        parser.add_argument(
            "--refresh-token", action="store_true",
            help="HTTP 401 발생 시 인증 토큰을 갱신하고 DB에 저장하도록 허용",
        )

    def handle(self, *args, **options):
        try:
            start = datetime.strptime(options["start_date"], "%Y-%m-%d").date()
            end = datetime.strptime(options["end_date"], "%Y-%m-%d").date()
        except ValueError as exc:
            raise CommandError("날짜는 YYYY-MM-DD 형식이어야 합니다.") from exc
        if end < start:
            raise CommandError("종료일은 시작일보다 빠를 수 없습니다.")

        # Read only the fields needed for API access. Older production schemas
        # may not yet have participant replacement columns; do not require them.
        fields = ["id", "user_id", "access_token", "refresh_token", "expires_at", "token_type", "scope"]
        with connection.cursor() as cursor:
            columns = {
                column.name for column in connection.introspection.get_table_description(
                    cursor, FitbitAccount._meta.db_table,
                )
            }
        has_source = "source_account_id" in columns
        if has_source:
            fields.append("source_account_id")
        try:
            participant = FitbitAccount.objects.only(*fields).get(user_id=options["user_id"])
        except FitbitAccount.DoesNotExist as exc:
            raise CommandError(f"user_id={options['user_id']}에 연결된 Fitbit 계정이 없습니다.") from exc

        account = participant
        if has_source and participant.source_account_id:
            account = FitbitAccount.objects.only(*fields).get(pk=participant.source_account_id)

        scope = "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly"
        if scope not in account.scope.split():
            raise CommandError("Google Health health_metrics_and_measurements.readonly 권한이 없습니다.")

        self.stdout.write(
            f"user_id={options['user_id']} | 인증 계정 ID={account.pk} | "
            f"KST {start.isoformat()}~{end.isoformat()} | 헬스데이터 저장 없음"
        )
        self.stdout.write(f"401 시 토큰 갱신 허용: {options['refresh_token']}")
        failures = 0
        date = start
        while date <= end:
            date_text = date.isoformat()
            try:
                data = fetch_spo2(date_text, account, allow_token_refresh=options["refresh_token"])
            except SpO2FetchError as exc:
                failures += 1
                self.stdout.write(f"{date_text} | 조회 실패 | {exc}")
                date += timedelta(days=1)
                continue

            matched_times = []
            invalid = 0
            outside = 0
            for point in data["dataPoints"]:
                try:
                    sample = point["oxygenSaturation"]
                    physical_time = sample["sampleTime"]["physicalTime"]
                    measured_at = google_time_to_kst_naive(physical_time)
                    if measured_at is None or sample.get("percentage") is None:
                        invalid += 1
                    elif measured_at.date() != date:
                        outside += 1
                    else:
                        matched_times.append(measured_at)
                except (KeyError, TypeError, ValueError, AttributeError):
                    invalid += 1

            self.stdout.write(
                f"{date_text} | HTTP 200 | 페이지={data['page_count']} | "
                f"원본={data['api_point_count']}건 | 해당 날짜={len(matched_times)}건 | "
                f"필드/시간 누락·오류={invalid}건 | 날짜 밖={outside}건"
            )
            self.stdout.write(f"  filter: {data['query_filter']}")
            if matched_times:
                self.stdout.write(
                    f"  KST 측정 범위: {min(matched_times).isoformat()}~{max(matched_times).isoformat()}"
                )
            date += timedelta(days=1)

        if failures:
            raise CommandError(
                f"{failures}일의 조회에 실패했습니다. HTTP 401이면 재연결 또는 "
                "--refresh-token 옵션으로 인증 토큰 갱신이 필요합니다."
            )
