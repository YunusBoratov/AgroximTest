from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from core.models import Ariza, ArizaTuri, NamunaTuri, Narxnoma, Shartnoma, ShartnomaBand, Tolov


import shutil  # noqa: E402
import tempfile  # noqa: E402

from django.test import override_settings  # noqa: E402

TEST_MEDIA = tempfile.mkdtemp()

from django.core.files.uploadedfile import SimpleUploadedFile as _SUF  # noqa: E402
from django.test import Client  # noqa: E402

_BLOK_KALIT = {"kategoriya": "kategoriya", "namuna_nomi": "nomi", "partiya_raqami": "partiya_raqami",
               "invoys_raqami": "invoys_raqami"}
_HUJJAT = ("invoys", "analiz", "guvohnoma", "qoshimcha")
_ARIZA_YOLLARI = ("/ariza/yangi/", "/tahrirlash/", "/namuna/yaratish/")


def bloklar(data):
    """Eski (bitta namunali) test ma'lumotini har bir namuna bloki uchun s0-, s1-... ko'rinishiga o'tkazadi."""
    d = dict(data)
    n = int(d.get("namuna_soni") or 1)
    tekis = {k: d.pop(k) for k in list(d) if k in _BLOK_KALIT or k in _HUJJAT}
    for i in range(n):
        for k, v in tekis.items():
            if k in _HUJJAT:
                if v and i:
                    v = _SUF(v.name, b"%PDF-1.4 test", content_type="application/pdf") \
                        if v.name.endswith(".pdf") else _SUF(v.name, b"MZ")
                d[f"s{i}-{k}"] = v
            else:
                d[f"s{i}-{_BLOK_KALIT[k]}"] = v
    return d


class ArizaClient(Client):
    def post(self, path, data=None, *a, **kw):
        if data and any(y in path for y in _ARIZA_YOLLARI) and not any(k.startswith("s0-") for k in data):
            data = bloklar(data)
        return super().post(path, data, *a, **kw)


TestCase.client_class = ArizaClient


@override_settings(MEDIA_ROOT=TEST_MEDIA)
class BaseTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        call_command("boshlangich", "--demo", verbosity=0)

    def login(self, username):
        self.client.login(username=username, password="demo12345")


class ModelTests(BaseTest):
    def _ariza(self):
        return Ariza.objects.create(
            turi=ArizaTuri.IXTIYORIY, fish="Test", inn="12345678901234", telefon="+998",
            namuna_turi=NamunaTuri.objects.first(), namuna_soni=2,
        )

    def test_raqamlash(self):
        a = self._ariza()
        self.assertRegex(a.raqam, r"^ATM-A-\d{4}-\d{5}$")
        sh = Shartnoma.objects.create(ariza=a)
        self.assertRegex(sh.raqam, r"^\d+$")
        sh2 = Shartnoma.objects.create(ariza=a)
        self.assertEqual(int(sh2.raqam), int(sh.raqam) + 1)

    def test_narxnoma_import(self):
        self.assertGreater(Narxnoma.objects.count(), 40)
        self.assertFalse(Narxnoma.objects.filter(parametr__regex=r"[А-Яа-яЎўҚқҒғҲҳ]").exists())

    def test_summa_va_30_foiz(self):
        sh = Shartnoma.objects.create(ariza=self._ariza())
        nx = Narxnoma.objects.filter(har_namunaga=True).first()
        ShartnomaBand.objects.create(shartnoma=sh, narxnoma=nx, narx=Decimal("1000"), namuna_soni=2)
        olish = Narxnoma.objects.filter(har_namunaga=False).first()
        ShartnomaBand.objects.create(shartnoma=sh, narxnoma=olish, narx=Decimal("500"), namuna_soni=2)
        sh.qayta_hisobla()
        self.assertEqual(sh.jami_summa, Decimal("2500"))  # 1000*2 + 500*1
        self.assertFalse(sh.tahlil_boshlash_mumkin)

        Tolov.objects.create(shartnoma=sh, summa=Decimal("700"))
        sh.qayta_hisobla()
        self.assertEqual(sh.tolov_holati, Shartnoma.TolovHolati.QISMAN)
        self.assertFalse(sh.tahlil_boshlash_mumkin)  # 28%

        Tolov.objects.create(shartnoma=sh, summa=Decimal("50"))
        sh.qayta_hisobla()
        self.assertTrue(sh.tahlil_boshlash_mumkin)  # 30%

        Tolov.objects.create(shartnoma=sh, summa=Decimal("1750"))
        sh.qayta_hisobla()
        self.assertEqual(sh.tolov_holati, Shartnoma.TolovHolati.TOLANGAN)


class AccessTests(BaseTest):
    def test_login_required(self):
        r = self.client.get(reverse("ariza_list"))
        self.assertEqual(r.status_code, 302)

    def test_rollar(self):
        cases = {
            "superadmin": {"ariza_list": 200, "xodim_list": 200, "narxnoma_list": 200},
            "admin": {"ariza_list": 200, "xodim_list": 403},
            "buxgalter": {"oferta_list": 200, "narxnoma_list": 200, "ariza_list": 403, "xulosa_list": 403},
            "lab_mineral": {"shartnoma_list": 200, "tahlil_holati": 200, "oferta_list": 403},
            "namuna": {"ariza_list": 200, "namuna_list": 200, "shartnoma_list": 403},
        }
        for user, urls in cases.items():
            self.client.logout()
            self.login(user)
            for name, code in urls.items():
                with self.subTest(user=user, url=name):
                    self.assertEqual(self.client.get(reverse(name)).status_code, code)

    def test_lab_faqat_oz_kategoriyasi(self):
        self.login("lab_kimyo")
        r = self.client.get(reverse("shartnoma_list"))
        for sh in r.context["page"].object_list:
            self.assertEqual(sh.ariza.kategoriya, "kimyoviy")

    def test_excel(self):
        self.login("superadmin")
        r = self.client.get(reverse("oferta_list") + "?export=excel")
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r["Content-Type"])

    def test_xodim_qoshish(self):
        self.login("superadmin")
        r = self.client.post(reverse("xodim_add"), {
            "fish": "Yangi Xodim", "username": "yangi", "telefon": "", "lavozim": "Laborant",
            "role": Role.LAB_KIMYO, "is_active": "on", "parol": "parol123",
        })
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(username="yangi")
        self.assertTrue(u.check_password("parol123"))
        self.assertEqual(u.role, Role.LAB_KIMYO)


# ---------------------------------------------------------------------------
# 2-bosqich: mijoz va namuna qabul qilish
# ---------------------------------------------------------------------------
from django.core.files.uploadedfile import SimpleUploadedFile  # noqa: E402

from core.models import ArizaHujjat, Namuna  # noqa: E402


def pdf(name="hujjat.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 test", content_type="application/pdf")


class MijozTests(BaseTest):
    def setUp(self):
        self.client.post(reverse("royxat"), {
            "turi": "yuridik", "telefon": "90 111 22 33", "fish": "Karimov Anvar", "inn": "123456789",
            "tashkilot_nomi": "Agro MCHJ", "parol1": "parol123", "parol2": "parol123",
        })
        self.mijoz = User.objects.get(username="+998901112233")

    def test_royxat_va_kirish(self):
        self.assertEqual(self.mijoz.role, Role.MIJOZ)
        self.assertEqual(self.mijoz.inn, "123456789")
        self.client.logout()
        # telefonni boshqa ko'rinishda yozsa ham kira oladi
        r = self.client.post(reverse("login"), {"username": "+998 (90) 111-22-33", "password": "parol123"})
        self.assertRedirects(r, reverse("bosh"), fetch_redirect_response=False)
        self.assertRedirects(self.client.get(reverse("bosh")), reverse("kabinet"))

    def test_mijoz_xodim_sahifasiga_kirolmaydi(self):
        self.assertEqual(self.client.get(reverse("ariza_list")).status_code, 403)

    def _importyor(self, **extra):
        data = {"turi": "importyor", "inn": "123456789", "buyurtmachi_nomi": "Agro MCHJ", "fish": "Karimov",
                "telefon": "+998901112233", "namuna_soni": 2,
                "kategoriya": "mineral",
                "namuna_nomi": "Ammofos", "chegara_maskani": "Olot", "partiya_raqami": "LOT-1",
                "invoys": pdf("inv.pdf"), "analiz": pdf("an.pdf"), "guvohnoma": pdf("gv.pdf")}
        data.update(extra)
        return self.client.post(reverse("ariza_yangi"), data)

    def test_importyor_ariza(self):
        r = self._importyor()
        self.assertRedirects(r, reverse("kabinet"))
        a = Ariza.objects.get(mijoz=self.mijoz)
        self.assertEqual(a.kategoriya, "mineral")
        self.assertEqual(a.hujjatlar.count(), 6)  # 2 namuna x 3 hujjat
        self.assertEqual(a.arizanamunalar.count(), 2)

    def test_hujjatsiz_ariza_qabul_qilinmaydi(self):
        r = self._importyor(invoys="")
        self.assertEqual(r.status_code, 200)
        self.assertIn("invoys", r.context["toplam"].bloklar[0].errors)
        self.assertFalse(Ariza.objects.filter(mijoz=self.mijoz).exists())

    def test_ixtiyoriy_jshshir_tekshiruvi(self):
        base = {"turi": "ixtiyoriy", "fish": "Ali", "telefon": "+998901112233", "namuna_soni": 1,
                "kategoriya": "mineral", "guvohnoma": pdf()}
        r = self.client.post(reverse("ariza_yangi"), dict(base, inn="123456789"))
        self.assertIn("inn", r.context["form"].errors)
        r = self.client.post(reverse("ariza_yangi"), dict(base, inn="12345678901234", guvohnoma=pdf()))
        self.assertRedirects(r, reverse("kabinet"))

    def test_notogri_fayl_turi(self):
        r = self._importyor(invoys=SimpleUploadedFile("x.exe", b"MZ"))
        self.assertIn("invoys", r.context["toplam"].bloklar[0].errors)

    def test_boshqa_mijoz_arizasini_korolmaydi(self):
        begona = Ariza.objects.first()
        self.assertEqual(self.client.get(reverse("ariza_detail", args=[begona.pk])).status_code, 403)


