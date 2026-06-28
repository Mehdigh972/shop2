# Free Fire Diamond Auto Top-up Bot

This bot runs on a Raspberry Pi (or similar Linux/macOS/Windows machines) and automates the verification of Free Fire player nicknames and redemption of top-up voucher PINs via Garena's official portals such as Shop2Game.

## Project Structure

- `bot.py`: Telegram bot state machine and commands.
- `garena_topup.py`: Garena / Shop2Game browser automation engine using Playwright.
- `api_server.py`: Local HTTP API for checking Free Fire player names from another bot/service.
- `config.json`: Telegram bot configuration.
- `config.env.example`: Helper API configuration template. Copy it to `config.env` locally.
- `scripts/install_helper.sh`: Raspberry Pi installer for the helper API systemd service.

## Helper API Quick Install on Raspberry Pi

Clone the repository and run the installer:

```bash
cd /home/mehdi
git clone https://github.com/Mehdigh972/shop2.git freefire_shop_helper
cd freefire_shop_helper
git checkout codex/helper-api-install
chmod +x scripts/install_helper.sh
./scripts/install_helper.sh
```

The installer creates `config.env`, generates `HELPER_API_KEY`, installs dependencies in `.venv`, and starts a systemd service on port `8088`.

Check the service:

```bash
systemctl status freefire-helper --no-pager
```

Read your local API key:

```bash
cd /home/mehdi/freefire_shop_helper
grep '^HELPER_API_KEY=' config.env
```

Local health test:

```bash
cd /home/mehdi/freefire_shop_helper
set -a
source config.env
set +a
curl -H "X-API-Key: $HELPER_API_KEY" http://127.0.0.1:8088/health
```

Player name check:

```bash
curl -X POST "http://127.0.0.1:8088/freefire/player/check" \
  -H "X-API-Key: $HELPER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"player_id":"6584595252"}'
```

For Keenetic/public access, forward your public helper hostname to Raspberry Pi port `8088`. Keep noVNC/browser/captcha on a separate hostname or port if possible.

## Helper API Endpoints

- `GET /health`
- `POST /freefire/player/check`

All endpoints require the `X-API-Key` header.

## Manual Configuration

If you do not use the installer:

```bash
cp config.env.example config.env
nano config.env
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn api_server:app --host 0.0.0.0 --port 8088
```

Important `config.env` values:

- `HELPER_API_KEY`: Generate with `openssl rand -hex 32`.
- `GARENA_DOMAIN`: Usually `shop2game.com`.
- `HEADLESS`: Use `1` on Raspberry Pi/server.
- `CHROMIUM_PATH`: Usually `/usr/bin/chromium-browser` or `/usr/bin/chromium` on Raspberry Pi.
- `NOVNC_URL`: Optional manual browser link returned when Shop2Game asks for verification/captcha.
- `USE_PLAYWRIGHT_STEALTH`: Default `0`; enable only if you confirm it helps.

Never commit `config.env`, Telegram tokens, API keys, or SSH passwords.

## Telegram Bot Setup

Edit `config.json`:

- Set `telegram_bot_token` to your Telegram Bot API token from @BotFather.
- Set `authorized_admin_ids` to Telegram user IDs allowed to access the bot.
- Set `garena_domain` to `shop2game.com` unless you intentionally use another Garena domain.
- Set `headless` to `true` for background browser operation.
- Set `chromium_executable_path` to the system Chromium path on Raspberry Pi.

Run the bot manually:

```bash
python3 bot.py
```

## How to Use the Telegram Bot

1. Send `/start` or `/topup` to the bot.
2. Send the Free Fire Card PIN/Voucher Code.
3. Send the customer's Free Fire Player ID (UID).
4. The bot launches a browser session, logs into Garena, retrieves the customer's in-game nickname, and asks for confirmation.
5. If confirmed, it enters the code, submits, and returns the Garena transaction result.
