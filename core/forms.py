from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import (ARIZA_MAYDONLARI, REKVIZIT_MAYDONLARI, ZARUR_HUJJATLAR, Ariza, ArizaHujjat, ArizaTuri,
                     Kategoriya, Namuna, NamunaTuri, Narxnoma)

MAX_FAYL_MB = 15
RUXSAT_KENGAYTMALAR = (".pdf", ".jpg", ".jpeg", ".png", ".doc", ".docx", ".xls", ".xlsx")


class StyledMixin:
    """Barcha maydonlarga dizayn klasslarini qo'shadi."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            w = f.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs.setdefault("class", "check")
            elif isinstance(w, forms.FileInput):
                w.attrs.setdefault("class", "file-input")
            else:
                w.attrs.setdefault("class", "input")
                if not isinstance(w, forms.Select):
                    w.attrs.setdefault("placeholder", _("yozing"))


class NarxnomaForm(StyledMixin, forms.ModelForm):
    class Meta:
        model = Narxnoma
        fields = ["tartib", "parametr", "tahlil_usuli", "sinov_obyekti", "obyekt_nomi", "narx", "har_namunaga",
                  "aktiv"]
        widgets = {"parametr": forms.Textarea(attrs={"rows": 3})}


def namuna_turi_choices():
    """<optgroup> ko'rinishida: Mineral o'g'it / Kimyoviy vosita."""
    groups = []
    for kat, label in Kategoriya.choices:
        groups.append((label, [(t.pk, t.nom) for t in NamunaTuri.objects.filter(kategoriya=kat, aktiv=True)]))
    return [("", _("Tanlang"))] + groups


def tekshir_fayl(f):
    if f.size > MAX_FAYL_MB * 1024 * 1024:
        raise forms.ValidationError(_("Fayl hajmi %(mb)s MB dan oshmasligi kerak") % {"mb": MAX_FAYL_MB})
    if not f.name.lower().endswith(RUXSAT_KENGAYTMALAR):
        raise forms.ValidationError(_("Ruxsat etilgan formatlar: PDF, JPG, PNG, Word, Excel"))
    return f


