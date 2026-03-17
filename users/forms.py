from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm


class LoginUserForm(AuthenticationForm):
    username = forms.CharField(
        label="Логин",
        widget=forms.TextInput(attrs={"class": "form-input"})
    )
    password = forms.CharField(
        label="Пароль",
        widget=forms.PasswordInput(attrs={"class": "form-input"})
    )

    class Meta:
        model = get_user_model()
        fields = ["username", "password"]


class SelectBusinessUnitForm(forms.Form):
    business_unit_id = forms.ChoiceField(label="Бизнес-юнит")

    def __init__(self, *args, business_units=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["business_unit_id"].choices = [
            (str(item["id"]), item["label"]) for item in (business_units or [])
        ]