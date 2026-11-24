# Serverga o'rnatish qo'llanmasi

Ubuntu 22.04 / 24.04 VPS uchun. Minimal talab: 2 GB RAM, 2 CPU, 20 GB disk.
Buyruqlar `root` yoki `sudo` huquqli foydalanuvchi bilan bajariladi.

## 1. Kerakli dasturlar

```bash
apt update && apt install -y python3-venv python3-dev postgresql nginx git libreoffice-writer fonts-dejavu certbot python3-certbot-nginx
```

`libreoffice-writer` shartnoma va sinov bayonnomasini PDF'ga aylantirish uchun kerak.

## 2. Ma'lumotlar bazasi

```bash
sudo -u postgres psql -c "CREATE USER agroximtest WITH PASSWORD 'kuchli-parol';"
sudo -u postgres psql -c "CREATE DATABASE agroximtest OWNER agroximtest;"
```

## 3. Loyiha

```bash
useradd -m -s /bin/bash agroximtest
mkdir -p /srv/agroximtest && chown agroximtest:www-data /srv/agroximtest
sudo -u agroximtest git clone -b claude/adoring-hopper-16bq23 https://github.com/YunusBoratov/AgroximTest.git /srv/agroximtest
cd /srv/agroximtest
sudo -u agroximtest python3 -m venv venv
sudo -u agroximtest venv/bin/pip install -r requirements.txt
sudo -u agroximtest cp .env.example .env
```

`.env` faylini to'ldiring (`nano .env`). Bu faylda barcha maxfiy kalitlar saqlanadi, u GitHub'ga yuklanmaydi.
`DJANGO_SECRET_KEY` uchun tasodifiy satr:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(50))"
```

Keyin:

```bash
chmod 600 .env
sudo -u agroximtest venv/bin/python manage.py migrate
sudo -u agroximtest venv/bin/python manage.py boshlangich
sudo -u agroximtest venv/bin/python manage.py collectstatic --noinput
sudo -u agroximtest venv/bin/python manage.py createsuperuser
```

`boshlangich` namuna turlari va narxnomani yuklaydi. Ishlab chiqarishda `--demo` ishlatilmaydi.
`createsuperuser` bilan yaratilgan foydalanuvchi — Super admin; qolgan xodimlarni u "Xodimlar" sahifasida qo'shadi.

## 4. Gunicorn va Nginx

```bash
cp deploy/agroximtest.service /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now agroximtest
cp deploy/nginx.conf /etc/nginx/sites-available/agroximtest
ln -s /etc/nginx/sites-available/agroximtest /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx
certbot --nginx -d agroximtest.uz -d www.agroximtest.uz
```

Domen DNS'ida `A` yozuvi server IP manziliga yo'naltirilgan bo'lishi kerak.

## 5. Telegram bot

1. Telegram'da **@BotFather** → `/newbot` → bot nomi va username (masalan `AgroximTestBot`).
2. BotFather bergan tokenni `.env` dagi `TELEGRAM_BOT_TOKEN` ga, username'ni `TELEGRAM_BOT_USERNAME` ga yozing.
   `TELEGRAM_WEBHOOK_SECRET` ga istalgan tasodifiy satr yozing.
3. `systemctl restart agroximtest`
4. Webhook'ni ulang (TOKEN va SECRET o'rniga o'z qiymatlaringiz):

```bash
curl "https://api.telegram.org/botTOKEN/setWebhook?url=https://agroximtest.uz/telegram/webhook/SECRET/"
```

Mijoz kabinetda **"Telegram'ni ulash"** tugmasini bosadi → botda **Start** → shundan keyin ariza, to'lov va tayyor
sinov bayonnomasi (PDF) Telegram'ga keladi.

## 6. Click (onlayn to'lov)

1. Click merchant kabinetiga kiring (merchant.click.uz) yoki Click qo'llab-quvvatlash xizmatiga murojaat qiling va
   **SHOP API** ulanishini so'rang.
2. Click'ga quyidagi manzillarni bering:
   - Prepare URL: `https://agroximtest.uz/click/prepare/`
   - Complete URL: `https://agroximtest.uz/click/complete/`
3. Click bergan `service_id`, `merchant_id`, `secret_key` (va `merchant_user_id`) ni `.env` ga yozing, keyin
   `systemctl restart agroximtest`.

Mijoz kabinetida shartnoma yonida **"Click orqali to'lash"** tugmasi paydo bo'ladi. To'lov shartnomaga avtomatik
yoziladi, buxgalteriya va laboratoriya darhol ko'radi. Statik QR orqali kelgan to'lovlarni buxgalter avvalgidek
qo'lda kiritadi.

## 7. SMS — Eskiz.uz

1. eskiz.uz saytida tashkilot nomidan ro'yxatdan o'ting va shartnoma tuzing, balansni to'ldiring.
2. Kabinetda jo'natuvchi nomini (masalan `AgroLab`) ro'yxatdan o'tkazing. Tasdiqlanguncha standart `4546` ishlaydi.
3. SMS matnlari Eskiz moderatsiyasidan o'tishi kerak — quyidagi shablonlarni yuboring (o'zgaruvchi qismlar `%w`
   bilan belgilangan; Eskiz boshqa belgi talab qilsa, ularni o'shanga almashtiring):
   - `Agrokimyo va tuproq tahlili markazi: %w raqamli arizangiz qabul qilindi, namunalar laboratoriyaga topshirildi.`
   - `Agrokimyo va tuproq tahlili markazi: %w raqamli arizangiz rad etildi. Sabab: %w`
   - `Agrokimyo va tuproq tahlili markazi: %w-sonli shartnoma tayyor. Summa: %w so'm. Tahlil kamida 30% to'lovdan keyin boshlanadi. Shartnoma va to'lov: kabinetingizda.`
   - `Agrokimyo va tuproq tahlili markazi: %w-sonli shartnoma bo'yicha %w so'm to'lov qabul qilindi. Jami to'langan: %w%.`
   - `Agrokimyo va tuproq tahlili markazi: %w raqamli sinov bayonnomasi tayyor. Kabinetingizdan yuklab olishingiz mumkin.`
4. Eskiz kabinetiga kirish email va parolini `.env` dagi `ESKIZ_EMAIL`, `ESKIZ_PASSWORD` ga, jo'natuvchi nomini
   `ESKIZ_FROM` ga yozing va `systemctl restart agroximtest`.

Kalitlar qo'yilmaguncha tizim ishlayveradi — xabarlar faqat admin paneldagi **"Xabarlar jurnali"** ga "Sozlanmagan"
deb yoziladi. Yuborilgan va xato bo'lgan barcha SMS/Telegram xabarlari ham shu jurnalda ko'rinadi.

## 8. Yangilash

Har safar GitHub'ga yangi versiya yuklanganda serverda bitta buyruq:

```bash
bash /srv/agroximtest/deploy/yangilash.sh
```

Skript avval bazaning zaxira nusxasini oladi (`/var/backups/agroximtest/`), keyin kodni yangilaydi va
platformani qayta ishga tushiradi. Oxirida `✅ Yangilandi` yozuvi chiqadi.

## 9. Zaxira nusxa (har kuni)

```bash
crontab -e
# qo'shing:
30 2 * * * pg_dump -U agroximtest agroximtest | gzip > /var/backups/agroximtest_$(date +\%F).sql.gz
40 2 * * * tar czf /var/backups/agroximtest_media_$(date +\%F).tgz -C /srv/agroximtest media
```

Yuklangan hujjatlar `media/` papkasida saqlanadi va faqat tizim orqali (ruxsat tekshirilib) beriladi.
