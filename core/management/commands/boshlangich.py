"""
Boshlang'ich ma'lumotlarni yuklash:
    python manage.py boshlangich            # namuna turlari + narxnoma (Excel'dan)
    python manage.py boshlangich --demo     # + har bir rol uchun sinov foydalanuvchilari va namunaviy arizalar
"""
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Role, User
from core.models import (Ariza, ArizaTuri, Kategoriya, Namuna, NamunaTuri, Narxnoma, Shartnoma, ShartnomaBand,
                         Tolov)

NAMUNA_TURLARI = {
    Kategoriya.MINERAL: [
        ("Murakkab o'g'itlar", "Сложные удобрения"),
        ("Organik o'g'itlar", "Органические удобрения"),
        ("Mikroelementlar", "Микроэлементы"),
        ("Azotli o'g'itlar", "Азотные удобрения"),
        ("Kaliyli o'g'itlar", "Калийные удобрения"),
        ("Fosforli o'g'itlar", "Фосфорные удобрения"),
        ("Organomineral o'g'itlar", "Органоминеральные удобрения"),
        ("O'sishni boshqaradigan o'g'itlar", "Регуляторы роста"),
        ("Boshqa turdagi o'g'itlar", "Другие удобрения"),
    ],
    Kategoriya.KIMYOVIY: [
        ("Insektitsidlar va akaritsidlar", "Инсектициды и акарициды"),
        ("Fungitsidlar", "Фунгициды"),
        ("Gerbitsidlar", "Гербициды"),
        ("Defoliantlar va desikantlar", "Дефолианты и десиканты"),
        ("Boshqa turdagi kimyoviy vositalar", "Другие химические средства"),
    ],
}

# O'zbek kirill -> lotin
_K2L = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "'", "ы": "i", "ь": "",
    "э": "e", "ю": "yu", "я": "ya", "ў": "o'", "қ": "q", "ғ": "g'", "ҳ": "h",
}


def kirill_lotin(text):
    out = []
    for i, ch in enumerate(text):
        low = ch.lower()
        if low not in _K2L:
            out.append(ch)
            continue
        lat = _K2L[low]
        if low == "е" and (i == 0 or not text[i - 1].isalpha()):
            lat = "ye"
        if ch.isupper():
            lat = lat[:1].upper() + lat[1:]
        out.append(lat)
    return "".join(out)


def sinov_obyekti(text):
    t = (text or "").lower()
    if "пестис" in t or "пестиц" in t:
        return Narxnoma.SinovObyekti.PESTITSID
    if "минерал" in t and "тупроқ" in t:
        return Narxnoma.SinovObyekti.UMUMIY
    if "озиқ-овқат" in t or "сабзавот" in t or ("тупроқ" in t and "қишлоқ" in t):
        return Narxnoma.SinovObyekti.OZIQ_OVQAT if "тупроқ" not in t else Narxnoma.SinovObyekti.UMUMIY
    if "органик" in t:
        return Narxnoma.SinovObyekti.ORGANIK
    if "тупроқ" in t:
        return Narxnoma.SinovObyekti.TUPROQ
    if "минерал" in t:
        return Narxnoma.SinovObyekti.MINERAL
    return Narxnoma.SinovObyekti.BOSHQA


NARXNOMA_FAYLLARI = ["narxnoma_jadvali.xlsx", "narxnoma_pestitsid.xlsx"]


