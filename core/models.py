import uuid
from datetime import time
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------------------------------
# Ma'lumotnomalar
# ---------------------------------------------------------------------------
class Kategoriya(models.TextChoices):
    MINERAL = "mineral", _("Mineral o'g'it")
    KIMYOVIY = "kimyoviy", _("Kimyoviy vosita")


class NamunaTuri(models.Model):
    """Namuna turi: Mineral o'g'it -> Azotli o'g'itlar va h.k."""

    kategoriya = models.CharField(_("Kategoriya"), max_length=20, choices=Kategoriya.choices)
    nomi = models.CharField(_("Nomi"), max_length=255)
    nomi_ru = models.CharField(_("Nomi (rus)"), max_length=255, blank=True)
    tartib = models.PositiveIntegerField(default=0)
    aktiv = models.BooleanField(default=True)

    class Meta:
        ordering = ["kategoriya", "tartib", "id"]
        verbose_name = _("Namuna turi")
        verbose_name_plural = _("Namuna turlari")

    @property
    def nom(self):
        """Tanlangan tildagi nomi."""
        from django.utils.translation import get_language

        if (get_language() or "").startswith("ru") and self.nomi_ru:
            return self.nomi_ru
        return self.nomi

    def __str__(self):
        return self.nom


class Narxnoma(models.Model):
    """Narxnoma: aniqlanadigan ko'rsatkich + tahlil usuli + sinov obyekti + narx."""

    class SinovObyekti(models.TextChoices):
        MINERAL = "mineral", _("Mineral o'g'itlar")
        ORGANIK = "organik", _("Organik o'g'itlar")
        PESTITSID = "pestitsid", _("Pestitsidlar")
        TUPROQ = "tuproq", _("Tuproqlar")
        OZIQ_OVQAT = "oziq_ovqat", _("Qishloq xo'jalik va oziq-ovqat mahsulotlari")
        UMUMIY = "umumiy", _("Mineral o'g'itlar, tuproq, qishloq xo'jalik mahsulotlari")
        BOSHQA = "boshqa", _("Boshqa")

    # Qaysi laboratoriya qaysi obyektlarni shartnomaga qo'sha oladi
    KATEGORIYA_OBYEKTLARI = {
        "mineral": ["mineral", "organik", "tuproq", "umumiy", "boshqa"],
        "kimyoviy": ["pestitsid", "tuproq", "oziq_ovqat", "umumiy", "boshqa"],
    }

    tartib = models.PositiveIntegerField(_("Tartib raqami"), default=0)
    parametr = models.CharField(_("Aniqlanadigan tavsif (parametr) nomi"), max_length=1000)
    tahlil_usuli = models.CharField(_("Tahlil usuli"), max_length=500, blank=True)
    sinov_obyekti = models.CharField(_("Sinov obyekti turi"), max_length=20, choices=SinovObyekti.choices)
    obyekt_nomi = models.CharField(_("Sinovlar obyektining nomi"), max_length=500, blank=True)
    narx = models.DecimalField(_("Narxi, so'm"), max_digits=14, decimal_places=2)
    har_namunaga = models.BooleanField(
        _("Har bir namunaga hisoblanadi"), default=True,
        help_text=_("O'chirilsa, namunalar sonidan qat'i nazar bir marta hisoblanadi (masalan, namuna olish)."),
    )
    aktiv = models.BooleanField(_("Faol"), default=True)

    class Meta:
        ordering = ["tartib", "id"]
        verbose_name = _("Narxnoma")
        verbose_name_plural = _("Narxnoma")

    def __str__(self):
        return f"{self.parametr} ({self.tahlil_usuli})"


# ---------------------------------------------------------------------------
# Raqamlash
# ---------------------------------------------------------------------------
class Hisoblagich(models.Model):
    """Har yil uchun ketma-ket raqamlar (ariza, shartnoma, xulosa)."""

    kalit = models.CharField(max_length=50)
    yil = models.PositiveIntegerField()
    qiymat = models.PositiveIntegerField(_("Oxirgi berilgan raqam"), default=0)

    class Meta:
        unique_together = ("kalit", "yil")
        verbose_name = _("Hisoblagich (raqamlash)")
        verbose_name_plural = _("Hisoblagichlar (raqamlash)")

    def __str__(self):
        return f"{self.kalit} {self.yil}: {self.qiymat}"

    @classmethod
    def keyingi(cls, kalit, boshlanish=0):
        """Navbatdagi raqam. `boshlanish` — yangi yil hisoblagichi shu raqamdan davom etadi."""
        yil = timezone.localdate().year
        with transaction.atomic():
            obj, _ = cls.objects.select_for_update().get_or_create(
                kalit=kalit, yil=yil, defaults={"qiymat": boshlanish})
            obj.qiymat += 1
            obj.save(update_fields=["qiymat"])
            return yil, obj.qiymat


