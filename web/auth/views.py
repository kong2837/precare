import csv
import hashlib
import json

from django.urls import reverse_lazy
from django.contrib.auth import get_user_model
from django.contrib.auth.views import LoginView as Login
from .forms import MyLoginForm
from django.contrib import messages
from django.views.generic import View, TemplateView, ListView, DetailView
from django.shortcuts import render

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

class ForgotPassword(View):
    template_name = 'auth/forgot_password.html'

    def get(self, request, *args, **kwargs):
        return render(request,self.template_name)

class Signup(View):
    template_name = 'auth/signup.html'

    def get(self, request, *args, **kwargs):
        return render(request, self.template_name)