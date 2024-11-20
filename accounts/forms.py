from django import forms
from django.contrib.auth.forms import SetPasswordForm as DjangoSetPasswordForm, AuthenticationForm, UsernameField
from django.contrib.auth.forms import UserCreationForm


class MyLoginForm(AuthenticationForm):
    username = UsernameField(widget=forms.TextInput(attrs={"autofocus": True, "placeholder": "아이디"}), label="아이디")


class MyAuthenticationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = ("username",)
        labels = {
            "username": "아이디"
        }

    def __init__(self, *args, **kwargs):
        super(MyAuthenticationForm, self).__init__(*args, **kwargs)

        # Customizing placeholders for fields
        self.fields['username'].widget.attrs.update({
            'placeholder': '아이디를 입력하세요',
            'class': 'form-control'
        })


class PasswordResetRequestForm(forms.Form):
    """비밀번호 찾기 시 입력 field
        """

    username = forms.CharField(max_length=100, label="아이디")
    email = forms.EmailField(label="이메일(Zepp life 계정을 입력해주세요)",
                             widget=forms.EmailInput(attrs={'placeholder': '이메일'}))


class VerifyCodeForm(forms.Form):
    """인증코드 field
        """
    verification_code = forms.CharField(max_length=8, label="인증번호")


class SetPasswordForm(DjangoSetPasswordForm):
    """새로운 비밀번호 입력
        """
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
    """아이디 찾기 시 입력 field
        """
    name = forms.CharField(max_length=100, label="이름",
                           widget=forms.TextInput(attrs={'placeholder': '홍길동'}))

    email = forms.EmailField(label="이메일(Zepp life 계정을 입력해주세요)",
                             widget=forms.EmailInput(attrs={'placeholder': '이메일'}))


class PhoneNumberChangeForm(forms.Form):
    phone_number = forms.CharField(
        max_length=15,
        label="기존 전화번호",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "전화번호 입력"})
    )
