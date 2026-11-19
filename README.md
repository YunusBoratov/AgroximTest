# AgroximTest — Mineral o'g'it va kimyoviy vositalar tahlili

Respublika agrokimyoviy tahlil markazi uchun platforma: ariza → namuna → shartnoma (oferta) →
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

`boshlangich` buyrug'i namuna turlarini yuklaydi va `docs/shablonlar/narxnoma_jadvali.xlsx` dan narxnomani import qiladi.
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

## Ishlab chiqarish sozlamalari (environment)

`DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS=agroximtest.uz`, `DJANGO_CSRF_ORIGINS=https://agroximtest.uz`,
`DB_ENGINE=postgres`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`.

## Biznes qoidalari

- Raqamlash: ariza `ATM-A-2026-00001`, shartnoma `ATM m 2026 00001`, xulosa `ATM-P-2026-00001` (har yili qaytadan).
- Tahlil kamida **30%** to'lovdan keyin boshlanadi (`TAHLIL_BOSHLASH_MIN_FOIZ`).
- Xulosa buyurtmachiga faqat **100%** to'lovdan keyin yuboriladi.
- Bitta shartnomada bir nechta namuna bo'lishi mumkin; har bir namuna uchun alohida xulosa chiqadi.
- Laboratoriya xodimi faqat o'z kategoriyasini (mineral yoki kimyoviy) ko'radi.

## Bosqichlar

- [x] **1-bosqich:** modellar, rollar, login, dizayn (sidebar, jadvallar, filtrlar, Excel), monitoring panellari, xodimlar, narxnoma
- [ ] **2-bosqich:** mijoz sayti (3 xil ariza + hujjat yuklash), ro'yxatdan o'tish, namuna qabul qiluvchi ishi
- [ ] **3-bosqich:** shartnoma tuzish (narxnomadan ko'rsatkich tanlash), shartnoma PDF, buxgalteriya to'lovlari, Click
- [ ] **4-bosqich:** laboratoriya jarayoni, natija kiritish, xulosa DOCX/PDF + QR, mijoz kabineti
- [ ] **5-bosqich:** OneID, SMS va Telegram bildirishnomalari, rus tili tarjimasi, serverga joylash

`docs/shablonlar/` — buyurtmachi bergan rasmiy shakllar (shartnoma, xulosa, narxnoma, namuna qabul qilish).
