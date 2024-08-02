from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.forms import SetPasswordForm as DjangoSetPasswordForm
from django import forms


class MyAuthenticationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = ("username", "first_name", "last_name")




class PasswordResetRequestForm(forms.Form):
    name = forms.CharField(max_length=100, label="이름")
    username = forms.CharField(max_length=100, label="아이디")
    email = forms.EmailField(label="이메일")

class VerifyCodeForm(forms.Form):
    verification_code = forms.CharField(max_length=8, label="인증번호")

class SetPasswordForm(DjangoSetPasswordForm):
    new_password1 = forms.CharField(
        label="새 비밀번호",
        strip=False,
        widget=forms.PasswordInput,
    )
    new_password2 = forms.CharField(
        label="새 비밀번호 확인",
        strip=False,
        widget=forms.PasswordInput,
    )

class FindUsernameForm(forms.Form):
    name = forms.CharField(max_length=100, label="이름")
    email = forms.EmailField(label="이메일")