# ---------------------------------------------------------------------------
# Ariza
# ---------------------------------------------------------------------------
class ArizaTuri(models.TextChoices):
    IMPORTYOR = "importyor", _("Importyor")
    DAVLAT = "davlat", _("Davlat ro'yxatidan o'tkazuvchi")
    IXTIYORIY = "ixtiyoriy", _("Ixtiyoriy")


class Ariza(models.Model):
    class Holat(models.TextChoices):
        YANGI = "yangi", _("Yangi")
        QABUL = "qabul", _("Qabul qilingan")
        RAD = "rad", _("Rad etilgan")

    raqam = models.CharField(_("Ariza raqami"), max_length=30, unique=True, editable=False)
    turi = models.CharField(_("Ariza turi"), max_length=20, choices=ArizaTuri.choices)
    kategoriya = models.CharField(_("Kategoriya"), max_length=20, choices=Kategoriya.choices)
    # Arizadagi barcha namunalarning guruhlari ("mineral,kimyoviy") — laboratoriyalar ko'rinishi uchun
    kategoriyalar = models.CharField(_("Namuna guruhlari"), max_length=60, blank=True, db_index=True)
    mijoz = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("Mijoz"), on_delete=models.SET_NULL,
        null=True, blank=True, related_name="arizalar",
    )

    # Buyurtmachi ma'lumotlari
    inn = models.CharField(_("INN / JSHSHIR"), max_length=20)
    buyurtmachi_nomi = models.CharField(_("Buyurtmachi nomi"), max_length=255, blank=True)
    fish = models.CharField(_("F.I.SH."), max_length=255)
    telefon = models.CharField(_("Telefon"), max_length=30)
    manzil = models.CharField(_("Manzil"), max_length=500, blank=True)

    # Shartnoma uchun rekvizitlar (mijoz kiritadi, buxgalter to'g'irlashi mumkin)
    rahbar = models.CharField(_("Rahbar F.I.SH."), max_length=255, blank=True)
    hisob_raqam = models.CharField(_("Hisob raqami (X/R)"), max_length=40, blank=True)
    bank = models.CharField(_("Bank"), max_length=255, blank=True)
    mfo = models.CharField(_("MFO"), max_length=10, blank=True)
    oked = models.CharField(_("OKED"), max_length=10, blank=True)

    # Namuna ma'lumotlari
    namuna_soni = models.PositiveIntegerField(_("Namuna soni"), default=1)
    # Mijoz faqat guruhni (kategoriya) tanlaydi; aniq turni namuna qabul qiluvchi har bir namuna uchun kiritadi.
    # Bu maydon eski arizalar uchun saqlanib qolgan.
    namuna_turi = models.ForeignKey(NamunaTuri, verbose_name=_("Namuna turi"), on_delete=models.PROTECT,
                                    null=True, blank=True)
    namuna_nomi = models.CharField(_("Namuna nomi"), max_length=255, blank=True)
    partiya_raqami = models.CharField(_("Partiya raqami (LOT)"), max_length=100, blank=True)
    invoys_raqami = models.CharField(_("Invoys raqami"), max_length=100, blank=True)
    chegara_maskani = models.CharField(_("Chegara maskani / ombor"), max_length=255, blank=True)

    holat = models.CharField(_("Holati"), max_length=20, choices=Holat.choices, default=Holat.YANGI)
    qabul_qilgan = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("Qabul qilgan xodim"), on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    qabul_vaqti = models.DateTimeField(_("Qabul qilingan vaqt"), null=True, blank=True)
    rad_sababi = models.CharField(_("Rad etish sababi"), max_length=500, blank=True)
    created_at = models.DateTimeField(_("Yaratilgan vaqt"), default=timezone.now)
    yuborilgan_at = models.DateTimeField(_("Yuborilgan (qayta yuborilgan) vaqt"), default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Ariza")
        verbose_name_plural = _("Arizalar")

    def __str__(self):
        return self.raqam

    def save(self, *args, **kwargs):
        if not self.raqam:
            yil, n = Hisoblagich.keyingi("ariza")
            self.raqam = f"ATM-A-{yil}-{n:05d}"
        if self.namuna_turi_id and not self.kategoriya:
            self.kategoriya = self.namuna_turi.kategoriya
        if not self.kategoriyalar and self.kategoriya:
            self.kategoriyalar = self.kategoriya
        super().save(*args, **kwargs)

    @property
    def kategoriyalar_list(self):
        return [k for k in (self.kategoriyalar or self.kategoriya or "").split(",") if k]

    @property
    def aralash(self):
        return len(self.kategoriyalar_list) > 1

    def kategoriyalar_matni(self):
        nomlar = dict(Kategoriya.choices)
        return ", ".join(str(nomlar.get(k, k)) for k in self.kategoriyalar_list)

    def namunalar_yangila(self):
        """Namuna bloklaridan umumiy maydonlarni (eski kod va hujjatlar uchun) to'ldiradi."""
        bloklar = list(self.arizanamunalar.all())
        if not bloklar:
            return
        kat = []
        for b in bloklar:
            if b.kategoriya and b.kategoriya not in kat:
                kat.append(b.kategoriya)

        def qosh(maydon):
            q = []
            for b in bloklar:
                v = getattr(b, maydon)
                if v and v not in q:
                    q.append(v)
            return ", ".join(q)

        self.kategoriya = kat[0] if kat else self.kategoriya
        self.kategoriyalar = ",".join(sorted(kat, key=lambda k: Kategoriya.values.index(k)))
        self.namuna_soni = len(bloklar)
        self.namuna_nomi = qosh("nomi")[:255]
        self.partiya_raqami = qosh("partiya_raqami")[:100]
        self.invoys_raqami = qosh("invoys_raqami")[:100]
        Ariza.objects.filter(pk=self.pk).update(
            kategoriya=self.kategoriya, kategoriyalar=self.kategoriyalar, namuna_soni=self.namuna_soni,
            namuna_nomi=self.namuna_nomi, partiya_raqami=self.partiya_raqami, invoys_raqami=self.invoys_raqami)

    @property
    def turlar_matni(self):
        """Namunalar qabul qilingan bo'lsa ularning aniq turlari, aks holda guruh nomi."""
        turlar = []
        for n in self.namunalar.all():
            if n.namuna_turi_id and str(n.namuna_turi) not in turlar:
                turlar.append(str(n.namuna_turi))
        if not turlar and self.namuna_turi_id:
            turlar = [str(self.namuna_turi)]
        return ", ".join(turlar) or self.kategoriyalar_matni()

    @property
    def buyurtmachi(self):
        return self.buyurtmachi_nomi or self.fish

    @property
    def berilgan_soni(self):
        """Buyurtmachiga xulosasi berilgan namunalar soni (prefetch bilan ishlaydi)."""
        return sum(1 for n in self.namunalar.all() if n.lab_holat == "berildi")


class ArizaNamuna(models.Model):
    """Mijoz arizada har bir namuna uchun alohida to'ldiradigan blok."""

    ariza = models.ForeignKey(Ariza, on_delete=models.CASCADE, related_name="arizanamunalar")
    tartib = models.PositiveIntegerField(default=1)
    kategoriya = models.CharField(_("Namuna turi"), max_length=20, choices=Kategoriya.choices)
    nomi = models.CharField(_("Namuna nomi"), max_length=255, blank=True)
    partiya_raqami = models.CharField(_("Partiya raqami (LOT)"), max_length=100, blank=True)
    invoys_raqami = models.CharField(_("Invoys raqami"), max_length=100, blank=True)

    class Meta:
        ordering = ["tartib"]
        verbose_name = _("Arizadagi namuna")
        verbose_name_plural = _("Arizadagi namunalar")

    def __str__(self):
        return f"{self.ariza.raqam} / {self.tartib}"


def _hujjat_yoli(instance, filename):
    """Fayl nomi taxmin qilib bo'lmaydigan bo'lsin (asl kengaytma saqlanadi)."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"ariza/{timezone.now():%Y/%m}/{uuid.uuid4().hex}.{ext}"


class ArizaHujjat(models.Model):
    class Turi(models.TextChoices):
        INVOYS = "invoys", _("Invoys")
        ANALIZ = "analiz", _("Analiz sertifikati")
        GUVOHNOMA = "guvohnoma", _("Guvohnoma")
        QOSHIMCHA = "qoshimcha", _("Qo'shimcha hujjat")

    ariza = models.ForeignKey(Ariza, on_delete=models.CASCADE, related_name="hujjatlar")
    ariza_namuna = models.ForeignKey(ArizaNamuna, on_delete=models.CASCADE, null=True, blank=True,
                                     related_name="hujjatlar")
    turi = models.CharField(_("Hujjat turi"), max_length=20, choices=Turi.choices)
    fayl = models.FileField(_("Fayl"), upload_to=_hujjat_yoli)
    yuklangan = models.DateTimeField(auto_now_add=True)

    @property
    def url(self):
        from django.urls import reverse

        return reverse("ariza_hujjat", args=[self.pk])

    @property
    def nomi(self):
        if self.ariza_namuna_id:
            return f"№{self.ariza_namuna.tartib} · {self.get_turi_display()}"
        return self.get_turi_display()

    class Meta:
        ordering = ["ariza_namuna__tartib", "id"]
        verbose_name = _("Ariza hujjati")
        verbose_name_plural = _("Ariza hujjatlari")


# Har bir ariza turi uchun majburiy hujjatlar
ZARUR_HUJJATLAR = {
    ArizaTuri.IMPORTYOR: [ArizaHujjat.Turi.INVOYS, ArizaHujjat.Turi.ANALIZ, ArizaHujjat.Turi.GUVOHNOMA],
    ArizaTuri.DAVLAT: [ArizaHujjat.Turi.GUVOHNOMA, ArizaHujjat.Turi.ANALIZ],
    ArizaTuri.IXTIYORIY: [],  # o'zi uchun tekshirtiradiganlarda hujjat majburiy emas
}

# Har bir ariza turi formada qaysi maydonlarni ko'rsatadi (dizayn bo'yicha)
ARIZA_MAYDONLARI = {
    ArizaTuri.IMPORTYOR: {
        "majburiy": ["inn", "buyurtmachi_nomi", "fish", "telefon", "namuna_soni", "chegara_maskani"],
        "ixtiyoriy": [],
    },
    ArizaTuri.DAVLAT: {
        "majburiy": ["inn", "buyurtmachi_nomi", "fish", "telefon", "namuna_soni"],
        "ixtiyoriy": [],
    },
    ArizaTuri.IXTIYORIY: {
        "majburiy": ["inn", "fish", "telefon", "namuna_soni"],
        "ixtiyoriy": [],
    },
}

# Har bir namuna blokidagi maydonlar (ariza turiga qarab)
NAMUNA_MAYDONLARI = {
    ArizaTuri.IMPORTYOR: {"majburiy": ["kategoriya", "partiya_raqami", "nomi"], "ixtiyoriy": ["invoys_raqami"]},
    ArizaTuri.DAVLAT: {"majburiy": ["kategoriya"], "ixtiyoriy": ["nomi", "partiya_raqami"]},
    ArizaTuri.IXTIYORIY: {"majburiy": ["kategoriya"], "ixtiyoriy": ["nomi"]},
}
REKVIZIT_MAYDONLARI = ["manzil", "rahbar", "hisob_raqam", "bank", "mfo", "oked"]


# ---------------------------------------------------------------------------
# Shartnoma (Oferta) va to'lovlar
# ---------------------------------------------------------------------------
class Shartnoma(models.Model):
    class Holat(models.TextChoices):
        YUBORILMAGAN = "yuborilmagan", _("Buxgalteriyaga yuborilmagan")
        YUBORILGAN = "yuborilgan", _("Buxgalteriyaga yuborilgan")
        QABUL = "qabul", _("Buxgalter qabul qilgan")

    class TolovHolati(models.TextChoices):
        KUTILMOQDA = "kutilmoqda", _("To'lov kutilmoqda")
        QISMAN = "qisman", _("Qisman to'langan")
        TOLANGAN = "tolangan", _("To'langan")

    raqam = models.CharField(_("Shartnoma raqami"), max_length=30, unique=True, editable=False)
    ariza = models.ForeignKey(Ariza, verbose_name=_("Ariza"), on_delete=models.PROTECT, related_name="shartnomalar")
    holat = models.CharField(_("Holati"), max_length=20, choices=Holat.choices, default=Holat.YUBORILMAGAN)
    tolov_holati = models.CharField(
        _("To'lov holati"), max_length=20, choices=TolovHolati.choices, default=TolovHolati.KUTILMOQDA
    )
    jami_summa = models.DecimalField(_("Summasi"), max_digits=16, decimal_places=2, default=0)
    tolangan_summa = models.DecimalField(_("To'langan"), max_digits=16, decimal_places=2, default=0)

    yaratgan = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(_("Shakllantirilgan vaqt"), default=timezone.now)
    yuborilgan_at = models.DateTimeField(_("Buxgalteriyaga yuborilgan vaqt"), null=True, blank=True)
    qabul_at = models.DateTimeField(_("Buxgalter qabul qilgan vaqt"), null=True, blank=True)
    tahlilga_ruxsat_at = models.DateTimeField(_("30% to'langan vaqt"), null=True, blank=True)
    toliq_tolangan_at = models.DateTimeField(_("100% to'langan vaqt"), null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Shartnoma")
        verbose_name_plural = _("Shartnomalar")

    def __str__(self):
        return self.raqam

    def save(self, *args, **kwargs):
        if not self.raqam:
            _yil, n = Hisoblagich.keyingi("shartnoma", boshlanish=settings.SHARTNOMA_RAQAM_BOSHLANISH)
            self.raqam = str(n)
        super().save(*args, **kwargs)

    @property
    def tolangan_foiz(self):
        if not self.jami_summa:
            return Decimal(0)
        return (self.tolangan_summa / self.jami_summa * 100).quantize(Decimal("0.01"))

    @property
    def qoldiq(self):
        return max(self.jami_summa - self.tolangan_summa, Decimal(0))

    @property
    def tahrirlash_mumkin(self):
        """Ko'rsatkichlarni faqat buxgalteriyaga yuborilmagan va to'lov bo'lmagan shartnomada o'zgartirish mumkin."""
        return self.holat == self.Holat.YUBORILMAGAN and not self.tolovlar.exists()

    @property
    def narxsiz_kategoriyalar(self):
        """Aralash arizada hali narx belgilamagan laboratoriyalar (bo'lsa, buxgalteriyaga yuborib bo'lmaydi)."""
        bor = set(self.bandlar.values_list("kategoriya", flat=True))
        return [k for k in self.ariza.kategoriyalar_list if k not in bor]

    def narxsiz_matni(self):
        nomlar = dict(Kategoriya.choices)
        return ", ".join(str(nomlar.get(k, k)) for k in self.narxsiz_kategoriyalar)

    @property
    def tolov_ochirish_mumkin(self):
        """To'lovni faqat shartnomadagi namunalar tahlilga olinmaguncha o'chirish mumkin."""
        return not self.namunalar.exclude(lab_holat=Namuna.LabHolat.YANGI).exists()

    @property
    def xulosa_yuborish_mumkin(self):
        return self.jami_summa > 0 and self.tolangan_foiz >= settings.XULOSA_YUBORISH_MIN_FOIZ

    @property
    def tahlil_boshlash_mumkin(self):
        return self.jami_summa > 0 and self.tolangan_foiz >= settings.TAHLIL_BOSHLASH_MIN_FOIZ

    def qayta_hisobla(self):
        self.jami_summa = sum((b.summa for b in self.bandlar.all()), Decimal(0))
        self.tolangan_summa = sum((t.summa for t in self.tolovlar.all()), Decimal(0))
        if self.tolangan_summa <= 0:
            self.tolov_holati = self.TolovHolati.KUTILMOQDA
        elif self.tolangan_summa < self.jami_summa:
            self.tolov_holati = self.TolovHolati.QISMAN
        else:
            self.tolov_holati = self.TolovHolati.TOLANGAN
        # muddatlarni hisoblash uchun: 30% va 100% chegarasi qachon o'tilgan
        now = timezone.now()
        if self.tahlil_boshlash_mumkin:
            self.tahlilga_ruxsat_at = self.tahlilga_ruxsat_at or now
        else:
            self.tahlilga_ruxsat_at = None
        if self.xulosa_yuborish_mumkin:
            self.toliq_tolangan_at = self.toliq_tolangan_at or now
        else:
            self.toliq_tolangan_at = None
        self.save(update_fields=["jami_summa", "tolangan_summa", "tolov_holati", "tahlilga_ruxsat_at",
                                 "toliq_tolangan_at"])


class ShartnomaBand(models.Model):
    """Shartnomadagi tekshiriladigan ko'rsatkich (narxnomadan)."""

    shartnoma = models.ForeignKey(Shartnoma, on_delete=models.CASCADE, related_name="bandlar")
    narxnoma = models.ForeignKey(Narxnoma, on_delete=models.PROTECT)
    # qaysi laboratoriya qo'shgan (aralash arizada bitta shartnomaga ikkala laboratoriya narx qo'shadi)
    kategoriya = models.CharField(max_length=20, choices=Kategoriya.choices, blank=True)
    parametr = models.CharField(max_length=1000)
    tahlil_usuli = models.CharField(max_length=500, blank=True)
    narx = models.DecimalField(max_digits=14, decimal_places=2)
    namuna_soni = models.PositiveIntegerField(default=1)
    summa = models.DecimalField(max_digits=16, decimal_places=2)

    class Meta:
        ordering = ["id"]

    def save(self, *args, **kwargs):
        if not self.parametr:
            self.parametr = self.narxnoma.parametr
            self.tahlil_usuli = self.narxnoma.tahlil_usuli
        if self.narx is None:
            self.narx = self.narxnoma.narx
        soni = self.namuna_soni if self.narxnoma.har_namunaga else 1
        self.summa = (self.narx * soni).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)


