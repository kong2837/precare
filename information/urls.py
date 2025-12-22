from django.urls import path
from . import views

app_name = 'information'

urlpatterns = [
    path('', views.index, name='index'),          # 산모 및 태아정보(세 카드) 화면
    path('early/', views.early, name='early'),    # 임신 초기
    path('mid/', views.mid, name='mid'),          # 임신 중기
    path('late/', views.late, name='late'),       # 임신 후기
]
