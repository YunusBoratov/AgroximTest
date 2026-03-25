from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Narxnoma, Shartnoma, ShartnomaItem, Namuna, Xulosa, Natija
from .utils.docx_gen import generate_xulosa_docx
from django.contrib import messages
from decimal import Decimal

from django.template.loader import render_to_string
from django.http import HttpResponse
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Image
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib import pagesizes
from reportlab.lib.units import mm
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import os
from reportlab.pdfgen import canvas
from reportlab.lib.colors import Color
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import Paragraph
#from reportlab.lib.enums import TA_LEFT
from docxtpl import DocxTemplate
import os
from django.conf import settings
from datetime import datetime

def generate_shartnoma_docx(shartnoma):
    doc = DocxTemplate("templates/shartnoma/template.docx")

    context = {
        "id": shartnoma.id,
        "buyurtmachi": shartnoma.buyurtmachi,
        "jami": shartnoma.jami_summa,
        "sana": datetime.now().strftime("%d-%m-%Y"),
    }

    doc.render(context)

    filename = f"shartnoma_{shartnoma.id}.docx"
    path = os.path.join("media", filename)

    os.makedirs("media", exist_ok=True)
    filename = f"shartnoma_{shartnoma.id}.docx"
    path = os.path.join("media", filename)

    os.makedirs("media", exist_ok=True)

    print("FILE PATH:", path)

    doc.save(path)
    with open(path, "rb") as f:
        shartnoma.file.save(filename, File(f))


styles = getSampleStyleSheet()

def buxgalter_required(user):
    return user.groups.filter(name="Buxgalteriya").exists() or user.is_superuser


def lab_required(user):
    return user.groups.filter(name="Laboratoriya").exists() or user.is_superuser


@login_required
@user_passes_test(buxgalter_required)
def shartnoma_monitoring(request):
    shartnomalar = Shartnoma.objects.all().order_by("-sana")
    return render(request, "shartnoma/monitoring.html", {
        "shartnomalar": shartnomalar
    })

def tolov_kiritish(request, pk):
    shartnoma = get_object_or_404(Shartnoma, pk=pk)

    if request.method == "POST":
        summa = request.POST.get("summa")

        try:
            summa = Decimal(summa)
        except:
            messages.error(request, "Noto‘g‘ri summa")
            return redirect("shartnoma_monitoring")

        shartnoma.tolangan_summa += summa
        shartnoma.yangila_status()
        shartnoma.save()

        messages.success(request, "To‘lov kiritildi")
        return redirect("shartnoma_monitoring")

@login_required
@user_passes_test(buxgalter_required)
def status_update(request, pk, new_status):
    shartnoma = get_object_or_404(Shartnoma, pk=pk)

    shartnoma.status = new_status
    shartnoma.save()

    if new_status == "tolangan":
        print("🔔 Laboratoriyaga xabar: Shartnoma to‘landi")

    return redirect("shartnoma_monitoring")

def shartnoma_soft_delete(request, pk):
    shartnoma = get_object_or_404(Shartnoma, pk=pk)
    shartnoma.status = "ochirilgan"
    shartnoma.is_active = False
    shartnoma.save()
    return redirect("shartnoma_monitoring")

def shartnoma_yangi(request):
    narxnomalar = Narxnoma.objects.filter(aktiv=True)

    if request.method == "POST":
        buyurtmachi = request.POST.get("buyurtmachi")
        inn = request.POST.get("inn")
        telefon = request.POST.get("telefon")
        namuna_soni = int(request.POST.get("namuna_soni", 1))

        shartnoma = Shartnoma.objects.create(
            buyurtmachi=buyurtmachi,
            inn=inn,
            telefon=telefon,
            jami_summa=0,
            status="tolanmagan",
        )
        generate_shartnoma_docx(shartnoma)
                        
        umumiy_jami = 0

        for i in range(1, namuna_soni + 1):
            namuna_turi = request.POST.get(f"namuna_{i}_turi")
            narxlar = request.POST.getlist(f"namuna_{i}_narxlar")

            namuna = Namuna.objects.create(
                shartnoma=shartnoma,
                korxona_nomi=buyurtmachi,
                inn=inn,
                telefon=telefon,
                #masul_shaxs="",
                namuna_turi=namuna_turi
            )

            jami = 0
            for narx_id in narxlar:
                narx = Narxnoma.objects.get(id=narx_id)
                jami += narx.narx

                ShartnomaItem.objects.create(
                    shartnoma=shartnoma,
                    narxnoma=narx
                )

            umumiy_jami += jami

        shartnoma.jami_summa = umumiy_jami
        shartnoma.save()

        return redirect("shartnoma_monitoring")

    return render(request, "shartnoma/yangi.html", {
        "narxnomalar": narxnomalar
    })


