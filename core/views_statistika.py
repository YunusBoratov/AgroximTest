"""Statistika: kunlik / oylik / yillik kesimda asosiy ko'rsatkichlar va Excel."""
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncYear
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _

from .listing import sana_filtri
from .models import Ariza, Kategoriya, Namuna, Shartnoma, Tolov
from .permissions import AD, BX, role_required

TRUNC = {"kun": TruncDay, "oy": TruncMonth, "yil": TruncYear}


def _sana(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _kalit(v, guruh):
    if isinstance(v, datetime):
        v = timezone.localtime(v).date() if timezone.is_aware(v) else v.date()
    if guruh == "oy":
        return v.replace(day=1)
    if guruh == "yil":
        return v.replace(month=1, day=1)
    return v


def _davrlar(d1, d2, guruh):
    out, d = [], _kalit(d1, guruh)
    while d <= d2:
        out.append(d)
        if guruh == "kun":
            d += timedelta(days=1)
        elif guruh == "oy":
            d = date(d.year + d.month // 12, d.month % 12 + 1, 1)
        else:
            d = date(d.year + 1, 1, 1)
    return out


def _yorliq(d, guruh):
    if guruh == "kun":
        return d.strftime("%d.%m.%Y")
    if guruh == "oy":
        return d.strftime("%m.%Y")
    return str(d.year)


def hisobla(guruh, d1, d2, kategoriya=""):
    tz = timezone.get_current_timezone()
    tr = TRUNC[guruh]

    def guruhla(qs, field, summa=None):
        qs = sana_filtri(qs, field, d1, d2).annotate(p=tr(field, tzinfo=tz)).values("p")
        agg = {"n": Count("id")}
        if summa:
            agg["s"] = Sum(summa)
        return {_kalit(r["p"], guruh): r for r in qs.annotate(**agg).order_by("p")}

    k = kategoriya
    ar = Ariza.objects.filter(kategoriyalar__contains=k) if k else Ariza.objects.all()
    nam = Namuna.objects.filter(namuna_turi__kategoriya=k) if k else Namuna.objects.all()
    sh = Shartnoma.objects.filter(is_active=True)
    tl = Tolov.objects.all()
    if k:
        sh, tl = sh.filter(ariza__kategoriyalar__contains=k), tl.filter(shartnoma__ariza__kategoriyalar__contains=k)
    data = {
        "ariza": guruhla(ar, "created_at"),
        "rad": guruhla(ar.filter(holat=Ariza.Holat.RAD), "created_at"),
        "namuna": guruhla(nam, "qabul_vaqti"),
        "shartnoma": guruhla(sh, "created_at", "jami_summa"),
        "tolov": guruhla(tl, "sana", "summa"),
        "xulosa": guruhla(nam.filter(berilgan_vaqti__isnull=False), "berilgan_vaqti"),
    }
    if d1 is None:  # "Barchasi" (yillik): eng birinchi yozuvdan
        kalitlar = [kk for v in data.values() for kk in v]
        d1 = min(kalitlar) if kalitlar else timezone.localdate()
    rows = []
    for d in _davrlar(d1, d2, guruh):
        g = lambda key, f="n": (data[key].get(d) or {}).get(f) or 0  # noqa: E731
        rows.append({"davr": _yorliq(d, guruh), "ariza": g("ariza"), "rad": g("rad"), "namuna": g("namuna"),
                     "shartnoma": g("shartnoma"), "shartnoma_summa": Decimal(g("shartnoma", "s")),
                     "tolov_soni": g("tolov"), "tolov": Decimal(g("tolov", "s")), "xulosa": g("xulosa")})
    if guruh == "kun":
        rows.reverse()  # eng yangi kun tepada
    jami = {key: sum(r[key] for r in rows) for key in rows[0] if key != "davr"} if rows else {}
    return rows, jami


USTUNLAR = [("davr", _("Davr")), ("ariza", _("Arizalar")), ("rad", _("Rad etilgan")),
            ("namuna", _("Qabul qilingan namunalar")), ("shartnoma", _("Shartnomalar")),
            ("shartnoma_summa", _("Shartnomalar summasi")), ("tolov_soni", _("To'lovlar soni")),
            ("tolov", _("Tushgan to'lovlar")), ("xulosa", _("Berilgan xulosalar"))]


@role_required(AD, BX)
def statistika(request):
    g = request.GET
    guruh = g.get("guruh") if g.get("guruh") in TRUNC else "oy"
    bugun = timezone.localdate()
    d2 = min(_sana(g.get("gacha")) or bugun, bugun)
    d1 = _sana(g.get("dan"))
    if not d1 and guruh != "yil":
        d1 = bugun.replace(day=1) if guruh == "kun" else bugun.replace(month=1, day=1)
    if d1 and d1 > d2:
        d1 = d2
    kat = g.get("kategoriya") if g.get("kategoriya") in Kategoriya.values else ""
    rows, jami = hisobla(guruh, d1, d2, kat)
    ustunlar = [(k, str(v)) for k, v in USTUNLAR]
    if g.get("excel"):
        return _excel(ustunlar, rows, jami)
    return render(request, "core/statistika.html", {
        "title": _("Statistika"), "rows": rows, "jami": jami, "ustunlar": ustunlar,
        "guruh": guruh, "guruhlar": [("kun", _("Kunlik")), ("oy", _("Oylik")), ("yil", _("Yillik"))],
        "dan": d1.isoformat() if d1 and g.get("dan") else "", "gacha": g.get("gacha", ""),
        "kategoriya": kat, "kategoriyalar": Kategoriya.choices,
        "oraliq": f"{d1:%d.%m.%Y} — {d2:%d.%m.%Y}" if d1 else f"— {d2:%d.%m.%Y}",
    })


def _excel(ustunlar, rows, jami):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = str(_("Statistika"))[:31]
    ws.append([t for _k, t in ustunlar])
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="3E7B4F")
        c.alignment = Alignment(wrap_text=True, horizontal="center", vertical="center")
    for r in rows:
        ws.append([float(r[k]) if isinstance(r[k], Decimal) else r[k] for k, _t in ustunlar])
    ws.append([str(_("Jami"))] + [float(jami[k]) if isinstance(jami[k], Decimal) else jami[k]
                                  for k, _t in ustunlar[1:]])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    for i, col in enumerate("ABCDEFGHI"):
        ws.column_dimensions[col].width = 14 if i == 0 else 20
    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    resp["Content-Disposition"] = f'attachment; filename="Statistika_{timezone.localdate():%Y-%m-%d}.xlsx"'
    wb.save(resp)
    return resp
