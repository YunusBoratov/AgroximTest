from django import forms
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .models import (ARIZA_MAYDONLARI, NAMUNA_MAYDONLARI, REKVIZIT_MAYDONLARI, ZARUR_HUJJATLAR, Ariza, ArizaHujjat, ArizaTuri,
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
    """Arizaning umumiy qismi (buyurtmachi). Namunalar — NamunaBlokForm, har biri alohida."""

    class Meta:
        model = Ariza
        fields = ["turi", "inn", "buyurtmachi_nomi", "fish", "telefon", "namuna_soni",
                  "chegara_maskani"] + REKVIZIT_MAYDONLARI
        labels = {"inn": _("INN / JSHSHIR")}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["namuna_soni"].widget.attrs.update({"min": 1, "max": MAX_NAMUNA})
        for name in self.Meta.fields:
            if name != "turi":
                self.fields[name].required = False  # turiga qarab clean() da tekshiriladi
        # mijozning profilidan oldindan to'ldirish
        if user is not None and not self.instance.pk:
            # profildagi INN (tashkilot) yoki JSHSHIR (jismoniy shaxs): JS ariza turiga mosini qo'yadi
            self.fields["inn"].widget.attrs.update({"data-inn": user.inn or "", "data-pinfl": user.pinfl or ""})
        if user is not None and not self.is_bound and not self.instance.pk:
            self.initial.setdefault("fish", user.fish)
            self.initial.setdefault("telefon", user.telefon)
            self.initial.setdefault("inn", user.inn or user.pinfl)
            self.initial.setdefault("buyurtmachi_nomi", user.tashkilot_nomi)
            if user.pinfl and not user.inn:  # jismoniy shaxs — JSHSHIR bilan ishlaydigan tur
                self.initial.setdefault("turi", ArizaTuri.IXTIYORIY)

    def turi(self):
        return self.data.get("turi") or self.initial.get("turi") or self.instance.turi or ArizaTuri.IMPORTYOR

    def clean(self):
        data = super().clean()
        turi = data.get("turi")
        if not turi:
            return data
        for name in ARIZA_MAYDONLARI[turi]["majburiy"]:
            if data.get(name) in (None, ""):
                self.add_error(name, _("Bu maydon to'ldirilishi shart"))
        if data.get("namuna_soni") is not None and not 1 <= data["namuna_soni"] <= MAX_NAMUNA:
            self.add_error("namuna_soni", _("Namuna soni 1 dan %(n)s gacha bo'lishi kerak") % {"n": MAX_NAMUNA})
        inn = (data.get("inn") or "").strip()
        if inn:
            if not inn.isdigit():
                self.add_error("inn", _("Faqat raqamlar kiritilishi kerak"))
            elif turi == ArizaTuri.IXTIYORIY and len(inn) != 14:
                self.add_error("inn", _("JSHSHIR 14 ta raqamdan iborat bo'lishi kerak"))
            elif turi != ArizaTuri.IXTIYORIY and len(inn) != 9:
                self.add_error("inn", _("INN 9 ta raqamdan iborat bo'lishi kerak"))
        ruxsat = set(ARIZA_MAYDONLARI[turi]["majburiy"] + ARIZA_MAYDONLARI[turi]["ixtiyoriy"])
        for name in ["buyurtmachi_nomi", "chegara_maskani"]:
            if name not in ruxsat:
                data[name] = ""
        return data


MAX_NAMUNA = 50


class NamunaBlokForm(StyledMixin, forms.Form):
    """Arizadagi bitta namuna: turi, partiya, nomi, invoys raqami va hujjatlari."""

    kategoriya = forms.ChoiceField(label=_("Namuna turi"), required=False)
    partiya_raqami = forms.CharField(label=_("Partiya raqami (LOT)"), max_length=100, required=False)
    nomi = forms.CharField(label=_("Namuna nomi"), max_length=255, required=False)
    invoys_raqami = forms.CharField(label=_("Invoys raqami"), max_length=100, required=False)
    invoys = forms.FileField(label=_("Invoys"), required=False)
    analiz = forms.FileField(label=_("Analiz sertifikati"), required=False)
    guvohnoma = forms.FileField(label=_("Guvohnoma"), required=False)
    qoshimcha = forms.FileField(label=_("Qo'shimcha hujjatlar"), required=False)

    MAYDONLAR = ["kategoriya", "partiya_raqami", "nomi", "invoys_raqami"]
    HUJJAT_MAYDONLARI = ["invoys", "analiz", "guvohnoma", "qoshimcha"]

    def __init__(self, *args, turi=None, tartib=1, mavjud=None, saqlangan=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.turi = turi or ArizaTuri.IMPORTYOR
        self.tartib = tartib
        self.mavjud = mavjud or {}  # {hujjat turi: ArizaHujjat} — oldin yuklangan
        self.saqlangan = saqlangan if saqlangan is not None else {}  # vaqtincha saqlangan fayllar
        self.fields["kategoriya"].choices = [("", _("Tanlang"))] + list(Kategoriya.choices)

    def clean(self):
        data = super().clean()
        cfg = NAMUNA_MAYDONLARI[self.turi]
        for name in cfg["majburiy"]:
            if not data.get(name):
                self.add_error(name, _("Bu maydon to'ldirilishi shart"))
        for name in self.MAYDONLAR:
            if name not in cfg["majburiy"] + cfg["ixtiyoriy"]:
                data[name] = ""
        zarur = ZARUR_HUJJATLAR[self.turi]
        for name in self.HUJJAT_MAYDONLARI:
            f = data.get(name)
            if f:
                try:
                    tekshir_fayl(f)
                except forms.ValidationError as e:
                    self.add_error(name, e)
            elif name in zarur and name not in self.mavjud and name not in self.saqlangan:
                self.add_error(name, _("Hujjatni yuklang"))
        return data

    def save_hujjatlar(self, ariza, blok):
        """Vaqtincha saqlangan fayllarni namunaga biriktiradi. Bir turdagi eski hujjat yangisi bilan almashadi."""
        from django.core.files import File
        from django.core.files.storage import default_storage

        for name, info in self.saqlangan.items():
            if not default_storage.exists(info["path"]):
                continue
            eski = ariza.hujjatlar.filter(turi=name, ariza_namuna=blok)
            if ariza.arizanamunalar.count() == 1:  # eski (umumiy) hujjat ham almashadi
                eski = ariza.hujjatlar.filter(turi=name).filter(
                    models.Q(ariza_namuna=blok) | models.Q(ariza_namuna__isnull=True))
            for h in eski:
                h.fayl.delete(save=False)
                h.delete()
            with default_storage.open(info["path"], "rb") as fh:
                ArizaHujjat.objects.create(ariza=ariza, ariza_namuna=blok, turi=name, fayl=File(fh, name=info["nom"]))
            default_storage.delete(info["path"])


class ArizaToplam:
    """Ariza formasi + namuna soniga teng bloklar."""

    def __init__(self, data=None, files=None, instance=None, user=None, saqlangan=None):
        self.form = ArizaForm(data, files, instance=instance, user=user)
        self.instance = instance
        self.saqlangan = saqlangan or {}
        turi = self.form.turi()
        mavjud_bloklar = list(instance.arizanamunalar.all()) if instance and instance.pk else []
        if data is not None:
            try:
                n = int(data.get("namuna_soni") or 1)
            except (TypeError, ValueError):
                n = 1
        else:
            n = len(mavjud_bloklar) or (instance.namuna_soni if instance and instance.pk else 1)
        n = max(1, min(n, MAX_NAMUNA))
        umumiy = {}
        if instance and instance.pk:
            for h in instance.hujjatlar.filter(ariza_namuna__isnull=True):
                umumiy[h.turi] = h
        self.bloklar = []
        for i in range(n):
            blok = mavjud_bloklar[i] if i < len(mavjud_bloklar) else None
            initial = {k: getattr(blok, k) for k in NamunaBlokForm.MAYDONLAR} if blok else {}
            mavjud = dict(umumiy)
            if blok:
                mavjud.update({h.turi: h for h in blok.hujjatlar.all()})
            self.bloklar.append(NamunaBlokForm(
                data, files, prefix=f"s{i}", initial=initial, turi=turi, tartib=i + 1, mavjud=mavjud,
                saqlangan=self.saqlangan.setdefault(f"s{i}", {})))
        self.andoza = NamunaBlokForm(prefix="s__i__", turi=turi, tartib="__n__")  # JS uchun andoza

    def is_valid(self):
        natija = self.form.is_valid()
        for b in self.bloklar:
            natija = b.is_valid() and natija
        return natija

    @property
    def errors(self):
        return self.form.errors or any(b.errors for b in self.bloklar)

    def save(self, user=None):
        from .models import ArizaNamuna

        ariza = self.form.save(commit=False)
        if user is not None and not ariza.mijoz_id:
            ariza.mijoz = user
        ariza.namuna_soni = len(self.bloklar)
        ariza.save()
        eski = list(ariza.arizanamunalar.all())
        for i, b in enumerate(self.bloklar):
            blok = eski[i] if i < len(eski) else ArizaNamuna(ariza=ariza)
            blok.tartib = i + 1
            for k in NamunaBlokForm.MAYDONLAR:
                setattr(blok, k, b.cleaned_data.get(k) or "")
            blok.save()
            b.save_hujjatlar(ariza, blok)
        for blok in eski[len(self.bloklar):]:
            for h in blok.hujjatlar.all():
                h.fayl.delete(save=False)
            blok.delete()
        ariza.namunalar_yangila()
        return ariza


class NamunaQabulForm(StyledMixin, forms.ModelForm):
    """Namuna qabul qiluvchi har bir namuna uchun to'ldiradi."""

    class Meta:
        model = Namuna
        fields = ["namuna_turi", "nomi", "tavsifi", "tasir_etuvchi_modda", "namuna_olgan", "ogirligi"]

    def __init__(self, *args, kategoriya=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not kategoriya and self.instance.pk:
            kategoriya = (self.instance.ariza_namuna.kategoriya if self.instance.ariza_namuna_id
                          else self.instance.namuna_turi.kategoriya if self.instance.namuna_turi_id
                          else self.instance.ariza.kategoriya)
        qs = NamunaTuri.objects.filter(aktiv=True)
        if kategoriya:
            qs = qs.filter(kategoriya=kategoriya)
        self.fields["namuna_turi"].queryset = qs
        self.fields["namuna_turi"].empty_label = _("Tanlang")
        self.fields["namuna_turi"].required = True
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


def masul_xodimlar(kategoriya):
    """Laboratoriyaning faol mas'ul xodimlari."""
    from accounts.models import Role, User

    role = {"mineral": Role.MASUL_MINERAL, "kimyoviy": Role.MASUL_KIMYO}.get(kategoriya)
    return User.objects.filter(role=role, is_active=True).order_by("fish", "username")


class XulosaForm(StyledMixin, forms.ModelForm):
    """Mudir xulosani tasdiqlashda to'ldiradi (barcha maydonlar majburiy, tavsif ixtiyoriy)."""

    ogirligi = forms.CharField(label=_("Og'irligi / hajmi"), max_length=50)
    tavsifi = forms.CharField(label=_("Namuna tavsifi"), max_length=500, required=False)
    bosh_agrokimyogar = forms.ChoiceField(label=_("Bosh agrokimyogar"))
    yetakchi_agrokimyogar = forms.ChoiceField(label=_("Yetakchi agrokimyogar"))

    class Meta:
        model = Xulosa
        # sinov sanasi qo'lda kiritilmaydi: tasdiqlangan paytdagi sana va vaqt avtomatik yoziladi
        fields = ["dalolatnoma", "sinov_joyi", "harorat", "namlik", "bosh_agrokimyogar", "yetakchi_agrokimyogar"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nam = self.instance.namuna
        self.initial.setdefault("ogirligi", nam.ogirligi)
        self.initial.setdefault("tavsifi", nam.tavsifi)
        ismlar = [("", _("Tanlang"))] + [(u.fish or u.username, u.fish or u.username)
                                         for u in masul_xodimlar(nam.kategoriya)]
        for name in ("bosh_agrokimyogar", "yetakchi_agrokimyogar"):
            self.fields[name].choices = ismlar
            self.fields[name].widget.attrs["class"] = "input"
        for name in ("dalolatnoma", "sinov_joyi", "harorat", "namlik"):
            self.fields[name].required = True

    def save(self, commit=True):
        x = super().save(commit=False)
        nam = x.namuna
        nam.ogirligi = self.cleaned_data.get("ogirligi", "")
        nam.tavsifi = self.cleaned_data.get("tavsifi", "")
        if commit:
            x.save()
            nam.save(update_fields=["ogirligi", "tavsifi"])
        return x


class NatijaForm(forms.ModelForm):
    """Mas'ul xodim faqat sinov natijasi va sinov usulini kiritadi (ikkalasi majburiy).
    Me'yoriy qiymatni mudir tasdiqlashda kiritadi; muvofiqlik qarori vaqtincha ishlatilmaydi."""

    class Meta:
        model = XulosaNatija
        fields = ["natija", "sinov_usuli"]
        widgets = {
            "natija": forms.TextInput(attrs={"class": "input"}),
            "sinov_usuli": forms.TextInput(attrs={"class": "input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in self.fields.values():
            f.required = True
            f.error_messages["required"] = _("To'ldirilishi shart")


NatijaFormSet = forms.modelformset_factory(XulosaNatija, form=NatijaForm, extra=0, can_delete=False)


class MeyorForm(forms.ModelForm):
    """Mudir tasdiqlashda har bir ko'rsatkichning me'yoriy qiymatini kiritadi (majburiy)."""

    class Meta:
        model = XulosaNatija
        fields = ["meyor"]
        widgets = {"meyor": forms.TextInput(attrs={"class": "input"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["meyor"].required = True
        self.fields["meyor"].error_messages["required"] = _("To'ldirilishi shart")


MeyorFormSet = forms.modelformset_factory(XulosaNatija, form=MeyorForm, extra=0, can_delete=False)


class QaytarishForm(forms.Form):
    topshiriq = forms.ModelChoiceField(label=_("Kimga qaytarilsin"), queryset=None, empty_label=_("Tanlang"),
                                       widget=forms.Select(attrs={"class": "input"}))
    izoh = forms.CharField(label=_("Nima tuzatilishi kerak"), widget=forms.Textarea(attrs={"rows": 3, "class": "input"}))

    def __init__(self, *args, namuna=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["topshiriq"].queryset = namuna.topshiriqlar.select_related("masul") if namuna else None
        self.fields["topshiriq"].label_from_instance = lambda t: f"{t.masul} — {t.natijalar.count()} " + str(_("ko'rsatkich"))
