"""
Parol tanlash (brute-force) hujumidan himoya.

- Bitta login uchun ketma-ket 5 ta noto'g'ri parol  -> shu login 15 daqiqaga bloklanadi.
- Bitta IP manzildan 20 ta noto'g'ri urinish         -> shu IP 15 daqiqaga bloklanadi.
Bloklash holatlari Nazorat tarixiga yoziladi. Hisoblagichlar umumiy keshda (barcha jarayonlar uchun bitta).
"""
import hashlib

from django.core.cache import cache

LOGIN_URINISH = 5
IP_URINISH = 20
BLOK_SONIYA = 15 * 60


def mijoz_ip(request):
    """Haqiqiy IP: nginx X-Forwarded-For oxiriga o'zi qo'shgan manzil (oldingilarini mijoz soxtalashtirishi mumkin)."""
    xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if xff:
        return xff.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "") or "nomalum"


def _k(tur, qiymat):
    return f"kirish:{tur}:" + hashlib.sha256(str(qiymat).lower().encode()).hexdigest()[:32]


def qolgan_vaqt(request, username):
    """Bloklangan bo'lsa — necha daqiqadan keyin urinish mumkin, aks holda 0."""
    for kalit in (_k("blok-login", username), _k("blok-ip", mijoz_ip(request))):
        tugash = cache.get(kalit)
        if tugash:
            import time

            return max(1, int((tugash - time.time()) // 60) + 1)
    return 0


def _oshir(kalit):
    n = (cache.get(kalit) or 0) + 1
    cache.set(kalit, n, BLOK_SONIYA)
    return n


def _blokla(kalit, request, nima):
    import time

    cache.set(kalit, time.time() + BLOK_SONIYA, BLOK_SONIYA)
    from core.models import NazoratTarixi

    NazoratTarixi.yoz(None, NazoratTarixi.Turi.XAVFSIZLIK, nima,
                      f"Ko'p marta noto'g'ri parol kiritildi — 15 daqiqaga bloklandi. IP: {mijoz_ip(request)}")


def xato_urinish(request, username):
    if username and _oshir(_k("login", username)) >= LOGIN_URINISH:
        cache.delete(_k("login", username))
        _blokla(_k("blok-login", username), request, f"Login: {username}")
    if _oshir(_k("ip", mijoz_ip(request))) >= IP_URINISH:
        cache.delete(_k("ip", mijoz_ip(request)))
        _blokla(_k("blok-ip", mijoz_ip(request)), request, f"IP: {mijoz_ip(request)}")


def muvaffaqiyatli(request, username):
    cache.delete(_k("login", username))