class NamunaQabulTests(BaseTest):
    def setUp(self):
        self.ariza = Ariza.objects.create(
            turi="davlat", inn="123456789", buyurtmachi_nomi="X", fish="Y", telefon="+998",
            namuna_soni=2, namuna_turi=NamunaTuri.objects.get(nomi="Fungitsidlar"))
        self.login("namuna")

    def test_qabul_namunalar_yaratadi(self):
        url = reverse("ariza_qabul", args=[self.ariza.pk])
        data = {}
        for i in range(2):
            data.update({f"n{i}-nomi": f"Namuna {i}", f"n{i}-namuna_olgan": "R. Qarayev", f"n{i}-ogirligi": "0.5 kg",
                         f"n{i}-namuna_turi": self.ariza.namuna_turi_id})
        r = self.client.post(url, data)
        self.assertRedirects(r, reverse("namuna_list"))
        self.ariza.refresh_from_db()
        self.assertEqual(self.ariza.holat, Ariza.Holat.QABUL)
        nams = list(self.ariza.namunalar.order_by("tartib"))
        self.assertEqual([n.tartib for n in nams], [1, 2])
        self.assertTrue(all(n.lab_holat == Namuna.LabHolat.YANGI for n in nams))
        # kimyoviy laboratoriya yangi namunani ko'radi, mineral ko'rmaydi
        self.client.logout()
        self.login("lab_kimyo")
        r = self.client.get(reverse("tahlil_holati") + "?holat=yangi")
        self.assertEqual(r.context["total"], 2)
        self.client.logout()
        self.login("lab_mineral")
        r = self.client.get(reverse("tahlil_holati") + "?q=" + self.ariza.raqam)
        self.assertEqual(r.context["total"], 0)

    def test_rad_etish(self):
        self.client.post(reverse("ariza_rad", args=[self.ariza.pk]), {"sabab": "Hujjatlar to'liq emas"})
        self.ariza.refresh_from_db()
        self.assertEqual(self.ariza.holat, Ariza.Holat.RAD)

    def test_namuna_ochirish(self):
        n = Namuna.objects.create(ariza=self.ariza, namuna_turi=self.ariza.namuna_turi, nomi="A")
        self.client.post(reverse("namuna_delete", args=[n.pk]))
        self.assertFalse(Namuna.objects.filter(pk=n.pk).exists())

    def test_xodim_ariza_yaratadi(self):
        r = self.client.post(reverse("namuna_yaratish"), {
            "turi": "ixtiyoriy", "inn": "12345678901234", "fish": "Ali Valiyev", "telefon": "+998901234567",
            "namuna_soni": 1, "kategoriya": "kimyoviy", "guvohnoma": pdf()})
        a = Ariza.objects.get(fish="Ali Valiyev")
        self.assertRedirects(r, reverse("ariza_qabul", args=[a.pk]))
        self.assertIsNone(a.mijoz)


# ---------------------------------------------------------------------------
# 3-bosqich: shartnoma va to'lovlar
# ---------------------------------------------------------------------------
from core.hujjatlar import sonni_sozga  # noqa: E402


class ShartnomaTests(BaseTest):
    def setUp(self):
        self.ariza = Ariza.objects.create(
            turi="importyor", inn="123456789", buyurtmachi_nomi="Test MCHJ", fish="Y", telefon="+998",
            namuna_soni=2, namuna_turi=NamunaTuri.objects.get(nomi="Azotli o'g'itlar"), holat=Ariza.Holat.QABUL)
        for i in (1, 2):
            Namuna.objects.create(ariza=self.ariza, tartib=i, namuna_turi=self.ariza.namuna_turi, nomi="N")
        self.olish = Narxnoma.objects.filter(har_namunaga=False, sinov_obyekti="mineral").first()
        self.azot = Narxnoma.objects.filter(parametr__startswith="Umumiy azot", sinov_obyekti="mineral").first()

    def _tuz(self):
        self.login("lab_mineral")
        r = self.client.post(reverse("shartnoma_yangi", args=[self.ariza.pk]), {
            f"band_{self.olish.pk}": "1", f"soni_{self.olish.pk}": "2",
            f"band_{self.azot.pk}": "1", f"soni_{self.azot.pk}": "2",
        })
        sh = Shartnoma.objects.get(ariza=self.ariza, is_active=True)
        self.assertRedirects(r, reverse("shartnoma_detail", args=[sh.pk]))
        return sh

    def test_shartnoma_tuzish_summa(self):
        sh = self._tuz()
        kutilgan = self.olish.narx + self.azot.narx * 2  # namuna olish bir marta
        self.assertEqual(sh.jami_summa, kutilgan)
        self.assertEqual(self.ariza.namunalar.filter(shartnoma=sh).count(), 2)

    def test_kimyo_lab_mineral_shartnoma_tuzolmaydi(self):
        self.login("lab_kimyo")
        r = self.client.get(reverse("shartnoma_yangi", args=[self.ariza.pk]))
        self.assertEqual(r.status_code, 403)

    def test_lab_faqat_oz_narxnomasini_koradi(self):
        self.login("lab_mineral")
        r = self.client.get(reverse("shartnoma_yangi", args=[self.ariza.pk]))
        obyektlar = {nx.sinov_obyekti for nx, _c, _s in r.context["rows"]}
        self.assertNotIn("pestitsid", obyektlar)

    def test_toliq_jarayon(self):
        sh = self._tuz()
        # yuborilmagan shartnomani buxgalter ko'rmaydi
        self.client.logout()
        self.login("buxgalter")
        self.assertEqual(self.client.get(reverse("shartnoma_detail", args=[sh.pk])).status_code, 403)
        # laboratoriya yuboradi
        self.client.logout()
        self.login("lab_mineral")
        self.client.post(reverse("shartnoma_yuborish", args=[sh.pk]))
        sh.refresh_from_db()
        self.assertEqual(sh.holat, Shartnoma.Holat.YUBORILGAN)
        # yuborilgandan keyin tahrirlab bo'lmaydi
        self.assertRedirects(self.client.get(reverse("shartnoma_edit", args=[sh.pk])),
                             reverse("shartnoma_detail", args=[sh.pk]))
        # buxgalter ochadi -> qabul qilgan
        self.client.logout()
        self.login("buxgalter")
        self.client.get(reverse("shartnoma_detail", args=[sh.pk]))
        sh.refresh_from_db()
        self.assertEqual(sh.holat, Shartnoma.Holat.QABUL)
        # 30% to'lov
        bugun = timezone.localdate().isoformat()
        uchdan = (sh.jami_summa * Decimal("0.3")).quantize(Decimal("1")) + 1
        self.client.post(reverse("tolov_qoshish", args=[sh.pk]), {"summa": uchdan, "usul": "bank", "sana": bugun})
        sh.refresh_from_db()
        self.assertEqual(sh.tolov_holati, Shartnoma.TolovHolati.QISMAN)
        self.assertTrue(sh.tahlil_boshlash_mumkin)
        self.assertFalse(sh.xulosa_yuborish_mumkin)
        # qoldiqdan ko'p to'lov qabul qilinmaydi
        self.client.post(reverse("tolov_qoshish", args=[sh.pk]), {"summa": sh.jami_summa, "usul": "bank", "sana": bugun})
        self.assertEqual(sh.tolovlar.count(), 1)
        self.client.post(reverse("tolov_qoshish", args=[sh.pk]), {"summa": sh.qoldiq, "usul": "click", "sana": bugun})
        sh.refresh_from_db()
        self.assertEqual(sh.tolov_holati, Shartnoma.TolovHolati.TOLANGAN)
        self.assertTrue(sh.xulosa_yuborish_mumkin)

    def test_hujjat_docx(self):
        sh = self._tuz()
        r = self.client.get(reverse("shartnoma_hujjat", args=[sh.pk, "docx"]))
        self.assertEqual(r.status_code, 200)
        import io

        import docx
        d = docx.Document(io.BytesIO(r.content))
        matn = "\n".join(p.text for p in d.paragraphs)
        self.assertIn(f"№ {sh.raqam}", matn)
        self.assertIn("Агрокимё ва тупроқ таҳлили маркази", matn)
        self.assertNotIn("Республика агрокимёвий таҳлил маркази", matn)
        jadval = "\n".join(c.text for row in d.tables[0].rows for c in row.cells)
        self.assertIn(self.azot.tahlil_usuli, jadval)

    def test_namuna_qabul_shartnoma_ochirish(self):
        sh = self._tuz()
        self.client.post(reverse("shartnoma_ochirish", args=[sh.pk]))
        sh.refresh_from_db()
        self.assertFalse(sh.is_active)
        self.assertFalse(self.ariza.namunalar.filter(shartnoma__isnull=False).exists())

    def test_sonni_sozga(self):
        self.assertEqual(sonni_sozga(5374888), "беш миллион уч юз етмиш тўрт минг саккиз юз саксон саккиз")
        self.assertEqual(sonni_sozga(2256400), "икки миллион икки юз эллик олти минг тўрт юз")


# ---------------------------------------------------------------------------
# 4-bosqich: laboratoriya jarayoni va xulosa
# ---------------------------------------------------------------------------
from core.models import Xulosa, XulosaNatija  # noqa: E402


