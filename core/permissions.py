from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext_lazy as _

from accounts.models import Role

SA, AD, BX, LM, LK, NQ = (Role.SUPER_ADMIN, Role.ADMIN, Role.BUXGALTERIYA,
                          Role.LAB_MINERAL, Role.LAB_KIMYO, Role.NAMUNA_QABUL)
LAB = (LM, LK)
MASUL = (Role.MASUL_MINERAL, Role.MASUL_KIMYO)
ADMINS = (SA, AD)

# (url nomi, yorliq, kimlarga ko'rinadi)
MENU = [
    ("dashboard", _("Monitoring"), ADMINS + (NQ,)),
    ("dashboard", _("Asosiy panel"), (BX,) + LAB),
    ("masul_topshiriqlar", _("Topshiriqlar"), MASUL),
    ("ariza_list", _("Ariza"), ADMINS + (NQ,)),
    ("namuna_yaratish", _("Namuna yaratish"), (NQ,)),
    ("namuna_list", _("Namuna"), ADMINS),
    ("namuna_list", _("Namunalar"), (NQ,)),
    ("shartnoma_list", _("Shartnoma tuzilishi va bajarilishi"), ADMINS + LAB),
    ("oferta_list", _("Oferta"), ADMINS + (BX,)),
    ("tahlil_holati", _("Laboratoriya tahlil holati"), ADMINS + LAB),
    ("xulosa_list", _("Xulosa"), ADMINS + LAB),
    ("narxnoma_list", _("Narxnoma"), (SA, BX)),
    ("xodim_list", _("Xodimlar"), (SA,)),
    ("buyurtmachi_list", _("Buyurtmachilar"), (SA,)),
    ("statistika", _("Statistika"), ADMINS + (BX,)),
    ("sozlamalar", _("Sozlamalar"), ADMINS),
    ("nazorat_tarixi", _("Nazorat tarixi"), (SA,)),
]


def user_role(user):
    if user.is_superuser:
        return SA
    return user.role


def menu_for(user):
    role = user_role(user)
    seen, items = set(), []
    for name, label, roles in MENU:
        if role in roles and (name, str(label)) not in seen:
            # bir xil url ikki marta chiqmasin (masalan Monitoring/Asosiy panel)
            if any(i[0] == name for i in items):
                continue
            seen.add((name, str(label)))
            items.append((name, label))
    return items


def role_required(*roles):
    """Faqat ko'rsatilgan rollarga ruxsat (super admin har doim kiradi)."""

    def deco(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            role = user_role(request.user)
            if role != SA and role not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return deco


def hujjat_korinadimi(user, hujjat):
    """Invoysni faqat ruxsat etilgan rollar (sozlamada) va arizaning egasi (mijoz) ko'radi."""
    from django.conf import settings

    # laboratoriya xodimi (mudir yoki mas'ul) faqat o'z guruhidagi namunaning hujjatlarini ko'radi
    kat = getattr(user, "lab_kategoriya", None) if user_role(user) != Role.SUPER_ADMIN else None
    if kat and hujjat.ariza_namuna_id and hujjat.ariza_namuna.kategoriya != kat:
        return False
    if hujjat.turi != "invoys":
        return True
    role = user_role(user)
    if role in settings.INVOYS_KORADI_ROLLAR:
        return True
    return role == Role.MIJOZ and hujjat.ariza.mijoz_id == user.id


def korinadigan_hujjatlar(user, hujjatlar, namuna=None):
    """namuna berilsa — faqat shu namunaning (va arizaning umumiy) hujjatlari."""
    if namuna is not None:
        hujjatlar = [h for h in hujjatlar if h.ariza_namuna_id in (None, namuna.ariza_namuna_id)]
    return [h for h in hujjatlar if hujjat_korinadimi(user, h)]