class Tolov(models.Model):
    class Usul(models.TextChoices):
        BANK = "bank", _("Bank o'tkazmasi")
        CLICK = "click", _("Click")
        NAQD = "naqd", _("Naqd")

    shartnoma = models.ForeignKey(Shartnoma, on_delete=models.CASCADE, related_name="tolovlar")
    summa = models.DecimalField(_("Summa"), max_digits=16, decimal_places=2)
    usul = models.CharField(_("To'lov usuli"), max_length=10, choices=Usul.choices, default=Usul.BANK)
    sana = models.DateTimeField(_("To'lov sanasi"), default=timezone.now)
    izoh = models.CharField(_("Izoh"), max_length=255, blank=True)
    tashqi_id = models.CharField(_("Tranzaksiya ID"), max_length=100, blank=True, db_index=True)
    kiritgan = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-sana"]
        verbose_name = _("To'lov")
        verbose_name_plural = _("To'lovlar")


# ---------------------------------------------------------------------------
# Namuna (laboratoriyadagi har bir namuna) va Xulosa
# ---------------------------------------------------------------------------
class Namuna(models.Model):
    class LabHolat(models.TextChoices):
        YANGI = "yangi", _("Yangi namuna")
        TAHLILDA = "tahlilda", _("Tahlil uchun yuborilgan")       # mas'ullarga yuborildi, qabul kutilmoqda
        JARAYONDA = "jarayonda", _("Tahlil jarayonida")          # mas'ullar qabul qilib oldi
        NATIJA = "natija", _("Xulosa tayyor")                     # barcha mas'ullar natijani yubordi
        XULOSA = "xulosa", _("Xulosa tasdiqlangan")               # mudir tasdiqladi
        BERILDI = "berildi", _("Buyurtmachiga berilgan")

    ariza = models.ForeignKey(Ariza, verbose_name=_("Ariza"), on_delete=models.PROTECT, related_name="namunalar")
    ariza_namuna = models.ForeignKey(ArizaNamuna, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name="qabul_namunalar")
    shartnoma = models.ForeignKey(
        Shartnoma, verbose_name=_("Shartnoma"), on_delete=models.SET_NULL, null=True, blank=True,
        related_name="namunalar",
    )
    tartib = models.PositiveIntegerField(_("Namuna tartib raqami"), default=1)
    namuna_turi = models.ForeignKey(NamunaTuri, verbose_name=_("Namuna turi"), on_delete=models.PROTECT)
    nomi = models.CharField(_("Namuna nomi"), max_length=255, blank=True)
    tavsifi = models.CharField(_("Namuna tavsifi"), max_length=500, blank=True)
    tasir_etuvchi_modda = models.CharField(_("Ta'sir etuvchi modda"), max_length=500, blank=True)
    namuna_olgan = models.CharField(_("Namuna olgan mas'ul xodim"), max_length=255, blank=True)
    ogirligi = models.CharField(_("Og'irligi / hajmi"), max_length=50, blank=True)

    qabul_qilgan = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("Qabul qilgan"), on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    qabul_vaqti = models.DateTimeField(_("Namuna qabul qilingan vaqt"), default=timezone.now)

    lab_holat = models.CharField(_("Laboratoriya holati"), max_length=20, choices=LabHolat.choices,
                                 default=LabHolat.YANGI)
    tahlilga_vaqti = models.DateTimeField(_("Tahlilga topshirilgan vaqt"), null=True, blank=True)
    tahlil_qabul_qilgan = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("Tahlilga qabul qilgan"), on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )
    tahlil_tugagan_vaqti = models.DateTimeField(_("Tahlil yakunlangan vaqt"), null=True, blank=True)
    berilgan_vaqti = models.DateTimeField(_("Buyurtmachiga berilgan vaqt"), null=True, blank=True)

    class Meta:
        ordering = ["-qabul_vaqti"]
        verbose_name = _("Namuna")
        verbose_name_plural = _("Namunalar")

    def __str__(self):
        return f"{self.ariza.raqam}/{self.tartib}"

    @property
    def kategoriya(self):
        return self.namuna_turi.kategoriya