class LabJarayonTests(ShartnomaTests):
    def setUp(self):
        super().setUp()
        # demo foydalanuvchilar (boshlangich --demo): ikki mineral va bitta kimyoviy mas'ul
        self.m1, self.m2 = User.objects.get(username="masul1"), User.objects.get(username="masul2")
        self.mk = User.objects.get(username="masul_k")

    def _yuborilgan_shartnoma(self, foiz):
        sh = self._tuz()
        self.client.post(reverse("shartnoma_yuborish", args=[sh.pk]))
        if foiz:
            Tolov.objects.create(shartnoma=sh, summa=(sh.jami_summa * Decimal(foiz) / 100).quantize(Decimal("0.01")))
            sh.qayta_hisobla()
        return sh

    def _masul_post(self, t, toliq=True):
        rows = list(t.natijalar.order_by("tartib", "id"))
        data = {"nt-TOTAL_FORMS": len(rows), "nt-INITIAL_FORMS": len(rows), "nt-MIN_NUM_FORMS": 0,
                "nt-MAX_NUM_FORMS": 1000}
        for i, r in enumerate(rows):
            data.update({f"nt-{i}-id": r.pk, f"nt-{i}-natija": "12.4" if toliq else "",
                         f"nt-{i}-sinov_usuli": r.sinov_usuli or "Vizual"})
        return data

    def _meyor_post(self, x, toliq=True):
        rows = list(x.natijalar.order_by("tartib", "id"))
        data = {"my-TOTAL_FORMS": len(rows), "my-INITIAL_FORMS": len(rows), "my-MIN_NUM_FORMS": 0,
                "my-MAX_NUM_FORMS": 1000}
        for i, r in enumerate(rows):
            data.update({f"my-{i}-id": r.pk, f"my-{i}-meyor": "12±1" if toliq else ""})
        return data

    def test_30_foizsiz_tahlilga_yuborilmaydi(self):
        sh = self._yuborilgan_shartnoma(10)
        nam = sh.namunalar.first()
        r = self.client.get(reverse("tahlilga_yuborish", args=[nam.pk]))
        self.assertRedirects(r, reverse("tahlil_holati"))
        nam.refresh_from_db()
        self.assertEqual(nam.lab_holat, Namuna.LabHolat.YANGI)

    def test_toliq_lab_jarayoni(self):
        from core.models import NazoratTarixi, Topshiriq
        sh = self._yuborilgan_shartnoma(40)
        nam = sh.namunalar.order_by("tartib").first()
        # mudir: faqat o'z laboratoriyasi mas'ullari ro'yxatda
        r = self.client.get(reverse("tahlilga_yuborish", args=[nam.pk]))
        self.assertContains(r, "Sh. Rahimova")
        self.assertNotContains(r, "B. Aliyev")
        rows = r.context["rows"]
        self.assertEqual(rows[0][1], "Tashqi ko‘rinishi, rangi")
        self.assertFalse(any(k.startswith("Namuna olish") for _i, k, _u, _t in rows))
        # birinchi qator 1-mas'ulga, qolganlari 2-mas'ulga
        data = {f"masul_{i}": (self.m1.pk if i == 0 else self.m2.pk) for i, *_r in rows}
        self.client.post(reverse("tahlilga_yuborish", args=[nam.pk]), data)
        nam.refresh_from_db()
        self.assertEqual(nam.lab_holat, Namuna.LabHolat.TAHLILDA)
        t1, t2 = Topshiriq.objects.get(namuna=nam, masul=self.m1), Topshiriq.objects.get(namuna=nam, masul=self.m2)
        self.assertEqual(t1.natijalar.count(), 1)
        self.assertEqual(t2.natijalar.count(), len(rows) - 1)
        # mas'ullar qabul qiladi
        self.client.logout()
        self.client.login(username="masul1", password="demo12345")
        self.assertEqual(self.client.get(reverse("topshiriq_natija", args=[t2.pk])).status_code, 403)  # begona
        self.client.post(reverse("topshiriq_qabul", args=[t1.pk]))
        nam.refresh_from_db()
        self.assertEqual(nam.lab_holat, Namuna.LabHolat.TAHLILDA)  # 2-mas'ul hali qabul qilmagan
        # bo'sh maydon bilan saqlanmaydi
        self.client.post(reverse("topshiriq_natija", args=[t1.pk]), self._masul_post(t1, toliq=False))
        t1.refresh_from_db()
        self.assertEqual(t1.holat, Topshiriq.Holat.QABUL)
        self.client.post(reverse("topshiriq_natija", args=[t1.pk]), self._masul_post(t1))
        t1.refresh_from_db()
        self.assertEqual(t1.holat, Topshiriq.Holat.TAYYOR)
        self.client.logout()
        self.client.login(username="masul2", password="demo12345")
        self.client.post(reverse("topshiriq_qabul", args=[t2.pk]))
        nam.refresh_from_db()
        self.assertEqual(nam.lab_holat, Namuna.LabHolat.JARAYONDA)
        self.client.post(reverse("topshiriq_natija", args=[t2.pk]), self._masul_post(t2))
        nam.refresh_from_db()
        self.assertEqual(nam.lab_holat, Namuna.LabHolat.NATIJA)  # "Xulosa tayyor"
        # mudir qaytaradi
        self.client.logout()
        self.login("lab_mineral")
        x = Xulosa.objects.get(namuna=nam)
        self.client.post(reverse("xulosa_qaytarish", args=[x.pk]), {"topshiriq": t2.pk, "izoh": "pH qayta o'lchansin"})
        t2.refresh_from_db()
        nam.refresh_from_db()
        self.assertEqual(t2.holat, Topshiriq.Holat.QAYTARILDI)
        self.assertEqual(nam.lab_holat, Namuna.LabHolat.JARAYONDA)
        self.assertTrue(NazoratTarixi.objects.filter(turi="xulosa_qaytarish").exists())
        self.client.logout()
        self.client.login(username="masul2", password="demo12345")
        self.assertContains(self.client.get(reverse("topshiriq_natija", args=[t2.pk])), "pH qayta")
        self.client.post(reverse("topshiriq_natija", args=[t2.pk]), self._masul_post(t2))
        # mudir tasdiqlaydi: majburiy maydonlarsiz tasdiqlanmaydi
        self.client.logout()
        self.login("lab_mineral")
        self.client.post(reverse("xulosa_tasdiqlash", args=[x.pk]), {})
        x.refresh_from_db()
        self.assertFalse(x.tasdiqlangan)
        asosiy = {"dalolatnoma": "5", "sinov_joyi": "Laboratoriya",
                  "harorat": "T=(23±1)°C", "namlik": "W=(45±1)%", "bosh_agrokimyogar": "Sh. Rahimova",
                  "yetakchi_agrokimyogar": "D. Tursunov", "ogirligi": "0.5 kg"}
        # me'yoriy qiymatlarsiz tasdiqlanmaydi
        self.client.post(reverse("xulosa_tasdiqlash", args=[x.pk]), dict(asosiy, **self._meyor_post(x, False)))
        x.refresh_from_db()
        self.assertFalse(x.tasdiqlangan)
        oldin = timezone.now()
        self.client.post(reverse("xulosa_tasdiqlash", args=[x.pk]), dict(asosiy, **self._meyor_post(x)))
        x.refresh_from_db()
        self.assertGreaterEqual(x.sinov_sanasi, oldin)  # sinov sanasi — tasdiqlash vaqti (avtomatik)
        self.assertEqual(set(x.natijalar.values_list("meyor", flat=True)), {"12±1"})
        nomlar = list(nam.ariza.bosqichlar.values_list("nomi", flat=True))
        for kerak in ("Mas'ullarga tahlilga yuborildi", "Mas'ul topshiriqni qabul qildi", "Mas'ul natijani yubordi",
                      "Natija mas'ulga qaytarildi", "Xulosa tasdiqlandi"):
            self.assertIn(kerak, nomlar)
        nam.refresh_from_db()
        self.assertTrue(x.tasdiqlangan)
        self.assertEqual(nam.lab_holat, Namuna.LabHolat.XULOSA)
        self.assertEqual(x.bosh_agrokimyogar, "Sh. Rahimova")
        # Word hujjat (faqat mudirga): yangi shakl, raqam, mudir va agrokimyogarlar
        r = self.client.get(reverse("xulosa_hujjat", args=[x.pk, "docx"]))
        import io

        import docx
        d = docx.Document(io.BytesIO(r.content))
        self.assertIn(x.raqam, d.tables[1].rows[0].cells[0].text)
        imzo = d.tables[4].rows[0].cells[1].text
        self.assertIn("Sh. Rahimova", imzo)
        self.assertIn("D. Tursunov", imzo)
        self.assertNotIn("QR KOD", d.tables[4]._tbl.xml)  # QR rasm qo'yilgan
        self.assertEqual(len(d.tables[3].columns), 5)  # muvofiqlik ustuni yo'q
        self.assertNotIn("Muvofiqlik", d.tables[3].rows[0].cells[-1].text)
        self.assertEqual(self.client.get(reverse("xulosa_tekshirish", args=[x.verify_token])).status_code, 200)
        # 40% to'lovda mijozga berilmaydi, 100% da beriladi
        self.client.post(reverse("xulosa_berish", args=[x.pk]))
        nam.refresh_from_db()
        self.assertEqual(nam.lab_holat, Namuna.LabHolat.XULOSA)
        Tolov.objects.create(shartnoma=sh, summa=sh.qoldiq)
        sh.qayta_hisobla()
        self.client.post(reverse("xulosa_berish", args=[x.pk]))
        nam.refresh_from_db()
        self.assertEqual(nam.lab_holat, Namuna.LabHolat.BERILDI)

    def test_word_faqat_mudirga(self):
        nam = self.ariza.namunalar.first()
        x = Xulosa.objects.create(namuna=nam, tasdiqlangan_at=timezone.now())
        XulosaNatija.objects.create(xulosa=x, korsatkich="pH", natija="7")
        for user in ("admin", "superadmin", "namuna"):
            self.client.logout()
            self.login(user)
            with self.subTest(user=user):
                self.assertEqual(self.client.get(reverse("xulosa_hujjat", args=[x.pk, "docx"])).status_code, 403)
        self.client.logout()
        self.login("lab_mineral")
        self.assertEqual(self.client.get(reverse("xulosa_hujjat", args=[x.pk, "docx"])).status_code, 200)

    def test_mijoz_faqat_berilgan_xulosani_yuklaydi(self):
        mijoz = User.objects.create_user("+998900000001", password="parol123", role=Role.MIJOZ)
        self.ariza.mijoz = mijoz
        self.ariza.save()
        nam = self.ariza.namunalar.first()
        x = Xulosa.objects.create(namuna=nam, tasdiqlangan_at=timezone.now())
        XulosaNatija.objects.create(xulosa=x, korsatkich="pH", natija="7")
        self.client.login(username="+998900000001", password="parol123")
        self.assertEqual(self.client.get(reverse("xulosa_hujjat", args=[x.pk, "pdf"])).status_code, 403)
        nam.lab_holat = Namuna.LabHolat.BERILDI
        nam.save()
        r = self.client.get(reverse("xulosa_hujjat", args=[x.pk, "pdf"]))
        self.assertEqual(r.status_code, 200)
        from pypdf import PdfReader
        self.assertTrue(PdfReader(io.BytesIO(r.content)).is_encrypted)  # tahrirlashdan himoyalangan
        self.assertEqual(r.headers.get("X-Frame-Options"), "SAMEORIGIN")

    def test_buxgalter_xulosa_yuklay_olmaydi(self):
        nam = self.ariza.namunalar.first()
        x = Xulosa.objects.create(namuna=nam)
        self.login("buxgalter")
        self.assertEqual(self.client.get(reverse("xulosa_hujjat", args=[x.pk, "pdf"])).status_code, 403)


