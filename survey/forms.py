from django import forms


class PostpartumContextForm(forms.Form):
    postpartum_weeks = forms.IntegerField(
        required=False, min_value=0, max_value=2147483647, label="출산 후 경과",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "1", "inputmode": "numeric", "placeholder": "예: 6", "aria-describedby": "postpartum-weeks-help postpartum-weeks-unit"}),
        error_messages={"invalid": "출산 후 경과는 0 이상의 정수로 입력해주세요.", "min_value": "출산 후 경과는 0주 이상이어야 합니다."},
    )
