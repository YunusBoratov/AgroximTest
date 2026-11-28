#!/bin/bash
# Kunlik zaxira nusxa: ma'lumotlar bazasi + yuklangan hujjatlar (media).
# cron har kecha ishga tushiradi; qo'lda:  bash /srv/agroximtest/deploy/zaxira.sh
set -euo pipefail

DIR=/var/backups/agroximtest/kunlik
SAQLASH_KUN=14
SANA=$(date +%F_%H%M)
mkdir -p "$DIR"

# 1) Baza (avval vaqtinchalik faylga — yarim yozilgan nusxa qolmasin)
sudo -u postgres pg_dump agroximtest | gzip > "$DIR/.baza_$SANA.tmp"
gzip -t "$DIR/.baza_$SANA.tmp"
mv "$DIR/.baza_$SANA.tmp" "$DIR/baza_$SANA.sql.gz"

# 2) Yuklangan hujjatlar (arizalar fayllari)
if [ -d /srv/agroximtest/media ]; then
  tar czf "$DIR/.hujjatlar_$SANA.tmp" -C /srv/agroximtest media
  mv "$DIR/.hujjatlar_$SANA.tmp" "$DIR/hujjatlar_$SANA.tgz"
fi

# 3) Eski nusxalarni o'chirish (serverda oxirgi 14 kun saqlanadi; ofis kompyuterida — uzoqroq)
find "$DIR" -maxdepth 1 -type f \( -name 'baza_*' -o -name 'hujjatlar_*' \) -mtime +$SAQLASH_KUN -delete

# 4) Faqat "zaxira" foydalanuvchisi o'qiy olsin (ofis kompyuteri shu foydalanuvchi bilan oladi)
if getent group zaxira >/dev/null; then
  chgrp zaxira "$DIR" "$DIR"/baza_* "$DIR"/hujjatlar_* 2>/dev/null || true
  chmod 750 "$DIR"; chmod 640 "$DIR"/baza_* "$DIR"/hujjatlar_* 2>/dev/null || true
fi

echo "$(date '+%F %T') OK: baza_$SANA.sql.gz ($(du -h "$DIR/baza_$SANA.sql.gz" | cut -f1))"