class ArizaForm(StyledMixin, forms.ModelForm):
    """Uch xil ariza turi uchun bitta forma; maydonlar turiga qarab majburiy bo'ladi."""

    invoys = forms.FileField(label=_("Invoys"), required=False)
    analiz = forms.FileField(label=_("Analiz sertifikati"), required=False)
    guvohnoma = forms.FileField(label=_("Guvohnoma"), required=False)
    qoshimcha = forms.FileField(label=_("Qo'shimcha hujjatlar"), required=False)

    HUJJAT_MAYDONLARI = ["invoys", "analiz", "guvohnoma", "qoshimcha"]

    class Meta:
        model = Ariza
        fields = ["turi", "inn", "buyurtmachi_nomi", "fish", "telefon", "namuna_soni", "namuna_turi",
                  "namuna_nomi", "partiya_raqami", "invoys_raqami", "chegara_maskani"] + REKVIZIT_MAYDONLARI
        labels = {"inn": _("INN / JSHSHIR")}

    def __init__(self, *args, user=None, saqlangan=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Oldingi urinishda yuklangan (vaqtincha saqlangan) fayllar: {turi: {"path":..., "nom":...}}
        self.saqlangan = saqlangan or {}
        self.fields["namuna_turi"].choices = namuna_turi_choices()
        self.fields["namuna_soni"].widget.attrs.update({"min": 1, "max": 50})
        for name in self.Meta.fields:
            if name != "turi":
                self.fields[name].required = False  # turiga qarab clean() da tekshiriladi
        # mijozning profilidan oldindan to'ldirish
        if user is not None and not self.is_bound and not self.instance.pk:
            self.initial.setdefault("fish", user.fish)
            self.initial.setdefault("telefon", user.telefon)
            self.initial.setdefault("inn", user.inn or user.pinfl)
            self.initial.setdefault("buyurtmachi_nomi", user.tashkilot_nomi)

    def turi(self):
        return self.data.get("turi") or self.initial.get("turi") or ArizaTuri.IMPORTYOR

    def clean(self):
        data = super().clean()
        turi = data.get("turi")
        if not turi:
            return data
        for name in ARIZA_MAYDONLARI[turi]["majburiy"]:
            if data.get(name) in (None, ""):
                self.add_error(name, _("Bu maydon to'ldirilishi shart"))
        if data.get("namuna_soni") is not None and not 1 <= data["namuna_soni"] <= 50:
            self.add_error("namuna_soni", _("Namuna soni 1 dan 50 gacha bo'lishi kerak"))
        inn = (data.get("inn") or "").strip()
        if inn:
            if not inn.isdigit():
                self.add_error("inn", _("Faqat raqamlar kiritilishi kerak"))
            elif turi == ArizaTuri.IXTIYORIY and len(inn) != 14:
                self.add_error("inn", _("JSHSHIR 14 ta raqamdan iborat bo'lishi kerak"))
            elif turi != ArizaTuri.IXTIYORIY and len(inn) != 9:
                self.add_error("inn", _("INN 9 ta raqamdan iborat bo'lishi kerak"))
        # turiga tegishli bo'lmagan maydonlarni tozalash
        ruxsat = set(ARIZA_MAYDONLARI[turi]["majburiy"] + ARIZA_MAYDONLARI[turi]["ixtiyoriy"])
        for name in ["buyurtmachi_nomi", "namuna_nomi", "partiya_raqami", "invoys_raqami", "chegara_maskani"]:
            if name not in ruxsat:
                data[name] = ""
        # hujjatlar
        zarur = ZARUR_HUJJATLAR[turi]
        mavjud = set(self.instance.hujjatlar.values_list("turi", flat=True)) if self.instance.pk else set()
        for name in self.HUJJAT_MAYDONLARI:
            f = data.get(name)
            if f:
                try:
                    tekshir_fayl(f)
                except forms.ValidationError as e:
                    self.add_error(name, e)
            elif name in zarur and name not in mavjud and name not in self.saqlangan:
                self.add_error(name, _("Hujjatni yuklang"))
        return data

    def save_hujjatlar(self, ariza):
        """Vaqtincha saqlangan fayllarni arizaga biriktiradi. Bir turdagi eski hujjat yangisi bilan almashadi."""
        from django.core.files import File
        from django.core.files.storage import default_storage

        for name, info in self.saqlangan.items():
            if not default_storage.exists(info["path"]):
                continue
            for eski in ariza.hujjatlar.filter(turi=name):
                eski.fayl.delete(save=False)
                eski.delete()
            with default_storage.open(info["path"], "rb") as fh:
                ArizaHujjat.objects.create(ariza=ariza, turi=name, fayl=File(fh, name=info["nom"]))
            default_storage.delete(info["path"])


class NamunaQabulForm(StyledMixin, forms.ModelForm):
    """Namuna qabul qiluvchi har bir namuna uchun to'ldiradi."""

    class Meta:
        model = Namuna
        fields = ["nomi", "tavsifi", "tasir_etuvchi_modda", "namuna_olgan", "ogirligi"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nomi"].required = True
        self.fields["namuna_olgan"].required = True


NamunaFormSet = forms.modelformset_factory(Namuna, form=NamunaQabulForm, extra=0)


class RadForm(forms.Form):
    sabab = forms.CharField(label=_("Rad etish sababi"), max_length=500,
                            widget=forms.Textarea(attrs={"rows": 3, "class": "input"}))


class RekvizitForm(StyledMixin, forms.ModelForm):
    """Buxgalter shartnoma uchun buyurtmachi rekvizitlarini to'g'irlaydi."""

    class Meta:
        model = Ariza
        fields = ["buyurtmachi_nomi", "inn", "telefon", "manzil", "rahbar", "hisob_raqam", "bank", "mfo", "oked"]


class TolovForm(StyledMixin, forms.Form):
    summa = forms.DecimalField(label=_("Summa, so'm"), min_value=1, max_digits=16, decimal_places=2)
    usul = forms.ChoiceField(label=_("To'lov usuli"), choices=[])
    sana = forms.DateField(label=_("To'lov sanasi"),
                           widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"))
    izoh = forms.CharField(label=_("Izoh (to'lov topshiriqnomasi №)"), max_length=255, required=False)

    def __init__(self, *args, qoldiq=None, **kwargs):
        from .models import Tolov

        super().__init__(*args, **kwargs)
        self.fields["usul"].choices = Tolov.Usul.choices
        self.qoldiq = qoldiq

    def clean_summa(self):
        v = self.cleaned_data["summa"]
        if self.qoldiq is not None and v > self.qoldiq:
            raise forms.ValidationError(_("Summa qoldiqdan (%(q)s so'm) oshmasligi kerak") % {"q": self.qoldiq})
        return v


# ---------------------------------------------------------------------------
# 4-bosqich: xulosa (sinov bayonnomasi)
# ---------------------------------------------------------------------------
from .models import Xulosa, XulosaNatija  # noqa: E402


class XulosaForm(StyledMixin, forms.ModelForm):
    ogirligi = forms.CharField(label=_("Og'irligi / hajmi"), max_length=50, required=False)
    tavsifi = forms.CharField(label=_("Namuna tavsifi"), max_length=500, required=False)

    class Meta:
        model = Xulosa
        fields = ["sinov_sanasi", "dalolatnoma", "sinov_joyi", "harorat", "namlik", "tasdiqlagan",
                  "bosh_agrokimyogar", "yetakchi_agrokimyogar"]
        widgets = {"sinov_sanasi": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sinov_sanasi"] = forms.DateField(
            label=_("Sinov o'tkazilgan sana"),
            widget=forms.DateInput(attrs={"type": "date", "class": "input"}, format="%Y-%m-%d"))
        if self.instance.pk and self.instance.sinov_sanasi:
            self.initial["sinov_sanasi"] = timezone.localtime(self.instance.sinov_sanasi).date()
        nam = self.instance.namuna
        self.initial.setdefault("ogirligi", nam.ogirligi)
        self.initial.setdefault("tavsifi", nam.tavsifi)
        for name in ("tasdiqlagan", "bosh_agrokimyogar"):
            self.fields[name].required = True

    def save(self, commit=True):
        from datetime import datetime, time

        x = super().save(commit=False)
        x.sinov_sanasi = timezone.make_aware(datetime.combine(self.cleaned_data["sinov_sanasi"], time(12, 0)))
        nam = x.namuna
        nam.ogirligi = self.cleaned_data.get("ogirligi", "")
        nam.tavsifi = self.cleaned_data.get("tavsifi", "")
        if commit:
            x.save()
            nam.save(update_fields=["ogirligi", "tavsifi"])
        return x


class NatijaForm(forms.ModelForm):
    class Meta:
        model = XulosaNatija
        fields = ["korsatkich", "meyor", "natija", "sinov_usuli", "muvofiqlik"]
        widgets = {
            "korsatkich": forms.Textarea(attrs={"rows": 2, "class": "input"}),
            "meyor": forms.TextInput(attrs={"class": "input"}),
            "natija": forms.TextInput(attrs={"class": "input"}),
            "sinov_usuli": forms.TextInput(attrs={"class": "input"}),
            "muvofiqlik": forms.TextInput(attrs={"class": "input", "list": "muvofiqlik-list"}),
        }


NatijaFormSet = forms.inlineformset_factory(Xulosa, XulosaNatija, form=NatijaForm, extra=0, can_delete=True)
