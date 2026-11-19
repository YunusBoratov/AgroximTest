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
                "namuna_turi": NamunaTuri.objects.filter(kategoriya="mineral").first().pk,
                "namuna_nomi": "Ammofos", "chegara_maskani": "Olot", "partiya_raqami": "LOT-1",
                "invoys": pdf("inv.pdf"), "analiz": pdf("an.pdf"), "guvohnoma": pdf("gv.pdf")}
        data.update(extra)
        return self.client.post(reverse("ariza_yangi"), data)

    def test_importyor_ariza(self):
        r = self._importyor()
        self.assertRedirects(r, reverse("kabinet"))
        a = Ariza.objects.get(mijoz=self.mijoz)
        self.assertEqual(a.kategoriya, "mineral")
        self.assertEqual(a.hujjatlar.count(), 3)

    def test_hujjatsiz_ariza_qabul_qilinmaydi(self):
        r = self._importyor(invoys="")
        self.assertEqual(r.status_code, 200)
        self.assertIn("invoys", r.context["form"].errors)
        self.assertFalse(Ariza.objects.filter(mijoz=self.mijoz).exists())

    def test_ixtiyoriy_jshshir_tekshiruvi(self):
        base = {"turi": "ixtiyoriy", "fish": "Ali", "telefon": "+998901112233", "namuna_soni": 1,
                "namuna_turi": NamunaTuri.objects.first().pk, "guvohnoma": pdf()}
        r = self.client.post(reverse("ariza_yangi"), dict(base, inn="123456789"))
        self.assertIn("inn", r.context["form"].errors)
        r = self.client.post(reverse("ariza_yangi"), dict(base, inn="12345678901234", guvohnoma=pdf()))
        self.assertRedirects(r, reverse("kabinet"))

    def test_notogri_fayl_turi(self):
        r = self._importyor(invoys=SimpleUploadedFile("x.exe", b"MZ"))
        self.assertIn("invoys", r.context["form"].errors)

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
            data.update({f"n{i}-nomi": f"Namuna {i}", f"n{i}-namuna_olgan": "R. Qarayev", f"n{i}-ogirligi": "0.5 kg"})
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
            "namuna_soni": 1, "namuna_turi": NamunaTuri.objects.first().pk, "guvohnoma": pdf()})
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
