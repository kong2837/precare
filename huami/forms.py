from django import forms
from .models import HuamiAccount
from .utils import HuamiAmazfit


class HuamiAccountCreationForm(forms.ModelForm):
    """Huami Account생성을 위한 모델 폼
    Raises:
        forms.ValidationError: 이메일이 이미 존재하거나 옳바르지 않은 계정정보인 경우 에러
    """    
    class Meta:
        model = HuamiAccount
        fields = (
            'email',
            'password',
        )
        
        widgets={
            'password': forms.PasswordInput()
        }
    
    def clean(self) -> dict:
        """폼에 들어온 데이터가 유효한지 검증

        Raises:
            forms.ValidationError: 이메일이 이미 존재하거나 옳바르지 않은 계정정보인 경우 에러

        Returns:
            dict: 검증을 거친 데이터 딕셔너리
        """        
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')
        
        #email이 Unique한지 확인하는 절차
        self.validate_unique()
                
        try:
            HuamiAmazfit.is_valid(email, password)
        except ValueError:
            raise forms.ValidationError('이메일이나 비밀번호가 옳바르지 않습니다.')
        
        return cleaned_data


class HuamiAccountCertificationForm(forms.ModelForm):
    """Huami 재인증을 위한 폼
    Raises:
        forms.ValidationError: 옳바르지 않은 계정정보인 경우 에러
    """

    class Meta:
        model = HuamiAccount
        fields = (
            'email',
            'password',
        )

        widgets = {
            'password': forms.PasswordInput()
        }

    def clean(self) -> dict:
        """폼에 들어온 데이터가 유효한지 검증

        Raises:
            forms.ValidationError: 이메일이 이미 존재하거나 옳바르지 않은 계정정보인 경우 에러

        Returns:
            dict: 검증을 거친 데이터 딕셔너리
        """
        cleaned_data = self.cleaned_data
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')

        try:
            HuamiAmazfit.is_valid(email, password)
        except ValueError:
            raise forms.ValidationError('이메일이나 비밀번호가 옳바르지 않습니다.')

        return cleaned_data