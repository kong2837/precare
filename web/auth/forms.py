from django import forms
from django.contrib.auth.forms import SetPasswordForm as DjangoSetPasswordForm, AuthenticationForm, UsernameField
from django.contrib.auth.forms import UserCreationForm


class MyLoginForm(AuthenticationForm):
    username = UsernameField(widget=forms.TextInput(attrs={"autofocus": True, "placeholder": "아이디"}), label="아이디")