class Xulosa(models.Model):
    """Sinov bayonnomasi (xulosa) — har bir namuna uchun alohida."""

    namuna = models.OneToOneField(Namuna, on_delete=models.CASCADE, related_name="xulosa")
    raqam = models.CharField(_("Xulosa raqami"), max_length=30, unique=True, editable=False)
    sinov_sanasi = models.DateTimeField(_("Sinov o'tkazilgan sana"), null=True, blank=True)
    sinov_joyi = models.CharField(_("Sinov joyi"), max_length=255, default="Tahlil laboratoriyasi")
    dalolatnoma = models.CharField(_("Dalolatnoma №"), max_length=100, blank=True)
    harorat = models.CharField(_("Harorat"), max_length=50, default="T=(23±1)°C")
    namlik = models.CharField(_("Havoning nisbiy namligi"), max_length=50, default="W=(45±1)%")
    tasdiqlagan = models.CharField(_("Laboratoriya mudiri"), max_length=255, blank=True)
    bosh_agrokimyogar = models.CharField(_("Bosh agrokimyogar"), max_length=255, blank=True)
    yetakchi_agrokimyogar = models.CharField(_("Yetakchi agrokimyogar"), max_length=255, blank=True)

    verify_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    yaratgan = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(_("Yaratilgan vaqt"), default=timezone.now)
    tayyor_at = models.DateTimeField(_("Xulosa tayyor qilingan vaqt"), null=True, blank=True)
    tasdiqlangan_at = models.DateTimeField(_("Tasdiqlangan vaqt"), null=True, blank=True)
    tasdiqlagan_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, verbose_name=_("Tasdiqlagan xodim"), on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+",
    )

    @property
    def tasdiqlangan(self):
        return self.tasdiqlangan_at is not None

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Xulosa")
        verbose_name_plural = _("Xulosalar")

    def __str__(self):
        return self.raqam

    def save(self, *args, **kwargs):
        if not self.raqam:
            yil, n = Hisoblagich.keyingi("xulosa")
            self.raqam = f"ATM-P-{yil}-{n:05d}"
        super().save(*args, **kwargs)


