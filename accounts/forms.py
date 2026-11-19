from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _

from core.forms import StyledMixin

from .models import STAFF_ROLES, Role, User


class LoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # mijozlar telefon raqamini istalgan ko'rinishda yozishi mumkin
        if self.data.get("username"):
            tel = normalize_phone(self.data["username"])
            if tel and not self.data["username"].isalpha():
                self.data = self.data.copy()
                self.data["username"] = tel
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


def normalize_phone(raw):
    digits = "".join(ch for ch in raw or "" if ch.isdigit())
    if len(digits) == 9:
        digits = "998" + digits
    return "+" + digits if len(digits) == 12 and digits.startswith("998") else None


class RoyxatForm(StyledMixin, forms.Form):
    MIJOZ_TURI = [("yuridik", _("Yuridik shaxs (tashkilot)")), ("jismoniy", _("Jismoniy shaxs"))]

    turi = forms.ChoiceField(label=_("Buyurtmachi turi"), choices=MIJOZ_TURI)
    telefon = forms.CharField(label=_("Telefon raqami (login)"), max_length=20,
                              widget=forms.TextInput(attrs={"placeholder": "+998 90 123 45 67"}))
    fish = forms.CharField(label=_("F.I.SH."), max_length=255)
    inn = forms.CharField(label=_("INN (tashkilot) yoki JSHSHIR"), max_length=14)
    tashkilot_nomi = forms.CharField(label=_("Tashkilot nomi"), max_length=255, required=False)
    parol1 = forms.CharField(label=_("Parol"), widget=forms.PasswordInput, min_length=6)
    parol2 = forms.CharField(label=_("Parolni takrorlang"), widget=forms.PasswordInput)

    def clean_telefon(self):
        tel = normalize_phone(self.cleaned_data["telefon"])
        if not tel:
            raise forms.ValidationError(_("Telefon raqami noto'g'ri. Masalan: +998 90 123 45 67"))
        if User.objects.filter(username=tel).exists():
            raise forms.ValidationError(_("Bu telefon raqami bilan allaqachon ro'yxatdan o'tilgan"))
        return tel

    def clean(self):
        data = super().clean()
        inn = (data.get("inn") or "").strip()
        if inn and (not inn.isdigit() or len(inn) not in (9, 14)):
            self.add_error("inn", _("INN 9 ta, JSHSHIR 14 ta raqamdan iborat bo'ladi"))
        if data.get("turi") == "yuridik" and not data.get("tashkilot_nomi"):
            self.add_error("tashkilot_nomi", _("Tashkilot nomini kiriting"))
        if data.get("parol1") and data.get("parol1") != data.get("parol2"):
            self.add_error("parol2", _("Parollar mos kelmadi"))
        return data

    def save(self):
        d = self.cleaned_data
        inn = d["inn"].strip()
        user = User(username=d["telefon"], telefon=d["telefon"], fish=d["fish"], role=Role.MIJOZ,
                    tashkilot_nomi=d.get("tashkilot_nomi") or "",
                    inn=inn if len(inn) == 9 else "", pinfl=inn if len(inn) == 14 else "")
        user.set_password(d["parol1"])
        user.save()
        return user
