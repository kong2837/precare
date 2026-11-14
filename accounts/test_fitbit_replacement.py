from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import UserClickLog
from fitbit.models import FitbitAccount, FitbitMinuteMetric, ParticipantReplacement
from fitbit.participants import replace_participant, participant_at
from huami.models import HuamiAccount
from survey.models import Survey, UserSurvey, ActionFeedback, Question, SurveyQuestion, Reply


@override_settings(ALLOWED_HOSTS=['testserver'])
class FitbitReplacementTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser('replace-admin', '', 'test')
        self.user = get_user_model().objects.create_user('google_health_source', first_name='홍길동')
        self.account = FitbitAccount.objects.create(user=self.user, fitbit_user_id='source',
            access_token='access', refresh_token='refresh', expires_at=timezone.now(), scope='',
            full_name='홍길동', birthday='1990-01-01', note='이전 메모', pregnancy_week_at_join=12)
        self.boundary = timezone.now().replace(second=0, microsecond=0) - timedelta(hours=2)
        self.url = f'/accounts/fitbit/{self.user.pk}/replace/'
        self.client.force_login(self.admin)

    def replace(self, account=None, boundary=None, name='김민서'):
        return replace_participant((account or self.account).pk, name, boundary or self.boundary, self.admin)

    def preview(self):
        return self.client.post(self.url, {'name': '김민서', 'effective_at': timezone.localtime(self.boundary).strftime('%Y-%m-%dT%H:%M')})

    def test_two_steps_new_id_and_original_admin_access(self):
        self.assertContains(self.client.get(self.url), '교체 일시')
        response = self.preview()
        self.assertContains(response, '아래 정보로 참여자를 교체하는 게 맞나요?')
        self.assertContains(response, 'fitbit sense 공동 계정을 사용하는 참여자인지 확인해주세요.')
        self.assertFalse(ParticipantReplacement.objects.exists())
        token = response.context['confirmation']
        self.assertRedirects(self.client.post(self.url, {'confirmation': token}), '/accounts/fitbit_manage/')
        new = ParticipantReplacement.objects.get().replacement
        self.assertNotEqual(new.user_id, self.user.pk)
        self.assertEqual(new.fitbit_user_id, self.account.fitbit_user_id)
        self.assertEqual(new.full_name, '김민서')
        self.assertIsNone(new.birthday)
        self.assertIsNone(new.pregnancy_week_at_join)
        self.assertNotEqual(new.note, '이전 메모')
        self.account.refresh_from_db()
        self.assertEqual(self.account.full_name, '홍길동')
        self.assertContains(self.client.get('/accounts/fitbit_manage/'), '홍길동')
        self.assertContains(self.client.get('/accounts/fitbit_manage/'), '김민서')
        for user in [self.user, new.user]:
            self.assertEqual(self.client.get(f'/accounts/fitbit_info/{user.pk}/').status_code, 200)
            self.assertEqual(self.client.get(f'/accounts/user/{user.pk}/click-logs/').status_code, 200)
            self.assertEqual(self.client.get(f'/accounts/{user.pk}/fitbit_csvData/').status_code, 200)
        self.assertEqual(self.client.post(self.url, {'confirmation': token}).status_code, 409)
        self.assertEqual(ParticipantReplacement.objects.count(), 1)

    def test_existing_and_late_health_data_use_measurement_boundary(self):
        before = FitbitMinuteMetric.objects.create(account=self.account, timestamp=self.boundary - timedelta(minutes=1), heart_rate=60)
        at = FitbitMinuteMetric.objects.create(account=self.account, timestamp=self.boundary, heart_rate=70)
        new = self.replace()
        before.refresh_from_db(); at.refresh_from_db()
        self.assertEqual(before.account_id, self.account.pk)
        self.assertEqual(at.account_id, new.pk)
        # Stale worker/root and new participant both route by measurement time.
        row, _ = FitbitMinuteMetric.objects.get_or_create(account=self.account, timestamp=self.boundary + timedelta(minutes=1), defaults={'heart_rate': 80})
        self.assertEqual(row.account_id, new.pk)
        row, _ = FitbitMinuteMetric.objects.get_or_create(account=new, timestamp=self.boundary - timedelta(minutes=1))
        self.assertEqual(row.pk, before.pk)
        row, created = FitbitMinuteMetric.objects.get_or_create(account=self.account, timestamp=self.boundary)
        self.assertFalse(created)
        self.assertEqual(row.pk, at.pk)

    def test_surveys_feedback_and_logs_partition_without_copy_or_deletion(self):
        survey = Survey.objects.create(title='검사', description='검사')
        old = UserSurvey.objects.create(user=self.user, survey=survey, score=1)
        recent = UserSurvey.objects.create(user=self.user, survey=survey, score=2)
        UserSurvey.objects.filter(pk=old.pk).update(create_at=self.boundary - timedelta(minutes=1))
        UserSurvey.objects.filter(pk=recent.pk).update(create_at=self.boundary)
        question = Question.objects.create(title='질문')
        link = SurveyQuestion.objects.create(survey=survey, question=question, order=1)
        reply = Reply.objects.create(user_survey=recent, survey_question=link, content='답변', score=2)
        feedback = ActionFeedback.objects.create(user_survey=recent, action_code='REST', performed=True)
        log = UserClickLog.objects.create(user=self.user, log_type='survey_click')
        new = self.replace()
        old.refresh_from_db(); recent.refresh_from_db(); log.refresh_from_db(); feedback.refresh_from_db()
        self.assertEqual(old.user_id, self.user.pk)
        self.assertEqual(recent.user_id, new.user_id)
        self.assertEqual(log.user_id, new.user_id)
        self.assertEqual(feedback.user_survey_id, recent.pk)
        reply.refresh_from_db()
        self.assertEqual(reply.user_survey.user_id, new.user_id)
        self.assertEqual(reply.content, "답변")
        self.assertEqual(UserSurvey.objects.count(), 2)
        late = UserSurvey.objects.create(user=self.user, survey=survey)
        self.assertEqual(late.user_id, new.user_id)
        self.assertEqual(UserClickLog.objects.create(user=self.user, log_type='survey_click').user_id, new.user_id)

    def test_multiple_replacements_and_invalid_boundaries(self):
        new = self.replace()
        third = self.replace(new, self.boundary + timedelta(minutes=1), '세번째')
        self.assertEqual(participant_at(self.account, self.boundary - timedelta(seconds=1)), self.account)
        self.assertEqual(participant_at(self.account, self.boundary), new)
        self.assertEqual(participant_at(self.account, self.boundary + timedelta(minutes=1)), third)
        for item, boundary in [(self.account, self.boundary), (third, self.boundary), (third, timezone.now()+timedelta(days=1))]:
            with self.assertRaises(ValidationError):
                self.replace(item, boundary)
        self.assertEqual(ParticipantReplacement.objects.count(), 2)

    def test_confirmation_tampering_cancel_and_permissions(self):
        response = self.preview()
        token = response.context['confirmation']
        self.assertEqual(self.client.post(self.url, {'confirmation': token+'bad'}).status_code, 400)
        self.assertFalse(ParticipantReplacement.objects.exists())
        for data in [{'name':'', 'effective_at':'bad'}, {'name':'김민서', 'effective_at':'2099-01-01T00:00'}]:
            self.assertEqual(self.client.post(self.url, data).status_code, 400)
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post(self.url, {'confirmation': token}).status_code, 403)

    def test_huami_is_untouched_and_cannot_be_replaced(self):
        HuamiAccount.objects.create(user=self.user, email='huami@example.com', password='test')
        self.assertEqual(self.client.get(self.url).status_code, 404)
        with self.assertRaises(ValidationError):
            self.replace()
        self.assertContains(self.client.get('/accounts/manage/'), '설문')
        self.assertNotContains(self.client.get('/accounts/manage/'), '참여자 교체하기')
        self.assertEqual(HuamiAccount.objects.get(user=self.user).email, 'huami@example.com')
        self.assertFalse(ParticipantReplacement.objects.exists())

    def test_stale_session_follows_current_user_without_affecting_admin(self):
        self.client.force_login(self.user)
        new = self.replace()
        self.client.get('/accounts/profile/')
        self.assertEqual(int(self.client.session['_auth_user_id']), new.user_id)
        self.client.force_login(self.admin)
        self.client.get('/accounts/fitbit_manage/')
        self.assertEqual(int(self.client.session['_auth_user_id']), self.admin.pk)

    @patch('accounts.views.requests.get')
    @patch('accounts.views.requests.post')
    def test_google_reauthentication_keeps_active_user(self, post, get):
        new = self.replace()
        post.return_value = Mock(status_code=200, json=lambda: {'access_token':'fresh', 'refresh_token':'refresh', 'expires_in':3600})
        get.return_value = Mock(status_code=200, text='{}', json=lambda: {'healthUserId':'source'})
        self.client.logout()
        response = self.client.get('/accounts/google-health/callback/?code=test')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), new.user_id)
        self.account.refresh_from_db()
        self.assertEqual(self.account.access_token, 'fresh')
        self.assertEqual(self.account.full_name, '홍길동')

    def test_replacement_failure_rolls_back_everything(self):
        original_users = get_user_model().objects.count()
        with patch('fitbit.models.account.ParticipantReplacement.objects.create', side_effect=RuntimeError('fail')):
            with self.assertRaises(RuntimeError):
                self.replace()
        self.account.refresh_from_db()
        self.assertIsNone(self.account.participant_ended_at)
        self.assertEqual(get_user_model().objects.count(), original_users)
        self.assertFalse(ParticipantReplacement.objects.exists())

    def test_only_source_is_polled_and_latest_measurements_follow_owner(self):
        from jobs.tasks import sync_intra_data
        from fitbit.sync.sync import update_last_synced
        new = self.replace()
        with patch('jobs.tasks.get_heart_rate') as hr, patch('jobs.tasks.get_step_count') as steps:
            sync_intra_data()
        self.assertEqual(hr.call_count, 1)
        self.assertEqual(steps.call_count, 1)
        self.assertEqual(hr.call_args.args[1].pk, self.account.pk)
        update_last_synced(self.account, self.boundary + timedelta(minutes=1))
        update_last_synced(new, self.boundary - timedelta(minutes=1))
        self.account.refresh_from_db(); new.refresh_from_db()
        self.assertEqual(self.account.last_synced, self.boundary - timedelta(minutes=1))
        self.assertEqual(new.last_synced, self.boundary + timedelta(minutes=1))

    def test_replacement_button_is_red_and_last_column(self):
        import re
        response = self.client.get('/accounts/fitbit_manage/')
        html = response.content.decode()
        row = re.search(r'<tr data-href=.*?</tr>', html, re.S)[0]
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
        self.assertIn('참여자 교체하기', cells[-1])
        self.assertIn('btn btn-danger', cells[-1])
        self.assertIn(self.url, cells[-1])

    def test_confirmation_required_expired_or_different_admin_rejected(self):
        from django.core import signing
        response = self.preview()
        token = response.context['confirmation']
        with patch('django.core.signing.time.time', return_value=0):
            expired = signing.dumps(signing.loads(token, salt='fitbit-replacement'), salt='fitbit-replacement')
        self.assertEqual(self.client.post(self.url, {'confirmation': expired}).status_code, 400)
        other = get_user_model().objects.create_superuser('other-admin', '', 'test')
        self.client.force_login(other)
        self.assertEqual(self.client.post(self.url, {'confirmation': token}).status_code, 400)
        self.assertFalse(ParticipantReplacement.objects.exists())

    def test_replacement_history_is_shared_by_chain_and_fitbit_only(self):
        new = self.replace()
        third = self.replace(new, self.boundary + timedelta(minutes=1), '세번째')
        unrelated_user = get_user_model().objects.create_user('unrelated-history')
        unrelated = FitbitAccount.objects.create(user=unrelated_user, fitbit_user_id='unrelated',
            access_token='test', refresh_token='test', expires_at=timezone.now(), scope='', full_name='다른 계정')
        replace_participant(unrelated.pk, '다른 교체', self.boundary, self.admin)
        for account in [self.account, new, third]:
            response = self.client.get(f'/accounts/fitbit_info/{account.user_id}/')
            self.assertContains(response, '참여자 교체 기록')
            self.assertEqual(len(response.context['replacement_history']), 2)
            self.assertContains(response, f'홍길동 (ID {self.user.pk})')
            self.assertContains(response, f'김민서 (ID {new.user_id})')
            self.assertContains(response, f'세번째 (ID {third.user_id})')
            self.assertContains(response, '처리 관리자: replace-admin')
            self.assertContains(response, '교체 일시 (한국 시간)')
            self.assertNotContains(response, '다른 교체')
        HuamiAccount.objects.create(user=self.user, email='history@example.com', password='test')
        response = self.client.get(f'/accounts/info/{self.user.pk}/')
        self.assertNotContains(response, '참여자 교체 기록')
        self.assertNotIn('replacement_history', response.context)

    def test_empty_replacement_history(self):
        response = self.client.get(f'/accounts/fitbit_info/{self.user.pk}/')
        self.assertContains(response, '참여자 교체 기록이 없습니다.')