import io  # noqa: E402


# ---------------------------------------------------------------------------
# 5-bosqich: Click, Telegram, SMS
# ---------------------------------------------------------------------------
import hashlib  # noqa: E402
import json  # noqa: E402
from unittest import mock  # noqa: E402

from core import xabarnoma  # noqa: E402
from core.models import ClickTranzaksiya, Xabar  # noqa: E402

CLICK = dict(CLICK_SERVICE_ID="111", CLICK_MERCHANT_ID="222", CLICK_SECRET_KEY="maxfiy")


@override_settings(**CLICK)
class ClickTests(BaseTest):
    def setUp(self):
        self.ariza = Ariza.objects.create(turi="importyor", inn="123456789", buyurtmachi_nomi="T", fish="Y",
                                          telefon="+998901234567", namuna_turi=NamunaTuri.objects.first(),
                                          holat=Ariza.Holat.QABUL)
        self.sh = Shartnoma.objects.create(ariza=self.ariza, holat=Shartnoma.Holat.QABUL)
        nx = Narxnoma.objects.filter(har_namunaga=True).first()
        ShartnomaBand.objects.create(shartnoma=self.sh, narxnoma=nx, narx=Decimal("100000"), namuna_soni=1)
        self.sh.qayta_hisobla()
        self.n = 0

    def _p(self, action, amount, prepare_id="", error="0", trans="9001", sign=None):
        p = {"click_trans_id": trans, "service_id": "111", "click_paydoc_id": "555",
             "merchant_trans_id": str(self.sh.pk), "amount": amount, "action": str(action), "error": error,
             "error_note": "", "sign_time": "2026-11-21 10:00:00"}
        if prepare_id != "":
            p["merchant_prepare_id"] = str(prepare_id)
        raw = f"{p['click_trans_id']}111maxfiy{p['merchant_trans_id']}{prepare_id}{amount}{action}{p['sign_time']}"
        p["sign_string"] = sign or hashlib.md5(raw.encode()).hexdigest()
        return p

    def _post(self, name, p):
        with self.captureOnCommitCallbacks(execute=True):
            return json.loads(self.client.post(reverse(name), p).content)

    def test_toliq_tolov(self):
        r = self._post("click_prepare", self._p(0, "40000.00"))
        self.assertEqual(r["error"], 0)
        pid = r["merchant_prepare_id"]
        r = self._post("click_complete", self._p(1, "40000.00", pid))
        self.assertEqual(r["error"], 0)
        self.sh.refresh_from_db()
        self.assertEqual(self.sh.tolangan_summa, Decimal("40000"))
        self.assertEqual(self.sh.tolovlar.get().usul, Tolov.Usul.CLICK)
        self.assertTrue(self.sh.tahlil_boshlash_mumkin)
        # takroriy complete — ikkinchi marta yozilmaydi
        r = self._post("click_complete", self._p(1, "40000.00", pid))
        self.assertEqual(r["error"], -4)
        self.assertEqual(self.sh.tolovlar.count(), 1)
        # mijozga xabar jurnalga yozildi (kalit sozlanmagan -> "ochiq")
        self.assertTrue(Xabar.objects.filter(kanal="sms", holat="ochiq").exists())

    def test_notogri_imzo(self):
        r = self._post("click_prepare", self._p(0, "1000.00", sign="00"))
        self.assertEqual(r["error"], -1)

    def test_qoldiqdan_kop_summa(self):
        r = self._post("click_prepare", self._p(0, "150000.00"))
        self.assertEqual(r["error"], -2)

    def test_topilmagan_shartnoma(self):
        self.sh.holat = Shartnoma.Holat.YUBORILMAGAN
        self.sh.save()
        self.assertEqual(self._post("click_prepare", self._p(0, "1000.00"))["error"], -5)

    def test_bekor_qilingan(self):
        pid = self._post("click_prepare", self._p(0, "1000.00"))["merchant_prepare_id"]
        r = self._post("click_complete", self._p(1, "1000.00", pid, error="-5017"))
        self.assertEqual(r["error"], -9)
        self.assertEqual(ClickTranzaksiya.objects.get().holat, "cancelled")
        self.assertFalse(self.sh.tolovlar.exists())

    def test_complete_summasi_boshqa(self):
        pid = self._post("click_prepare", self._p(0, "1000.00"))["merchant_prepare_id"]
        self.assertEqual(self._post("click_complete", self._p(1, "2000.00", pid))["error"], -2)

    def test_mijoz_click_havolasi(self):
        mijoz = User.objects.create_user("+998901234567", password="parol123", role=Role.MIJOZ)
        self.ariza.mijoz = mijoz
        self.ariza.save()
        self.client.login(username="+998901234567", password="parol123")
        r = self.client.post(reverse("click_tolash", args=[self.sh.pk]), {"summa": "30000"})
        self.assertTrue(r["Location"].startswith("https://my.click.uz/services/pay?"))
        self.assertIn("transaction_param=%d" % self.sh.pk, r["Location"])
        self.assertIn("amount=30000.00", r["Location"])


@override_settings(TELEGRAM_BOT_TOKEN="123:abc", TELEGRAM_BOT_USERNAME="TestBot", TELEGRAM_WEBHOOK_SECRET="s3cret")
class TelegramTests(BaseTest):
    def test_ulash(self):
        mijoz = User.objects.create_user("+998901112299", password="parol123", role=Role.MIJOZ)
        havola = xabarnoma.telegram_ulash_havolasi(mijoz)
        self.assertTrue(havola.startswith("https://t.me/TestBot?start="))
        kod = havola.split("start=")[1]
        with mock.patch("core.xabarnoma._http", return_value={"ok": True}) as http:
            r = self.client.post(reverse("telegram_webhook", args=["s3cret"]),
                                 data=json.dumps({"message": {"chat": {"id": 777}, "text": f"/start {kod}"}}),
                                 content_type="application/json")
        self.assertEqual(r.status_code, 200)
        mijoz.refresh_from_db()
        self.assertEqual(mijoz.telegram_chat_id, "777")
        self.assertTrue(http.called)

    def test_notogri_secret(self):
        r = self.client.post(reverse("telegram_webhook", args=["xato"]), data="{}", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_soxta_kod(self):
        with mock.patch("core.xabarnoma._http", return_value={"ok": True}):
            self.client.post(reverse("telegram_webhook", args=["s3cret"]),
                             data=json.dumps({"message": {"chat": {"id": 5}, "text": "/start 123"}}),
                             content_type="application/json")
        self.assertFalse(User.objects.filter(telegram_chat_id="5").exists())


@override_settings(ESKIZ_EMAIL="a@b.uz", ESKIZ_PASSWORD="p")
class SmsTests(BaseTest):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()

    def test_sms_eskiz(self):
        javoblar = [{"data": {"token": "T"}}, {"status": "waiting"}]
        with mock.patch("core.xabarnoma._http", side_effect=javoblar) as http:
            self.assertTrue(xabarnoma.sms_yubor("+998 90 123 45 67", "Salom"))
        url = http.call_args_list[1].args[1]
        self.assertTrue(url.endswith("/message/sms/send"))
        self.assertEqual(http.call_args_list[1].kwargs["data"]["mobile_phone"], "998901234567")
        self.assertEqual(Xabar.objects.get().holat, "yuborildi")

    def test_sms_xato_jarayonni_toxtatmaydi(self):
        with mock.patch("core.xabarnoma._http", side_effect=OSError("tarmoq yo'q")):
            self.assertFalse(xabarnoma.sms_yubor("+998901234567", "Salom"))
        self.assertEqual(Xabar.objects.get().holat, "xato")


class HujjatHimoyaTests(BaseTest):
    def test_hujjat_faqat_ruxsat_bilan(self):
        egasi = User.objects.create_user("+998901000001", password="parol123", role=Role.MIJOZ)
        begona = User.objects.create_user("+998901000002", password="parol123", role=Role.MIJOZ)
        a = Ariza.objects.create(turi="ixtiyoriy", inn="12345678901234", fish="A", telefon="+998",
                                 namuna_turi=NamunaTuri.objects.get(nomi="Fungitsidlar"), mijoz=egasi)
        h = ArizaHujjat.objects.create(ariza=a, turi="guvohnoma", fayl=pdf("asl nomi.pdf"))
        self.assertNotIn("asl", h.fayl.name)  # fayl nomi taxmin qilinmaydigan
        url = reverse("ariza_hujjat", args=[h.pk])
        self.assertEqual(self.client.get(url).status_code, 302)  # kirmagan
        self.client.login(username="+998901000002", password="parol123")
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        self.client.login(username="+998901000001", password="parol123")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.logout()
        self.login("lab_mineral")  # boshqa soha laboratoriyasi
        self.assertEqual(self.client.get(url).status_code, 403)
        self.client.logout()
        self.login("namuna")
        self.assertEqual(self.client.get(url).status_code, 200)


class TilTests(BaseTest):
    def test_rus_tili(self):
        self.client.cookies["django_language"] = "ru"
        r = self.client.get(reverse("login"))
        self.assertContains(r, "Введите логин и пароль")
        self.assertContains(r, "Центр агрохимического и почвенного анализа")
        self.login("superadmin")
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, "Азотные удобрения")  # namuna turi ruscha nomi
        self.assertNotContains(r, "Tuproq tahlili")

    def test_ozbek_tili_standart(self):
        r = self.client.get(reverse("login"))
        self.assertContains(r, "Login va parolni kiriting")


