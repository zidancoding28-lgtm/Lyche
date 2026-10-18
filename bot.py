# bot.py | DanzzBot v34 (Lite & Stable)
import os
import io
import requests
import logging
import string
import secrets
import re
import random
import hashlib
import base64
import urllib.parse
from datetime import datetime
from PIL import Image, ImageDraw
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

BOT_TOKEN = "8965097448:AAGM6xwbkjXPRwkb-9jd2fVCdA0p_pOluKM"
ADMIN_ID = 8901247073

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
user_sessions = {}

# ═══════════════════════════════════════════════════════════
# CORE
# ═══════════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Halo! Gue DanzzBot v34. Ketik /menu.")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🤖 AI Chat", callback_data='menu_ai'), InlineKeyboardButton("🛠️ Dev Tools", callback_data='menu_dev')],
        [InlineKeyboardButton("🌐 Network", callback_data='menu_net'), InlineKeyboardButton("🎲 Generator", callback_data='menu_gen')]
    ]
    await update.message.reply_text("Pilih tools:", reply_markup=InlineKeyboardMarkup(keyboard))

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'menu_ai': await query.edit_message_text("Ketik pesan bebas.")
    elif query.data == 'menu_dev': await query.edit_message_text("`/hash` | `/b64` | `/math` | `/time`")
    elif query.data == 'menu_net': await query.edit_message_text("`/ip` | `/short` | `/cuaca`")
    elif query.data == 'menu_gen': await query.edit_message_text("`/usn` | `/pass` | `/luhn`")

# ═══════════════════════════════════════════════════════════
# AI & DEV TOOLS
# ═══════════════════════════════════════════════════════════
async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args) if context.args else update.message.text
    msg = await update.message.reply_text("🤖 Mikir...")
    try:
        res = requests.get(f"https://text.pollinations.ai/{requests.utils.quote(prompt)}", timeout=15)
        await msg.edit_text(res.text)
    except: await msg.edit_text("❌ AI timeout.")

async def hash_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/hash [teks]`")
    text = " ".join(context.args)
    await update.message.reply_text(f"🔐 **MD5:** `{hashlib.md5(text.encode()).hexdigest()}`\n**SHA256:** `{hashlib.sha256(text.encode()).hexdigest()}`", parse_mode='Markdown')

async def b64_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2: return await update.message.reply_text("Format: `/b64 [encode/decode] [teks]`")
    try:
        res = base64.b64encode(" ".join(context.args[1:]).encode()).decode() if context.args[0] == "encode" else base64.b64decode(" ".join(context.args[1:]).encode()).decode()
        await update.message.reply_text(f"📦 `{res}`", parse_mode='Markdown')
    except: await update.message.reply_text("❌ Gagal.")

async def math_calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/math 5*5`")
    try:
        expr = " ".join(context.args).replace("x", "*").replace(":", "/")
        if not re.match(r"^[0-9+\-*/().\s]+$", expr): raise ValueError
        await update.message.reply_text(f"🧮 `{eval(expr)}`", parse_mode='Markdown')
    except: await update.message.reply_text("❌ Format salah.")

async def time_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏱️ Waktu server: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

# ═══════════════════════════════════════════════════════════
# NETWORK & GENERATORS
# ═══════════════════════════════════════════════════════════
async def ip_tracker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/ip 8.8.8.8`")
    msg = await update.message.reply_text("🌍 Cek IP...")
    try:
        res = requests.get(f"http://ip-api.com/json/{context.args[0]}", timeout=10).json()
        await msg.edit_text(f"📍 `{res['query']}`\nNegara: `{res['country']}`\nISP: `{res['isp']}`", parse_mode='Markdown')
    except: await msg.edit_text("❌ Gagal.")

async def shortlink(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/short [link]`")
    try:
        res = requests.get(f"https://is.gd/create.php?format=simple&url={requests.utils.quote(context.args[0])}", timeout=10)
        await update.message.reply_text(f"🔗 `{res.text}`", parse_mode='Markdown')
    except: await update.message.reply_text("❌ Gagal.")

async def weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/cuaca Jakarta`")
    try:
        res = requests.get(f"https://wttr.in/{context.args[0]}?format=j1", timeout=10).json()
        await update.message.reply_text(f"🌤️ Suhu: `{res['current_condition'][0]['temp_C']}°C`", parse_mode='Markdown')
    except: await update.message.reply_text("❌ Gagal.")

async def usn_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/usn nama`")
    base = context.args[0].lower()
    res = set()
    while len(res) < 5:
        res.add(f"{base}{random.choice(['01','99','666'])}")
    await update.message.reply_text("✨ " + ", ".join(res))

async def pass_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"🔑 `{''.join(secrets.choice(string.ascii_letters + string.digits) for i in range(16))}`", parse_mode='Markdown')

async def luhn_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/luhn [nomor]`")
    card = context.args[0].replace(" ", "")
    try:
        digits = [int(d) for d in card]
        checksum = sum(d if i % 2 != len(digits) % 2 else (d * 2 - 9 if d * 2 > 9 else d * 2) for i, d in enumerate(digits))
        await update.message.reply_text(f"💳 Status: **{'VALID' if checksum % 10 == 0 else 'INVALID'}**", parse_mode='Markdown')
    except: await update.message.reply_text("❌ Gagal.")

# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(menu_callback))
    
    app.add_handler(CommandHandler("ai", ai_chat))
    app.add_handler(CommandHandler("hash", hash_gen))
    app.add_handler(CommandHandler("b64", b64_tool))
    app.add_handler(CommandHandler("math", math_calc))
    app.add_handler(CommandHandler("time", time_conv))
    
    app.add_handler(CommandHandler("ip", ip_tracker))
    app.add_handler(CommandHandler("short", shortlink))
    app.add_handler(CommandHandler("cuaca", weather))
    
    app.add_handler(CommandHandler("usn", usn_gen))
    app.add_handler(CommandHandler("pass", pass_gen))
    app.add_handler(CommandHandler("luhn", luhn_check))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat))

    print("[@Cancer666] Bot v34 berjalan...")
    app.run_polling()

if __name__ == '__main__':
    main()
