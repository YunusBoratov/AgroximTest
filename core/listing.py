"""
Umumiy jadval (ro'yxat) infratuzilmasi: qidiruv, sana/holat filtrlari, sahifalash va Excel eksport.

Har bir sahifa `Column` ro'yxati va queryset beradi, qolganini shu modul bajaradi.
"""
from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _


@dataclass
class Column:
    title: str
    value: Callable[[Any], Any] | str
    kind: str = "text"  # text | datetime | money | badge | file | actions | bold
    excel: bool = True
    badge: Callable[[Any], str] | None = None  # obj -> css klass (badge uchun)
    url: Callable[[Any], str] | None = None
    width: str = ""

    def get(self, obj):
        if callable(self.value):
            return self.value(obj)
        val = obj
        for part in self.value.split("."):
            val = getattr(val, part, None) if val is not None else None
            if callable(val) and part.startswith("get_"):
                val = val()
        return val


@dataclass
class Filters:
    search_fields: list[str] = field(default_factory=list)
    date_field: str | None = None
    date_label: str = ""
    holat_field: str | None = None
    holat_choices: list = field(default_factory=list)
    summa_field: str | None = None
    turi_field: str | None = None  # ariza turi bo'yicha yuqori tablar


def _parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def apply_filters(request, qs, f: Filters):
    g = request.GET
    state = {"q": g.get("q", "").strip(), "dan": g.get("dan", ""), "gacha": g.get("gacha", ""),
             "holat": g.get("holat", ""), "summa": g.get("summa", ""), "turi": g.get("turi", "")}
    if state["q"] and f.search_fields:
        cond = Q()
        for fld in f.search_fields:
            cond |= Q(**{f"{fld}__icontains": state["q"]})
        qs = qs.filter(cond)
    if f.date_field:
        tz = timezone.get_current_timezone()
        d1, d2 = _parse_date(state["dan"]), _parse_date(state["gacha"])
        if d1:
            qs = qs.filter(**{f"{f.date_field}__gte": timezone.make_aware(datetime.combine(d1, time.min), tz)})
        if d2:
            qs = qs.filter(**{f"{f.date_field}__lte": timezone.make_aware(datetime.combine(d2, time.max), tz)})
    if f.holat_field and state["holat"]:
        qs = qs.filter(**{f.holat_field: state["holat"]})
    if f.summa_field and state["summa"]:
        try:
            qs = qs.filter(**{f"{f.summa_field}__gte": Decimal(state["summa"].replace(" ", ""))})
        except InvalidOperation:
            pass
    if f.turi_field and state["turi"]:
        qs = qs.filter(**{f.turi_field: state["turi"]})
    return qs, state


def excel_response(title, columns, rows):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = title[:31]
    cols = [c for c in columns if c.excel and c.kind not in ("actions", "file")]
    ws.append(["№"] + [c.title for c in cols])
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="3E7B4F")
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    for i, obj in enumerate(rows, 1):
        line = [i]
        for c in cols:
            v = c.get(obj)
            if isinstance(v, datetime):
                v = timezone.localtime(v).strftime("%d.%m.%Y %H:%M:%S")
            elif isinstance(v, Decimal):
                v = float(v)
            elif v is not None and not isinstance(v, (int, float, str)):
                v = str(v)
            line.append(v)
        ws.append(line)
    for idx, c in enumerate(["№"] + cols, 1):
        ws.column_dimensions[get_column_letter(idx)].width = 8 if idx == 1 else 22
    resp = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    fname = f"{title}_{timezone.localdate():%Y-%m-%d}.xlsx".replace(" ", "_")
    resp["Content-Disposition"] = f'attachment; filename="{fname}"'
    wb.save(resp)
    return resp


def list_page(request, *, title, qs, columns, filters: Filters, template="core/list.html",
              add_url=None, add_label=None, extra=None, turi_tabs=None, per_page=20):
    qs, state = apply_filters(request, qs, filters)
    if request.GET.get("export") == "excel":
        return excel_response(title, columns, qs)
    page = Paginator(qs, per_page).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    params.pop("export", None)
    ctx = {
        "title": title,
        "columns": columns,
        "page": page,
        "rows": [(obj, [(c, c.get(obj), c.badge(obj) if c.badge else "") for c in columns])
                 for obj in page.object_list],
        "total": page.paginator.count,
        "f": filters,
        "state": state,
        "querystring": params.urlencode(),
        "add_url": add_url,
        "add_label": add_label or _("Qo'shish"),
        "turi_tabs": turi_tabs,
    }
    if extra:
        ctx.update(extra)
    return render(request, template, ctx)