# ---------------------------------------------------------------------------
# Xodimlar sinovidan keyingi tuzatishlar
# ---------------------------------------------------------------------------
class SinovTuzatishTests(BaseTest):
    def setUp(self):
        self.mijoz = User.objects.create_user("+998905550011", password="parol123", role=Role.MIJOZ)
        self.client.login(username="+998905550011", password="parol123")
        self.tur = NamunaTuri.objects.filter(kategoriya="mineral").first()

    def _data(self, **kw):
        d = {"turi": "importyor", "inn": "123456789", "buyurtmachi_nomi": "Agro", "fish": "Ali",
             "telefon": "+998905550011", "namuna_soni": 1, "kategoriya": "mineral", "namuna_nomi": "N",
             "partiya_raqami": "LOT-1",
             "chegara_maskani": "Olot"}
        d.update(kw)
        return d

    def test_xatoda_fayllar_saqlanadi(self):
        r = self.client.post(reverse("ariza_yangi"), self._data(
            fish="", invoys=pdf("inv.pdf"), analiz=pdf("an.pdf"), guvohnoma=pdf("gv.pdf")))
        self.assertEqual(r.status_code, 200)
        self.assertIn("fish", r.context["form"].errors)
        self.assertNotIn("invoys", r.context["toplam"].bloklar[0].errors)
        self.assertContains(r, "inv.pdf")  # fayl nomi "yuklangan" bo'lib ko'rinadi
        # ikkinchi urinish: fayllarsiz, faqat xato tuzatildi
        r = self.client.post(reverse("ariza_yangi"), self._data())
        self.assertRedirects(r, reverse("kabinet"))
        a = Ariza.objects.get(mijoz=self.mijoz)
        self.assertEqual(sorted(a.hujjatlar.values_list("turi", flat=True)), ["analiz", "guvohnoma", "invoys"])
        import os
        self.assertFalse(os.listdir(os.path.join(TEST_MEDIA, "vaqtincha")))  # vaqtinchalik fayllar tozalandi

    def test_yangi_forma_eski_fayllarni_unutadi(self):
        self.client.post(reverse("ariza_yangi"), self._data(fish="", invoys=pdf()))
        self.client.get(reverse("ariza_yangi"))
        r = self.client.post(reverse("ariza_yangi"), self._data())
        self.assertIn("invoys", r.context["toplam"].bloklar[0].errors)

    def _rad_ariza(self):
        a = Ariza.objects.create(mijoz=self.mijoz, turi="importyor", inn="123456789", buyurtmachi_nomi="Agro",
                                 fish="Ali", telefon="+998", namuna_turi=self.tur, namuna_nomi="N",
                                 chegara_maskani="Olot", holat=Ariza.Holat.RAD, rad_sababi="Invoys noto'g'ri")
        for t in ("invoys", "analiz", "guvohnoma"):
            ArizaHujjat.objects.create(ariza=a, turi=t, fayl=pdf(f"{t}.pdf"))
        return a

    def test_rad_etilgan_arizani_qayta_yuborish(self):
        a = self._rad_ariza()
        eski_invoys = a.hujjatlar.get(turi="invoys").pk
        r = self.client.get(reverse("ariza_tahrirlash", args=[a.pk]))
        self.assertContains(r, "Invoys noto")
        r = self.client.post(reverse("ariza_tahrirlash", args=[a.pk]),
                             self._data(namuna_nomi="Tuzatilgan", invoys=pdf("yangi_invoys.pdf")))
        self.assertRedirects(r, reverse("kabinet"))
        a.refresh_from_db()
        self.assertEqual(a.holat, Ariza.Holat.YANGI)
        self.assertEqual(a.rad_sababi, "")
        self.assertEqual(a.namuna_nomi, "Tuzatilgan")
        self.assertEqual(a.hujjatlar.count(), 3)  # invoys almashtirildi, qolganlari saqlandi
        self.assertFalse(a.hujjatlar.filter(pk=eski_invoys).exists())

    def test_begona_va_qabul_qilingan_arizani_tahrirlab_bolmaydi(self):
        a = self._rad_ariza()
        boshqa = User.objects.create_user("+998905550012", password="parol123", role=Role.MIJOZ)
        self.client.logout()
        self.client.login(username="+998905550012", password="parol123")
        self.assertEqual(self.client.get(reverse("ariza_tahrirlash", args=[a.pk])).status_code, 403)
        a.holat = Ariza.Holat.QABUL
        a.save()
        self.client.logout()
        self.client.login(username="+998905550011", password="parol123")
        self.assertRedirects(self.client.get(reverse("ariza_tahrirlash", args=[a.pk])),
                             reverse("ariza_detail", args=[a.pk]))

    def test_lab_narx_belgilash_tugmasi(self):
        a = Ariza.objects.create(turi="davlat", inn="123456789", buyurtmachi_nomi="X", fish="Y", telefon="+998",
                                 namuna_turi=self.tur, holat=Ariza.Holat.QABUL)
        Namuna.objects.create(ariza=a, namuna_turi=self.tur, nomi="N")
        self.client.logout()
        self.login("lab_mineral")
        r = self.client.get(reverse("tahlil_holati") + "?q=" + a.raqam)
        self.assertContains(r, reverse("shartnoma_yangi", args=[a.pk]))
        self.assertContains(r, "Narx belgilash")
        r = self.client.get(reverse("ariza_detail", args=[a.pk]))
        self.assertContains(r, reverse("shartnoma_yangi", args=[a.pk]))



class KategoriyaTests(BaseTest):
    def test_mijoz_faqat_guruh_tanlaydi_qabulda_tur_kiritiladi(self):
        mijoz = User.objects.create_user("+998905550099", password="parol123", role=Role.MIJOZ)
        self.client.login(username="+998905550099", password="parol123")
        r = self.client.get(reverse("ariza_yangi"))
        html = r.content.decode()
        self.assertIn('name="s0-kategoriya"', html)
        self.assertNotIn("Azotli o", html.split('name="s0-kategoriya"')[1].split("</select>")[0])
        self.client.post(reverse("ariza_yangi"), {
            "turi": "ixtiyoriy", "inn": "12345678901234", "fish": "Ali", "telefon": "+998905550099",
            "namuna_soni": 2, "kategoriya": "kimyoviy", "guvohnoma": pdf()})
        a = Ariza.objects.get(mijoz=mijoz)
        self.assertEqual(a.kategoriya, "kimyoviy")
        self.assertIsNone(a.namuna_turi)
        self.client.logout()
        self.login("namuna")
        r = self.client.get(reverse("ariza_qabul", args=[a.pk]))
        select = r.content.decode().split('name="n0-namuna_turi"')[1].split("</select>")[0]
        self.assertIn("Fungitsidlar", select)
        self.assertNotIn("Azotli", select)  # faqat o'z guruhining turlari
        fung = NamunaTuri.objects.get(nomi="Fungitsidlar")
        gerb = NamunaTuri.objects.get(nomi="Gerbitsidlar")
        self.client.post(reverse("ariza_qabul", args=[a.pk]), {
            "n0-namuna_turi": fung.pk, "n0-nomi": "A", "n0-namuna_olgan": "X",
            "n1-namuna_turi": gerb.pk, "n1-nomi": "B", "n1-namuna_olgan": "X"})
        a.refresh_from_db()
        self.assertEqual(a.holat, Ariza.Holat.QABUL)
        self.assertEqual(sorted(a.namunalar.values_list("namuna_turi__nomi", flat=True)), ["Fungitsidlar", "Gerbitsidlar"])
        self.assertIn("Fungitsidlar", a.turlar_matni)

    def test_boshqa_guruh_turi_qabul_qilinmaydi(self):
        a = Ariza.objects.create(turi="ixtiyoriy", inn="12345678901234", fish="A", telefon="+998",
                                 kategoriya="kimyoviy", namuna_soni=1)
        self.login("namuna")
        azot = NamunaTuri.objects.get(nomi="Azotli o'g'itlar")
        r = self.client.post(reverse("ariza_qabul", args=[a.pk]), {"n0-namuna_turi": azot.pk, "n0-nomi": "A",
                                                                     "n0-namuna_olgan": "X"})
        self.assertEqual(r.status_code, 200)
        a.refresh_from_db()
        self.assertEqual(a.holat, Ariza.Holat.YANGI)


