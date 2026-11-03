from django.core.management.base import BaseCommand
from django.db import transaction
from django.http import QueryDict

from survey.models import UserSurvey
from survey.scoring import epds_answers, epds_survey_filter


class Command(BaseCommand):
    help = "Preview missing K-EPDS scores; use --apply to save scores from configured answers."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **options):
        updated = skipped = 0
        for submission in UserSurvey.objects.filter(
            epds_survey_filter(), score__isnull=True
        ).select_related("survey"):
            replies = list(submission.replies.select_related("survey_question"))
            data = QueryDict(mutable=True)
            for reply in replies:
                data.appendlist(str(reply.survey_question.question_id), reply.content)
            try:
                answers = epds_answers(submission.survey, data)
                if any(reply.score is not None for reply in replies):
                    raise ValueError("Existing score snapshot requires review")
            except ValueError:
                skipped += 1
                self.stdout.write(f"Skipped submission {submission.pk}: incomplete or invalid answers")
                continue
            if options["apply"]:
                with transaction.atomic():
                    points = {sq.pk: score for sq, _, score in answers}
                    for reply in replies:
                        reply.score = points[reply.survey_question_id]
                        reply.save(update_fields=["score"])
                    submission.score = sum(points.values())
                    submission.save(update_fields=["score"])
            updated += 1
        self.stdout.write(f"{'Saved' if options['apply'] else 'Eligible'}: {updated}; skipped: {skipped}")