@login_required
@user_passes_test(lab_required)
def lab_shartnomalar(request):
    shartnomalar = Shartnoma.objects.filter(
        status="tolangan"
    ).order_by("-sana")

    return render(request, "shartnoma/lab_list.html", {
        "shartnomalar": shartnomalar
    })
@login_required
def xulosa_yaratish(request, namuna_id):

    namuna = get_object_or_404(Namuna, id=namuna_id)
    

    if request.method == "POST":
        
        matn = request.POST.get("matn")
        sinov_otkazuvchi = request.POST.get("sinov_otkazuvchi")

        sinov_otkazilgan_sana = request.POST.get("sinov_otkazilgan_sana")
        sinov_joy = request.POST.get("sinov_joy")
        namuna_ogirligi = request.POST.get("namuna_ogirligi")
        bayonnoma_raqami = request.POST.get("bayonnoma_raqami")
        bayonnoma_sana = request.POST.get("bayonnoma_sana")
        tashqi_tahlil_natija = request.POST.get("tashqi_tahlil_natija")
        harorat = request.POST.get("harorat")
        namlik = request.POST.get("namlik")
        namuna_tavsifi = request.POST.get("namuna_tavsifi")

        xulosa, created = Xulosa.objects.get_or_create(
            namuna=namuna,
            defaults={
                "matn": matn,
                "sinov_otkazilgan_sana": sinov_otkazilgan_sana,
                "sinov_joy": sinov_joy,
                "namuna_ogirligi": namuna_ogirligi,
                "bayonnoma_raqami": bayonnoma_raqami,
                "bayonnoma_sana": bayonnoma_sana,
                "tashqi_tahlil_natija": tashqi_tahlil_natija,
                "harorat": harorat,
                "namlik": namlik,
                "namuna_tavsifi": namuna_tavsifi,
                "sinov_otkazuvchi": sinov_otkazuvchi,
            }
        )

        if not created:

            xulosa.matn = matn
            xulosa.sinov_otkazilgan_sana = sinov_otkazilgan_sana
            xulosa.sinov_joy = sinov_joy
            xulosa.namuna_ogirligi = namuna_ogirligi
            xulosa.bayonnoma_raqami = bayonnoma_raqami
            xulosa.bayonnoma_sana = bayonnoma_sana
            xulosa.tashqi_tahlil_natija = tashqi_tahlil_natija
            xulosa.harorat = harorat
            xulosa.namlik = namlik
            xulosa.namuna_tavsifi = namuna_tavsifi

            xulosa.save()

        return redirect("lab_namunalar")

    return render(request, "lab/xulosa_form.html", {
        "namuna": namuna
    })

@login_required
def lab_namunalar(request):
    namunalar = Namuna.objects.all().order_by("-id")

    return render(request, "lab/lab_panel.html", {
        "namunalar": namunalar
    })

@login_required
@user_passes_test(lab_required)
def natija_kiritish(request, pk):
    shartnoma = get_object_or_404(Shartnoma, pk=pk)

    namuna = shartnoma.namunalar.first()

    # 🔥 Agar Xulosa yo‘q bo‘lsa — yaratamiz
    xulosa, created = Xulosa.objects.get_or_create(
        namuna=namuna,
        defaults={
            "shartnoma": shartnoma,
            "status": "kiritilmagan"
        }
    )

    itemlar = shartnoma.items.all()

    if request.method == "POST":
        for item in itemlar:
            qiymat = request.POST.get(f"narx_{item.narxnoma.id}")
            meyor = request.POST.get(f"meyor_{item.narxnoma.id}")

            if qiymat:
                Natija.objects.update_or_create(
                    xulosa=xulosa,
                    korsatkich_nomi=item.narxnoma.korsatkich_nomi,
                    defaults={
                        "sinov_usuli": item.narxnoma.tahlil_usuli,
                        "meyor": meyor,
                        "natija": qiymat
                    }
                )

        messages.success(request, "Natijalar saqlandi")
        return redirect("xulosa_yaratish", namuna_id=namuna.id)

    return render(request, "shartnoma/natija_kiritish.html", {
        "shartnoma": shartnoma,
        "itemlar": itemlar
    })

