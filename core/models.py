import uuid
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
    namuna_turi = models.ForeignKey(NamunaTuri, verbose_name=_("Namuna turi"), on_delete=models.PROTECT)
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
        super().save(*args, **kwargs)

    @property
    def buyurtmachi(self):
        return self.buyurtmachi_nomi or self.fish

    @property
    def berilgan_soni(self):
        """Buyurtmachiga xulosasi berilgan namunalar soni (prefetch bilan ishlaydi)."""
        return sum(1 for n in self.namunalar.all() if n.lab_holat == "berildi")


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
    turi = models.CharField(_("Hujjat turi"), max_length=20, choices=Turi.choices)
    fayl = models.FileField(_("Fayl"), upload_to=_hujjat_yoli)
    yuklangan = models.DateTimeField(auto_now_add=True)

    @property
    def url(self):
        from django.urls import reverse

        return reverse("ariza_hujjat", args=[self.pk])

    class Meta:
        verbose_name = _("Ariza hujjati")
        verbose_name_plural = _("Ariza hujjatlari")


# Har bir ariza turi uchun majburiy hujjatlar
ZARUR_HUJJATLAR = {
    ArizaTuri.IMPORTYOR: [ArizaHujjat.Turi.INVOYS, ArizaHujjat.Turi.ANALIZ, ArizaHujjat.Turi.GUVOHNOMA],
    ArizaTuri.DAVLAT: [ArizaHujjat.Turi.GUVOHNOMA, ArizaHujjat.Turi.ANALIZ],
    ArizaTuri.IXTIYORIY: [ArizaHujjat.Turi.GUVOHNOMA],
}

# Har bir ariza turi formada qaysi maydonlarni ko'rsatadi (dizayn bo'yicha)
ARIZA_MAYDONLARI = {
    ArizaTuri.IMPORTYOR: {
        "majburiy": ["inn", "buyurtmachi_nomi", "fish", "telefon", "namuna_soni", "namuna_turi", "namuna_nomi",
                     "chegara_maskani"],
        "ixtiyoriy": ["partiya_raqami", "invoys_raqami"],
    },
    ArizaTuri.DAVLAT: {
        "majburiy": ["inn", "buyurtmachi_nomi", "fish", "telefon", "namuna_soni", "namuna_turi"],
        "ixtiyoriy": ["namuna_nomi", "partiya_raqami"],
    },
    ArizaTuri.IXTIYORIY: {
        "majburiy": ["inn", "fish", "telefon", "namuna_soni", "namuna_turi"],
        "ixtiyoriy": ["namuna_nomi"],
    },
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
        self.save(update_fields=["jami_summa", "tolangan_summa", "tolov_holati"])


class ShartnomaBand(models.Model):
    """Shartnomadagi tekshiriladigan ko'rsatkich (narxnomadan)."""

    shartnoma = models.ForeignKey(Shartnoma, on_delete=models.CASCADE, related_name="bandlar")
    narxnoma = models.ForeignKey(Narxnoma, on_delete=models.PROTECT)
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
        TAHLILDA = "tahlilda", _("Tahlil uchun yuborilgan")
        NATIJA = "natija", _("Tahlil natijalari tayyor")
        XULOSA = "xulosa", _("Xulosa kiritilgan")
        BERILDI = "berildi", _("Buyurtmachiga berilgan")

    ariza = models.ForeignKey(Ariza, verbose_name=_("Ariza"), on_delete=models.PROTECT, related_name="namunalar")
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
