# LoveMatchID

A Telegram bot + web dashboard for light matchmaking and anonymous chat, running 24/7 via systemd.

## Main Features

- Profile onboarding: name, age, gender, description, location, photo.
- Matching and user-to-user chat.
- Send text messages and images (photo or document image).
- Moderation: report, block, temporary ban.
- Web dashboard: users, reports, match history, chat transcripts.
- Admin broadcast to all users.

## Project Structure

- bot: the Telegram bot application (handlers, services, repositories).
- templates: the web dashboard pages.
- tools/ops: operational utility scripts.
- tools/tests: test/manual test scripts.
- main.py: the bot entrypoint.
- dashboard_web.py: the dashboard entrypoint.
- docker-compose.yml: the MongoDB container.
- lovematchid-bot.service: the bot systemd unit.
- lovematchid-dashboard.service: the dashboard systemd unit.

## Prerequisites

- Linux server
- Python 3.12+
- MongoDB (container via Docker Compose)
- Telegram bot token

## Quick Setup

1. Create a virtual environment and install dependencies.

```bash
cd /home/romi/lovematchid
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Prepare the environment file.

```env
MONGODB_URI=mongodb://localhost:27017
TELEGRAM_TOKEN=bot_token
ADMIN_TELEGRAM_IDS=123456789
DASHBOARD_AUTH_USERNAME=admin_dashboard
DASHBOARD_AUTH_PASSWORD=change_to_strong_password
DASHBOARD_SESSION_SECRET=change_to_random_session_secret
DASHBOARD_HOST=0.0.0.0
DASHBOARD_PORT=8090
```

3. Run MongoDB.

```bash
docker compose -f /home/romi/lovematchid/docker-compose.yml up -d mongodb
```

4. Run the bot and dashboard manually.

```bash
source .venv/bin/activate
python main.py
```

```bash
source .venv/bin/activate
python dashboard_web.py
```

## Running via systemd

```bash
sudo cp /home/romi/lovematchid/lovematchid-bot.service /etc/systemd/system/
sudo cp /home/romi/lovematchid/lovematchid-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lovematchid-bot.service lovematchid-dashboard.service
```

Check status:

```bash
sudo systemctl status lovematchid-bot.service
sudo systemctl status lovematchid-dashboard.service
```

## Daily Operations

Restart services:

```bash
sudo systemctl restart lovematchid-bot.service
sudo systemctl restart lovematchid-dashboard.service
```

View logs:

```bash
sudo journalctl -u lovematchid-bot.service -f
sudo journalctl -u lovematchid-dashboard.service -f
```

## Announcement Broadcast

Use the script:

```bash
source .venv/bin/activate
python tools/ops/broadcast_update.py
```

Notes:

- The broadcast target uses all valid telegram_id values (int32 and int64).
- Forbidden failures are generally caused by the user blocking the bot or an inactive account.

## Additional Documentation

- Detailed admin guide: PANDUAN_ADMIN.md
- Change history: CHANGELOG.md