@login_required
@user_passes_test(lab_required)
def xulosa_korish(request, pk):
    xulosa = get_object_or_404(Xulosa, pk=pk)
    natijalar = xulosa.natijalar.all()

    return render(request, "shartnoma/xulosa_korish.html", {
        "xulosa": xulosa,
        "natijalar": natijalar
    })

@login_required
def xulosa_pdf(request, pk):
    xulosa = get_object_or_404(Xulosa, pk=pk)
    namuna = xulosa.namuna
    shartnoma = namuna.shartnoma
    natijalar = xulosa.natijalar.all()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="xulosa_{xulosa.id}.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=pagesizes.A4,
        rightMargin=20,
        leftMargin=20,
        topMargin=20,
        bottomMargin=20
    )
    font_path = os.path.join("C:/Windows/Fonts/arial.ttf")
    pdfmetrics.registerFont(TTFont("Arial", font_path))
    elements = []

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.fontName = "Arial"
    normal.fontSize = 11

    header_style = ParagraphStyle(
        'header_style',
        parent=normal,
        fontName='Arial',
        fontSize=16,
        leading=20,
        alignment=TA_CENTER
    )   

    # ===== HEADER PROFESSIONAL =====

    logo = Image("media/logo.png", width=30*mm, height=35*mm)
    ozakk = Image("media/OZAKK.png", width=100*mm, height=25*mm)
    # Logo + matn bir blok bo‘lsin
    left_block = Table(
        [[logo,
        Paragraph(
            "<b>Respublika<br/>Agrokimyoviy<br/>Tahlil Markazi</b>",
            header_style
        )
        ]],
        colWidths=[10*mm, 75*mm]   # 👈 MUHIM
    )

    
    left_block.setStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ])
    # Asosiy header
    header_table = Table(
        [[left_block, ozakk]],
        colWidths=[95*mm, 100*mm]   # sahifani 2 ga bo‘lamiz
    )
    header_table.setStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (1,0), 'RIGHT'),  # OZAKK o‘ngga yopishadi
    ])

    elements.append(header_table)
    elements.append(Spacer(1, 1))
#/////////////////////////////////////////////
    elements.append(HRFlowable(width="100%", thickness=0.6, color=colors.black)) #qora chiziq
    elements.append(Spacer(1, 2))

    small_style = ParagraphStyle(
        'small',
        parent=normal,
        fontSize=8,
        alignment=TA_CENTER
    )
    elements.append(Paragraph(
        "Toshkent viloyati, Qibray tumani, Bobur ko'chasi, 8-uy. "
        "tel:+998712031414, https://agrokimlab.uz email:info@agrokimlab.uz",
        small_style
    ))
    elements.append(Spacer(1, 2))

    elements.append(HRFlowable(width="100%", thickness=0.6, color=colors.black))
    elements.append(Spacer(1, 6))

    
    # Header

    tasdiq_style = ParagraphStyle(
        'tasdiq_style',
        parent=normal,
        fontName='Arial',
        fontSize=11,
        leading=15,
        alignment=TA_CENTER # 👈 MUHIM
    )
    tasdiq = Paragraph(
        "<b>“TASDIQLAYMAN”</b><br/>"
        "Respublika agrokimyoviy tahlil<br/>"
        "markazi laboratoriya mudiri<br/>"
        "______________ N. Baysunova<br/>"
        "“___” __________ 2026 yil",
        tasdiq_style
    )

    
    tasdiq_table = Table([[tasdiq]], colWidths=[70*mm])
    tasdiq_table.hAlign = 'RIGHT'

    elements.append(Spacer(1, 8))
    elements.append(tasdiq_table)
    elements.append(Spacer(1, 15))

    elements.append(HRFlowable(width="100%", thickness=0.6, color=colors.black))
    elements.append(Spacer(1, 2))
    left_header_style = ParagraphStyle(
        'left_header_style',
        parent=normal,
        fontName='Arial',
        fontSize=16,
        leading=20,
        alignment=TA_LEFT
    )
    elements.append(Paragraph(
        f"<b>Sinov bayonnomasi №{shartnoma.id}</b>",
        left_header_style
    ))

    
    

    elements.append(HRFlowable(width="100%", thickness=0.6, color=colors.black))
    elements.append(Spacer(2, 4))
