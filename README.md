# Free Fire Diamond Auto Top-up Bot

This bot runs on a Raspberry Pi (or similar Linux/macOS/Windows machines) and automates the verification of Free Fire player nicknames and redemption of top-up voucher PINs via Garena's official portals (e.g., Shop2Game).

## Project Structure
- `bot.py`: Telegram Bot state machine and commands.
- `garena_topup.py`: Garena browser automation engine using Playwright.
- `config.json`: Configuration for bot token, admin IDs, and paths.

## Setup Instructions

### 1. Installation on Raspberry Pi (ARM)

Because Raspberry Pi has an ARM processor, standard Playwright browser downloads might not run correctly. We use the system's pre-compiled Chromium instead:

```bash
# Update system packages
sudo apt update

# Install Chromium and virtual framebuffer (for headless operations)
sudo apt install -y python3-pip chromium-browser chromium-codecs-ffmpeg xvfb

# Clone/copy this project to your Raspberry Pi, and install Python requirements
pip3 install -r requirements.txt
```

### 2. Configure the Bot

Edit `config.json`:
- Set `telegram_bot_token` to your Telegram Bot API token (obtained from @BotFather).
- Set `authorized_admin_ids` to a list of Telegram User IDs allowed to access the bot (e.g., `[54321098]`). Find your User ID using @userinfobot on Telegram.
- Set `garena_domain` to `shop2game.com` (default) or `shop.garena.sg`.
- Set `headless` to `true` (runs browser in background).
- Set `chromium_executable_path` to `/usr/bin/chromium-browser` (this tells Playwright to use the Raspberry Pi's system Chromium). On macOS or Windows, leave it empty `""` to let Playwright download its own browser.

### 3. Run the Bot

Start the bot with:
```bash
python3 bot.py
```

To run it in the background on your Raspberry Pi so it keeps running after you close the terminal, use `nohup` or `screen`:
```bash
nohup python3 bot.py > bot.log 2>&1 &
```

## How to Use the Bot

1. Send `/start` or `/topup` to the bot.
2. The bot will ask for the **Free Fire Card PIN/Voucher Code**. Send the code.
3. The bot will then ask for the customer's **Free Fire Player ID (UID)**. Send the Player ID.
4. The bot launches a stealth browser session, logs into Garena, retrieves the customer's **In-Game Nickname**, and presents it with options:
   - `✅ Confirm`: Proceed with top-up.
   - `❌ Cancel`: Cancel and abort.
5. If you confirm, it enters the code, submits, and returns the Garena transaction result.
