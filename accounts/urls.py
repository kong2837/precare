from django.urls import path
from .views import HealthDataCsvDownloadAPIView, HealthDataCsvDownloadView, LoginView, LogoutView, SignUpView, SuccessSignUpView, UserHealthDataSyncView, UserHealthNoteUpdateView, UserInfoView, UserManageView, UserNoteUpdateView, UserPrimaryKeyAPIView, ClientStatusView
app_name = 'accounts'

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('signup/', SignUpView.as_view(), name='signup'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('successSignup/', SuccessSignUpView.as_view(), name='successSignup'),
    path('manage/', UserManageView.as_view(), name='userManage'),
    path('info/<int:pk>/', UserInfoView.as_view(), name='userInfo'),
    path('heatlhInfo/<int:pk>/', UserHealthNoteUpdateView.as_view(), name='userHealthInfo'),
    path('<int:pk>/updateNote/', UserNoteUpdateView.as_view(), name='updateNote'),
    path('<int:pk>/syncData/', UserHealthDataSyncView.as_view(), name='syncHealth'),
    path('<int:pk>/csvData/', HealthDataCsvDownloadView.as_view(), name='csvDownload'),
    path('users/<int:pk>/healthData.csv', HealthDataCsvDownloadAPIView.as_view(), name='csvDownloadApi'),
    path('users.csv', UserPrimaryKeyAPIView.as_view(), name="usersCsvDownloadApi"),
    path('status/', ClientStatusView.as_view(), name='userStatus'),

]
