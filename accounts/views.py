from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from core.listing import Column, Filters, list_page
from core.permissions import SA, role_required

from django.contrib.auth import login

from .forms import LoginForm, RoyxatForm, XodimForm
from .models import STAFF_ROLES, Role, User


class LoginView(auth_views.LoginView):
    template_name = "auth/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True


def royxatdan_otish(request):
    if request.user.is_authenticated:
        return redirect("bosh")
    form = RoyxatForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, _("Ro'yxatdan o'tdingiz. Endi ariza yuborishingiz mumkin."))
        return redirect("ariza_yangi")
    return render(request, "auth/royxat.html", {"form": form})


def onaid_login(request):
    """OneID orqali kirish — OneID kalitlari olingach ulanadi."""
    messages.info(request, _("OneID orqali kirish tez orada ishga tushadi."))
    return redirect("login")


@role_required(SA)
def xodim_list(request):
    qs = User.objects.filter(role__in=STAFF_ROLES).order_by("-date_joined")
    cols = [
        Column(_("Rol"), "get_role_display", "bold"),
        Column(_("F.I.SH."), "fish"),
        Column(_("Login"), "username"),
        Column(_("Telefon"), "telefon"),
        Column(_("Xodim lavozimi"), "lavozim"),
        Column(_("Yaratilgan vaqt"), "date_joined", "datetime"),
        Column(_("Faol"), lambda o: _("Faol") if o.is_active else _("Nofaol"), "badge",
               badge=lambda o: "green" if o.is_active else "grey"),
        Column(_("Amallar"), lambda o: [(_("Tahrirlash"), reverse("xodim_edit", args=[o.pk]), "edit", ""),
                                         (_("Parolni tiklash"), reverse("parol_tiklash", args=[o.pk]), "key",
                                          "post danger")], "actions", excel=False),
    ]
    f = Filters(search_fields=["fish", "username", "telefon", "lavozim"], date_field="date_joined",
                holat_field="role", holat_choices=[(r, l) for r, l in Role.choices if r in STAFF_ROLES])
    return list_page(request, title=_("Xodimlar"), qs=qs, columns=cols, filters=f, add_url=reverse("xodim_add"))


@role_required(SA)
def xodim_form(request, pk=None):
    obj = get_object_or_404(User, pk=pk) if pk else None
    form = XodimForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        from core.models import NazoratTarixi

        ozgarish = []
        for name in form.changed_data:
            if name == "parol":
                ozgarish.append(_("parol o'zgartirildi"))
                continue
            f = form.fields[name]
            eski, yangi = form.initial.get(name), form.cleaned_data.get(name)
            if name == "role":
                eski, yangi = dict(f.choices).get(eski, eski), dict(f.choices).get(yangi, yangi)
            ozgarish.append(f"{f.label}: {eski if eski not in (None, '') else '—'} → {yangi if yangi not in (None, '') else '—'}")
        user = form.save()
        if ozgarish or not obj:
            NazoratTarixi.yoz(request.user, NazoratTarixi.Turi.XODIM, f"{user.fish} ({user.username})",
                              (_("Yangi xodim qo'shildi: %(r)s") % {"r": user.get_role_display()}) if not obj
                              else "; ".join(ozgarish), user.pk)
        messages.success(request, _("Saqlandi"))
        return redirect("xodim_list")
    return render(request, "core/form.html", {
        "title": _("Xodim") + " — " + (_("Tahrirlash") if obj else _("Qo'shish")),
        "form": form, "back": reverse("xodim_list"),
    })


# ---------------------------------------------------------------------------
# Buyurtmachilar (faqat Super admin) va parollarni tiklash
# Parollar shifrlangan (hash) holda saqlanadi — ularni hech kim, hatto Super admin ham ko'ra olmaydi.
# ---------------------------------------------------------------------------
import secrets  # noqa: E402

