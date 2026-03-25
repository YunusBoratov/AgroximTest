
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
import uuid
from django.db.models import Sum
from django.utils import timezone
#from .models import Xulosa

class Shartnoma(models.Model):
    xulosa_ruxsat = models.BooleanField(default=False)
    STATUS_CHOICES = [
        ("kutilmoqda", "To'lov kutilmoqda"),
        ("tolangan", "To'langan"),
        ("tayyor", "Tayyor"),
    ]
    buyurtmachi = models.CharField(max_length=255)
    masul_shaxs = models.CharField(max_length=255)
    inn = models.CharField(max_length=50)
    telefon = models.CharField(max_length=50)
    jami_summa = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    sana = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="kutilmoqda"
    )
    tolangan_summa = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0
    )

    is_active = models.BooleanField(default=True)
    umumiy_summa = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0
    )
    def hisobla(self):
        jami = self.bandlar.aggregate(
            jami=Sum("jami_summa")
        )["jami"] or Decimal("0.00")
        self.umumiy_summa = jami
        self.save(update_fields=["umumiy_summa"])
    def yangila_status(self):
        if self.tolangan_summa >= self.jami_summa and self.jami_summa > 0:
            self.status = "tolangan"
            self.xulosa_ruxsat = True
        else:
            self.status = "kutilmoqda"
            self.xulosa_ruxsat = False
    def __str__(self):
        return f"Shartnoma #{self.id} - {self.buyurtmachi}"
class ShartnomaItem(models.Model):
    shartnoma = models.ForeignKey(Shartnoma, on_delete=models.CASCADE, related_name="items")
    narxnoma = models.ForeignKey("Narxnoma", on_delete=models.CASCADE)


# =========================
# NAMUNA
# =========================
class Namuna(models.Model):

    shartnoma = models.ForeignKey(
        Shartnoma,
        on_delete=models.CASCADE,
        related_name="namunalar"
    )

    ariza_raqami = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
    )

    korxona_nomi = models.CharField(max_length=255)
    inn = models.CharField(max_length=20)
    telefon = models.CharField(max_length=30)


    NAMUNA_TURI = [
        ("mineral", "Mineral o'g'it"),
        ("pestsid", "Pestitsid"),
    ]

    namuna_turi = models.CharField(
        max_length=20,
        choices=NAMUNA_TURI
    )

    qabul_vaqti = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-qabul_vaqti"]

    def save(self, *args, **kwargs):
        if not self.ariza_raqami:
            last = Namuna.objects.order_by("id").last()
            next_id = 1 if not last else last.id + 1
            self.ariza_raqami = f"AGT-2026-{next_id:05d}"

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ariza_raqami} — {self.korxona_nomi}"


# =========================
# NARXNOMA
# =========================
class Narxnoma(models.Model):
    

    NAMUNA_TURI_CHOICES = [
        ("mineral", "Mineral o'g'it"),
        ("pestitsid", "Pestitsid"),
    ]

    korsatkich_nomi = models.CharField(max_length=100)
    tahlil_usuli = models.CharField(max_length=150)
    birlik = models.CharField(max_length=50, blank=True)
    narx = models.DecimalField(max_digits=12, decimal_places=2)
    aktiv = models.BooleanField(default=True)
    meyor = models.CharField(max_length=100, blank=True)

    namuna_turi = models.CharField(
        max_length=20,
        choices=NAMUNA_TURI_CHOICES,
        default="mineral"
    )

    def __str__(self):
        return self.korsatkich_nomi

    def __str__(self):
        return self.korsatkich_nomi
    class Meta:
        verbose_name = "Narxnoma"
        verbose_name_plural = "Narxnomalar"
        ordering = ["korsatkich_nomi"]

    def __str__(self):
        return f"{self.korsatkich_nomi} | {self.tahlil_usuli}"



# =========================
# SHARTNOMA BANDI
# =========================
class ShartnomaBand(models.Model):

    shartnoma = models.ForeignKey(
        Shartnoma,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="bandlar"
    )

    namuna = models.ForeignKey(
        Namuna,
        on_delete=models.CASCADE,
        related_name="bandlar"
    )

    narxnoma = models.ForeignKey(
        Narxnoma,
        on_delete=models.PROTECT
    )

    namuna_soni = models.PositiveIntegerField(default=1)

    birlik_narx = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False
    )

    jami_summa = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        editable=False
    )

    tartib_raqam = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["tartib_raqam"]

    def save(self, *args, **kwargs):

        # avtomatik shartnoma biriktirish
        if not self.shartnoma and self.namuna:
            self.shartnoma = self.namuna.shartnoma

        # avtomatik narx olish
        self.birlik_narx = self.narxnoma.narx
        self.jami_summa = Decimal(self.birlik_narx) * Decimal(self.namuna_soni)

        super().save(*args, **kwargs)

        # saqlangandan keyin umumiy summani yangilaymiz
        self.shartnoma.hisobla()

    def __str__(self):
        return f"{self.narxnoma} x {self.namuna_soni}"


