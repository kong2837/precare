from django.urls import path, include   # 🔗 URL 경로를 정의하고 다른 URLconf를 포함하기 위한 모듈
from . import views                     # 👀 현재 디렉토리의 views.py에서 뷰를 가져오기
from .views import LoginView

app_name = 'auth'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),  # 기본 페이지 연결

]
