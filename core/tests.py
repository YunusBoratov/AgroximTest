from decimal import Decimal

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import Role, User
from core.models import Ariza, ArizaTuri, NamunaTuri, Narxnoma, Shartnoma, ShartnomaBand, Tolov


class BaseTest(TestCase):
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
        self.assertRegex(sh.raqam, r"^ATM m \d{4} \d{5}$")

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
