from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    SUPER_ADMIN = "super_admin", _("Super admin")
    ADMIN = "admin", _("Admin")
    BUXGALTERIYA = "buxgalteriya", _("Buxgalteriya")
    LAB_MINERAL = "lab_mineral", _("Mineral o'g'it tahlil laboratoriyasi (mudir)")
    LAB_KIMYO = "lab_kimyo", _("Kimyoviy vositalar tahlil laboratoriyasi (mudir)")
    NAMUNA_QABUL = "namuna_qabul", _("Namuna qabul qilib oluvchi")
    MASUL_MINERAL = "masul_mineral", _("Sinov o'tkazuvchi mas'ul (mineral o'g'it)")
    MASUL_KIMYO = "masul_kimyo", _("Sinov o'tkazuvchi mas'ul (kimyoviy vosita)")
    MIJOZ = "mijoz", _("Buyurtmachi (mijoz)")


STAFF_ROLES = [r for r in Role.values if r != Role.MIJOZ]


class User(AbstractUser):
    role = models.CharField(_("Rol"), max_length=20, choices=Role.choices, default=Role.MIJOZ)
    fish = models.CharField(_("F.I.SH."), max_length=255, blank=True)
    telefon = models.CharField(_("Telefon"), max_length=30, blank=True)
    lavozim = models.CharField(_("Lavozimi"), max_length=255, blank=True)

    # Mijozlar uchun (OneID orqali to'ldiriladi)
    pinfl = models.CharField(_("JSHSHIR"), max_length=14, blank=True)
    inn = models.CharField(_("INN"), max_length=20, blank=True)
    tashkilot_nomi = models.CharField(_("Tashkilot nomi"), max_length=255, blank=True)
    telegram_chat_id = models.CharField(_("Telegram chat ID"), max_length=30, blank=True)
    sms_xabar = models.BooleanField(_("SMS xabarnomalar"), default=True)
    parol_almashtirish = models.BooleanField(_("Keyingi kirishda parolni almashtirishi shart"), default=False)

    class Meta:
        verbose_name = _("Foydalanuvchi")
        verbose_name_plural = _("Foydalanuvchilar")

    def __str__(self):
        return self.fish or self.username

    def save(self, *args, **kwargs):
        # `createsuperuser` bilan yaratilgan bosh admin "mijoz" bo'lib qolmasin
        if self.is_superuser and self.role == Role.MIJOZ:
            self.role = Role.SUPER_ADMIN
        super().save(*args, **kwargs)

    # --- rol yordamchilari ---
    @property
    def is_admin_role(self):
        return self.role in (Role.SUPER_ADMIN, Role.ADMIN) or self.is_superuser

    @property
    def is_lab(self):
        return self.role in (Role.LAB_MINERAL, Role.LAB_KIMYO)

    @property
    def is_masul(self):
        return self.role in (Role.MASUL_MINERAL, Role.MASUL_KIMYO)

    @property
    def lab_kategoriya(self):
        """Laboratoriya mudiri yoki mas'ul xodim qaysi kategoriya bilan ishlaydi."""
        return {Role.LAB_MINERAL: "mineral", Role.LAB_KIMYO: "kimyoviy",
                Role.MASUL_MINERAL: "mineral", Role.MASUL_KIMYO: "kimyoviy"}.get(self.role)
