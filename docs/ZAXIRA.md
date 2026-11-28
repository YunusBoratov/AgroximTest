# Zaxira nusxalar

## Qanday ishlaydi
1. **Serverda** har kecha 02:30 da `deploy/zaxira.sh` ma'lumotlar bazasi (`baza_*.sql.gz`) va yuklangan hujjatlar
   (`hujjatlar_*.tgz`) nusxasini `/var/backups/agroximtest/kunlik` ga yozadi. Serverda 14 kun saqlanadi.
   Jurnal: `/var/log/agroximtest-zaxira.log`.
2. **Ofis kompyuteri** (Windows) har kuni va yoqilganda `zaxira_olish.ps1` bilan yangi nusxalarni
   `C:\AgroximZaxira\nusxalar` ga ko'chirib oladi (90 kun saqlanadi). Jurnal: `C:\AgroximZaxira\jurnal.txt`.
   Ulanish faqat kalit orqali, `zaxira` foydalanuvchisi bilan; u faqat nusxalarni o'qiy oladi.

## Bir martalik sozlash (server)
```bash
bash /srv/agroximtest/deploy/zaxira_sozlash.sh
```

## Tiklash (server buzilsa yoki ma'lumot yo'qolsa)
Yangi serverda platforma `docs/SERVERGA_ORNATISH.md` bo'yicha o'rnatilgach (bo'sh baza bilan):
```bash
systemctl stop agroximtest
sudo -u postgres dropdb agroximtest && sudo -u postgres createdb -O agroximtest agroximtest
gunzip -c baza_SANA.sql.gz | sudo -u postgres psql agroximtest
tar xzf hujjatlar_SANA.tgz -C /srv/agroximtest && chown -R agroximtest:www-data /srv/agroximtest/media
systemctl start agroximtest
```
`.env` faylini (kalitlar) alohida, xavfsiz joyda saqlang — u zaxiraga kiritilmaydi.

## Tekshirish (oyiga bir marta)
- `C:\AgroximZaxira\jurnal.txt` da har kuni `OK` yozuvi bormi.
- Eng oxirgi `baza_*.sql.gz` faylining hajmi oldingilaridan keskin kichik emasmi.
