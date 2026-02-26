from django.urls import path
from django.views.generic import TemplateView

app_name = 'archive'

urlpatterns = [
    path('', TemplateView.as_view(template_name='archive/index.html'), name='index'),
]