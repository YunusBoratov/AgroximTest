"""
Ariza formasidagi fayllarni vaqtincha saqlash.

Brauzer xato bilan qaytgan formada tanlangan fayllarni qayta yubormaydi. Shuning uchun har bir to'g'ri
fayl yuklanishi bilan serverda vaqtincha saqlanadi va sessiyada eslab qolinadi. Forma qayta ko'rsatilganda
fayl nomi "yuklangan" deb chiqadi, ariza saqlanganda esa arizaga biriktiriladi.
"""
import uuid

from django.core.files.storage import default_storage

VAQTINCHA_DIR = "vaqtincha"


def _kalit(nom):
    return f"ariza_fayllar_{nom}"


def ol(request, nom):
    return dict(request.session.get(_kalit(nom), {}))


def _fayllar(saqlangan):
    """{blok: {turi: info}} (yoki eski {turi: info}) ichidagi barcha fayl ma'lumotlari."""
    for v in saqlangan.values():
        if isinstance(v, dict) and "path" in v:
            yield v
        elif isinstance(v, dict):
            yield from v.values()


def tozala(request, nom):
    for info in list(_fayllar(request.session.pop(_kalit(nom), {}))):
        if default_storage.exists(info["path"]):
            default_storage.delete(info["path"])


def eskilarini_tozala(soat=24):
    """Yakunlanmay tashlab ketilgan (bir kundan eski) vaqtincha fayllarni o'chiradi."""
    from datetime import timedelta

    from django.utils import timezone

    chegara = timezone.now() - timedelta(hours=soat)
    try:
        _dirs, files = default_storage.listdir(VAQTINCHA_DIR)
    except FileNotFoundError:
        return
    for f in files:
        path = f"{VAQTINCHA_DIR}/{f}"
        try:
            if default_storage.get_modified_time(path) < chegara:
                default_storage.delete(path)
        except (FileNotFoundError, OSError):
            pass


def yangilarini_saqla(request, nom, toplam):
    """Bloklardagi (tekshiruvdan o'tgan) yangi fayllarni vaqtincha saqlaydi: {blok prefiksi: {turi: info}}."""
    for blok in toplam.bloklar:
        data = getattr(blok, "cleaned_data", {}) or {}
        for name in blok.HUJJAT_MAYDONLARI:
            f = data.get(name)
            if not f or name in blok.errors:
                continue
            eski = blok.saqlangan.get(name)
            if eski and default_storage.exists(eski["path"]):
                default_storage.delete(eski["path"])
            ext = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else "bin"
            path = default_storage.save(f"{VAQTINCHA_DIR}/{uuid.uuid4().hex}.{ext}", f)
            blok.saqlangan[name] = {"path": path, "nom": f.name}
    request.session[_kalit(nom)] = toplam.saqlangan
    eskilarini_tozala()
    return toplam.saqlangan
