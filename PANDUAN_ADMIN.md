# Panduan Admin LoveMatchID

Panduan ini untuk operasional admin bot di server lab (mode 24/7 via `systemd`).

## Update Maintenance (Mei 2026)

- File helper sekali pakai (`apply_css.py`, `apply_sidebar.py`, `update_layout.py`, `aktifkanlink.txt`) sudah dihapus dari root project.
- Dokumentasi utama proyek sekarang ada di `README.md`.
- Broadcast user mengambil semua `telegram_id` numerik valid (BSON `int` dan `long`) agar target tidak terpotong.

## 1) Cara Menjadi Admin

Bot mengenali admin lewat **Telegram ID**.

### Konfigurasi admin via Telegram ID (dari `.env`)
1. Buka file `.env`.
2. Tambahkan/ubah variabel:
   ```env
   ADMIN_TELEGRAM_IDS=123456789,987654321
   ```

### Terapkan perubahan
```bash
sudo systemctl restart lovematchid-bot.service
```

### Konfigurasi limit harian matching (opsional, via `.env`)
Tambahkan variabel ini kalau ingin ubah perilaku default:

```env
DAILY_PROFILE_VIEW_LIMIT=30
MATCH_RESET_TIMEZONE=Asia/Jakarta
ERROR_NOTICE_COOLDOWN_SECONDS=60
AUTO_REPORT_BAN_THRESHOLD=3
AUTO_REPORT_BAN_DAYS=3650
```

Keterangan:
- `DAILY_PROFILE_VIEW_LIMIT`: batas maksimal profil yang bisa dilihat user per hari.
- `MATCH_RESET_TIMEZONE`: timezone untuk reset harian (format IANA, contoh `Asia/Jakarta`).
- `ERROR_NOTICE_COOLDOWN_SECONDS`: jeda minimum agar pesan error generic tidak spam ke user.
- `AUTO_REPORT_BAN_THRESHOLD`: jumlah report disetujui untuk memicu auto-ban.
- `AUTO_REPORT_BAN_DAYS`: lama auto-ban (default `3650` hari).

### Verifikasi dari akun admin
- Kirim `/start` → harus langsung masuk dashboard admin.
- Kirim `/admin` → harus membuka panel admin.

> Catatan: username Telegram bisa berubah sewaktu-waktu, jadi sistem admin memakai Telegram ID sebagai sumber kebenaran.

---

## 2) Perintah Operasional Harian (Service 24/7)

### Cek status bot
```bash
sudo systemctl status lovematchid-bot.service
```

### Start / Stop / Restart
```bash
sudo systemctl start lovematchid-bot.service
sudo systemctl stop lovematchid-bot.service
sudo systemctl restart lovematchid-bot.service
```

### Cek apakah auto-start saat boot aktif
```bash
sudo systemctl is-enabled lovematchid-bot.service
```

### Lihat log bot (real-time)
```bash
sudo journalctl -u lovematchid-bot.service -f
```

---

## 3) Fitur Admin di Bot Telegram

Setelah kirim `/admin`, menu admin yang tersedia:

- **👥 List Users**: lihat daftar user terbaru.
- **📊 Stats**: statistik user (total, aktif/nonaktif, gender).
- **🚨 Reports**: lihat laporan keamanan terbaru dari user (blok/report).
- **🧾 Review Report**: setujui atau tolak laporan dengan format `approve <report_id>` / `reject <report_id>`.
- **⛔ Ban Sementara**: batasi user dengan format `telegram_id durasi_jam alasan`.
- **🔍 Find User**: cari user via ID MongoDB atau Telegram ID.
- **❌ Delete User**: hapus user berdasarkan ID MongoDB.

Update fitur user terbaru (Maret 2026):
- User baru melewati **kuis kompatibilitas 3 pertanyaan** saat onboarding.
- Saat melihat profil, user bisa **lanjut / blokir / report** profil.
- User punya **batas lihat profil harian** (default `30/hari`) dan otomatis **reset tiap hari** sesuai `MATCH_RESET_TIMEZONE`.
- Jika sebuah user mencapai **3 report yang disetujui admin**, sistem akan **auto-ban** user tersebut.

Khusus akun admin:
- `/start` langsung ke dashboard admin.
- Fitur profile user (buat/edit/cari teman) tidak aktif untuk admin.

---

## 4) Monitoring Database MongoDB

### Lihat database yang ada
```bash
docker exec mongodb_lovematch mongosh --quiet --eval 'db.adminCommand({ listDatabases: 1 }).databases.forEach(d => print(d.name))'
```