#\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\\
    info_style = ParagraphStyle(
        'info',
        parent=normal,
        fontName='Arial',
        fontSize=10,
        leading=14
    )

    
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////

    # =========================
    # BUYURTMACHI
    # =========================

    buyurtmachi_table = Table(
    [
    ["Buyurtmachi:", shartnoma.buyurtmachi or ""]
    ],
    colWidths=[120, 435]
    )

    buyurtmachi_table.setStyle(TableStyle([
    ('FONTNAME',(0,0),(-1,-1),'Arial'),
    ('FONTSIZE',(0,0),(-1,-1),10),
    ('BOTTOMPADDING',(0,0),(-1,-1),2),
    ]))

    elements.append(buyurtmachi_table)
    elements.append(Spacer(1,4))
    elements.append(HRFlowable(width="100%", thickness=0.6, color=colors.black))
    elements.append(Spacer(1,4))


    # =========================
    # ASOSIY MA'LUMOTLAR
    # =========================

    info_data = [

        [
            "Namuna qabul qilingan sana:",
            xulosa.created_at.strftime('%d.%m.%Y') if xulosa.created_at else "",
            "Namuna og'irligi (kg):",
            xulosa.namuna_ogirligi or ""
        ],

        [
            "Sinov o'tkazilgan sana:",
            xulosa.sinov_otkazilgan_sana.strftime('%d.%m.%Y') if xulosa.sinov_otkazilgan_sana else "",
            Paragraph("Namuna olish bayonnomasi <br/>raqamiva sanasi:", styles["Normal"]),
            f"{xulosa.bayonnoma_raqami or ''} {xulosa.bayonnoma_sana.strftime('%d.%m.%Y') if xulosa.bayonnoma_sana else ''}"
        ],

        [
            "Sinov o'tkazilgan joy:",
            xulosa.sinov_joy or "",
            "",
            ""
        ],

    ]

     
    info_table = Table(info_data, colWidths=[145,110,190,110])

    info_table.setStyle(TableStyle([
    ('FONTNAME',(0,0),(-1,-1),'Arial'),
    ('FONTSIZE',(0,0),(-1,-1),10),
    ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ]))

    elements.append(info_table)
    elements.append(Spacer(1,4))

    elements.append(Paragraph(
        f"<b>Tashqi yetkazib beruvchilardan taqdim qilinadigan tahlil natijalari:</b> {xulosa.tashqi_tahlil_natija or ''}",
        normal
    ))
    elements.append(Spacer(1,4))
    #elements.append(Paragraph(
    #    f"{xulosa.tashqi_tahlil_natija or ''}",
    #    normal
    #))
    elements.append(HRFlowable(width="100%", thickness=0.6, color=colors.black))
    elements.append(Spacer(1,4))

    # =========================
    # ATROF MUHIT SHAROITI
    # =========================

    elements.append(Paragraph(
    "<b>Sinov o'tkazishda atrof-muhit sharoiti</b>",
    normal
    ))

    elements.append(Spacer(1,4))

    muhit_table = Table([

    ["Harorat, °S :", xulosa.harorat or ""],
    ["Havoning nisbiy namligi, % :", xulosa.namlik or ""]
    ], colWidths=[150,404])

    muhit_table.setStyle(TableStyle([
    ('FONTNAME',(0,0),(-1,-1),'Arial'),
    ('FONTSIZE',(0,0),(-1,-1),10),
    ]))

    elements.append(muhit_table)
    elements.append(Spacer(1,4))

    elements.append(HRFlowable(width="100%", thickness=0.6, color=colors.black))
    elements.append(Spacer(1,4))


    # =========================
    # NAMUNA IDENTIFIKATSIYA
    # =========================

    elements.append(Paragraph(
    f"<b>Namuna nomi, tavsifi, holati va boshqa identifikatsiyasi:</b> {xulosa.namuna_tavsifi or ''}",
    normal
    ))

    

    elements.append(Spacer(1,4))
    elements.append(HRFlowable(width="100%", thickness=0.6, color=colors.black))
    elements.append(Spacer(1,4))
    
    #///////////////////////////////////////////////////////////////////////////////////////////////////

    # Jadval
    # 5 ustunli professional jadval

    data = [[
        "№",
        "Ko‘rsatkich nomi,\no‘lchov birligi me’yoriy qiymat",
        "Sinov usuli",
        "O‘lchanadigan kattalikni\nme’yorlangan qiymati",
        "Sinov natijasi"
    ]]

    for i, n in enumerate(natijalar, start=1):
        data.append([
            str(i),
            n.korsatkich_nomi,
            n.sinov_usuli,
            n.meyor if hasattr(n, "meyor") else "",
            n.natija,
        ])

    table = Table(
    data,
    colWidths=[10*mm, 70*mm, 32*mm, 50*mm, 30*mm]
    )

    table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1.5, colors.black),   # tashqi border
        ('GRID', (0,0), (-1,-1), 0.8, colors.black),  # ichki grid

        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#E6E6E6")),

        ('FONTNAME', (0,0), (-1,-1), 'Arial'),
        ('FONTSIZE', (0,0), (-1,-1), 10),

        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))

    elements.append(Paragraph("<b>Sinov natijalari:</b>", normal))
    elements.append(Spacer(1, 8))
    elements.append(table)
    elements.append(Spacer(1, 20))


   # elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.black))
    #elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=0.6, color=colors.black))
    elements.append(Spacer(1,8))

    elements.append(Paragraph("<b>Sinov o'tkazuvchilar:</b>", normal))
    elements.append(Spacer(1, 8))

    sinovchilar = xulosa.sinov_otkazuvchi

    if not sinovchilar:
        elements.append(Paragraph("—", normal))
    else:
        royxat = [i.strip() for i in sinovchilar.split(",") if i.strip()]

        for odam in royxat:
            elements.append(Paragraph(odam, normal))