class XulosaNatija(models.Model):
    xulosa = models.ForeignKey(Xulosa, on_delete=models.CASCADE, related_name="natijalar")
    topshiriq = models.ForeignKey("Topshiriq", verbose_name=_("Topshiriq"), on_delete=models.SET_NULL,
                                  null=True, blank=True, related_name="natijalar")
    tartib = models.PositiveIntegerField(default=1)
    korsatkich = models.CharField(_("Ko'rsatkich nomi, o'lchov birligi"), max_length=500)
    meyor = models.CharField(_("Me'yoriy qiymat"), max_length=255, blank=True)
    natija = models.CharField(_("Sinov natijasi (Xcp ± Upac)"), max_length=255, blank=True)
    sinov_usuli = models.CharField(_("Sinov usuli (ND hujjati)"), max_length=255, blank=True)
    muvofiqlik = models.CharField(_("Muvofiqlik haqida qaror"), max_length=100, blank=True)

    class Meta:
        ordering = ["tartib", "id"]


# ---------------------------------------------------------------------------
# 5-bosqich: xabarnomalar va Click
# ---------------------------------------------------------------------------
class Xabar(models.Model):
    """Yuborilgan SMS / Telegram xabarlari jurnali."""

    class Kanal(models.TextChoices):
        SMS = "sms", "SMS"
        TELEGRAM = "telegram", "Telegram"

    class Holat(models.TextChoices):
        YUBORILDI = "yuborildi", _("Yuborildi")
        XATO = "xato", _("Xato")
        OCHIQ = "ochiq", _("Sozlanmagan (yuborilmadi)")

    kanal = models.CharField(max_length=10, choices=Kanal.choices)
    kimga = models.CharField(_("Kimga"), max_length=100)
    matn = models.TextField(_("Matn"))
    holat = models.CharField(max_length=10, choices=Holat.choices)
    xato = models.CharField(max_length=500, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="+")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Xabar")
        verbose_name_plural = _("Xabarlar jurnali")


