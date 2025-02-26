from django.urls import path, include   # 🔗 URL 경로를 정의하고 다른 URLconf를 포함하기 위한 모듈
from . import views                     # 👀 현재 디렉토리의 views.py에서 뷰를 가져오기
from .views import LoginView, ForgotId, Signup, ForgotPassword, VerifyEmailCodeId, VerifyEmailCodePassword, \
    password_reset_confirm

app_name = 'auth'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),  # 기본 페이지 연결
    path('forgot_id/', ForgotId.as_view(), name='forgot_id'),  # 기본 페이지 연결
    path('forgot_password/', ForgotPassword.as_view(), name='forgot_password'),  # 기본 페이지 연결
    path('signup/', Signup.as_view(), name='signup'),  # 기본 페이지 연결
    path('verify_email_code_id/', VerifyEmailCodeId.as_view(), name='verify_email_code_id'),  # 기본 페이지 연결
    path('verify_email_code_password/', VerifyEmailCodePassword.as_view(), name='verify_email_code_password'),
    path('password_reset/', password_reset_confirm, name='password_reset'),
]
