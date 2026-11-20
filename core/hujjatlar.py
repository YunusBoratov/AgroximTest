"""
Hujjatlar: shartnoma (DOCX/PDF) — buyurtmachi bergan rasmiy shablon asosida.

Shablon: docs/shablonlar/shartnoma_shakli.docx (o'zbek kirill yozuvida).
"""
import copy
import io
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.utils import timezone

SHABLON_DIR = Path(settings.BASE_DIR) / "docs" / "shablonlar"

ESKI_NOM = "Республика агрокимёвий таҳлил маркази"
YANGI_NOM = "Агрокимё ва тупроқ таҳлили маркази"

OYLAR = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь", "октябрь",
         "ноябрь", "декабрь"]

_BIRLAR = ["", "бир", "икки", "уч", "тўрт", "беш", "олти", "етти", "саккиз", "тўққиз"]
_ONLAR = ["", "ўн", "йигирма", "ўттиз", "қирқ", "эллик", "олтмиш", "етмиш", "саксон", "тўқсон"]
_DARAJALAR = [(10 ** 9, "миллиард"), (10 ** 6, "миллион"), (10 ** 3, "минг")]


def _uch_xona(n):
    parts = []
    if n >= 100:
        parts += [_BIRLAR[n // 100], "юз"]
        n %= 100
    if n >= 10:
        parts.append(_ONLAR[n // 10])
        n %= 10
    if n:
        parts.append(_BIRLAR[n])
    return [p for p in parts if p]


def sonni_sozga(n):
    """5374888 -> 'беш миллион уч юз етмиш тўрт минг саккиз юз саксон саккиз' (o'zbek kirill)."""
    n = int(n)
    if n == 0:
        return "нол"
    parts = []
    for daraja, nom in _DARAJALAR:
        if n >= daraja:
            parts += _uch_xona(n // daraja) + [nom]
            n %= daraja
    parts += _uch_xona(n)
    return " ".join(parts)


def pul(v):
    return f"{int(Decimal(v).quantize(Decimal('1'))):,}".replace(",", " ")


def _set_runs(paragraph, text):
    """Paragrafdagi matnni almashtiradi, birinchi run formatini saqlaydi."""
    runs = paragraph.runs
    if not runs:
        paragraph.add_run(text)
        return
    runs[0].text = text
    for r in runs[1:]:
        r.text = ""


def _nom_almashtir(doc):
    def fix(paragraphs):
        for p in paragraphs:
            if ESKI_NOM in p.text:
                for r in p.runs:
                    if ESKI_NOM in r.text:
                        r.text = r.text.replace(ESKI_NOM, YANGI_NOM)
                if ESKI_NOM in p.text:  # bir nechta run'ga bo'lingan bo'lsa
                    _set_runs(p, p.text.replace(ESKI_NOM, YANGI_NOM))

    fix(doc.paragraphs)
    for t in doc.tables:
        for row in t.rows:
            for cell in row.cells:
                fix(cell.paragraphs)


def _cell(cell, text, size=10):
    from docx.shared import Pt

    p = cell.paragraphs[0]
    _set_runs(p, str(text))
    for r in p.runs:
        r.font.size = Pt(size)
        r.font.name = "Times New Roman"
    for extra in cell.paragraphs[1:]:
        _set_runs(extra, "")


def shartnoma_docx(sh):
    """Shartnoma DOCX faylini bytes ko'rinishida qaytaradi."""
    import docx

    a = sh.ariza
    doc = docx.Document(SHABLON_DIR / "shartnoma_shakli.docx")
    sana = timezone.localtime(sh.created_at)
    nomi = a.buyurtmachi_nomi or a.fish
    pars = doc.paragraphs

    # № va sana
    for p in pars:
        t = p.text
        if t.strip().endswith("сонли") and "____" in t:
            _set_runs(p, f"№ {sh.raqam} сонли")
        elif "Қибрай тумани" in t and "йил" in t:
            for i, r in enumerate(p.runs):
                if r.text.strip() == "2026" or (r.text.strip().isdigit() and len(r.text.strip()) == 4):
                    r.text = str(sana.year)
                    rest = p.runs[i + 1:]
                    if rest:
                        rest[0].text = f" йил «{sana.day:02d}» {OYLAR[sana.month - 1]}"
                        for rr in rest[1:]:
                            rr.text = ""
                    break
        elif "(хўжалик номи ва манзили)" in t:
            runs = p.runs
            runs[0].text = f"{nomi}{', ' + a.manzil if a.manzil else ''}     ("
        elif "фаолият юритувчи раҳбари" in t and "____" in t:
            for r in p.runs:
                if "_____" in r.text:
                    r.text = r.text.replace("_____________________________", a.rahbar or a.fish, 1)
        elif t.strip().startswith("2.2.") and "умумий баҳоси" in t:
            done_sum = False
            for r in p.runs:
                if "_____" in r.text and not done_sum:
                    if r.text.strip().startswith("___") and ")" not in r.text:
                        r.text = pul(sh.jami_summa)
                        done_sum = True
                elif "_____" in r.text and ")" in r.text:
                    r.text = f" {sonni_sozga(sh.jami_summa)})"

    _nom_almashtir(doc)

    # 2.1 jadval: ko'rsatkichlar
    t = doc.tables[0]
    header, jami_row = t.rows[0], t.rows[-1]
    blank_rows = list(t.rows)[1:-1]
    bandlar = list(sh.bandlar.all())
    template_tr = copy.deepcopy(blank_rows[0]._tr)
    for r in blank_rows:
        t._tbl.remove(r._tr)
    for b in bandlar:
        tr = copy.deepcopy(template_tr)
        jami_row._tr.addprevious(tr)
    rows = list(t.rows)[1:-1]
    for row, b in zip(rows, bandlar):
        soni = b.namuna_soni if b.narxnoma.har_namunaga else 1
        vals = [b.parametr, b.tahlil_usuli, pul(b.narx), soni, pul(b.summa)]
        cells = []
        for c in row.cells:  # birlashtirilgan katakchalar takrorlanmasin
            if not cells or c._tc is not cells[-1]._tc:
                cells.append(c)
        for c, v in zip(cells, vals):
            _cell(c, v)
    jami_cells = []
    for c in jami_row.cells:
        if not jami_cells or c._tc is not jami_cells[-1]._tc:
            jami_cells.append(c)
    _cell(jami_cells[-1], pul(sh.jami_summa))

    # X. Buyurtmachi rekvizitlari
    rek = doc.tables[1].rows[0].cells[1]
    qiymat = {
        "____": nomi,
        "Манзил": f"Манзил: {a.manzil or '—'}",
        "Х/Р": f"Х/Р: {a.hisob_raqam or '—'}",
        "Банк": f"Банк: {a.bank or '—'}",
        "МФО": f"МФО: {a.mfo or '—'}",
        "ИНН": f"ИНН: {a.inn}    ОКЭД: {a.oked or '—'}",
        "Телефон": f"Телефон: {a.telefon}",
    }
    for p in rek.paragraphs:
        txt = p.text.strip()
        for key, val in qiymat.items():
            if txt.startswith(key) and "_" in txt:
                _set_runs(p, val)
                break
    for p in rek.paragraphs:
        if "имзо, мансаби" in p.text:
            p.insert_paragraph_before(a.rahbar or a.fish)
            break

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def docx_to_pdf(data: bytes) -> bytes:
    """LibreOffice orqali DOCX -> PDF."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "hujjat.docx"
        src.write_bytes(data)
        subprocess.run(
            ["soffice", "--headless", f"-env:UserInstallation=file://{tmp}/lo", "--convert-to", "pdf",
             "--outdir", tmp, str(src)],
            check=True, capture_output=True, timeout=120,
        )
        return (Path(tmp) / "hujjat.pdf").read_bytes()


# ---------------------------------------------------------------------------
# Sinov bayonnomasi (xulosa) — docs/shablonlar/xulosa_shakli.docx
# ---------------------------------------------------------------------------
def qr_png(url, box=6):
    import qrcode

    img = qrcode.make(url, box_size=box, border=1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _sana(dt):
    if not dt:
        return "____.____.____"
    if hasattr(dt, "tzinfo") and getattr(dt, "hour", None) is not None:
        dt = timezone.localtime(dt)
    return dt.strftime("%d.%m.%Y")


def _uniq_cells(row):
    cells = []
    for c in row.cells:
        if not cells or c._tc is not cells[-1]._tc:
            cells.append(c)
    return cells


def xulosa_docx(x, verify_url=""):
    """Sinov bayonnomasi DOCX (bytes)."""
    import docx
    from docx.shared import Cm

    n = x.namuna
    a = n.ariza
    doc = docx.Document(SHABLON_DIR / "xulosa_shakli.docx")
    t_head, t_info, t_res, t_sign = doc.tables[1], doc.tables[2], doc.tables[3], doc.tables[4]

    # Sarlavha: raqam, sana, QR
    c = _uniq_cells(t_head.rows[0])
    _set_runs(c[0].paragraphs[0], f"SINOV BAYONNOMASI № {x.raqam}")
    _set_runs(c[1].paragraphs[0], f"Sana: {_sana(x.tayyor_at or x.created_at)} y.")
    if verify_url and len(c) > 2:
        p = c[2].paragraphs[0]
        p.alignment = 2  # o'ngga
        p.add_run().add_picture(qr_png(verify_url), width=Cm(2.1))

    # Ma'lumotlar jadvali
    rows = [_uniq_cells(r) for r in t_info.rows]
    nomi = n.nomi or a.namuna_nomi
    tavsif = ", ".join(v for v in [nomi, n.tavsifi, n.tasir_etuvchi_modda] if v)
    vals = [
        a.buyurtmachi_nomi or a.fish,
        f"{tavsif} ({n.namuna_turi.nomi})",
        f"LOT (partiya raqami): {a.partiya_raqami or '—'}   |   INVOICE: {a.invoys_raqami or '—'}",
        f"{_sana(n.qabul_vaqti)} y.   |   Og‘irligi/hajmi: {n.ogirligi or '—'}",
        f"{_sana(x.sinov_sanasi)} y.   |   Dalolatnoma №: {x.dalolatnoma or '—'}",
        f"{x.sinov_joyi}   |   {x.harorat}, {x.namlik}",
    ]
    for r, v in zip(rows, vals):
        _cell(r[1], v, size=11)

    # Natijalar jadvali
    natijalar = list(x.natijalar.all())
    tmpl = copy.deepcopy(t_res.rows[2]._tr)
    for r in list(t_res.rows)[1:]:
        t_res._tbl.remove(r._tr)
    for _ in natijalar:
        t_res._tbl.append(copy.deepcopy(tmpl))
    for i, (row, nt) in enumerate(zip(list(t_res.rows)[1:], natijalar), 1):
        cells = _uniq_cells(row)
        for cell, v in zip(cells, [i, nt.korsatkich, nt.meyor, nt.natija, nt.sinov_usuli, nt.muvofiqlik]):
            _cell(cell, v or "", size=10)

    # Shablonda imzo va "Rasmiy eslatma" orasida bo'sh qatorlar bor (eslatma sahifa pastida turishi uchun).
    # Natijalar ko'p bo'lsa, bayonnoma bitta sahifaga sig'ishi uchun shu bo'sh qatorlardan olib tashlaymiz.
    import math

    satrlar = sum(max(1, math.ceil(len(nt.korsatkich) / 30), math.ceil(len(nt.sinov_usuli or "") / 16),
                      math.ceil(len(nt.natija or "") / 16), math.ceil(len(nt.meyor or "") / 10))
                  for nt in natijalar)
    ortiqcha = max(0, satrlar - 6) * 3
    bosh = []
    el = t_sign._tbl.getnext()
    while el is not None and el.tag.endswith("}p") and not "".join(el.itertext()).strip():
        bosh.append(el)
        el = el.getnext()
    for el in bosh[:min(ortiqcha, max(0, len(bosh) - 1))]:
        el.getparent().remove(el)

    # Hujjat oxiridagi majburiy bo'sh paragraf ortiqcha sahifa ochmasin
    from docx.shared import Pt

    oxirgi = doc.paragraphs[-1]
    if not oxirgi.text.strip():
        pf = oxirgi.paragraph_format
        pf.space_before = pf.space_after = Pt(0)
        pf.line_spacing = Pt(1)
        for r in oxirgi.runs:
            r.font.size = Pt(1)
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn

        rpr = oxirgi._p.get_or_add_pPr()
        mark = OxmlElement("w:rPr")
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), "2")
        mark.append(sz)
        rpr.append(mark)

    # Imzolar
    sc = _uniq_cells(t_sign.rows[0])
    for r in sc[0].paragraphs[0].runs:
        if r.text.strip().startswith("____"):
            r.text = r.text + " " + (x.tasdiqlagan or "")
            break
    runs = sc[1].paragraphs[0].runs
    for i, r in enumerate(runs):
        if r.text.startswith(":") and "___" in r.text and "Bosh" in "".join(z.text for z in runs[max(0, i - 3):i]):
            r.text = f":   ________________  {x.bosh_agrokimyogar}"
            j = i + 1
            while j < len(runs) and set(runs[j].text) <= {"_"} and runs[j].text:
                runs[j].text = ""
                j += 1
        elif r.text.startswith(": ___") and "Yetakchi" in "".join(z.text for z in runs[max(0, i - 3):i]):
            r.text = f":   ________________  {x.yetakchi_agrokimyogar}"

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
