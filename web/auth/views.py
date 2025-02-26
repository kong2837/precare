import csv
import hashlib
import json

from django.contrib.auth.tokens import default_token_generator
from django.shortcuts import get_object_or_404, redirect
from django.shortcuts import render
from django.core.mail import send_mail
from django.urls import reverse_lazy
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView as Login

from accounts.utils import generate_verification_code
from accounts.views import create_profile_if_not_exists
from huami.models import HuamiAccount
from .forms import MyLoginForm
from django.contrib import messages
from django.views.generic import View, TemplateView, ListView, DetailView
from django.shortcuts import render
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse
from django.http import JsonResponse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from accounts.forms import SetPasswordForm
from django.utils.encoding import force_str

class LoginView(Login):
    """로그인을 위한 클래스 기반 뷰
    """
    template_name = 'auth/login.html'
    redirect_field_name = 'redirect_to'
    next_page = reverse_lazy('home')
    form_class = MyLoginForm

class ForgotId(View):
    template_name = 'auth/forgot_id.html'

    def get(self, request, *args, **kwargs):
        return render(request,self.template_name)

    def post(self, request, *args, **kwargs):
        email = request.POST.get('email')  # 폼에서 전달된 이메일 받기
        # 이메일 인증번호 전송 로직 추가


        try:
                user = HuamiAccount.objects.get(email=email).user

                create_profile_if_not_exists(user)

                verification_code = generate_verification_code()
                user.profile.verification_code = verification_code
                user.profile.save()

                request.session['reset_email'] = email

                send_mail(
                    '진통감지 및 스트레스 완화연구 사이트 인증코드',
                    f'인증코드는 다음과 같습니다.: {verification_code}',
                    'pregnancy_re@naver.com',
                    [email],
                    fail_silently=False,
                )

                messages.success(request, '이메일로 인증번호를 발송하였습니다')
                return redirect('auth:verify_email_code_id')
        except HuamiAccount.DoesNotExist:
            messages.error(request, '등록되지 않은 이메일입니다.')
            return redirect('auth:forgot_id')


class ForgotPassword(View):
    template_name = 'auth/forgot_password.html'

    def get(self, request, *args, **kwargs):
        return render(request,self.template_name)

    def post(self, request, *args, **kwargs):
        email = request.POST.get('email')  # 폼에서 전달된 이메일 받기
        username = request.POST.get('username')
        # 이메일 인증번호 전송 로직 추가

        try:
            user = User.objects.get(username=username)
            huami_account = HuamiAccount.objects.get(email=email)
            create_profile_if_not_exists(user)
            verification_code = generate_verification_code()
            user.profile.verification_code = verification_code
            user.profile.save()

            request.session['reset_username'] = username

            send_mail(
                'Password Reset Verification Code',
                f'Your verification code is {verification_code}',
                'pregnancy_re@naver.com',
                [huami_account.email],
                fail_silently=False,
            )

            messages.success(request, '이메일로 인증번호를 발송하였습니다')
            return redirect('auth:verify_email_code_password')
        except User.DoesNotExist:
            messages.error(request, '아이디가 존재하지 않습니다.')
            return redirect('auth:forgot_password')
        except HuamiAccount.DoesNotExist:
            messages.error(request, '등록되지 않은 이메일입니다.')
            return redirect('auth:forgot_password')


class Signup(View):
    template_name = 'auth/signup.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)

class VerifyEmailCodeId(View):
    template_name='auth/verify_email_code_id.html'
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        verification_code = request.POST.get('verification_code')
        email = request.session.get('reset_email')

        if not email:
            messages.error(request, 'No email found in session. Please start over.')
            return redirect('auth:forgot_id')

        try:
            huami_account = HuamiAccount.objects.get(email=email)
            from django.contrib.auth.models import User
            user = User.objects.get(id=huami_account.user_id)

            if user.profile.verification_code == verification_code:
                return render(request, 'auth/complete_id.html', {'username': user.username})
            else:
                messages.error(request, '인증번호가 일치하지 않습니다.')

        except HuamiAccount.DoesNotExist:
            messages.error(request, 'Email not found in HuamiAccount.')
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
        return redirect('auth:verify_email_code_id')

class VerifyEmailCodePassword(View):
    template_name='auth/verify_email_code_id.html'
    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)

    def post(self, request, *args, **kwargs):
        verification_code = request.POST.get('verification_code')
        email = request.session.get('reset_email')

        if not email:
            messages.error(request, 'No email found in session. Please start over.')
            return redirect('auth:forgot_id')

        try:
            huami_account = HuamiAccount.objects.get(email=email)
            from django.contrib.auth.models import User
            user = User.objects.get(id=huami_account.user_id)

            if user.profile.verification_code == verification_code:
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                token = default_token_generator.make_token(user)
                return redirect('auth:password_reset', uidb64=uid, token=token)
            else:
                messages.error(request, '인증번호가 일치하지 않습니다.')

        except HuamiAccount.DoesNotExist:
            messages.error(request, 'Email not found in HuamiAccount.')
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
        return redirect('auth:verify_email_code_id')

def password_reset_confirm(request, uidb64=None, token=None):
    """새로운 비밀번호 변경 관련 코드
     """
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, 'Your password was successfully updated!')
                return redirect('accounts:password_reset_complete')
        else:
            form = SetPasswordForm(user)
    else:
        messages.error(request, "The reset link is no longer valid.")
        return redirect("accounts:email_password_reset_request")

    return render(request, 'auth/password_reset.html', {'form': form})