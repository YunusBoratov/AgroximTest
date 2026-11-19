from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

from core.forms import StyledMixin

from .models import STAFF_ROLES, Role, User


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = _("Login")
        self.fields["password"].label = _("Parol")
        for f in self.fields.values():
            f.widget.attrs.update({"class": "input", "placeholder": _("Kiriting")})


class XodimForm(StyledMixin, forms.ModelForm):
    parol = forms.CharField(label=_("Parol"), required=False, widget=forms.PasswordInput(render_value=False),
                            help_text=_("Tahrirlashda bo'sh qoldirilsa, parol o'zgarmaydi."))

    class Meta:
        model = User
        fields = ["fish", "username", "telefon", "lavozim", "role", "is_active"]
        labels = {"username": _("Login"), "is_active": _("Faol")}
        help_texts = {"username": _("Lotin harflari, raqamlar va @ . + - _ belgilari"), "is_active": ""}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [(r, l) for r, l in Role.choices if r in STAFF_ROLES]
        self.fields["fish"].required = True
        if not self.instance.pk:
            self.fields["parol"].required = True

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("parol"):
            user.set_password(self.cleaned_data["parol"])
        if commit:
            user.save()
        return user