#/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

    def add_watermark(canvas, doc):
        canvas.saveState()
        canvas.setFont("Arial", 14)
        canvas.setFillColorRGB(0.9, 0.9, 0.9)

        width, height = pagesizes.A4

        for x in range(0, int(width), 150):
            for y in range(0, int(height), 100):
                canvas.saveState()
                canvas.translate(x, y)
                canvas.rotate(30)
                canvas.drawString(70, 0, "RATM")
                canvas.restoreState()

        canvas.restoreState()


    def draw_footer(canvas, doc):

        canvas.saveState()

        width, height = pagesizes.A4

        # chiziq
        canvas.setLineWidth(1)
        canvas.line(20, 60, width-20, 60)

        footer_style = ParagraphStyle(
            "footer",
            fontName="Arial",
            fontSize=8,
            alignment=TA_JUSTIFY,
            leading=10
        )

        footer_text = """
        Laboratoriya namuna olish bosqichiga javobgarlikni o‘z zimmasiga olmaydi.
        Respublika agrokimyoviy tahlil markazining yozma ruxsatisiz ushbu bayonnomani
        qisman yoki to‘liq nusxalash, o‘zgartirishlar kiritish mumkin emas.
        Sinov bayonnomasi faqatgina sinovga keltirilgan va sinov jarayonida
        tahlil o‘tkazilgan namuna uchungina tegishlidir.
        """

        p = Paragraph(footer_text, footer_style)

        w, h = p.wrap(width-40, height)
        p.drawOn(canvas, 20, 25)

        canvas.restoreState()

    def page_layout(canvas, doc):
        add_watermark(canvas, doc)
        draw_footer(canvas, doc)

    doc.build(
        elements,
        onFirstPage=page_layout,
        onLaterPages=page_layout
    )
    return response