class ClickTranzaksiya(models.Model):
    """Click SHOP API tranzaksiyalari (prepare -> complete)."""

    class Holat(models.TextChoices):
        PREPARED = "prepared", _("Tayyorlandi")
        COMPLETED = "completed", _("To'landi")
        CANCELLED = "cancelled", _("Bekor qilindi")

    click_trans_id = models.CharField(max_length=40, unique=True)
    click_paydoc_id = models.CharField(max_length=40, blank=True)
    shartnoma = models.ForeignKey(Shartnoma, on_delete=models.PROTECT, related_name="click_tranzaksiyalar")
    summa = models.DecimalField(max_digits=16, decimal_places=2)
    holat = models.CharField(max_length=10, choices=Holat.choices, default=Holat.PREPARED)
    tolov = models.OneToOneField(Tolov, on_delete=models.SET_NULL, null=True, blank=True, related_name="click")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Click tranzaksiya")
        verbose_name_plural = _("Click tranzaksiyalar")


# ---------------------------------------------------------------------------
# Nazorat tarixi (faqat Super admin ko'radi, o'chirib bo'lmaydi)
# ---------------------------------------------------------------------------
class NazoratTarixi(models.Model):
    class Turi(models.TextChoices):
        NARXNOMA = "narxnoma", _("Narxnoma o'zgarishi")
        TOLOV_OCHIRISH = "tolov_ochirish", _("To'lov o'chirildi")
        ARIZA_RAD = "ariza_rad", _("Ariza rad etildi")
        XODIM = "xodim", _("Xodim o'zgarishi")
        XULOSA_QAYTARISH = "xulosa_qaytarish", _("Xulosa qaytarildi")
        SOZLAMA = "sozlama", _("Sozlamalar o'zgarishi")
        PAROL = "parol", _("Parol tiklandi")

    vaqt = models.DateTimeField(_("Vaqt"), default=timezone.now, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_("Xodim"), on_delete=models.SET_NULL,
                             null=True, blank=True, related_name="+")
    user_nomi = models.CharField(_("Xodim"), max_length=255, blank=True)
    turi = models.CharField(_("Harakat turi"), max_length=30, choices=Turi.choices, db_index=True)
    obyekt = models.CharField(_("Obyekt"), max_length=500, blank=True)
    obyekt_id = models.CharField(max_length=40, blank=True, db_index=True)
    tafsilot = models.TextField(_("Tafsilot"), blank=True)

    class Meta:
        ordering = ["-vaqt", "-id"]
        verbose_name = _("Nazorat tarixi")
        verbose_name_plural = _("Nazorat tarixi")

    def __str__(self):
        return f"{self.vaqt:%d.%m.%Y %H:%M} {self.get_turi_display()}"

    @classmethod
    def yoz(cls, user, turi, obyekt="", tafsilot="", obyekt_id=""):
        nom = ""
        if user is not None and getattr(user, "is_authenticated", False):
            nom = f"{user.fish or user.username} ({user.get_role_display()})"
        return cls.objects.create(user=user if nom else None, user_nomi=nom, turi=turi, obyekt=str(obyekt)[:500],
                                  obyekt_id=str(obyekt_id), tafsilot=tafsilot)



