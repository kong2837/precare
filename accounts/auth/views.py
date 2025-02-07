import csv
import hashlib
import json

from django.urls import reverse_lazy
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView as Login
from .forms import MyLoginForm
from django.contrib import messages



class LoginView(Login):
    """로그인을 위한 클래스 기반 뷰
    """
    template_name = 'accounts/auth/login.html'
    redirect_field_name = 'redirect_to'
    next_page = reverse_lazy('home')
    form_class = MyLoginForm