from django import forms  # noqa: E402
from django.contrib.auth import update_session_auth_hash  # noqa: E402
from django.contrib.auth.decorators import login_required  # noqa: E402
from django.contrib.auth.forms import SetPasswordForm  # noqa: E402
from django.core.cache import cache  # noqa: E402
from django.db.models import Count  # noqa: E402
from django.views.decorators.http import require_POST  # noqa: E402

from core.models import NazoratTarixi  # noqa: E402

from .forms import normalize_phone  # noqa: E402


@role_required(SA)
def buyurtmachi_list(request):
    qs = User.objects.filter(role=Role.MIJOZ, is_superuser=False).annotate(arizalar_soni=Count("arizalar")) \
        .order_by("-date_joined")
    cols = [
        Column(_("F.I.SH."), "fish", "bold", url=lambda o: reverse("ariza_list") + f"?q={o.username}"),
        Column(_("Login (telefon)"), "username"),
        Column(_("Tashkilot nomi"), "tashkilot_nomi"),
        Column(_("INN / JSHSHIR"), lambda o: o.inn or o.pinfl),
        Column(_("Arizalar soni"), "arizalar_soni"),
        Column(_("Telegram"), lambda o: _("Ulangan") if o.telegram_chat_id else "—"),
        Column(_("Oxirgi kirish"), "last_login", "datetime"),
        Column(_("Ro'yxatdan o'tgan"), "date_joined", "datetime"),
        Column(_("Faol"), lambda o: _("Faol") if o.is_active else _("Nofaol"), "badge",
               badge=lambda o: "green" if o.is_active else "grey"),
        Column(_("Amallar"), lambda o: [(_("Parolni tiklash"), reverse("parol_tiklash", args=[o.pk]), "key",
                                         "post danger")], "actions", excel=False),
    ]
    f = Filters(search_fields=["fish", "username", "telefon", "tashkilot_nomi", "inn", "pinfl"],
                date_field="date_joined")
    return list_page(request, title=_("Buyurtmachilar"), qs=qs, columns=cols, filters=f,
                     stats=lambda q: [(_("Jami buyurtmachilar"), q.count(), ""),
                                      (_("Telegram ulangan"), q.exclude(telegram_chat_id="").count(), "")])


@require_POST
@role_required(SA)
def parol_tiklash(request, pk):
    u = get_object_or_404(User, pk=pk, is_superuser=False)
    vaqtinchalik = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz23456789") for _i in range(8))
    u.set_password(vaqtinchalik)
    u.parol_almashtirish = True
    u.save()
    NazoratTarixi.yoz(request.user, NazoratTarixi.Turi.PAROL, f"{u.fish or u.username} ({u.username})",
                      _("Super admin vaqtinchalik parol berdi"), obyekt_id=u.pk)
    orqaga = reverse("buyurtmachi_list") if u.role == Role.MIJOZ else reverse("xodim_list")
    return render(request, "auth/parol_berildi.html", {"title": _("Parol tiklandi"), "u": u,
                                                       "parol": vaqtinchalik, "orqaga": orqaga})


class _Parol(SetPasswordForm):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["new_password1"].label = _("Yangi parol")
        self.fields["new_password2"].label = _("Yangi parolni takrorlang")
        for f in self.fields.values():
            f.widget.attrs.update({"class": "input"})
            f.help_text = ""


