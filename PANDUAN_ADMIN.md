# Panduan Admin LoveMatchID

Panduan ini untuk operasional admin bot di server lab (mode 24/7 via `systemd`).

## 1) Cara Menjadi Admin

Bot mengenali admin lewat **username Telegram** dan/atau **Telegram ID**.

### Opsi A — Via Username (statis di code)
1. Buka file `bot/config.py`.
2. Cari bagian:
   ```python
   ADMIN_USERNAMES = ["rrscriptt", "romiscript"]
   ```
3. Tambahkan username lain (tanpa `@`, huruf kecil disarankan).

### Opsi B — Via Telegram ID (direkomendasikan, dari `.env`)
1. Buka file `.env`.
2. Tambahkan/ubah variabel:
   ```env
   ADMIN_TELEGRAM_IDS=123456789,987654321
   ```

### Terapkan perubahan
```bash
sudo systemctl restart lovematchid-bot.service
```

### Verifikasi dari akun admin
- Kirim `/start` → harus langsung masuk dashboard admin.
- Kirim `/admin` → harus membuka panel admin.

> Catatan: akun tanpa username tetap bisa jadi admin jika Telegram ID sudah terdaftar di `ADMIN_TELEGRAM_IDS`.

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
- **✅ Resolve Report**: tandai laporan selesai berdasarkan ID report.
- **⛔ Ban Sementara**: batasi user dengan format `telegram_id durasi_jam alasan`.
- **🔍 Find User**: cari user via ID MongoDB atau username.
- **❌ Delete User**: hapus user berdasarkan ID MongoDB.

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
- Pastikan username Telegram ada di `ADMIN_USERNAMES` di `bot/config.py`, atau
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