class Command(BaseCommand):
    help = "Namuna turlari, narxnoma va (ixtiyoriy) demo ma'lumotlarni yuklaydi"

    def add_arguments(self, parser):
        parser.add_argument("--demo", action="store_true", help="Sinov foydalanuvchilari va arizalar")

    @transaction.atomic
    def handle(self, *args, **opts):
        self.namuna_turlari()
        self.narxnoma()
        if opts["demo"]:
            self.demo()

    def namuna_turlari(self):
        for kat, items in NAMUNA_TURLARI.items():
            for i, (uz, ru) in enumerate(items, 1):
                NamunaTuri.objects.update_or_create(kategoriya=kat, nomi=uz, defaults={"nomi_ru": ru, "tartib": i})
        self.stdout.write(f"Namuna turlari: {NamunaTuri.objects.count()}")

    def narxnoma(self):
        if Narxnoma.objects.exists():
            self.stdout.write("Narxnoma allaqachon bor — o'tkazib yuborildi")
            return
        from openpyxl import load_workbook

        n = 0
        for fayl in NARXNOMA_FAYLLARI:
            ws = load_workbook(Path(settings.BASE_DIR) / "docs" / "shablonlar" / fayl).active
            tartib, parametr, usul, obyekt = 0, "", "", ""
            for row in ws.iter_rows(min_row=1, max_row=ws.max_row):
                a, b, c, d, e = (cell.value for cell in row[:5])
                if not isinstance(e, (int, float)):
                    continue  # sarlavha, "Jami" va bo'sh qatorlar
                if a not in (None, "") and str(a).strip().isdigit():
                    tartib = int(str(a).strip())
                if b:  # yangi parametr: usul ham yangidan olinadi (bo'sh bo'lishi mumkin)
                    parametr = kirill_lotin(" ".join(str(b).split()))
                    if parametr.startswith("Sb)"):
                        parametr = "Surma (" + parametr
                    usul = ""
                if c:
                    usul = kirill_lotin(" ".join(str(c).split()).replace("ГОСТ", "GOST"))
                if d:
                    obyekt = str(d).strip()
                namuna = "намуна" in str(b or parametr).lower() and ("олиш" in str(b or "").lower()
                                                                        or "тайёрлаш" in str(b or "").lower())
                Narxnoma.objects.create(
                    tartib=0 if namuna else tartib,
                    parametr=parametr,
                    tahlil_usuli=usul,
                    sinov_obyekti=sinov_obyekti(obyekt),
                    obyekt_nomi=kirill_lotin(obyekt).rstrip("."),
                    narx=Decimal(str(e)).quantize(Decimal("0.01")),
                    har_namunaga="олиш" not in str(b or "").lower(),
                )
                n += 1
        self.stdout.write(f"Narxnoma qatorlari: {n}")

    def demo(self):
        users = [
            ("superadmin", Role.SUPER_ADMIN, "Super admin"),
            ("admin", Role.ADMIN, "Admin"),
            ("buxgalter", Role.BUXGALTERIYA, "O. Toshtemirov"),
            ("lab_mineral", Role.LAB_MINERAL, "N. Baysunova"),
            ("lab_kimyo", Role.LAB_KIMYO, "X. Sottiyev"),
            ("namuna", Role.NAMUNA_QABUL, "F. Egamova"),
        ]
        for username, role, fish in users:
            u, created = User.objects.get_or_create(username=username, defaults={"role": role, "fish": fish})
            if created:
                u.set_password("demo12345")
                u.is_superuser = u.is_staff = role == Role.SUPER_ADMIN
                u.save()
        self.stdout.write("Demo foydalanuvchilar: parol 'demo12345'")

        if Ariza.objects.exists():
            return
        namuna_user = User.objects.get(username="namuna")
        lab = User.objects.get(username="lab_mineral")
        turlar = list(NamunaTuri.objects.filter(kategoriya=Kategoriya.MINERAL)) + list(
            NamunaTuri.objects.filter(kategoriya=Kategoriya.KIMYOVIY))
        narx = list(Narxnoma.objects.filter(sinov_obyekti=Narxnoma.SinovObyekti.MINERAL)[:3])
        misollar = [
            (ArizaTuri.IMPORTYOR, "Yulduz MCHJ", "R. Qarayev", "Basfoliar Aktiv SL", 0, "Angor bojxona posti"),
            (ArizaTuri.DAVLAT, "VALAGRO MCHJ", "A. Karimov", "Perful", 3, ""),
            (ArizaTuri.IXTIYORIY, "", "Alijonov Botir Alimovich", "Ammofos", 5, ""),
            (ArizaTuri.IMPORTYOR, "Corel MCHJ", "S. Rahimov", "Agroplan Super 5%", 9, "Olot bojxona posti"),
        ]
        for i, (turi, nomi, fish, nm, t_idx, chegara) in enumerate(misollar):
            a = Ariza.objects.create(
                turi=turi, buyurtmachi_nomi=nomi, fish=fish, inn=f"30{i}123456", telefon="+998901234567",
                namuna_soni=1, namuna_turi=turlar[t_idx], namuna_nomi=nm, chegara_maskani=chegara,
                holat=Ariza.Holat.QABUL if i < 3 else Ariza.Holat.YANGI, qabul_qilgan=namuna_user,
            )
            if i >= 3:
                continue
            nam = Namuna.objects.create(ariza=a, namuna_turi=a.namuna_turi, nomi=nm, namuna_olgan=fish,
                                        qabul_qilgan=namuna_user)
            sh = Shartnoma.objects.create(ariza=a, yaratgan=lab, holat=Shartnoma.Holat.YUBORILGAN)
            for nx in narx:
                ShartnomaBand.objects.create(shartnoma=sh, narxnoma=nx, narx=nx.narx, namuna_soni=1)
            nam.shartnoma = sh
            nam.save()
            sh.qayta_hisobla()
            if i == 1:
                Tolov.objects.create(shartnoma=sh, summa=sh.jami_summa * Decimal("0.4"))
                sh.qayta_hisobla()
        self.stdout.write("Demo arizalar yaratildi")
