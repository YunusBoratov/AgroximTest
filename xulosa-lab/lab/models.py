import uuid
from decimal import Decimal

from django.db import models


class Norma(models.Model):
    ELEMENT_CHOICES = [
        ('azot', 'Azot (N)'),
        ('fosfor', 'Fosfor (P2O5)'),
        ('kaliy', 'Kaliy (K2O)'),
        ('namlik', 'Namlik'),
    ]

    element = models.CharField(max_length=20, choices=ELEMENT_CHOICES, unique=True)
    min_qiymat = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    max_qiymat = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.get_element_display()}: {self.min_qiymat} - {self.max_qiymat}"


class Xulosa(models.Model):
    STATUS_CHOICES = [
        ('kutilmoqda', 'Kutilmoqda'),
        ('tahlil', 'Tahlil qilinmoqda'),
        ('tayyor', 'Xulosa tayyor'),
        ('yuborildi', 'Xulosa yuborildi'),
    ]

    yuborilgan = models.BooleanField(default=False)
    yuborilgan_vaqt = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='kutilmoqda'
    )

    sana = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Xulosa"
        verbose_name_plural = "Xulosa"

    def __str__(self):
        return f"Xulosa #{self.id}"

    verify_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    namuna_raqami = models.CharField(max_length=50)
    buyurtmachi = models.CharField(max_length=255)
    sana = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='kutilmoqda')

    azot = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    fosfor = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    kaliy = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    namlik = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    xulosa_matni = models.TextField(blank=True)

    moslik = models.CharField(
        max_length=10,
        choices=[('mos', 'Mos'), ('mos_emas', 'Mos emas')],
        blank=True
    )

    def _norma_ichidami(self, element: str, qiymat):
        if qiymat is None:
            return None

        norma = Norma.objects.filter(element=element).first()
        if norma is None:
            return None

        v = Decimal(qiymat)

        if norma.min_qiymat is not None and v < norma.min_qiymat:
            return False
        if norma.max_qiymat is not None and v > norma.max_qiymat:
            return False
        return True

    def hisobla_moslik_va_matn(self):
        tekshiruvlar = {
            'azot': self._norma_ichidami('azot', self.azot),
            'fosfor': self._norma_ichidami('fosfor', self.fosfor),
            'kaliy': self._norma_ichidami('kaliy', self.kaliy),
            'namlik': self._norma_ichidami('namlik', self.namlik),
        }

        muammo = []
        mos_emaslar = []

        nomlar = {
            'azot': 'Azot',
            'fosfor': 'Fosfor',
            'kaliy': 'Kaliy',
            'namlik': 'Namlik',
        }

        for key, natija in tekshiruvlar.items():
            if natija is None:
                muammo.append(nomlar[key])
            elif natija is False:
                mos_emaslar.append(nomlar[key])

        if mos_emaslar:
            moslik = 'mos_emas'
        else:
            if all(v is None for v in tekshiruvlar.values()):
                moslik = ''
            else:
                moslik = 'mos'

        if moslik == '':
            matn = "Natijalar kiritilmagan yoki me'yorlar sozlanmagan."
        elif moslik == 'mos':
            matn = "Kiritilgan ko'rsatkichlar me'yorlarga MOS."
        else:
            matn = "Quyidagi ko'rsatkichlar me'yorlarga MOS EMAS: " + ", ".join(mos_emaslar) + "."

        if muammo:
            matn += " (Norma yo'q yoki qiymat kiritilmagan: " + ", ".join(muammo) + ")"

        return moslik, matn

    def save(self, *args, **kwargs):
        self.moslik, self.xulosa_matni = self.hisobla_moslik_va_matn()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.namuna_raqami} — {self.buyurtmachi}"
import uuid
from django.db import models


class Namuna(models.Model):
    ariza_raqami = models.CharField(
        max_length=20,
        unique=True,
        editable=False
    )

    masul_shaxs = models.CharField("Namuna olgan mas’ul shaxs (F.I.Sh)", max_length=255)

    korxona_nomi = models.CharField("Korxona / tashkilot nomi", max_length=255)
    korxona_inn = models.CharField("INN", max_length=20)
    korxona_telefon = models.CharField("Telefon raqam", max_length=30)

    namuna_turi = models.CharField("Namuna turi", max_length=100)
    namuna_soni = models.PositiveIntegerField("Namuna soni")

    qabul_vaqti = models.DateTimeField("Qabul qilingan vaqt", auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.ariza_raqami:
            last = Namuna.objects.order_by("id").last()
            next_id = 1 if not last else last.id + 1
            self.ariza_raqami = f"AGT-{self.qabul_vaqti.year if self.pk else 2026}-{next_id:05d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ariza_raqami} — {self.korxona_nomi}"

    class Meta:
        verbose_name = "Namuna"
        verbose_name_plural = "Namunalar"
        ordering = ["-qabul_vaqti"]