# telegram_cars_bot.py
"""
Telegram Bot (Parts & Prices)
- python-telegram-bot v20
- Webhook ready for Render
- Inline keyboard Persian
- Cart stored locally (carts.json)
- Admin receives order
"""

import os
import json
import logging
from typing import Dict, Any
from flask import Flask, request

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    Dispatcher,
)

# --- CONFIG ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_CHAT_ID = os.environ.get("ADMIN_CHAT_ID")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
PORT = int(os.environ.get("PORT", 5000))

if not BOT_TOKEN or not ADMIN_CHAT_ID or not WEBHOOK_URL:
    raise RuntimeError("Please set BOT_TOKEN, ADMIN_CHAT_ID, WEBHOOK_URL env variables")

ADMIN_CHAT_ID_INT = int(ADMIN_CHAT_ID)

# --- Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Flask app for Webhook ---
app = Flask(__name__)

# --- Data & Utilities ---
CARTS_FILE = "carts.json"
CARS = {
    "پراید": ["111", "131", "141"],
    "پژو": ["405", "پارس", "207"],
    "سمند": ["سورن", "سورن پلاس"],
}
TIRES_PRICES = {"خارجی": {"185": 185, "195": 195, "205": 205}, "داخلی": {"185": 185, "195": 195, "205": 205}}
OTHER_PARTS_PRICES = {"لایت‌بک خارجی": 205, "آینه بغل": 120, "شیشه جلو": 250, "شیشه عقب": 200}

def load_carts() -> Dict[str, Any]:
    if not os.path.exists(CARTS_FILE):
        return {}
    try:
        with open(CARTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_carts(carts: Dict[str, Any]):
    with open(CARTS_FILE, "w", encoding="utf-8") as f:
        json.dump(carts, f, ensure_ascii=False, indent=2)

def get_cart(user_id: int) -> Dict[str, Any]:
    carts = load_carts()
    key = str(user_id)
    if key not in carts:
        carts[key] = {"items": []}
        save_carts(carts)
    return carts[key]

def update_cart(user_id: int, cart: Dict[str, Any]):
    carts = load_carts()
    carts[str(user_id)] = cart
    save_carts(carts)

def clear_cart(user_id: int):
    carts = load_carts()
    carts.pop(str(user_id), None)
    save_carts(carts)

# --- Keyboards ---
def main_menu_keyboard():
    buttons = [InlineKeyboardButton(text=car, callback_data=f"car|{car}") for car in CARS.keys()]
    buttons.append(InlineKeyboardButton(text="🧾 سبد خرید", callback_data="view_cart"))
    kb = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(kb)

def models_keyboard(car_name: str):
    models = CARS.get(car_name, [])
    kb = []
    for m in models:
        kb.append([InlineKeyboardButton(text=m, callback_data=f"model|{car_name}|{m}")])
    kb.append([InlineKeyboardButton(text="🔙 برگشت", callback_data="back_main")])
    kb.append([InlineKeyboardButton(text="🧾 سبد خرید", callback_data="view_cart")])
    return InlineKeyboardMarkup(kb)

def model_options_keyboard(car_name: str, model: str):
    kb = [
        [InlineKeyboardButton(text="لاستیک خارجی", callback_data=f"tires_type|{car_name}|{model}|خارجی")],
        [InlineKeyboardButton(text="لاستیک داخلی", callback_data=f"tires_type|{car_name}|{model}|داخلی")],
        [InlineKeyboardButton(text="لایت‌بک", callback_data=f"part|{car_name}|{model}|لایت‌بک")],
        [InlineKeyboardButton(text="آینه بغل", callback_data=f"part|{car_name}|{model}|آینه بغل")],
        [InlineKeyboardButton(text="شیشه جلو", callback_data=f"part|{car_name}|{model}|شیشه جلو")],
        [InlineKeyboardButton(text="شیشه عقب", callback_data=f"part|{car_name}|{model}|شیشه عقب")],
        [InlineKeyboardButton(text="🔙 برگشت", callback_data=f"back_models|{car_name}")],
        [InlineKeyboardButton(text="🏠 منو اصلی", callback_data="back_main")],
        [InlineKeyboardButton(text="🧾 سبد خرید", callback_data="view_cart")]
    ]
    return InlineKeyboardMarkup(kb)

def tires_size_keyboard(car_name: str, model: str, tire_type: str):
    kb = []
    prices = TIRES_PRICES.get(tire_type, {})
    for size, price in prices.items():
        cb = f"add_item|{car_name}|{model}|لاستیک {tire_type}|{size}|{price}"
        kb.append([InlineKeyboardButton(text=f"{size} — {price} تومان", callback_data=cb)])
    kb.append([InlineKeyboardButton(text="🔙 برگشت", callback_data=f"back_model_options|{car_name}|{model}")])
    kb.append([InlineKeyboardButton(text="🧾 سبد خرید", callback_data="view_cart")])
    return InlineKeyboardMarkup(kb)

def part_confirm_keyboard(car_name: str, model: str, part_name: str, price: int):
    cb_add = f"add_item|{car_name}|{model}|{part_name}|1|{price}"
    kb = [
        [InlineKeyboardButton(text=f"اضافه به سبد — {price} تومان", callback_data=cb_add)],
        [InlineKeyboardButton(text="🔙 برگشت", callback_data=f"back_model_options|{car_name}|{model}")],
        [InlineKeyboardButton(text="🧾 سبد خرید", callback_data="view_cart")]
    ]
    return InlineKeyboardMarkup(kb)

def cart_keyboard(user_id: int):
    kb = []
    cart = get_cart(user_id)
    if cart.get("items"):
        kb.append([InlineKeyboardButton(text="ثبت سفارش و ارسال به ادمین", callback_data="checkout")])
        kb.append([InlineKeyboardButton(text="پاک کردن سبد", callback_data="clear_cart")])
    kb.append([InlineKeyboardButton(text="🏠 منو اصلی", callback_data="back_main")])
    return InlineKeyboardMarkup(kb)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = f"سلام {user.first_name}!\nبه ربات فروش قطعات خودرو خوش اومدی.\nیکی از برندها رو انتخاب کن:" 
    await update.message.reply_text(text, reply_markup=main_menu_keyboard())

# === اینجا تمام هندلرهای قبلی callback_router, show_cart, handle_checkout, cart_command, help_command را همانند نسخه قبلی اضافه کنید ===

# --- Flask routes for Webhook ---
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    """Receive updates from Telegram and process them"""
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    bot_app.dispatcher.process_update(update)
    return "OK"

@app.route("/")
def index():
    """Simple page for pings"""
    return "Telegram bot is running!"

# --- App start ---
bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("cart", cart_command))
bot_app.add_handler(CommandHandler("help", help_command))
bot_app.add_handler(CallbackQueryHandler(callback_router))

if __name__ == "__main__":
    # Set webhook
    webhook_url = f"{WEBHOOK_URL}/{BOT_TOKEN}"
    logger.info(f"Setting webhook to: {webhook_url}")
    bot_app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=webhook_url
    )
