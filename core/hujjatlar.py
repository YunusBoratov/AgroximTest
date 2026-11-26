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


def _soffice():
    """LibreOffice dasturini topadi (Linux: PATH; Windows/macOS: odatiy o'rnatish joyi)."""
    import shutil

    for nom in ("soffice", "libreoffice"):
        if shutil.which(nom):
            return shutil.which(nom)
    for yol in (r"C:\Program Files\LibreOffice\program\soffice.exe",
                r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
                "/Applications/LibreOffice.app/Contents/MacOS/soffice"):
        if Path(yol).exists():
            return yol
    raise FileNotFoundError("LibreOffice topilmadi")


def docx_to_pdf(data: bytes) -> bytes:
    """LibreOffice orqali DOCX -> PDF."""
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "hujjat.docx"
        src.write_bytes(data)
        profil = Path(tmp, "lo").as_uri()
        subprocess.run(
            [_soffice(), "--headless", f"-env:UserInstallation={profil}", "--convert-to", "pdf",
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


def _vaqt(dt):
    """Sinov vaqti (soat:daqiqa) — sana yonida."""
    from django.utils import timezone as _tz

    if not dt or getattr(dt, "hour", None) is None:
        return ""
    return " " + _tz.localtime(dt).strftime("%H:%M")


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


def _chiziq_png():
    """1 pt qalinlikdagi vertikal qora chiziq (rasm)."""
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (4, 160), (0, 0, 0)).save(buf, "PNG")
    buf.seek(0)
    return buf


def _logo_kichrayt(doc, koef=0.84):
    """Sarlavhadagi markaz logotipini (birinchi katakdagi rasm) kichraytiradi — pastki chiziqqa tegmasin.
    Yuqori chekka joyida qoladi, gorizontal markaz saqlanadi."""
    WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
    A = "http://schemas.openxmlformats.org/drawingml/2006/main"
    if not doc.tables:
        return
    tc = doc.tables[0].rows[0].cells[0]._tc
    for anchor in tc.iter(f"{{{WP}}}anchor"):
        ext = anchor.find(f"{{{WP}}}extent")
        if ext is None or not list(anchor.iter("{http://schemas.openxmlformats.org/drawingml/2006/picture}pic")):
            continue
        cx, cy = int(ext.get("cx")), int(ext.get("cy"))
        ncx, ncy = int(cx * koef), int(cy * koef)
        ext.set("cx", str(ncx))
        ext.set("cy", str(ncy))
        for e in anchor.iter(f"{{{A}}}ext"):
            if e.get("cx") == str(cx) and e.get("cy") == str(cy):
                e.set("cx", str(ncx))
                e.set("cy", str(ncy))
        ph = anchor.find(f"{{{WP}}}positionH")
        off = ph.find(f"{{{WP}}}posOffset") if ph is not None else None
        if off is not None:
            off.text = str(int(off.text) + (cx - ncx) // 2)
        return


CHIZIQ_PASTGA = 112000  # EMU (~0.31 sm)


def _ajratuvchi_chiziqlar(doc):
    """Sarlavhadagi vertikal ajratuvchi chiziqlarni (shakl) xuddi shu joydagi ingichka rasmga almashtiradi:
    LibreOffice jadval katagidagi vertikal chiziq-shaklni ba'zan gorizontal chizadi (PDF'da yozuv ustidan o'tadi)."""
    from docx.shared import Emu

    WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
    A = "http://schemas.openxmlformats.org/drawingml/2006/main"
    for anchor in list(doc.element.body.iter(f"{{{WP}}}anchor")):
        ext = anchor.find(f"{{{WP}}}extent")
        graphic = anchor.find(f"{{{A}}}graphic")
        if ext is None or graphic is None or ext.get("cx") != "0":
            continue
        if not any(g.get("prst") == "line" for g in graphic.iter(f"{{{A}}}prstGeom")):
            continue
        cy = int(ext.get("cy"))
        inline = doc.part.new_pic_inline(_chiziq_png(), Emu(12700), Emu(cy))
        yangi = inline.find(f"{{{A}}}graphic")
        anchor.replace(graphic, yangi)
        ext.set("cx", "12700")
        eff = anchor.find(f"{{{WP}}}effectExtent")
        if eff is not None:
            for k in ("l", "t", "r", "b"):
                eff.set(k, "0")
        pv = anchor.find(f"{{{WP}}}positionV")
        off = pv.find(f"{{{WP}}}posOffset") if pv is not None else None
        if off is not None:  # logotiplar balandligining o'rtasiga tushirish
            off.text = str(int(off.text) + CHIZIQ_PASTGA)


def _ichki_chetsiz(txbx):
    """Ramka ichidagi chetlarni nolga tushirib, QR'ni markazga qo'yadi."""
    WPS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    el = txbx
    while el is not None and el.tag != f"{{{WPS}}}wsp":
        el = el.getparent()
    if el is not None:
        body = el.find(f"{{{WPS}}}bodyPr")
        if body is not None:
            for k in ("lIns", "tIns", "rIns", "bIns"):
                body.set(k, "0")
            body.set("anchor", "ctr")
    for p in txbx.iter(f"{{{W}}}p"):
        ppr = p.find(f"{{{W}}}pPr")
        if ppr is None:
            ppr = p.makeelement(f"{{{W}}}pPr", {})
            p.insert(0, ppr)
        for jc in ppr.findall(f"{{{W}}}jc"):
            ppr.remove(jc)
        ppr.append(ppr.makeelement(f"{{{W}}}jc", {f"{{{W}}}val": "center"}))


def _ramkasiz(txbx):
    """Shablondagi "QR KOD" ramkasi faqat joy ko'rsatkichi: chegara chizig'i olib tashlanadi (QR ramkasiz)."""
    A = "http://schemas.openxmlformats.org/drawingml/2006/main"
    WPS = "http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
    V = "urn:schemas-microsoft-com:vml"
    el = txbx
    while el is not None and el.tag not in (f"{{{WPS}}}wsp", f"{{{V}}}rect", f"{{{V}}}shape"):
        el = el.getparent()
    if el is None:
        return
    if el.tag == f"{{{WPS}}}wsp":
        sppr = el.find(f"{{{WPS}}}spPr")
        if sppr is not None:
            for ln in sppr.findall(f"{{{A}}}ln"):
                for ch in list(ln):
                    ln.remove(ch)
                ln.append(ln.makeelement(f"{{{A}}}noFill", {}))
        style = el.find(f"{{{WPS}}}style")
        if style is not None:  # mavzu bo'yicha chiziq ham chizilmasin
            el.remove(style)
    else:
        el.set("stroked", "f")
        for st in el.findall(f"{{{V}}}stroke"):
            el.remove(st)


def _qr_matn_qutisiga(doc, cell, verify_url):
    """Imzo jadvalidagi "QR KOD" yozuvli ramka ichiga QR rasmini joylaydi. Topilmasa False."""
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Emu

    W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    WP = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
    joylandi = False
    for txbx in cell._tc.iter(f"{{{W}}}txbxContent"):
        for p in txbx.iter(f"{{{W}}}p"):
            if "QR" not in "".join(t.text or "" for t in p.iter(f"{{{W}}}t")):
                continue
            _ramkasiz(txbx)
            # ramka o'lchami (wp:extent) bo'yicha QR kattaligi
            anchor = txbx
            while anchor is not None and anchor.tag != f"{{{WP}}}anchor":
                anchor = anchor.getparent()
            olcham = 1_000_000
            if anchor is not None:
                ext = anchor.find(f"{{{WP}}}extent")
                if ext is not None:
                    olcham = int(min(int(ext.get("cx")), int(ext.get("cy"))) * 0.98)
            for r in list(p.iter(f"{{{W}}}r")):
                r.getparent().remove(r)
            _ichki_chetsiz(txbx)
            inline = doc.part.new_pic_inline(qr_png(verify_url), Emu(olcham), Emu(olcham))
            run = OxmlElement("w:r")
            drawing = OxmlElement("w:drawing")
            drawing.append(inline)
            run.append(drawing)
            p.append(run)
            ppr = p.find(qn("w:pPr"))
            if ppr is not None:
                for sp in ppr.findall(qn("w:spacing")):
                    ppr.remove(sp)
            joylandi = True
    return joylandi


def _ustunni_olib_tashla(table, idx):
    """Jadvaldan idx-ustunni olib tashlaydi; uning kengligi qolgan ustunlarga (№ dan tashqari) teng bo'linadi."""
    from docx.oxml.ns import qn

    tbl = table._tbl
    cols = tbl.tblGrid.findall(qn("w:gridCol"))
    if len(cols) <= idx:
        return
    w = int(cols[idx].get(qn("w:w")))
    tbl.tblGrid.remove(cols[idx])
    cols = tbl.tblGrid.findall(qn("w:gridCol"))
    oluvchi = list(range(1, len(cols)))
    qosh = w // len(oluvchi)
    for k in oluvchi:
        cols[k].set(qn("w:w"), str(int(cols[k].get(qn("w:w"))) + qosh))
    for tr in tbl.tr_lst:
        tcs = tr.findall(qn("w:tc"))
        if len(tcs) <= idx:
            continue
        tr.remove(tcs[idx])
        for k in oluvchi:
            tcw = tcs[k].tcPr.find(qn("w:tcW")) if tcs[k].tcPr is not None else None
            if tcw is not None and tcw.get(qn("w:type")) in (None, "dxa"):
                tcw.set(qn("w:w"), str(int(tcw.get(qn("w:w"))) + qosh))


# "Muvofiqlik haqida qaror" ustuni vaqtincha chiqarilmaydi (markaz faqat natijani beradi).
# Qaytarish kerak bo'lsa: True qiling — ma'lumot bazada saqlanadi.
MUVOFIQLIK_USTUNI = False


def xulosa_docx(x, verify_url=""):
    """Sinov bayonnomasi DOCX (bytes) — docs/shablonlar/xulosa_shakli.docx asosida."""
    import docx
    from docx.oxml.ns import qn as qn_
    from docx.shared import Cm

    n = x.namuna
    a = n.ariza
    doc = docx.Document(SHABLON_DIR / "xulosa_shakli.docx")
    t_head, t_info, t_res, t_sign = doc.tables[1], doc.tables[2], doc.tables[3], doc.tables[4]

    # Sarlavha: raqam va sana
    c = _uniq_cells(t_head.rows[0])
    _set_runs(c[0].paragraphs[0], f"SINOV BAYONNOMASI № {x.raqam}")
    from docx.shared import Pt as _Pt

    for r in c[0].paragraphs[0].runs:
        r.font.size = _Pt(10.5)
    from docx.oxml import OxmlElement as _OE

    tcpr = c[0]._tc.get_or_add_tcPr()
    if tcpr.find(qn_("w:noWrap")) is None:
        tcpr.append(_OE("w:noWrap"))
    _set_runs(c[1].paragraphs[0], f"Sana: {_sana(x.tasdiqlangan_at or x.tayyor_at or x.created_at)} y.")

    # Ma'lumotlar jadvali
    rows = [_uniq_cells(r) for r in t_info.rows]
    b = n.ariza_namuna  # mijoz kiritgan namuna bloki (partiya, invoys)
    nomi = n.nomi or a.namuna_nomi
    tavsif = ", ".join(v for v in [nomi, n.tavsifi, n.tasir_etuvchi_modda] if v)
    vals = [
        a.buyurtmachi_nomi or a.fish,
        f"{tavsif} ({n.namuna_turi.nomi})",
        f"LOT (partiya raqami): {(b.partiya_raqami if b else a.partiya_raqami) or '—'}   |   "
        f"INVOICE: {(b.invoys_raqami if b else a.invoys_raqami) or '—'}",
        f"{_sana(n.qabul_vaqti)} y.   |   Oğirligi/hajmi: {n.ogirligi or '—'}",
        f"{_sana(x.sinov_sanasi)} y.{_vaqt(x.sinov_sanasi)}   |   Dalolatnoma №: {x.dalolatnoma or '—'}",
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
    if not MUVOFIQLIK_USTUNI:
        _ustunni_olib_tashla(t_res, 5)

    # Bayonnoma bitta sahifaga sig'ishi uchun imzo va "Rasmiy eslatma" orasidagi bo'sh qatorlardan olib tashlash
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
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt

    oxirgi = doc.paragraphs[-1]
    if not oxirgi.text.strip():
        pf = oxirgi.paragraph_format
        pf.space_before = pf.space_after = Pt(0)
        pf.line_spacing = Pt(1)
        rpr = oxirgi._p.get_or_add_pPr()
        mark = OxmlElement("w:rPr")
        sz = OxmlElement("w:sz")
        sz.set(qn("w:val"), "2")
        mark.append(sz)
        rpr.append(mark)

    # Imzolar: "TASDIQLANDI" — laboratoriya mudiri; sinov o'tkazuvchilar
    sc = _uniq_cells(t_sign.rows[0])
    runs0 = sc[0].paragraphs[0].runs
    mudir_run = None
    for r in runs0:
        if r.text.strip().startswith("____") or (r.text.strip() and r is runs0[-1]):
            mudir_run = r
    if mudir_run is not None and x.tasdiqlagan:
        mudir_run.text = x.tasdiqlagan if not mudir_run.text.strip().startswith("____") \
            else mudir_run.text + " " + x.tasdiqlagan
    runs = sc[1].paragraphs[0].runs
    for i, r in enumerate(runs):
        oldin = "".join(z.text for z in runs[max(0, i - 4):i])
        if r.text.startswith(":") and "_" in r.text:
            if "Bo" in oldin and "agrokimyogar" in oldin:
                r.text = f":   {x.bosh_agrokimyogar or '________________'}"
            elif "Yetak" in oldin and "agrokimyogar" in oldin:
                r.text = f":   {x.yetakchi_agrokimyogar or '________________'}"
            j = i + 1
            while j < len(runs) and runs[j].text and set(runs[j].text) <= {"_", " "}:
                runs[j].text = ""
                j += 1

    _ajratuvchi_chiziqlar(doc)
    _logo_kichrayt(doc)

    # QR kod: yangi shaklda imzo jadvalidagi ramkada, eski shaklda sarlavhaning 3-katagida
    if verify_url and not _qr_matn_qutisiga(doc, sc[-1], verify_url) and len(c) > 2:
        p = c[2].paragraphs[0]
        p.alignment = 2
        p.add_run().add_picture(qr_png(verify_url), width=Cm(2.1))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# PDF himoyasi: xira fon yozuvi + tahrirlashni taqiqlash
# ---------------------------------------------------------------------------
SUV_BELGISI = "Agrokimyo va tuproq tahlili markazi"


def _suv_belgisi_sahifa(width, height, matn=SUV_BELGISI):
    from reportlab.lib.colors import Color
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(width, height))
    c.setFillColor(Color(0.55, 0.62, 0.57, alpha=0.13))
    from reportlab.pdfbase.pdfmetrics import stringWidth

    shrift, olcham = "Helvetica-Bold", 15
    c.setFont(shrift, olcham)
    qadam_x, qadam_y = int(stringWidth(matn, shrift, olcham)) + 70, 110
    c.translate(width / 2, height / 2)
    c.rotate(32)
    diag = int((width ** 2 + height ** 2) ** 0.5)
    for i, y in enumerate(range(-diag, diag, qadam_y)):
        siljish = (qadam_x // 2) if i % 2 else 0
        for x in range(-diag - siljish, diag, qadam_x):
            c.drawString(x, y, matn)
    c.save()
    buf.seek(0)
    from pypdf import PdfReader

    return PdfReader(buf).pages[0]


def pdf_himoyala(pdf_bytes: bytes) -> bytes:
    """Har bir sahifa ostiga xira qiya yozuv qo'yadi va PDF'ni tahrirlashdan himoyalaydi
    (ochish uchun parol kerak emas; faqat ko'rish va chop etishga ruxsat)."""
    import secrets

    from pypdf import PdfReader, PdfWriter
    from pypdf.constants import UserAccessPermissions as P

    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        page.merge_page(_suv_belgisi_sahifa(w, h), over=False)  # matn ostida
        writer.add_page(page)
    writer.add_metadata({"/Title": "Sinov bayonnomasi", "/Author": SUV_BELGISI, "/Producer": SUV_BELGISI})
    try:
        writer.encrypt(user_password="", owner_password=secrets.token_hex(16), algorithm="AES-128",
                       permissions_flag=P.PRINT | P.PRINT_TO_REPRESENTATION)
    except Exception:  # shifrlash kutubxonasi bo'lmasa ham bayonnoma (suv belgisi bilan) beriladi
        import logging

        logging.getLogger("core.hujjat").exception("PDF himoyasi qo'yilmadi (cryptography o'rnatilganmi?)")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
