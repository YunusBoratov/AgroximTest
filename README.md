# AgroximTest — Mineral o'g'it va kimyoviy vositalar tahlili

"Agrokimyo va tuproq tahlili markazi" uchun platforma: ariza → namuna → shartnoma (oferta) →
to'lov → laboratoriya tahlili → xulosa (sinov bayonnomasi) → mijozga berish.

Texnologiya: **Django 5.2**, server tomonida render qilinadigan sahifalar, **PostgreSQL** (ishlab chiqarishda)
yoki SQLite (lokal sinov uchun).

## Ishga tushirish (lokal)

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py boshlangich --demo
python manage.py runserver
```

`boshlangich` buyrug'i namuna turlarini yuklaydi va `docs/shablonlar/narxnoma_jadvali.xlsx` hamda `narxnoma_pestitsid.xlsx` dan narxnomani import qiladi.
`--demo` qo'shilsa, har bir rol uchun sinov foydalanuvchilari va namunaviy arizalar yaratiladi (parol: `demo12345`):

| Login | Rol |
|---|---|
| `superadmin` | Super admin (hamma narsa + xodimlar) |
| `admin` | Admin |
| `buxgalter` | Buxgalteriya |
| `lab_mineral` | Mineral o'g'it tahlil laboratoriyasi |
| `lab_kimyo` | Kimyoviy vositalar tahlil laboratoriyasi |
| `namuna` | Namuna qabul qilib oluvchi |

Testlar: `python manage.py test`

`PUBLIC_BASE_URL` (masalan `https://agroximtest.uz`) — bayonnomadagi QR kod shu manzilga olib boradi.

Shartnoma PDF uchun serverda LibreOffice (`soffice`) o'rnatilgan bo'lishi kerak; bo'lmasa Word fayl beriladi.

Mijozlar `/royxatdan-otish/` sahifasida telefon raqami va parol bilan ro'yxatdan o'tadi (OneID kalitlari olingach qo'shiladi).

## Serverga o'rnatish

To'liq qo'llanma: [docs/SERVERGA_ORNATISH.md](docs/SERVERGA_ORNATISH.md). Barcha maxfiy kalitlar `.env` faylida (namuna: `.env.example`).

## Ishlab chiqarish sozlamalari (environment)

`DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS=agroximtest.uz`, `DJANGO_CSRF_ORIGINS=https://agroximtest.uz`,
`DB_ENGINE=postgres`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.

## Biznes qoidalari

- Raqamlash: ariza `ATM-A-2026-00001`, shartnoma oddiy tartib raqami (`381`), xulosa `ATM-P-2026-00001` (har yili qaytadan).
  Joriy yil uchun shartnoma raqamini davom ettirish: admin paneldagi "Hisoblagich" yoki `SHARTNOMA_RAQAM_BOSHLANISH`.
- Tahlil kamida **30%** to'lovdan keyin boshlanadi (`TAHLIL_BOSHLASH_MIN_FOIZ`).
- Xulosa buyurtmachiga faqat **100%** to'lovdan keyin yuboriladi.
- Bitta shartnomada bir nechta namuna bo'lishi mumkin; har bir namuna uchun alohida xulosa chiqadi.
- Laboratoriya xodimi faqat o'z kategoriyasini (mineral yoki kimyoviy) ko'radi.

## Bosqichlar

- [x] **1-bosqich:** modellar, rollar, login, dizayn (sidebar, jadvallar, filtrlar, Excel), monitoring panellari, xodimlar, narxnoma
- [x] **2-bosqich:** mijoz sayti (3 xil ariza + hujjat yuklash), ro'yxatdan o'tish (telefon + parol), kabinet, namuna qabul qiluvchi ishi (qabul / rad / namuna yaratish / tahrirlash)
- [x] **3-bosqich:** shartnoma tuzish (narxnomadan ko'rsatkich tanlash), shartnoma Word/PDF (rasmiy shablon asosida), buxgalteriyaga yuborish, rekvizitlar, to'lovlar (30% / 100% qoidalari)
- [x] **4-bosqich:** laboratoriya jarayoni (tahlilga olish 30%+, natijalar tayyor, natija kiritish), sinov bayonnomasi Word/PDF (yangi shakl, QR kod), tasdiqlash, 100% to'lovdan keyin mijozga berish, QR orqali ochiq tekshirish sahifasi
- [x] **5-bosqich (qisman):** Click SHOP API (onlayn to'lov avtomatik shartnomaga yoziladi), SMS (Eskiz.uz) va Telegram bot xabarnomalari, xabarlar jurnali, hujjatlarni ruxsat bilan berish, serverga o'rnatish qo'llanmasi
- [ ] Rus tili tarjimasi, OneID (kalitlar olingach)

`docs/shablonlar/` — buyurtmachi bergan rasmiy shakllar (shartnoma, xulosa, narxnoma, namuna qabul qilish).
