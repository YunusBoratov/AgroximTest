# Platformani o'z kompyuteringizda sinab ko'rish (Windows)

Bu faqat **sinov uchun**. Kompyuter yoqiq turgan paytda ishlaydi. Click va Telegram ishlamaydi, chunki ular
internetdan kiriladigan manzil talab qiladi. Qolgan hamma narsa ishlaydi: ariza, namuna, shartnoma, to'lov
va xulosa.

## 1. Dasturlarni o'rnatish (bir marta)

1. **Python 3.12** — https://www.python.org/downloads/ dan yuklab o'rnating.
   O'rnatishning birinchi oynasida **"Add python.exe to PATH"** belgisini albatta qo'ying.
2. **LibreOffice** (PDF uchun, ixtiyoriy) — https://www.libreoffice.org/download/ .
   O'rnatilmasa shartnoma va xulosa Word ko'rinishida yuklanadi.

## 2. Loyihani yuklab olish

1. GitHub'da repozitoriyni oching, `claude/adoring-hopper-16bq23` branchini tanlang.
2. Yashil **Code** tugmasi → **Download ZIP**.
3. ZIP'ni `C:\AgroximTest` papkasiga chiqaring (ichida `manage.py` fayli bo'lishi kerak).

## 3. Ishga tushirish (birinchi marta)

`C:\AgroximTest` papkasini oching, yuqoridagi manzil satriga `cmd` deb yozib Enter bosing.
Ochilgan qora oynaga quyidagilarni birma-bir kiriting:

```
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py boshlangich --demo
python manage.py runserver 0.0.0.0:8000
```

Brauzerda oching: **http://127.0.0.1:8000**

## 4. Keyingi safar

```
cd C:\AgroximTest
venv\Scripts\activate
python manage.py runserver 0.0.0.0:8000
```

Qora oynani yopsangiz platforma to'xtaydi.

## Sinov loginlari (parol: `demo12345`)

| Login | Rol |
|---|---|
| `superadmin` | Super admin |
| `admin` | Admin |
| `buxgalter` | Buxgalteriya |
| `lab_mineral` | Mineral o'g'it laboratoriyasi |
| `lab_kimyo` | Kimyoviy vositalar laboratoriyasi |
| `namuna` | Namuna qabul qiluvchi |

Mijoz sifatida sinash uchun bosh sahifada **"Ro'yxatdan o'tish"**.

## Ofisdagi hamkasblar ham sinashi uchun (bir xil tarmoqda)

1. `C:\AgroximTest` papkasida `.env` nomli fayl yarating va ichiga bitta qator yozing:
   `DJANGO_ALLOWED_HOSTS=*`
2. Qora oynada `ipconfig` buyrug'i bilan kompyuteringiz IP manzilini toping (masalan `192.168.1.25`).
3. Platformani qayta ishga tushiring. Windows "Brandmauer" so'rasa — **Ruxsat berish**.
4. Hamkasblar brauzerda `http://192.168.1.25:8000` ni ochadi.

Sinov tugagach, haqiqiy ishga serverda `.env.example` asosida yangi `.env` tuziladi (bu yerdagi demo
ma'lumotlar o'tkazilmaydi).
