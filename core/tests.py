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


# ---------------------------------------------------------------------------
# 4-bosqich: laboratoriya jarayoni va xulosa
# ---------------------------------------------------------------------------
from core.models import Xulosa, XulosaNatija  # noqa: E402


class LabJarayonTests(ShartnomaTests):
    def _yuborilgan_shartnoma(self, foiz):
        sh = self._tuz()
        self.client.post(reverse("shartnoma_yuborish", args=[sh.pk]))
        if foiz:
            Tolov.objects.create(shartnoma=sh, summa=(sh.jami_summa * Decimal(foiz) / 100).quantize(Decimal("0.01")))
            sh.qayta_hisobla()
        return sh

    def _natija_post(self, x, natija="12.4"):
        data = {"sinov_sanasi": timezone.localdate().isoformat(), "dalolatnoma": "5", "sinov_joyi": "Laboratoriya",
                "harorat": "T=(23±1)°C", "namlik": "W=(45±1)%", "tasdiqlagan": "N. Baysunova",
                "bosh_agrokimyogar": "X. Sottiyev", "yetakchi_agrokimyogar": "F. Egamova",
                "ogirligi": "0.5 kg", "tavsifi": "oq donador"}
        rows = list(x.natijalar.all())
        data.update({"nt-TOTAL_FORMS": len(rows) + 1, "nt-INITIAL_FORMS": len(rows),
                     "nt-MIN_NUM_FORMS": 0, "nt-MAX_NUM_FORMS": 1000})
        for i, r in enumerate(rows):
            data.update({f"nt-{i}-id": r.pk, f"nt-{i}-xulosa": x.pk, f"nt-{i}-korsatkich": r.korsatkich,
                         f"nt-{i}-meyor": "12±1", f"nt-{i}-natija": natija, f"nt-{i}-sinov_usuli": r.sinov_usuli,
                         f"nt-{i}-muvofiqlik": "Muvofiq"})
        i = len(rows)  # narxnomada yo'q qo'shimcha ko'rsatkich
        data.update({f"nt-{i}-xulosa": x.pk, f"nt-{i}-korsatkich": "Zichlik, g/sm3", f"nt-{i}-natija": "1.1"})
        return data

    def test_30_foizsiz_tahlil_boshlanmaydi(self):
        sh = self._yuborilgan_shartnoma(10)
        nam = sh.namunalar.first()
        self.client.post(reverse("tahlilga_olish", args=[nam.pk]))
        nam.refresh_from_db()
        self.assertEqual(nam.lab_holat, Namuna.LabHolat.YANGI)

    def test_toliq_lab_jarayoni(self):
        sh = self._yuborilgan_shartnoma(40)
        nam = sh.namunalar.order_by("tartib").first()
        self.client.post(reverse("tahlilga_olish", args=[nam.pk]))
        nam.refresh_from_db()
        self.assertEqual(nam.lab_holat, Namuna.LabHolat.TAHLILDA)
        r = self.client.post(reverse("natija_tayyor", args=[nam.pk]))
        self.assertRedirects(r, reverse("xulosa_kiritish", args=[nam.pk]))
        # natija sahifasi xulosani shartnoma ko'rsatkichlari bilan yaratadi (namuna olish kirmaydi)
        self.client.get(reverse("xulosa_kiritish", args=[nam.pk]))
        x = Xulosa.objects.get(namuna=nam)
        korsatkichlar = list(x.natijalar.values_list("korsatkich", flat=True))
        self.assertEqual(korsatkichlar[0], "Tashqi ko‘rinishi, rangi")
        self.assertIn(self.azot.parametr, korsatkichlar)
        self.assertFalse(any(k.startswith("Namuna olish") for k in korsatkichlar))
        r = self.client.post(reverse("xulosa_kiritish", args=[nam.pk]), self._natija_post(x))
        self.assertRedirects(r, reverse("xulosa_korish", args=[x.pk]))
        nam.refresh_from_db()
        x.refresh_from_db()
        self.assertEqual(nam.lab_holat, Namuna.LabHolat.XULOSA)
        self.assertEqual(x.natijalar.count(), len(korsatkichlar) + 1)
        self.assertEqual(x.natijalar.order_by("tartib").last().korsatkich, "Zichlik, g/sm3")
        self.assertEqual(nam.ogirligi, "0.5 kg")
        # hujjat
        r = self.client.get(reverse("xulosa_hujjat", args=[x.pk, "docx"]))
        import io

        import docx
        d = docx.Document(io.BytesIO(r.content))
        jadval = "\n".join(c.text for row in d.tables[3].rows for c in row.cells)
        self.assertIn("Zichlik, g/sm3", jadval)
        self.assertIn(x.raqam, d.tables[1].rows[0].cells[0].text)
        # tasdiqlanmagan xulosa QR orqali ochilmaydi
        self.assertEqual(self.client.get(reverse("xulosa_tekshirish", args=[x.verify_token])).status_code, 404)
        self.client.post(reverse("xulosa_tasdiqlash", args=[x.pk]))
        x.refresh_from_db()
        self.assertTrue(x.tasdiqlangan)
        # tasdiqlangandan keyin tahrirlab bo'lmaydi
        self.assertRedirects(self.client.get(reverse("xulosa_kiritish", args=[nam.pk])),
                             reverse("xulosa_korish", args=[x.pk]))
        self.client.logout()
        self.assertEqual(self.client.get(reverse("xulosa_tekshirish", args=[x.verify_token])).status_code, 200)
        # 40% to'lovda mijozga berilmaydi
        self.login("lab_mineral")
        self.client.post(reverse("xulosa_berish", args=[x.pk]))
        nam.refresh_from_db()
        self.assertEqual(nam.lab_holat, Namuna.LabHolat.XULOSA)
        Tolov.objects.create(shartnoma=sh, summa=sh.qoldiq)
        sh.qayta_hisobla()
        self.client.post(reverse("xulosa_berish", args=[x.pk]))
        nam.refresh_from_db()
        self.assertEqual(nam.lab_holat, Namuna.LabHolat.BERILDI)

    def test_mijoz_faqat_berilgan_xulosani_yuklaydi(self):
        mijoz = User.objects.create_user("+998900000001", password="parol123", role=Role.MIJOZ)
        self.ariza.mijoz = mijoz
        self.ariza.save()
        nam = self.ariza.namunalar.first()
        x = Xulosa.objects.create(namuna=nam, tasdiqlangan_at=timezone.now())
        XulosaNatija.objects.create(xulosa=x, korsatkich="pH", natija="7")
        self.client.login(username="+998900000001", password="parol123")
        self.assertEqual(self.client.get(reverse("xulosa_hujjat", args=[x.pk, "docx"])).status_code, 403)
        nam.lab_holat = Namuna.LabHolat.BERILDI
        nam.save()
        self.assertEqual(self.client.get(reverse("xulosa_hujjat", args=[x.pk, "docx"])).status_code, 200)

    def test_buxgalter_xulosa_yuklay_olmaydi(self):
        nam = self.ariza.namunalar.first()
        x = Xulosa.objects.create(namuna=nam)
        self.login("buxgalter")
        self.assertEqual(self.client.get(reverse("xulosa_hujjat", args=[x.pk, "docx"])).status_code, 403)


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
