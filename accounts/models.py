from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class Role(models.TextChoices):
    SUPER_ADMIN = "super_admin", _("Super admin")
    ADMIN = "admin", _("Admin")
    BUXGALTERIYA = "buxgalteriya", _("Buxgalteriya")
    LAB_MINERAL = "lab_mineral", _("Mineral o'g'it tahlil laboratoriyasi")
    LAB_KIMYO = "lab_kimyo", _("Kimyoviy vositalar tahlil laboratoriyasi")
    NAMUNA_QABUL = "namuna_qabul", _("Namuna qabul qilib oluvchi")
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

    class Meta:
        verbose_name = _("Foydalanuvchi")
        verbose_name_plural = _("Foydalanuvchilar")

    def __str__(self):
        return self.fish or self.username

    # --- rol yordamchilari ---
    @property
    def is_admin_role(self):
        return self.role in (Role.SUPER_ADMIN, Role.ADMIN) or self.is_superuser

    @property
    def is_lab(self):
        return self.role in (Role.LAB_MINERAL, Role.LAB_KIMYO)

    @property
    def lab_kategoriya(self):
        """Laboratoriya xodimi qaysi kategoriya bilan ishlaydi."""
        return {Role.LAB_MINERAL: "mineral", Role.LAB_KIMYO: "kimyoviy"}.get(self.role)