class Topshiriq(models.Model):
    """Laboratoriya mudiri namunaning ko'rsatkichlarini mas'ul xodimlarga taqsimlaydi."""

    class Holat(models.TextChoices):
        YUBORILDI = "yuborildi", _("Qabul qilinishi kutilmoqda")
        QABUL = "qabul", _("Tahlil jarayonida")
        TAYYOR = "tayyor", _("Natija yuborildi")
        QAYTARILDI = "qaytarildi", _("Tuzatish uchun qaytarildi")

    namuna = models.ForeignKey(Namuna, on_delete=models.CASCADE, related_name="topshiriqlar")
    masul = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_("Mas'ul xodim"), on_delete=models.PROTECT,
                              related_name="topshiriqlar")
    yuborgan = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="+")
    holat = models.CharField(_("Holati"), max_length=12, choices=Holat.choices, default=Holat.YUBORILDI)
    yuborilgan_at = models.DateTimeField(_("Yuborilgan vaqt"), default=timezone.now)
    qabul_at = models.DateTimeField(_("Qabul qilingan vaqt"), null=True, blank=True)
    tayyor_at = models.DateTimeField(_("Natija yuborilgan vaqt"), null=True, blank=True)
    qaytarilgan_at = models.DateTimeField(_("Qaytarilgan vaqt"), null=True, blank=True)
    izoh = models.TextField(_("Qaytarish sababi"), blank=True)

    class Meta:
        ordering = ["-yuborilgan_at"]
        unique_together = ("namuna", "masul")
        verbose_name = _("Topshiriq")
        verbose_name_plural = _("Topshiriqlar")

    def __str__(self):
        return f"{self.namuna} — {self.masul}"

    @property
    def tahrirlash_mumkin(self):
        return self.holat in (self.Holat.QABUL, self.Holat.QAYTARILDI)