### Lihat ringkasan user (gender, age_group, aktif/nonaktif, ban)
```bash
docker exec mongodb_lovematch mongosh --quiet --eval 'const d=db.getSiblingDB("love_match"); print("=== User per Gender ==="); d.users.aggregate([{ $group:{ _id:"$gender", total:{ $sum:1 } } },{ $sort:{ total:-1 } }]).forEach(x=>print((x._id||"(tanpa gender)")+": "+x.total)); print("=== User per Age Group ==="); d.users.aggregate([{ $group:{ _id:"$age_group", total:{ $sum:1 } } },{ $sort:{ total:-1 } }]).forEach(x=>print((x._id||"(tanpa age_group)")+": "+x.total)); print("=== User Aktif vs Nonaktif ==="); print("Aktif: "+d.users.countDocuments({is_active:true})); print("Nonaktif: "+d.users.countDocuments({is_active:false})); print("=== User Sedang Ban ==="); print("Banned: "+d.users.countDocuments({ban_until:{$gt:new Date()}}));'
```

### Lihat 20 user terbaru
```bash
docker exec mongodb_lovematch mongosh --quiet --eval 'const d=db.getSiblingDB("love_match"); printjson(d.users.find({}, {name:1,username:1,gender:1,age_group:1,is_active:1,ban_until:1,created_at:1}).sort({created_at:-1}).limit(20).toArray())'
```

### Lihat 20 laporan terbaru
```bash
docker exec mongodb_lovematch mongosh --quiet --eval 'const d=db.getSiblingDB("love_match"); printjson(d.reports.find({}).sort({created_at:-1}).limit(20).toArray())'
```

### Lihat 20 riwayat seen profile terbaru
```bash
docker exec mongodb_lovematch mongosh --quiet --eval 'const d=db.getSiblingDB("love_match"); printjson(d.seen_profiles.find({}).sort({viewed_at:-1}).limit(20).toArray())'
```

---

## 5) Troubleshooting Cepat

### Akses `/admin` ditolak
- Pastikan Telegram ID ada di `ADMIN_TELEGRAM_IDS` pada `.env`.
- Restart service setelah ubah config admin.
- Pastikan akun yang dites benar-benar akun yang sama (ID sama).

### Bot tidak merespons
1. Cek status service:
   ```bash
   sudo systemctl status lovematchid-bot.service
   ```
2. Cek log:
   ```bash
   sudo journalctl -u lovematchid-bot.service -n 100 --no-pager
   ```
3. Restart:
   ```bash
   sudo systemctl restart lovematchid-bot.service
   ```

### MongoDB bermasalah
```bash
docker compose -f /home/romi/lovematchid/docker-compose.yml ps
docker compose -f /home/romi/lovematchid/docker-compose.yml up -d mongodb
```

---

## 6) Keamanan Dasar Admin

- Jangan share nilai `TELEGRAM_TOKEN` dan `MONGODB_URI` ke publik.
- Batasi jumlah admin seperlunya.
- Cek log berkala untuk aktivitas tidak biasa.
- Kalau token bocor, regenerate token bot dan update `.env`, lalu restart service.

---

## 7) Checklist Rutin (Disarankan)

Harian:
- Cek `systemctl status` bot.
- Cek log error singkat (`journalctl -n 100`).

Mingguan:
- Cek statistik user dari menu admin.
- Cek kapasitas data MongoDB.
- Lakukan backup database jika diperlukan.

---

## 8) Dashboard Versi Website

Dashboard website tersedia untuk monitoring cepat dengan fitur:
- Statistik ringkas.
- Daftar user terbaru.
- **Detail user** (klik tombol `Lihat Detail`).
- **Jawaban kuis kompatibilitas** di halaman detail user.
- **Koordinat ke Google Maps** (klik tombol `Buka Maps` / `Buka Lokasi`).
- Daftar report terbaru.
- **Review report** langsung dari dashboard: `Setujui` / `Tolak`.
- **Reset limit harian user** langsung dari dashboard.
- **Aksi massal user**: `Ban`, `Unban`, `Hapus` banyak user sekaligus (checkbox multi-select).

### Install dependency (sekali saja)
```bash
cd /home/romi/lovematchid
source .venv/bin/activate
pip install -r requirements.txt
```

### Jalankan dashboard
```bash
cd /home/romi/lovematchid
source .venv/bin/activate
python dashboard_web.py
```

Default akses: `http://localhost:8090`

### Jalankan 24/7 via systemd
```bash
sudo cp /home/romi/lovematchid/lovematchid-dashboard.service /etc/systemd/system/lovematchid-dashboard.service
sudo systemctl daemon-reload
sudo systemctl enable --now lovematchid-dashboard.service
sudo systemctl status lovematchid-dashboard.service
```

`lovematchid-dashboard.service` membaca credential login dashboard dari file `.env` (username/password wajib diisi).

### Akses publik (siapa pun yang punya link)
1. Pastikan service dashboard aktif (lihat langkah systemd di atas).
2. Buka port firewall server:
   ```bash
   sudo ufw allow 8090/tcp
   ```
