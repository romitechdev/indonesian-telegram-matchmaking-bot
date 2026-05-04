# LoveMatchID

Telegram bot + dashboard web untuk matchmaking dan chat anonim ringan, dengan operasional 24/7 via systemd.

## Fitur Utama

- Onboarding profil: nama, umur, gender, deskripsi, lokasi, foto.
- Matching dan chat antarpengguna.
- Kirim pesan teks dan gambar (photo atau document image).
- Moderasi: report, block, temporary ban.
- Dashboard web: user, report, match history, chat transcript.
- Broadcast admin ke seluruh pengguna.

## Struktur Proyek

- bot: aplikasi bot Telegram (handler, service, repository).
- templates: halaman dashboard web.
- tools/ops: skrip utilitas operasional.
- tools/tests: skrip uji/manual test.
- main.py: entrypoint bot.
- dashboard_web.py: entrypoint dashboard.
- docker-compose.yml: MongoDB container.
- lovematchid-bot.service: unit systemd bot.
- lovematchid-dashboard.service: unit systemd dashboard.

## Prasyarat

- Linux server
- Python 3.12+
- MongoDB (container via Docker Compose)
- Token bot Telegram

## Setup Cepat

1. Buat virtual environment dan install dependency.

```bash
cd /home/romi/lovematchid
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Siapkan file environment.

```env
MONGODB_URI=mongodb://localhost:27017
TELEGRAM_TOKEN=isi_token_bot
ADMIN_TELEGRAM_IDS=123456789
DASHBOARD_AUTH_USERNAME=admin_dashboard
DASHBOARD_AUTH_PASSWORD=ganti_password_kuat
DASHBOARD_SESSION_SECRET=ganti_session_secret_acak
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8090
```

3. Jalankan MongoDB.

```bash
docker compose -f /home/romi/lovematchid/docker-compose.yml up -d mongodb
```

4. Jalankan bot dan dashboard manual.

```bash
source .venv/bin/activate
python main.py
```

```bash
source .venv/bin/activate
python dashboard_web.py
```

## Menjalankan via systemd

```bash
sudo cp /home/romi/lovematchid/lovematchid-bot.service /etc/systemd/system/
sudo cp /home/romi/lovematchid/lovematchid-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lovematchid-bot.service lovematchid-dashboard.service
```

Cek status:

```bash
sudo systemctl status lovematchid-bot.service
sudo systemctl status lovematchid-dashboard.service
```

## Operasional Harian

Restart layanan:

```bash
sudo systemctl restart lovematchid-bot.service
sudo systemctl restart lovematchid-dashboard.service
```

Lihat log:

```bash
sudo journalctl -u lovematchid-bot.service -f
sudo journalctl -u lovematchid-dashboard.service -f
```

## Broadcast Pengumuman

Gunakan skrip:

```bash
source .venv/bin/activate
python tools/ops/broadcast_update.py
```

Catatan:

- Target broadcast memakai seluruh telegram_id valid (int32 dan int64).
- Kegagalan Forbidden umumnya karena user memblokir bot atau akun tidak aktif.

## Dokumentasi Tambahan

- Panduan admin rinci: PANDUAN_ADMIN.md
- Riwayat perubahan: CHANGELOG.md
