from django import forms
from django.contrib.auth.forms import UserCreationForm

class MyAuthenticationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = ("username", "first_name", "last_name")