class InvoysTests(BaseTest):
    def setUp(self):
        self.mijoz = User.objects.create_user("+998901110077", password="parol123", role=Role.MIJOZ)
        self.a = Ariza.objects.create(turi="importyor", inn="123456789", buyurtmachi_nomi="T", fish="Y",
                                      telefon="+998", kategoriya="mineral", mijoz=self.mijoz,
                                      holat=Ariza.Holat.QABUL)
        self.inv = ArizaHujjat.objects.create(ariza=self.a, turi="invoys", fayl=pdf("inv.pdf"))
        self.gv = ArizaHujjat.objects.create(ariza=self.a, turi="guvohnoma", fayl=pdf("gv.pdf"))
        sh = Shartnoma.objects.create(ariza=self.a, holat=Shartnoma.Holat.QABUL)
        self.sh = sh

    def test_invoys_kimga_korinadi(self):
        inv_url = reverse("ariza_hujjat", args=[self.inv.pk])
        gv_url = reverse("ariza_hujjat", args=[self.gv.pk])
        for user, kutilgan in [("namuna", 200), ("superadmin", 403), ("admin", 403), ("lab_mineral", 403),
                               ("buxgalter", 403)]:
            self.client.logout()
            self.login(user)
            with self.subTest(user=user):
                self.assertEqual(self.client.get(inv_url).status_code, kutilgan)
                self.assertEqual(self.client.get(gv_url).status_code, 200)
        self.client.logout()
        self.client.login(username="+998901110077", password="parol123")
        self.assertEqual(self.client.get(inv_url).status_code, 200)

    def test_sahifalarda_invoys_havolasi_yoq(self):
        inv_url = reverse("ariza_hujjat", args=[self.inv.pk])
        self.login("lab_mineral")
        for url in [reverse("ariza_detail", args=[self.a.pk]), reverse("shartnoma_detail", args=[self.sh.pk]),
                    reverse("shartnoma_list")]:
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertNotContains(r, inv_url)
                self.assertContains(r, reverse("ariza_hujjat", args=[self.gv.pk]))
        self.client.logout()
        self.login("namuna")
        self.assertContains(self.client.get(reverse("ariza_detail", args=[self.a.pk])), inv_url)


class TolovOchirishTests(BaseTest):
    def setUp(self):
        from core.models import NazoratTarixi  # noqa: F401
        self.a = Ariza.objects.create(turi="davlat", inn="123456789", buyurtmachi_nomi="T", fish="Y",
                                      telefon="+998", kategoriya="mineral", holat=Ariza.Holat.QABUL)
        self.nam = Namuna.objects.create(ariza=self.a, namuna_turi=NamunaTuri.objects.filter(kategoriya="mineral").first(), nomi="N")
        self.sh = Shartnoma.objects.create(ariza=self.a, holat=Shartnoma.Holat.QABUL)
        self.nam.shartnoma = self.sh
        self.nam.save()
        self.t = Tolov.objects.create(shartnoma=self.sh, summa=Decimal("50000"))
        self.url = reverse("tolov_ochirish", args=[self.sh.pk, self.t.pk])
        self.login("buxgalter")

    def test_sababsiz_ochmaydi(self):
        self.client.post(self.url, {"sabab": ""})
        self.assertTrue(Tolov.objects.filter(pk=self.t.pk).exists())

    def test_sabab_bilan_ochadi_va_tarixga_yoziladi(self):
        from core.models import NazoratTarixi
        self.client.post(self.url, {"sabab": "Xato summa kiritilgan"})
        self.assertFalse(Tolov.objects.filter(pk=self.t.pk).exists())
        log = NazoratTarixi.objects.get(turi="tolov_ochirish")
        self.assertIn("50 000", log.tafsilot)
        self.assertIn("Xato summa", log.tafsilot)
        self.assertIn("Buxgalteriya", log.user_nomi)

    def test_tahlildan_keyin_ochmaydi(self):
        self.nam.lab_holat = Namuna.LabHolat.TAHLILDA
        self.nam.save()
        self.client.post(self.url, {"sabab": "Xato summa kiritilgan"})
        self.assertTrue(Tolov.objects.filter(pk=self.t.pk).exists())
        self.assertNotContains(self.client.get(reverse("shartnoma_detail", args=[self.sh.pk])), self.url)

    def test_tarixni_faqat_superadmin_koradi(self):
        self.assertEqual(self.client.get(reverse("nazorat_tarixi")).status_code, 403)
        self.client.logout()
        self.login("superadmin")
        self.assertEqual(self.client.get(reverse("nazorat_tarixi")).status_code, 200)


class NarxnomaHuquqTests(BaseTest):
    def test_huquqlar_va_tarix(self):
        from core.models import NazoratTarixi
        nx = Narxnoma.objects.filter(sinov_obyekti="mineral").first()
        edit = reverse("narxnoma_edit", args=[nx.pk])
        for user, ro_yxat, tahrir in [("admin", 403, 403), ("lab_mineral", 403, 403), ("superadmin", 200, 403),
                                      ("buxgalter", 200, 200)]:
            self.client.logout()
            self.login(user)
            with self.subTest(user=user):
                self.assertEqual(self.client.get(reverse("narxnoma_list")).status_code, ro_yxat)
                self.assertEqual(self.client.get(edit).status_code, tahrir)
        # buxgalter narxni o'zgartiradi -> tarix
        data = {"tartib": nx.tartib, "parametr": nx.parametr, "tahlil_usuli": nx.tahlil_usuli,
                "sinov_obyekti": nx.sinov_obyekti, "obyekt_nomi": nx.obyekt_nomi, "narx": "90000",
                "har_namunaga": "on", "aktiv": "on"}
        self.client.post(edit, data)
        log = NazoratTarixi.objects.get(turi="narxnoma", obyekt_id=str(nx.pk))
        self.assertIn("→ 90 000", log.tafsilot)
        self.assertIn("Buxgalteriya", log.user_nomi)
        # buxgalter tarixni ko'rmaydi, super admin ko'radi
        self.assertEqual(self.client.get(reverse("nazorat_tarixi")).status_code, 403)
        self.assertNotContains(self.client.get(reverse("narxnoma_list")), "nazorat-tarixi")
        self.client.logout()
        self.login("superadmin")
        r = self.client.get(reverse("nazorat_tarixi") + f"?holat=narxnoma&obyekt_id={nx.pk}")
        self.assertContains(r, "90 000")


class NamunaQabulBayonnomaTests(BaseTest):
    def test_nq_tasdiqlangan_bayonnomani_koradi(self):
        a = Ariza.objects.create(turi="davlat", inn="123456789", buyurtmachi_nomi="T", fish="Y", telefon="+998",
                                 kategoriya="mineral", holat=Ariza.Holat.QABUL)
        nam = Namuna.objects.create(ariza=a, namuna_turi=NamunaTuri.objects.filter(kategoriya="mineral").first(),
                                    nomi="N", lab_holat=Namuna.LabHolat.NATIJA)
        x = Xulosa.objects.create(namuna=nam)
        XulosaNatija.objects.create(xulosa=x, korsatkich="pH", natija="7")
        pdf_url = reverse("xulosa_hujjat", args=[x.pk, "pdf"])
        self.login("namuna")
        self.assertNotContains(self.client.get(reverse("namuna_list")), pdf_url)  # tasdiqlanmagan
        self.assertEqual(self.client.get(pdf_url).status_code, 403)
        x.tasdiqlangan_at = timezone.now()
        x.save()
        self.assertContains(self.client.get(reverse("namuna_list")), pdf_url)
        r = self.client.get(pdf_url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertEqual(self.client.get(reverse("xulosa_hujjat", args=[x.pk, "docx"])).status_code, 403)


class SlaTests(TestCase):
    def setUp(self):
        from django.core.management import call_command
        call_command("boshlangich", "--demo", stdout=io.StringIO())

    def _t(self, y, mo, d, h, mi=0):
        from datetime import datetime
        return timezone.make_aware(datetime(y, mo, d, h, mi))

    def test_ish_daqiqalari(self):
        from .sla import Muddat
        m = Muddat(hozir=self._t(2026, 11, 23, 9, 30))  # dushanba 9:30
        self.assertEqual(m.ish_daqiqalari(self._t(2026, 11, 20, 17, 30)), 60)  # juma 17:30 -> 30+30
        self.assertFalse(m.otdimi(self._t(2026, 11, 20, 17, 30), "muddat_ariza_qabul"))
        self.assertTrue(Muddat(hozir=self._t(2026, 11, 23, 9, 31)).otdimi(self._t(2026, 11, 20, 17, 30),
                                                                         "muddat_ariza_qabul"))

    def test_bayram_hisoblanmaydi(self):
        from .models import Bayram
        from .sla import Muddat
        Bayram.objects.create(sana=self._t(2026, 11, 23, 0).date(), nomi="Test")
        m = Muddat(hozir=self._t(2026, 11, 24, 9, 0))
        self.assertEqual(m.ish_daqiqalari(self._t(2026, 11, 20, 17, 30)), 30)

    def test_kechikkan_ariza_miltillaydi(self):
        a = Ariza.objects.filter(holat=Ariza.Holat.YANGI).first()
        Ariza.objects.filter(pk=a.pk).update(yuborilgan_at=timezone.now() - timedelta(days=10))
        self.client.force_login(User.objects.get(username="namuna"))
        r = self.client.get(reverse("ariza_list") + "?kechikkan=1")
        self.assertContains(r, 'class="kechikdi"')
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, "Kechikkan arizalar")

    def test_sozlamalar_admin_va_tarix(self):
        from .models import NazoratTarixi, Sozlama
        self.client.force_login(User.objects.get(username="admin"))
        data = {"sozlama": "1", "ish_boshlanishi": "08:00", "ish_tugashi": "17:00",
                "ish_kunlari_tanlov": ["0", "1", "2", "3", "4", "5"]}
        for f in Sozlama.MUDDAT_MAYDONLARI:
            data[f] = 120
        r = self.client.post(reverse("sozlamalar"), data)
        self.assertEqual(r.status_code, 302)
        s = Sozlama.ol()
        self.assertEqual(s.ish_kunlari, "0,1,2,3,4,5")
        self.assertEqual(s.muddat_tahlil, 120)
        self.assertTrue(NazoratTarixi.objects.filter(turi=NazoratTarixi.Turi.SOZLAMA).exists())
        self.client.force_login(User.objects.get(username="buxgalter"))
        self.assertEqual(self.client.get(reverse("sozlamalar")).status_code, 403)


