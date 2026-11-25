"""Nazorat tarixi — faqat Super admin. Yozuvlarni hech kim o'zgartira yoki o'chira olmaydi."""
from django.db.models import Count
from django.utils.translation import gettext as _

from .listing import Column, Filters, list_page
from .models import NazoratTarixi
from .permissions import SA, role_required


@role_required(SA)
def nazorat_tarixi(request):
    qs = NazoratTarixi.objects.all()
    if request.GET.get("obyekt_id"):
        qs = qs.filter(obyekt_id=request.GET["obyekt_id"])
    cols = [
        Column(_("Vaqt"), "vaqt", "datetime"),
        Column(_("Harakat turi"), "get_turi_display", "bold"),
        Column(_("Xodim"), "user_nomi"),
        Column(_("Obyekt"), "obyekt"),
        Column(_("Tafsilot"), "tafsilot", width="38%"),
    ]
    f = Filters(search_fields=["user_nomi", "obyekt", "tafsilot"], date_field="vaqt", holat_field="turi",
                holat_choices=NazoratTarixi.Turi.choices)

    def stats(q):
        nomlar = dict(NazoratTarixi.Turi.choices)
        return [(_("Jami yozuvlar"), q.count(), "")] + [
            (nomlar.get(r["turi"], r["turi"]), r["n"], "red" if r["turi"] == "tolov_ochirish" else "")
            for r in q.values("turi").annotate(n=Count("id")).order_by("-n")]

    return list_page(request, title=_("Nazorat tarixi"), qs=qs, columns=cols, filters=f, stats=stats, per_page=50)
