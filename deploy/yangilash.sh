#!/bin/bash
# Platformani GitHub'dagi oxirgi versiyaga yangilash.
# Ishlatish (serverda root sifatida):  bash /srv/agroximtest/deploy/yangilash.sh
set -e
cd /srv/agroximtest

echo "1/5 Baza zaxira nusxasi..."
mkdir -p /var/backups/agroximtest
sudo -u postgres pg_dump agroximtest | gzip > "/var/backups/agroximtest/oldin_$(date +%F_%H%M).sql.gz"
ls -1t /var/backups/agroximtest/oldin_*.sql.gz | tail -n +21 | xargs -r rm --   # oxirgi 20 tasi saqlanadi

echo "2/5 Yangi kod..."
sudo -u agroximtest git pull --ff-only

echo "3/5 Kutubxonalar..."
sudo -u agroximtest venv/bin/pip install -q -r requirements.txt

echo "4/5 Baza va fayllar..."
sudo -u agroximtest venv/bin/python manage.py migrate --noinput
sudo -u agroximtest venv/bin/python manage.py collectstatic --noinput -v0

echo "5/5 Qayta ishga tushirish..."
systemctl restart agroximtest
sleep 2
systemctl is-active --quiet agroximtest && echo "✅ Yangilandi: $(sudo -u agroximtest git log -1 --format='%h  %s')" \
  || { echo "❌ Xizmat ishga tushmadi:"; journalctl -u agroximtest -n 30 --no-pager; exit 1; }