class StatistikaTests(TestCase):
    def setUp(self):
        call_command("boshlangich", "--demo", stdout=io.StringIO())

    def test_oylik_kunlik_yillik_va_excel(self):
        self.client.force_login(User.objects.get(username="buxgalter"))
        for g in ("kun", "oy", "yil"):
            r = self.client.get(reverse("statistika") + f"?guruh={g}")
            self.assertEqual(r.status_code, 200)
            self.assertEqual(r.context["jami"]["ariza"], Ariza.objects.count())
            self.assertEqual(r.context["jami"]["tolov_soni"], Tolov.objects.count())
        r = self.client.get(reverse("statistika") + "?guruh=oy&kategoriya=mineral&excel=1")
        self.assertIn("spreadsheetml", r["Content-Type"])
        self.client.force_login(User.objects.get(username="namuna"))
        self.assertEqual(self.client.get(reverse("statistika")).status_code, 403)


class ParolTests(TestCase):
    def setUp(self):
        call_command("boshlangich", "--demo", stdout=io.StringIO())
        self.mijoz = User.objects.create_user(username="+998901112233", password="eski12345", role=Role.MIJOZ,
                                              fish="Mijoz Test")

    def test_sa_tiklaydi_majburiy_almashtirish(self):
        from .models import NazoratTarixi
        sa = User.objects.get(username="superadmin")
        self.client.force_login(sa)
        r = self.client.get(reverse("buyurtmachi_list"))
        self.assertContains(r, "+998901112233")
        self.assertNotContains(r, "pbkdf2")
        r = self.client.post(reverse("parol_tiklash", args=[self.mijoz.pk]))
        parol = r.context["parol"]
        self.assertTrue(NazoratTarixi.objects.filter(turi=NazoratTarixi.Turi.PAROL).exists())
        self.client.logout()
        self.assertTrue(self.client.login(username="+998901112233", password=parol))
        r = self.client.get(reverse("kabinet"))
        self.assertRedirects(r, reverse("parol_almashtirish"))
        r = self.client.post(reverse("parol_almashtirish"),
                             {"new_password1": "YangiParol!77", "new_password2": "YangiParol!77"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.client.get(reverse("kabinet")).status_code, 200)
        # boshqa rollar kira olmaydi
        self.client.force_login(User.objects.get(username="admin"))
        self.assertEqual(self.client.get(reverse("buyurtmachi_list")).status_code, 403)

    def test_sms_kod_orqali(self):
        from unittest import mock
        with mock.patch("core.xabarnoma.sms_sozlangan", return_value=True), \
                mock.patch("core.xabarnoma.sms_yubor") as yubor:
            self.client.post(reverse("parol_unutdim"), {"telefon": "+998 90 111 22 33"})
            matn = yubor.call_args[0][1]
        kod = "".join(ch for ch in matn if ch.isdigit())[:6]
        r = self.client.post(reverse("parol_unutdim"), {"kod": "000000" if kod != "000000" else "111111",
                                                        "parol1": "yangi123", "parol2": "yangi123"})
        self.assertContains(r, "Kod noto")
        r = self.client.post(reverse("parol_unutdim"), {"kod": kod, "parol1": "yangi123", "parol2": "yangi123"})
        self.assertRedirects(r, reverse("login"))
        self.assertTrue(self.client.login(username="+998901112233", password="yangi123"))

    def test_sms_ulanmagan(self):
        r = self.client.post(reverse("parol_unutdim"), {"telefon": "+998 90 111 22 33"}, follow=True)
        self.assertContains(r, "SMS xizmati hali ulanmagan")


class KopNamunaTests(BaseTest):
    def test_aralash_ariza_bitta_shartnoma(self):
        from .models import Narxnoma
        mijoz = User.objects.create_user("+998905557788", password="parol123", role=Role.MIJOZ)
        self.client.login(username="+998905557788", password="parol123")
        data = {"turi": "importyor", "inn": "123456789", "buyurtmachi_nomi": "Agro", "fish": "Ali",
                "telefon": "+998905557788", "namuna_soni": 2, "chegara_maskani": "Olot"}
        for i, (kat, nom) in enumerate([("mineral", "Ammofos"), ("kimyoviy", "Fungitsid X")]):
            data.update({f"s{i}-kategoriya": kat, f"s{i}-nomi": nom, f"s{i}-partiya_raqami": f"LOT-{i}",
                         f"s{i}-invoys_raqami": f"INV-{i}", f"s{i}-invoys": pdf(f"inv{i}.pdf"),
                         f"s{i}-analiz": pdf(f"an{i}.pdf"), f"s{i}-guvohnoma": pdf(f"gv{i}.pdf")})
        r = self.client.post(reverse("ariza_yangi"), data)
        self.assertRedirects(r, reverse("kabinet"))
        a = Ariza.objects.get(mijoz=mijoz)
        self.assertEqual(a.kategoriyalar, "mineral,kimyoviy")
        self.assertEqual(a.arizanamunalar.count(), 2)
        self.assertEqual(a.hujjatlar.filter(ariza_namuna__tartib=2).count(), 3)

        # namuna qabul qiluvchi: har bir blok o'z guruhining turlarini ko'radi
        self.client.logout()
        self.login("namuna")
        r = self.client.get(reverse("ariza_qabul", args=[a.pk]))
        html = r.content.decode()
        self.assertIn("Azotli", html.split('name="n0-namuna_turi"')[1].split("</select>")[0])
        self.assertIn("Fungitsidlar", html.split('name="n1-namuna_turi"')[1].split("</select>")[0])
        self.assertIn("LOT-1", html)
        post = {}
        for i, t in enumerate([NamunaTuri.objects.get(nomi="Azotli o'g'itlar"),
                               NamunaTuri.objects.get(nomi="Fungitsidlar")]):
            post.update({f"n{i}-namuna_turi": t.pk, f"n{i}-nomi": f"N{i}", f"n{i}-namuna_olgan": "Ali",
                         f"n{i}-ogirligi": "1 kg"})
        self.assertRedirects(self.client.post(reverse("ariza_qabul", args=[a.pk]), post), reverse("namuna_list"))

        # mineral laboratoriya o'z qismini qo'shadi
        self.client.logout()
        self.login("lab_mineral")
        nx_m = Narxnoma.objects.filter(sinov_obyekti__in=Narxnoma.KATEGORIYA_OBYEKTLARI["mineral"]).first()
        r = self.client.post(reverse("shartnoma_yangi", args=[a.pk]), {f"band_{nx_m.pk}": "1", f"soni_{nx_m.pk}": "1"})
        sh = Shartnoma.objects.get(ariza=a, is_active=True)
        self.assertEqual(sh.narxsiz_kategoriyalar, ["kimyoviy"])
        self.client.post(reverse("shartnoma_yuborish", args=[sh.pk]))
        sh.refresh_from_db()
        self.assertEqual(sh.holat, Shartnoma.Holat.YUBORILMAGAN)  # kimyoviy narxi yo'q — yuborilmaydi

        # kimyoviy laboratoriya: ariza ro'yxatda, xuddi shu shartnomaga qo'shadi
        self.client.logout()
        self.login("lab_kimyo")
        self.assertContains(self.client.get(reverse("shartnoma_tanlash")), a.raqam)
        self.assertRedirects(self.client.get(reverse("shartnoma_yangi", args=[a.pk])),
                             reverse("shartnoma_edit", args=[sh.pk]))
        nx_k = Narxnoma.objects.filter(sinov_obyekti__in=Narxnoma.KATEGORIYA_OBYEKTLARI["kimyoviy"]).first()
        self.client.post(reverse("shartnoma_edit", args=[sh.pk]), {f"band_{nx_k.pk}": "1", f"soni_{nx_k.pk}": "1"})
        self.assertEqual(sorted(sh.bandlar.values_list("kategoriya", flat=True)), ["kimyoviy", "mineral"])
        self.assertEqual(Shartnoma.objects.filter(ariza=a, is_active=True).count(), 1)
        self.client.post(reverse("shartnoma_yuborish", args=[sh.pk]))
        sh.refresh_from_db()
        self.assertEqual(sh.holat, Shartnoma.Holat.YUBORILGAN)
        self.assertEqual(sh.namunalar.count(), 2)


class RoyxatJshshirTests(TestCase):
    def _post(self, turi, inn):
        return self.client.post(reverse("royxat"), {
            "turi": turi, "telefon": "+998991571930", "fish": "Kazimjon", "inn": inn,
            "tashkilot_nomi": "Agro MCHJ" if turi == "yuridik" else "", "parol1": "parol123", "parol2": "parol123"})

    def test_jismoniy_faqat_14_xonali(self):
        r = self._post("jismoniy", "456654456")
        self.assertContains(r, "14 xonali JSHSHIR")
        self.assertFalse(User.objects.filter(username="+998991571930").exists())
        r = self._post("jismoniy", "12345678901234")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(User.objects.get(username="+998991571930").pinfl, "12345678901234")

    def test_yuridik_inn(self):
        self.assertEqual(self._post("yuridik", "123456789").status_code, 302)


class NqTahrirTests(BaseTest):
    def test_nq_mijoz_arizasini_tahrirlay_olmaydi(self):
        mijoz = User.objects.create_user("+998901230099", password="parol123", role=Role.MIJOZ)
        a = Ariza.objects.create(mijoz=mijoz, turi="ixtiyoriy", inn="12345678901234", fish="Ali", telefon="+998",
                                 kategoriya="mineral")
        xodim_a = Ariza.objects.create(turi="ixtiyoriy", inn="12345678901234", fish="Vali", telefon="+998",
                                       kategoriya="mineral")
        self.login("namuna")
        r = self.client.get(reverse("ariza_detail", args=[a.pk]))
        self.assertNotContains(r, reverse("ariza_tahrirlash", args=[a.pk]))
        self.assertContains(r, reverse("ariza_qabul", args=[a.pk]))  # qabul qilish tugmasi qoladi
        self.assertEqual(self.client.get(reverse("ariza_tahrirlash", args=[a.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("ariza_tahrirlash", args=[a.pk]), {}).status_code, 403)
        # xodimning o'zi yaratgan arizani tahrirlay oladi
        self.assertEqual(self.client.get(reverse("ariza_tahrirlash", args=[xodim_a.pk])).status_code, 200)


class HujjatLabTests(BaseTest):
    def test_lab_faqat_oz_namunasi_hujjatlarini_koradi(self):
        from .models import ArizaNamuna
        mijoz = User.objects.create_user("+998901230088", password="parol123", role=Role.MIJOZ)
        a = Ariza.objects.create(mijoz=mijoz, turi="davlat", inn="123456789", buyurtmachi_nomi="X", fish="Y",
                                 telefon="+998", kategoriya="mineral", kategoriyalar="mineral,kimyoviy",
                                 holat=Ariza.Holat.QABUL)
        b1 = ArizaNamuna.objects.create(ariza=a, tartib=1, kategoriya="mineral", nomi="M")
        b2 = ArizaNamuna.objects.create(ariza=a, tartib=2, kategoriya="kimyoviy", nomi="K")
        h1 = ArizaHujjat.objects.create(ariza=a, ariza_namuna=b1, turi="guvohnoma", fayl=pdf("m.pdf"))
        h2 = ArizaHujjat.objects.create(ariza=a, ariza_namuna=b2, turi="guvohnoma", fayl=pdf("k.pdf"))
        n1 = Namuna.objects.create(ariza=a, ariza_namuna=b1, namuna_turi=NamunaTuri.objects.get(nomi="Azotli o'g'itlar"),
                                   nomi="M", tartib=1)
        Namuna.objects.create(ariza=a, ariza_namuna=b2, namuna_turi=NamunaTuri.objects.get(nomi="Fungitsidlar"),
                              nomi="K", tartib=2)
        u1, u2 = reverse("ariza_hujjat", args=[h1.pk]), reverse("ariza_hujjat", args=[h2.pk])
        self.login("lab_mineral")
        r = self.client.get(reverse("ariza_detail", args=[a.pk]))
        self.assertContains(r, u1)
        self.assertNotContains(r, u2)
        self.assertContains(r, "Mineral o&#x27;g&#x27;it: Azotli o&#x27;g&#x27;itlar")
        self.assertNotContains(r, "Fungitsidlar")
        self.assertEqual(self.client.get(u2).status_code, 403)
        self.assertEqual(self.client.get(u1).status_code, 200)
        self.client.logout()
        self.login("lab_kimyo")
        self.assertEqual(self.client.get(u1).status_code, 403)
        # namuna qabul qiluvchi ro'yxatida har bir namuna faqat o'z hujjatlari bilan
        self.client.logout()
        self.login("namuna")
        r = self.client.get(reverse("namuna_list") + "?q=" + a.raqam)
        rows = {obj.pk: cells for obj, cells, _c in r.context["rows"]}
        fayllar = [c[1] for c in rows[n1.pk] if c[0].kind == "file"][0]
        self.assertEqual([h.pk for h in fayllar], [h1.pk])


class ArizaJshshirTests(BaseTest):
    def test_jismoniy_shaxsga_ixtiyoriy_va_jshshir(self):
        u = User.objects.create_user("+998901239911", password="parol123", role=Role.MIJOZ, fish="Ali",
                                     pinfl="36936936936936")
        self.client.login(username="+998901239911", password="parol123")
        r = self.client.get(reverse("ariza_yangi"))
        self.assertEqual(r.context["form"].turi(), "ixtiyoriy")
        self.assertContains(r, 'data-pinfl="36936936936936"')
        self.assertContains(r, '<option value="ixtiyoriy" selected')


class IxtiyoriyHujjatsizTests(BaseTest):
    def test_ixtiyoriy_hujjatsiz_yuboriladi(self):
        u = User.objects.create_user("+998901239922", password="parol123", role=Role.MIJOZ)
        self.client.login(username="+998901239922", password="parol123")
        r = self.client.post(reverse("ariza_yangi"), {
            "turi": "ixtiyoriy", "inn": "12345678901234", "fish": "Sitora", "telefon": "+998770199975",
            "namuna_soni": 2, "kategoriya": "mineral", "namuna_nomi": "tuproq"})
        self.assertRedirects(r, reverse("kabinet"))
        a = Ariza.objects.get(mijoz=u)
        self.assertEqual(a.hujjatlar.count(), 0)
        self.assertEqual(a.arizanamunalar.count(), 2)


class MasulVaPdfTests(LabJarayonTests):
    def _tayyor_topshiriq(self):
        from core.models import Topshiriq
        sh = self._yuborilgan_shartnoma(40)
        nam = sh.namunalar.order_by("tartib").first()
        r = self.client.get(reverse("tahlilga_yuborish", args=[nam.pk]))
        self.client.post(reverse("tahlilga_yuborish", args=[nam.pk]), {f"masul_{i}": self.m1.pk for i, *_r in r.context["rows"]})
        return nam, Topshiriq.objects.get(namuna=nam, masul=self.m1)

    def test_masul_hujjat_va_ortiqcha_ustun_kormaydi(self):
        nam, t = self._tayyor_topshiriq()
        h = ArizaHujjat.objects.create(ariza=nam.ariza, turi="guvohnoma", fayl=pdf("g.pdf"))
        self.client.logout()
        self.client.login(username="masul1", password="demo12345")
        self.client.post(reverse("topshiriq_qabul", args=[t.pk]))
        r = self.client.get(reverse("topshiriq_natija", args=[t.pk]))
        self.assertNotContains(r, reverse("ariza_hujjat", args=[h.pk]))
        self.assertNotContains(r, "-meyor")
        self.assertNotContains(r, "Muvofiqlik")
        self.assertContains(r, "nt-0-natija")
        self.assertEqual(self.client.get(reverse("ariza_hujjat", args=[h.pk])).status_code, 403)

    def test_pdf_shifrsiz_ham_beriladi_xato_yashirilmaydi(self):
        from unittest import mock

        from core.models import Xulosa
        nam, _t = self._tayyor_topshiriq()
        x = Xulosa.objects.get(namuna=nam)
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        c.drawString(100, 750, "test")
        c.save()
        fake = buf.getvalue()
        with mock.patch("core.views_lab.docx_to_pdf", return_value=fake), \
                mock.patch("pypdf.PdfWriter.encrypt", side_effect=ImportError("cryptography yo'q")):
            r = self.client.get(reverse("xulosa_hujjat", args=[x.pk, "pdf"]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        with mock.patch("core.views_lab.docx_to_pdf", side_effect=RuntimeError("soffice")):
            r = self.client.get(reverse("xulosa_hujjat", args=[x.pk, "pdf"]))
        self.assertEqual(r.status_code, 500)
        self.assertContains(r, "yaratib bo", status_code=500)


class DalolatnomaYoqTests(LabJarayonTests):
    def test_dalolatnoma_formada_va_bayonnomada_yoq(self):
        from core.forms import XulosaForm
        self.assertNotIn("dalolatnoma", XulosaForm.base_fields)
        self.assertNotIn("dalolatnoma", XulosaForm.Meta.fields)


class TelegramUlashTests(TestCase):
    def test_buyruq_webhook_ornatadi(self):
        from unittest import mock
        javob = {"getMe": {"ok": True, "result": {"username": "AgroximTestBot"}}, "setWebhook": {"ok": True},
                 "getWebhookInfo": {"ok": True, "result": {}}}
        with override_settings(TELEGRAM_BOT_TOKEN="x", TELEGRAM_BOT_USERNAME="AgroximTestBot",
                               TELEGRAM_WEBHOOK_SECRET="s3cr3t", PUBLIC_BASE_URL="https://agroximtest.uz"), \
                mock.patch("core.xabarnoma._tg", side_effect=lambda m, **kw: javob[m]) as tg:
            out = io.StringIO()
            call_command("telegram_ulash", stdout=out)
        url = [c for c in tg.call_args_list if c.args[0] == "setWebhook"][0].kwargs["json_body"]["url"]
        self.assertEqual(url, "https://agroximtest.uz/telegram/webhook/s3cr3t/")
        self.assertNotIn("s3cr3t", out.getvalue())  # maxfiy qism ekranga chiqmaydi
        self.assertIn("@AgroximTestBot", out.getvalue())
