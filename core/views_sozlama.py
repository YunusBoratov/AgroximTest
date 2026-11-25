"""Sozlamalar (Super admin va Admin): ish vaqti, kechikish muddatlari, bayram kunlari.
Har bir o'zgarish Nazorat tarixiga yoziladi."""
from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _, gettext_lazy as _l
from django.views.decorators.http import require_POST

from .models import Bayram, NazoratTarixi, Sozlama
from .permissions import AD, role_required

HAFTA = [("0", _l("Dushanba")), ("1", _l("Seshanba")), ("2", _l("Chorshanba")), ("3", _l("Payshanba")),
         ("4", _l("Juma")), ("5", _l("Shanba")), ("6", _l("Yakshanba"))]


class SozlamaForm(forms.ModelForm):
    ish_kunlari_tanlov = forms.MultipleChoiceField(label=_l("Ish kunlari"), choices=HAFTA,
                                                   widget=forms.CheckboxSelectMultiple)

    class Meta:
        model = Sozlama
        fields = ["ish_boshlanishi", "ish_tugashi"] + Sozlama.MUDDAT_MAYDONLARI
        widgets = {"ish_boshlanishi": forms.TimeInput(attrs={"type": "time"}, format="%H:%M"),
                   "ish_tugashi": forms.TimeInput(attrs={"type": "time"}, format="%H:%M")}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["ish_kunlari_tanlov"].initial = sorted(str(x) for x in self.instance.ish_kunlari_list)
        for f in Sozlama.MUDDAT_MAYDONLARI:
            self.fields[f].widget.attrs["min"] = 1

    def clean(self):
        d = super().clean()
        if d.get("ish_boshlanishi") and d.get("ish_tugashi") and d["ish_boshlanishi"] >= d["ish_tugashi"]:
            raise forms.ValidationError(_("Ish tugashi boshlanishidan keyin bo'lishi kerak"))
        return d

    def save(self, commit=True):
        self.instance.ish_kunlari = ",".join(sorted(self.cleaned_data["ish_kunlari_tanlov"]))
        return super().save(commit)


class BayramForm(forms.ModelForm):
    class Meta:
        model = Bayram
        fields = ["sana", "nomi"]
        widgets = {"sana": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d")}


def _qiymat(obj, f):
    v = getattr(obj, f)
    return v.strftime("%H:%M") if hasattr(v, "strftime") else v


@role_required(AD)
def sozlamalar(request):
    s = Sozlama.ol()
    eski = {f: _qiymat(s, f) for f in SozlamaForm.Meta.fields + ["ish_kunlari"]}
    form = SozlamaForm(request.POST if request.method == "POST" and "sozlama" in request.POST else None, instance=s)
    bform = BayramForm(request.POST if request.method == "POST" and "bayram" in request.POST else None)
    if request.method == "POST":
        if "sozlama" in request.POST and form.is_valid():
            s = form.save()
            ozgar = [f"{s._meta.get_field(f).verbose_name}: {eski[f]} → {_qiymat(s, f)}"
                     for f in eski if str(eski[f]) != str(_qiymat(s, f))]
            if ozgar:
                NazoratTarixi.yoz(request.user, NazoratTarixi.Turi.SOZLAMA, _("Ish muddatlari"), "; ".join(ozgar))
            messages.success(request, _("Sozlamalar saqlandi"))
            return redirect("sozlamalar")
        if "bayram" in request.POST and bform.is_valid():
            b = bform.save()
            NazoratTarixi.yoz(request.user, NazoratTarixi.Turi.SOZLAMA, _("Bayram kuni"),
                              _("Qo'shildi: %(s)s %(n)s") % {"s": b.sana.strftime("%d.%m.%Y"), "n": b.nomi})
            messages.success(request, _("Bayram kuni qo'shildi"))
            return redirect("sozlamalar")
    return render(request, "core/sozlamalar.html", {
        "title": _("Sozlamalar"), "form": form, "bform": bform, "bayramlar": Bayram.objects.all()})


@require_POST
@role_required(AD)
def bayram_ochirish(request, pk):
    b = get_object_or_404(Bayram, pk=pk)
    NazoratTarixi.yoz(request.user, NazoratTarixi.Turi.SOZLAMA, _("Bayram kuni"),
                      _("O'chirildi: %(s)s %(n)s") % {"s": b.sana.strftime("%d.%m.%Y"), "n": b.nomi})
    b.delete()
    messages.success(request, _("Bayram kuni o'chirildi"))
    return redirect("sozlamalar")
