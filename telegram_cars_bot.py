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
    kb = [[InlineKeyboardButton(text=m, callback_data=f"model|{car_name}|{m}")] for m in models]
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

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data == "view_cart":
        await show_cart(query, context)
        return
    if data == "back_main":
        await query.message.edit_text("منو اصلی:", reply_markup=main_menu_keyboard())
        return
    if data.startswith("car|"):
        _, car_name = data.split("|", 1)
        await query.message.edit_text(f"مدل‌های " + car_name + ":", reply_markup=models_keyboard(car_name))
        return
    if data.startswith("model|"):
        _, car_name, model = data.split("|", 2)
        await query.message.edit_text(f"انتخاب برای {car_name} — {model}:", reply_markup=model_options_keyboard(car_name, model))
        return
    if data.startswith("tires_type|"):
        _, car_name, model, tire_type = data.split("|", 3)
        await query.message.edit_text(f"لاستیک {tire_type} — انتخاب سایز:", reply_markup=tires_size_keyboard(car_name, model, tire_type))
        return
    if data.startswith("part|"):
        _, car_name, model, part_key = data.split("|", 3)
        if part_key == "لایت‌بک":
            price = OTHER_PARTS_PRICES.get("لایت‌بک خارجی", 205)
            await query.message.edit_text(f"{part_key} — قیمت: {price} تومان", reply_markup=part_confirm_keyboard(car_name, model, "لایت‌بک خارجی", price))
            return
        price = OTHER_PARTS_PRICES.get(part_key, 100)
        await query.message.edit_text(f"{part_key} — قیمت: {price} تومان", reply_markup=part_confirm_keyboard(car_name, model, part_key, price))
        return
    if data.startswith("add_item|"):
        parts = data.split("|")
        if len(parts) < 6:
            await query.message.reply_text("دادهٔ محصول نامعتبر است.")
            return
        _, car_name, model, item_name, meta, price_str = parts
        price = int(price_str)
        item = {"car": car_name, "model": model, "name": item_name, "meta": meta, "price": price, "qty": 1}
        cart = get_cart(user_id)
        cart_items = cart.get("items", [])
        cart_items.append(item)
        cart["items"] = cart_items
        update_cart(user_id, cart)
        await query.message.reply_text(f"✅ '{item_name} ({meta})' به سبد اضافه شد — {price} تومان")
        return
    if data == "clear_cart":
        clear_cart(user_id)
        await query.message.reply_text("🗑️ سبد خرید پاک شد.")
        return
    if data == "checkout":
        await handle_checkout(query, context)
        return
    if data.startswith("back_models|"):
        _, car_name = data.split("|", 1)
        await query.message.edit_text(f"مدل‌های " + car_name + ":", reply_markup=models_keyboard(car_name))
        return
    if data.startswith("back_model_options|"):
        _, car_name, model = data.split("|", 2)
        await query.message.edit_text(f"انتخاب برای {car_name} — {model}:", reply_markup=model_options_keyboard(car_name, model))
        return

    await query.message.reply_text("عملیات نامعتبر یا منقضی شده. از منو استفاده کن.")

async def show_cart(query, context: ContextTypes.DEFAULT_TYPE):
    user_id = query.from_user.id
    cart = get_cart(user_id)
    items = cart.get("items", [])
    if not items:
        await query.message.edit_text("سبد خرید شما خالی است.", reply_markup=cart_keyboard(user_id))
        return
    lines = []
    total = 0
    for i, it in enumerate(items, 1):
        subtotal = it["price"] * it["qty"]
        total += subtotal
        lines.append(f"{i}. {it['car']} - {it['model']} - {it['name']} ({it['meta']}) ×{it['qty']} = {subtotal} تومان")
    lines.append(f"\nجمع کل: {total} تومان")
    await query.message.edit_text("\n".join(lines), reply_markup=cart_keyboard(user_id))

async def handle_checkout(query, context: ContextTypes.DEFAULT_TYPE):
    user = query.from_user
    user_id = user.id
    cart = get_cart(user_id)
    items = cart.get("items", [])
    if not items:
        await query.message.reply_text("سبد خرید خالی است.")
        return
    lines = [f"سفارش جدید از @{user.username if user.username else user.first_name} (id: {user_id})"]
    total = 0
    for i, it in enumerate(items, 1):
        subtotal = it["price"] * it["qty"]
        total += subtotal
        lines.append(f"{i}. {it['car']} - {it['model']} - {it['name']} ({it['meta']}) ×{it['qty']} = {subtotal} تومان")
    lines.append(f"\nجمع کل: {total} تومان")
    text = "\n".join(lines)
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID_INT, text=text)
    except Exception as e:
        logger.exception("Failed to send order to admin")
        await query.message.reply_text("خطا در ارسال سفارش. لطفا بعداً دوباره تلاش کن.")
        return
    clear_cart(user_id)
    await query.message.reply_text("✅ سفارش شما با موفقیت ارسال شد. ما به زودی با شما تماس می‌گیریم.")

async def cart_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cart = get_cart(user.id)
    items = cart.get("items", [])
    if not items:
        await update.message.reply_text("سبد خرید شما خالی است.")
        return
    lines = []
    total = 0
    for i, it in enumerate(items, 1):
        subtotal = it["price"] * it["qty"]
        total += subtotal
        lines.append(f"{i}. {it['car']} - {it['model']} - {it['name']} ({it['meta']}) ×{it['qty']} = {subtotal} تومان")
    lines.append(f"\nجمع کل: {total} تومان")
    await update.message.reply_text("\n".join(lines))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("از دکمه‌ها برای انتخاب ماشین، مدل و قطعه استفاده کن. /cart برای دیدن سبد، /start برای منو")

# --- Flask routes for Webhook ---
@app.route(f"/{BOT_TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot_app.bot)
    bot_app.dispatcher.process_update(update)
    return "OK"

@app.route("/")
def index():
    return "Telegram bot is running!"

# --- App start ---
bot_app = ApplicationBuilder().token(BOT_TOKEN).build()
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("cart", cart_command))
bot_app.add_handler(CommandHandler("help", help_command))
bot_app.add_handler(CallbackQueryHandler(callback_router))

if __name__ == "__main__":
    webhook_url = f"{WEBHOOK_URL}/{BOT_TOKEN}"
    logger.info(f"Setting webhook to: {webhook_url}")
    bot_app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=BOT_TOKEN,
        webhook_url=webhook_url
    )