# =========================
# NORMA
# =========================
class Norma(models.Model):
    ELEMENT_CHOICES = [
        ('azot', 'Azot'),
        ('fosfor', 'Fosfor'),
        ('kaliy', 'Kaliy'),
        ('namlik', 'Namlik'),
    ]

    element = models.CharField(max_length=20, choices=ELEMENT_CHOICES, unique=True)
    min_qiymat = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    max_qiymat = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return self.get_element_display()


# =========================
# XULOSA
# =========================
class Xulosa(models.Model):
    shartnoma = models.ForeignKey(
        Shartnoma,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    namuna = models.OneToOneField(
        Namuna,
        on_delete=models.CASCADE,
        related_name="xulosa"
    )
#///////////////////////////////////////////////////////////////////////////////////////////////

    sinov_otkazilgan_sana = models.DateField(null=True, blank=True)

    sinov_joyi = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    namuna_ogirligi = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    namuna_bayonnoma = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )

    tashqi_tahlil_natija = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    harorat = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    namlik = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    namuna_identifikatsiya = models.TextField(
        blank=True,
        null=True
    )

    sinov_otkazuvchi = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )
    def clean_sinov_otkazuvchi(self):
        data = self.cleaned_data['sinov_otkazuvchi']
        if len(data.split(",")) < 3:
            raise forms.ValidationError("Kamida 3 ta sinov o'tkazuvchi kiriting")
        return data

#///////////////////////////////////////////////////////////////////////////////////////////////
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    matn = models.TextField(verbose_name="Xulosa matni (UZ)")

    STATUS_CHOICES = [
        ('kiritilmagan', 'Xulosa kiritilmagan'),
        ('tayyor', 'Tayyor'),
        ('yuborildi', 'Yuborildi'),
    ]

    class Meta:
            verbose_name = "Xulosa"
            verbose_name_plural = "Xulosa"

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='kiritilmagan')
    verify_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    sana = models.DateTimeField(auto_now_add=True)

    # --- SINOV MA'LUMOTLARI ---
    sinov_sana = models.DateTimeField(null=True, blank=True)
    sinov_joy = models.CharField(max_length=255, blank=True)

    namuna_ogirligi = models.FloatField(null=True, blank=True)
    bayonnoma_raqami = models.CharField(max_length=100, blank=True)
    bayonnoma_sana = models.DateField(null=True, blank=True)

    # --- ATROF MUHIT ---
    harorat = models.CharField(max_length=50, blank=True)
    namlik = models.CharField(max_length=50, blank=True)

    # --- NAMUNA TAVSIFI ---
    namuna_tavsifi = models.TextField(blank=True)

    # --- IMZO ---
    tahlilchi_1 = models.CharField(max_length=150, blank=True)
    tahlilchi_2 = models.CharField(max_length=150, blank=True)
    laboratoriya_mudiri = models.CharField(max_length=150, blank=True)

    tasdiqlangan_sana = models.DateTimeField(null=True, blank=True)
    tasdiqlovchi = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"Xulosa — {self.namuna.ariza_raqami}"
# ============================
# XULOSA BANDLARI (PDF jadval qatorlari)
# ============================

class XulosaBand(models.Model):
    
    xulosa = models.ForeignKey(
        Xulosa,
        on_delete=models.CASCADE,
        related_name="bandlar"
    )

    narxnoma = models.ForeignKey(
        Narxnoma,
        on_delete=models.CASCADE

    )

    tartib_raqam = models.IntegerField()

    meyor = models.CharField(max_length=255, blank=True)
    natija = models.CharField(max_length=255, blank=True)
    
    class Meta:
        ordering = ["tartib_raqam"]

    def save(self, *args, **kwargs):
        if not self.tartib_raqam:
            last = XulosaBand.objects.filter(
                xulosa=self.xulosa
            ).order_by("-tartib_raqam").first()

            if last:
                self.tartib_raqam = last.tartib_raqam + 1
            else:
                self.tartib_raqam = 1

        super().save(*args, **kwargs)

    def __str__(self):
        if self.narxnoma:
            return f"{self.tartib_raqam}. {self.narxnoma.korsatkich_nomi}"
        return f"{self.tartib_raqam}. (Narxnoma yo‘q)"
    
class Natija(models.Model):
    xulosa = models.ForeignKey(Xulosa, related_name="natijalar", on_delete=models.CASCADE)
    korsatkich_nomi = models.CharField(max_length=255)
    sinov_usuli = models.CharField(max_length=255)
    meyor = models.CharField(max_length=100, blank=True)
    natija = models.CharField(max_length=100)

    def __str__(self):
        return self.korsatkich_nomi
    