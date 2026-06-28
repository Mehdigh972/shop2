import os
import json
import logging
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from garena_topup import GarenaTopupSession

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')

def load_config():
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Configuration file not found at {CONFIG_PATH}. Please create it based on the template.")
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)

config = load_config()
BOT_TOKEN = config.get('telegram_bot_token')
AUTHORIZED_ADMINS = config.get('authorized_admin_ids', [])
GARENA_DOMAIN = config.get('garena_domain', 'shop2game.com')
HEADLESS = config.get('headless', True)
CHROMIUM_PATH = config.get('chromium_executable_path', '')

if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
    logging.error("Invalid Telegram bot token in config.json. Please update the configuration.")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)

# States:
# WAIT_VOUCHER: Waiting for voucher PIN
# WAIT_UID: Waiting for customer player ID
# WAIT_CONFIRM: Waiting for confirmation (Inline Keyboard)
user_states = {}

def get_user_state(chat_id):
    if chat_id not in user_states:
        user_states[chat_id] = {
            'step': None,
            'voucher_code': None,
            'player_id': None,
            'nickname': None,
            'session': None
        }
    return user_states[chat_id]

def clear_user_state(chat_id):
    state = user_states.get(chat_id)
    if state:
        session = state.get('session')
        if session:
            try:
                session.close()
            except Exception as e:
                logging.error(f"Error closing session during state clear: {e}")
        user_states[chat_id] = {
            'step': None,
            'voucher_code': None,
            'player_id': None,
            'nickname': None,
            'session': None
        }

def is_authorized(message):
    user_id = message.from_user.id
    if user_id in AUTHORIZED_ADMINS:
        return True
    bot.reply_to(message, "❌ دسترسی غیرمجاز! شما اجازه استفاده از این ربات را ندارید.")
    return False

@bot.message_handler(commands=['start', 'topup', 'cancel'])
def handle_commands(message):
    if not is_authorized(message):
        return
        
    chat_id = message.chat.id
    command = message.text.split()[0].lower()

    if command == '/cancel':
        clear_user_state(chat_id)
        bot.send_message(chat_id, "🔄 عملیات لغو شد. می‌توانید فرآیند جدیدی را آغاز کنید.")
        return

    # Start new top-up process
    clear_user_state(chat_id)
    state = get_user_state(chat_id)
    state['step'] = 'WAIT_UID'
    
    bot.send_message(chat_id, "👋 سلام همکار گرامی! به ربات شارژ جم خوش آمدید.\n\n🆔 لطفا **شناسه عددی (UID) مشتری** را وارد کنید:")

@bot.message_handler(func=lambda message: True)
def handle_text_messages(message):
    if not is_authorized(message):
        return

    chat_id = message.chat.id
    text = message.text.strip()
    state = get_user_state(chat_id)

    if state['step'] == 'WAIT_UID':
        if not text.isdigit():
            bot.send_message(chat_id, "❌ شناسه بازیکن باید فقط شامل عدد باشد. لطفا مجددا وارد کنید:")
            return

        state['player_id'] = text
        bot.send_message(chat_id, "⏳ در حال برقراری ارتباط با گارنا و استخراج نام کاربری... لطفا صبور باشید.")

        try:
            # Initialize and start Garena Session
            session = GarenaTopupSession(
                domain=GARENA_DOMAIN,
                headless=HEADLESS,
                executable_path=CHROMIUM_PATH if CHROMIUM_PATH else None
            )
            state['session'] = session
            session.start()

            # Attempt to login and fetch nickname
            nickname = session.login_player(state['player_id'])
            state['nickname'] = nickname
            state['step'] = 'WAIT_VOUCHER'

            # Ask user for voucher pin code
            prompt_msg = (
                f"👤 نام بازیکن: `{nickname}`\n"
                f"🆔 شناسه بازیکن: `{state['player_id']}`\n\n"
                f"🎟 لطفا **کد کارت/پین گیفت کارت فری فایر** را برای شارژ ارسال کنید:\n"
                f"(یا برای انصراف دستور /cancel را ارسال کنید)"
            )
            bot.send_message(chat_id, prompt_msg, parse_mode="Markdown")

        except Exception as e:
            logging.error(f"Error verifying player ID: {e}")
            bot.send_message(chat_id, f"❌ خطا در فرآیند ورود/استخراج نام کاربری:\n`{str(e)}`", parse_mode="Markdown")
            clear_user_state(chat_id)

    elif state['step'] == 'WAIT_VOUCHER':
        if not text:
            bot.send_message(chat_id, "❌ کد ارسال شده معتبر نیست. لطفا مجددا تلاش کنید:")
            return
            
        state['voucher_code'] = text
        bot.send_message(chat_id, "⚡️ در حال ثبت کد کارت در گارنا... لطفا شکیبا باشید. این فرآیند ممکن است تا ۳۰ ثانیه طول بکشد.")

        session = state['session']
        voucher_code = state['voucher_code']

        try:
            # Perform redemption
            result = session.redeem_voucher(voucher_code)

            if result['success']:
                bot.send_message(
                    chat_id,
                    f"🎉 **شارژ با موفقیت انجام شد!**\n\n"
                    f"👤 نام بازیکن: `{state['nickname']}`\n"
                    f"🆔 شناسه بازیکن: `{state['player_id']}`\n"
                    f"🟢 نتیجه: {result['message']}",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(
                    chat_id,
                    f"🔴 **شارژ ناموفق بود!**\n\n"
                    f"👤 نام بازیکن: `{state['nickname']}`\n"
                    f"🆔 شناسه بازیکن: `{state['player_id']}`\n"
                    f"❌ علت شکست: {result['message']}",
                    parse_mode="Markdown"
                )

            # Send transaction screenshot to the admin for reference
            screenshot_path = result.get('screenshot')
            if screenshot_path and os.path.exists(screenshot_path):
                with open(screenshot_path, 'rb') as photo:
                    bot.send_photo(chat_id, photo, caption="📸 اسکرین‌شات از صفحه تراکنش گارنا")
                try:
                    os.remove(screenshot_path)  # Cleanup local screenshot
                except Exception as ex:
                    logging.warning(f"Failed to delete screenshot file: {ex}")

        except Exception as e:
            logging.error(f"Error during voucher redemption: {e}")
            bot.send_message(chat_id, f"❌ خطای غیرمنتظره در ثبت پین:\n`{str(e)}`", parse_mode="Markdown")

        finally:
            # Clean up browser session and reset user state
            clear_user_state(chat_id)

    else:
        bot.send_message(chat_id, "💡 برای شروع فرآیند جدید دستور /topup یا /start را ارسال کنید.")

if __name__ == '__main__':
    logging.info("Starting Telegram Bot listener...")
    bot.infinity_polling()