@login_required
def parol_almashtirish(request):
    form = _Parol(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        u = form.save(commit=False)
        u.parol_almashtirish = False
        u.save()
        update_session_auth_hash(request, u)
        messages.success(request, _("Parolingiz o'zgartirildi"))
        return redirect("bosh")
    return render(request, "auth/parol_almashtirish.html", {"form": form, "majburiy": request.user.parol_almashtirish})


class _TelefonForm(forms.Form):
    telefon = forms.CharField(label=_("Telefon raqami (login)"), max_length=20,
                              widget=forms.TextInput(attrs={"class": "input", "placeholder": "+998 90 123 45 67"}))


class _KodForm(forms.Form):
    kod = forms.CharField(label=_("SMS kod"), max_length=6, widget=forms.TextInput(
        attrs={"class": "input", "inputmode": "numeric", "autocomplete": "one-time-code"}))
    parol1 = forms.CharField(label=_("Yangi parol"), min_length=6, widget=forms.PasswordInput(attrs={"class": "input"}))
    parol2 = forms.CharField(label=_("Yangi parolni takrorlang"), widget=forms.PasswordInput(attrs={"class": "input"}))

    def clean(self):
        d = super().clean()
        if d.get("parol1") and d.get("parol1") != d.get("parol2"):
            self.add_error("parol2", _("Parollar mos kelmadi"))
        return d


KOD_MUDDATI = 600  # 10 daqiqa
KOD_URINISH = 5


def parol_unutdim(request):
    """1) telefon -> SMS kod; 2) kod + yangi parol. SMS (Eskiz) ulanmagan bo'lsa — administratorga murojaat."""
    from core.xabarnoma import sms_sozlangan, sms_yubor

    tel = request.session.get("tiklash_tel")
    bosqich = "kod" if tel and request.GET.get("qayta") != "1" else "telefon"
    form = _KodForm(request.POST or None) if bosqich == "kod" else _TelefonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if bosqich == "telefon":
            tel = normalize_phone(form.cleaned_data["telefon"])
            if not sms_sozlangan():
                messages.error(request, _("SMS xizmati hali ulanmagan. Parolni tiklash uchun markaz "
                                          "administratoriga murojaat qiling."))
                return redirect("parol_unutdim")
            if tel and cache.get(f"tiklash_kutish:{tel}"):
                messages.error(request, _("Kod yaqinda yuborildi. 1 daqiqadan so'ng qayta urinib ko'ring."))
                return redirect("parol_unutdim")
            u = User.objects.filter(username=tel, is_active=True, is_superuser=False).first() if tel else None
            if u:
                kod = f"{secrets.randbelow(10 ** 6):06d}"
                cache.set(f"tiklash:{tel}", {"kod": kod, "urinish": 0}, KOD_MUDDATI)
                cache.set(f"tiklash_kutish:{tel}", 1, 60)
                sms_yubor(tel, _("Agrokimyo va tuproq tahlili markazi: parolni tiklash kodi %(k)s. "
                                 "Kodni hech kimga bermang.") % {"k": kod}, user=u)
            # raqam ro'yxatda bor-yo'qligini oshkor qilmaymiz
            request.session["tiklash_tel"] = tel or ""
            messages.info(request, _("Agar bu raqam ro'yxatdan o'tgan bo'lsa, unga SMS kod yuborildi."))
            return redirect("parol_unutdim")
        malumot = cache.get(f"tiklash:{tel}")
        if not malumot or malumot["urinish"] >= KOD_URINISH:
            cache.delete(f"tiklash:{tel}")
            messages.error(request, _("Kod eskirgan yoki urinishlar soni tugagan. Qaytadan kod oling."))
            return redirect(reverse("parol_unutdim") + "?qayta=1")
        if not secrets.compare_digest(malumot["kod"], form.cleaned_data["kod"].strip()):
            malumot["urinish"] += 1
            cache.set(f"tiklash:{tel}", malumot, KOD_MUDDATI)
            form.add_error("kod", _("Kod noto'g'ri"))
        else:
            u = User.objects.get(username=tel)
            u.set_password(form.cleaned_data["parol1"])
            u.parol_almashtirish = False
            u.save()
            cache.delete(f"tiklash:{tel}")
            request.session.pop("tiklash_tel", None)
            NazoratTarixi.yoz(None, NazoratTarixi.Turi.PAROL, f"{u.fish or u.username} ({u.username})",
                              _("Foydalanuvchi parolni SMS kod orqali tikladi"), obyekt_id=u.pk)
            messages.success(request, _("Parol yangilandi. Yangi parol bilan kiring."))
            return redirect("login")
    return render(request, "auth/parol_unutdim.html", {"form": form, "bosqich": bosqich, "tel": tel})
