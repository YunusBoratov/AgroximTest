#!/bin/bash
# Bir martalik sozlash (root): kunlik zaxira (har kecha 02:30) va ofis kompyuteri uchun "zaxira" foydalanuvchisi.
#   bash /srv/agroximtest/deploy/zaxira_sozlash.sh
set -euo pipefail

# Ofis kompyuteri faqat shu foydalanuvchi bilan va faqat kalit (parolsiz kirib bo'lmaydi) orqali ulanadi
if ! id zaxira >/dev/null 2>&1; then
  useradd -m -s /bin/bash zaxira
  passwd -l zaxira >/dev/null   # parol bilan kirish yopiq
fi
install -d -m 700 -o zaxira -g zaxira /home/zaxira/.ssh
touch /home/zaxira/.ssh/authorized_keys
chown zaxira:zaxira /home/zaxira/.ssh/authorized_keys
chmod 600 /home/zaxira/.ssh/authorized_keys

mkdir -p /var/backups/agroximtest/kunlik
chmod 755 /var/backups/agroximtest

cat > /etc/cron.d/agroximtest-zaxira <<'CRON'
# AgroximTest: har kecha 02:30 da zaxira nusxa
30 2 * * * root bash /srv/agroximtest/deploy/zaxira.sh >> /var/log/agroximtest-zaxira.log 2>&1
CRON
chmod 644 /etc/cron.d/agroximtest-zaxira

bash /srv/agroximtest/deploy/zaxira.sh
echo
echo "Tayyor. Zaxira har kecha 02:30 da olinadi: /var/backups/agroximtest/kunlik"
ls -lh /var/backups/agroximtest/kunlik
