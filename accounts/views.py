from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

from core.listing import Column, Filters, list_page
from core.permissions import SA, role_required

from .forms import LoginForm, XodimForm
from .models import STAFF_ROLES, Role, User


class LoginView(auth_views.LoginView):
    template_name = "auth/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True


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
        Column(_("Tahrirlash"), lambda o: reverse("xodim_edit", args=[o.pk]), "actions", excel=False),
    ]
    f = Filters(search_fields=["fish", "username", "telefon", "lavozim"], date_field="date_joined",
                holat_field="role", holat_choices=[(r, l) for r, l in Role.choices if r in STAFF_ROLES])
    return list_page(request, title=_("Xodimlar"), qs=qs, columns=cols, filters=f, add_url=reverse("xodim_add"))


@role_required(SA)
def xodim_form(request, pk=None):
    obj = get_object_or_404(User, pk=pk) if pk else None
    form = XodimForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, _("Saqlandi"))
        return redirect("xodim_list")
    return render(request, "core/form.html", {
        "title": _("Xodim") + (f" — {_('Tahrirlash')}" if obj else f" — {_('Qo‘shish')}"),
        "form": form, "back": reverse("xodim_list"),
    })