# ---------------------------------------------------------------------------
# Ish muddatlari (kechikish ogohlantirishi) sozlamalari
# ---------------------------------------------------------------------------
class Sozlama(models.Model):
    """Yagona yozuv (pk=1). Muddatlar ish vaqti bo'yicha, daqiqalarda."""

    ish_boshlanishi = models.TimeField(_("Ish boshlanishi"), default=time(9, 0))
    ish_tugashi = models.TimeField(_("Ish tugashi"), default=time(18, 0))
    ish_kunlari = models.CharField(_("Ish kunlari"), max_length=20, default="0,1,2,3,4",
                                   help_text=_("0 — dushanba ... 6 — yakshanba"))
    muddat_ariza_qabul = models.PositiveIntegerField(_("Arizani qabul qilish yoki rad etish"), default=60)
    muddat_narx_belgilash = models.PositiveIntegerField(_("Namuna qabul qilingach narx belgilash"), default=60)
    muddat_shartnoma_yuborish = models.PositiveIntegerField(_("Shartnomani buxgalteriyaga yuborish"), default=60)
    muddat_bux_korish = models.PositiveIntegerField(_("Buxgalter shartnomani ko'rishi"), default=60)
    muddat_tahlilga_yuborish = models.PositiveIntegerField(_("30% to'langach tahlilga yuborish"), default=60)
    muddat_topshiriq_qabul = models.PositiveIntegerField(_("Mas'ul topshiriqni qabul qilishi"), default=60)
    muddat_tahlil = models.PositiveIntegerField(_("Tahlil va natija kiritish"), default=540,
                                                help_text=_("540 daqiqa = 1 ish kuni"))
    muddat_qaytarilgan = models.PositiveIntegerField(_("Qaytarilgan natijani tuzatish"), default=60)
    muddat_xulosa_tasdiqlash = models.PositiveIntegerField(_("Mudir xulosani tasdiqlashi"), default=60)
    muddat_xulosa_berish = models.PositiveIntegerField(_("100% to'langach xulosani berish"), default=60)
    updated_at = models.DateTimeField(auto_now=True)

    MUDDAT_MAYDONLARI = ["muddat_ariza_qabul", "muddat_narx_belgilash", "muddat_shartnoma_yuborish",
                         "muddat_bux_korish", "muddat_tahlilga_yuborish", "muddat_topshiriq_qabul", "muddat_tahlil",
                         "muddat_qaytarilgan", "muddat_xulosa_tasdiqlash", "muddat_xulosa_berish"]

    class Meta:
        verbose_name = _("Sozlamalar")
        verbose_name_plural = _("Sozlamalar")

    @classmethod
    def ol(cls):
        obj, created = cls.objects.get_or_create(pk=1)
        return cls.objects.get(pk=1) if created else obj  # yangi bo'lsa vaqt maydonlari str bo'lib qolmasin

    @property
    def ish_kunlari_list(self):
        return {int(x) for x in self.ish_kunlari.split(",") if x.strip().isdigit()}


class Bayram(models.Model):
    sana = models.DateField(_("Sana"), unique=True)
    nomi = models.CharField(_("Nomi"), max_length=255, blank=True)

    class Meta:
        ordering = ["sana"]
        verbose_name = _("Bayram (dam olish) kuni")
        verbose_name_plural = _("Bayram (dam olish) kunlari")

    def __str__(self):
        return f"{self.sana:%d.%m.%Y} {self.nomi}"