3. Pakai IP publik server untuk link akses:
   ```bash
   curl -4 ifconfig.me
   ```
   Link contoh: `http://IP_PUBLIK_SERVER:8090`

> Kalau server ada di balik router/NAT, aktifkan port forwarding `8090` ke mesin ini.

### Auth login sederhana (username/password dari `.env`)
Tambahkan ke `.env`:
```env
DASHBOARD_AUTH_USERNAME=admin_dashboard
DASHBOARD_AUTH_PASSWORD=ganti_password_kuat
DASHBOARD_SESSION_SECRET=ganti_session_secret_acak
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8090
```

Keterangan:
- `DASHBOARD_AUTH_USERNAME`: username untuk halaman login dashboard (**wajib**).
- `DASHBOARD_AUTH_PASSWORD`: password untuk halaman login dashboard (**wajib**).
- `DASHBOARD_SESSION_SECRET`: secret untuk session login Flask (sangat disarankan isi nilai acak kuat di server produksi).

Setelah ubah `.env`, restart service:
```bash
sudo systemctl restart lovematchid-dashboard.service
```

### Cara pakai aksi massal user
1. Buka tabel **20 User Terbaru**.
2. Centang beberapa user (atau centang header untuk pilih semua yang terlihat).
3. Pilih aksi: `Ban massal`, `Unban massal`, atau `Hapus massal`.
4. Klik tombol **Terapkan ke User Terpilih**.

Catatan:
- Input `Durasi ban` dan `Alasan ban` dipakai saat aksi `Ban massal`.
- Aksi `Hapus massal` menampilkan konfirmasi sebelum submit.

---

## 9) Akses Publik Tanpa Port Forward (Cloudflare Tunnel)

Untuk akses publik yang stabil, gunakan **named tunnel** Cloudflare dengan subdomain tetap `lovematch.romitech.me`.

### Prasyarat
- Domain `romitech.me` sudah ada di akun Cloudflare Anda.
- Subdomain `lovematch.romitech.me` sudah diarahkan ke tunnel `47f2b9f8-50be-4b7f-a16a-2636a9d2e2b0`.
- File konfigurasi lokal ada di `/home/romi/.cloudflared/config.yml`.

Isi konfigurasi yang dipakai service:
```bash
cat /home/romi/.cloudflared/config.yml
```

Contoh isi yang benar:
```yaml
tunnel: 47f2b9f8-50be-4b7f-a16a-2636a9d2e2b0
credentials-file: /home/romi/.cloudflared/47f2b9f8-50be-4b7f-a16a-2636a9d2e2b0.json

ingress:
   - hostname: lovematch.romitech.me
      service: http://localhost:8090
   - hostname: romitech.me
      service: http://localhost:80
   - service: http_status:404
```

### Install service ke systemd
File service project:
- `lovematchid-cloudflared.service`

Install ke systemd:
```bash
sudo cp /home/romi/lovematchid/lovematchid-cloudflared.service /etc/systemd/system/lovematchid-cloudflared.service
sudo mkdir -p /etc/systemd/system/cloudflared.service.d
sudo tee /etc/systemd/system/cloudflared.service.d/override.conf >/dev/null <<'EOF'
[Service]
ExecStart=
ExecStart=/usr/bin/cloudflared --no-autoupdate --config /home/romi/.cloudflared/config.yml tunnel run
EOF
sudo systemctl disable --now lovematchid-cloudflared.service
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared.service
```

Cek status:
```bash
sudo systemctl status cloudflared.service
```

### Akses publik
Buka langsung:
- `https://lovematch.romitech.me`

### Catatan penting
- Mode ini memakai **named tunnel** dengan akun Cloudflare.
- Link tidak berubah saat service restart, selama DNS dan tunnel ID tetap sama.
- Pastikan tidak ada service quick tunnel lain yang bentrok.

### Verifikasi cepat
```bash
cloudflared tunnel info 47f2b9f8-50be-4b7f-a16a-2636a9d2e2b0
curl -I https://lovematch.romitech.me
```

### Opsional: Hilangkan warning `ping_group_range` & UDP buffer
Jika di log muncul warning seperti `ICMP proxy feature is disabled` atau
`failed to sufficiently increase receive buffer size`, jalankan:

```bash
sudo tee /etc/sysctl.d/99-cloudflared-tunnel.conf >/dev/null <<'EOF'
net.ipv4.ping_group_range = 0 2147483647
net.core.rmem_max = 8388608
net.core.rmem_default = 8388608
net.core.wmem_max = 8388608
net.core.wmem_default = 8388608
EOF

sudo sysctl --system
sudo systemctl restart lovematchid-cloudflared.service
```

Verifikasi:

```bash
sudo journalctl -u cloudflared.service -n 120 --no-pager | grep -Ei 'ping_group_range|ICMP proxy feature is disabled|failed to sufficiently increase receive buffer size'
```
