# AgroximTest: serverdagi kunlik zaxira nusxalarni ofis kompyuteriga ko'chirish.
# Windows "Task Scheduler" har kuni va kompyuter yoqilganda ishga tushiradi.
# Faqat yangi fayllar olinadi; ofisda oxirgi 90 kunlik nusxa saqlanadi.

$Server  = "194.107.115.203"
$Kalit   = "$env:USERPROFILE\.ssh\agroximzaxira"
$Papka   = "C:\AgroximZaxira\nusxalar"
$Jurnal  = "C:\AgroximZaxira\jurnal.txt"
$Masofa  = "/var/backups/agroximtest/kunlik"
$SaqlashKun = 90

New-Item -ItemType Directory -Force -Path $Papka | Out-Null
function Yoz($matn) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $matn" | Add-Content -Path $Jurnal -Encoding UTF8 }

$ssh = @("-i", $Kalit, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=20")
$royxat = & ssh @ssh "zaxira@$Server" "ls -1 $Masofa" 2>&1
if ($LASTEXITCODE -ne 0) { Yoz "XATO: serverga ulanib bo'lmadi: $royxat"; exit 1 }

$yangi = 0
foreach ($f in $royxat) {
  $f = "$f".Trim()
  if (-not ($f -match '^(baza|hujjatlar)_[0-9_-]+\.(sql\.gz|tgz)$')) { continue }
  $manzil = Join-Path $Papka $f
  if (Test-Path $manzil) { continue }
  & scp @ssh "zaxira@${Server}:$Masofa/$f" "$manzil.tmp" 2>&1 | Out-Null
  if ($LASTEXITCODE -eq 0) { Move-Item -Force "$manzil.tmp" $manzil; $yangi++ }
  else { Remove-Item -ErrorAction SilentlyContinue "$manzil.tmp"; Yoz "XATO: $f yuklanmadi" }
}

Get-ChildItem $Papka -File | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$SaqlashKun) } | Remove-Item
$jami = (Get-ChildItem $Papka -File | Measure-Object -Property Length -Sum)
Yoz ("OK: {0} ta yangi fayl. Jami {1} ta fayl, {2:N0} MB" -f $yangi, $jami.Count, ($jami.Sum / 1MB))
