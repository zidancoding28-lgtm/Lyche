# bot.py — Bot Telegram Pribadi (V1 - Termux)
import os
import re
import sqlite3
import random
import time
import datetime
import telebot
import yt_dlp
from telebot import types
from pathlib import Path

# --- PENGATURAN BOT ---
BOT_TOKEN = "ISI_TOKEN_BOTFATHER_LO"
OWNER_ID = 123456789  # Ganti pakai ID lo (dari @userinfobot)

DOWNLOAD_DIR = Path("./downloads")
MAX_FILESIZE_MB = 50
URL_RE = re.compile(r"https?://\S+")

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

bot = telebot.TeleBot(BOT_TOKEN)

# --- DATABASE (SQLite) ---
DB_PATH = "bot_data.db"
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT, joined_at TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS quotes (id INTEGER PRIMARY KEY AUTOINCREMENT, text TEXT)''')
    # Isi quote default kalau kosong
    c.execute('SELECT COUNT(*) FROM quotes')
    if c.fetchone()[0] == 0:
        default_quotes = [
            "yang diam lebih berbahaya dari yang bicara.",
            "kekuatan sejati tidak butuh penonton.",
            "kegagalan adalah data, bukan identitas.",
            "satu langkah benar lebih berharga dari seribu rencana indah."
        ]
        for q in default_quotes:
            c.execute('INSERT INTO quotes (text) VALUES (?)', (q,))
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (id, username, joined_at) VALUES (?, ?, ?)', 
              (user_id, username, datetime.datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_random_quote():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT text FROM quotes ORDER BY RANDOM() LIMIT 1')
    res = c.fetchone()
    conn.close()
    return res[0] if res else "belum ada kata-kata."

# --- MENU INLINE ---
def main_menu():
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_dl = types.InlineKeyboardButton("🎬 Download", callback_data="menu_dl")
    btn_anim = types.InlineKeyboardButton("✨ Animasi", callback_data="menu_anim")
    btn_quote = types.InlineKeyboardButton("💬 Kata-kata", callback_data="menu_quote")
    btn_sys = types.InlineKeyboardButton("📊 Sistem", callback_data="menu_sys")
    markup.add(btn_dl, btn_anim, btn_quote, btn_sys)
    return markup

def back_menu():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("⬅️ Kembali ke Menu", callback_data="menu_main"))
    return markup

# --- HANDLER PERINTAH DASAR ---
@bot.message_handler(commands=['start', 'menu'])
def send_welcome(message):
    add_user(message.from_user.id, message.from_user.username)
    
    # Cek apakah yang chat adalah owner (opsional)
    # if message.from_user.id != OWNER_ID: return bot.reply_to(message, "Akses ditolak.")
    
    text = f"*Halo {message.from_user.first_name}!*\nID lo: `{message.from_user.id}`\n\nSilakan pilih menu di bawah:"
    bot.send_message(message.chat.id, text, parse_mode='Markdown', reply_markup=main_menu())

@bot.message_handler(commands=['help'])
def send_help(message):
    text = (
        "*Perintah Tersedia:*\n"
        "/start /menu — Tampilkan menu\n"
        "/quote — Kata-kata random\n"
        "/sysinfo — Info server bot\n"
        "/ping — Cek latency\n\n"
        "*Download:*\n"
        "Kirim link video/audio langsung ke chat, atau ketik `/dl <url>`."
    )
    bot.reply_to(message, text, parse_mode='Markdown')

# --- HANDLER CALLBACK (TOMBOL MENU) ---
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "menu_main":
        bot.edit_message_text("Silakan pilih menu:", call.message.chat.id, call.message.message_id, reply_markup=main_menu())
    
    elif call.data == "menu_dl":
        text = "*Menu Download*\nKirim link langsung ke chat, atau ketik:\n`/dl <url>`"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=back_menu())
    
    elif call.data == "menu_anim":
        # Animasi loading
        msg = bot.edit_message_text("⠋ Memproses...", call.message.chat.id, call.message.message_id)
        spinners = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
        for i in range(5):
            for spin in spinners:
                bot.edit_message_text(f"{spin} Memproses...", call.message.chat.id, msg.message_id)
                time.sleep(0.2)
        bot.edit_message_text("✔ Selesai!", call.message.chat.id, msg.message_id, reply_markup=back_menu())
    
    elif call.data == "menu_quote":
        q = get_random_quote()
        bot.edit_message_text(f"_{q}_", call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=back_menu())
    
    elif call.data == "menu_sys":
        text = "*Sistem Bot*\nStatus: Online\nServer: Termux (Android)"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=back_menu())

# --- DOWNLOADER (YT-DLP) ---
def progress_hook(d, chat_id, msg_id):
    if d['status'] == 'downloading':
        try:
            p = d.get('_percent_str', '0%').strip()
            speed = d.get('_speed_str', 'N/A').strip()
            bot.edit_message_text(f"📥 Mengunduh... {p} (Kecepatan: {speed})", chat_id, msg_id)
        except:
            pass
    elif d['status'] == 'finished':
        bot.edit_message_text("⚙️ Memproses file...", chat_id, msg_id)

def process_download(message, url, mode="video"):
    chat_id = message.chat.id
    msg = bot.reply_to(message, "🔍 Menganalisa link...")
    
    outtmpl = str(DOWNLOAD_DIR / f"%(title)s_{int(time.time())}.%(ext)s")
    
    if mode == "audio":
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': outtmpl,
            'postprocessors': [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'}],
            'progress_hooks': [lambda d: progress_hook(d, chat_id, msg.message_id)],
            'quiet': True,
            'noplaylist': True
        }
    else:
        ydl_opts = {
            'format': 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
            'outtmpl': outtmpl,
            'progress_hooks': [lambda d: progress_hook(d, chat_id, msg.message_id)],
            'quiet': True,
            'noplaylist': True
        }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
            
            # YT-DLP kadang mengubah ekstensi (misal .webm jadi .mp3 atau .mp4)
            if mode == "audio":
                filepath = str(Path(filepath).with_suffix('.mp3'))
            else:
                filepath = str(Path(filepath).with_suffix('.mp4'))
                
            if not os.path.exists(filepath):
                # Cari file terbaru di folder kalau nama beda
                files = sorted(DOWNLOAD_DIR.glob("*"), key=os.path.getmtime, reverse=True)
                if files: filepath = str(files[0])

        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        if size_mb > MAX_FILESIZE_MB:
            bot.edit_message_text(f"❌ File terlalu besar ({size_mb:.1f} MB). Limit Telegram 50 MB.", chat_id, msg.message_id)
            os.remove(filepath)
            return

        bot.edit_message_text("📤 Mengirim file...", chat_id, msg.message_id)
        
        with open(filepath, 'rb') as f:
            if mode == "audio":
                bot.send_audio(chat_id, f, title=os.path.basename(filepath))
            else:
                bot.send_video(chat_id, f, supports_streaming=True)
                
        bot.delete_message(chat_id, msg.message_id)
        
    except Exception as e:
        bot.edit_message_text(f"❌ Gagal: {str(e)[:100]}", chat_id, msg.message_id)
    finally:
        if 'filepath' in locals() and os.path.exists(filepath):
            os.remove(filepath)

@bot.message_handler(commands=['dl'])
def cmd_dl(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return bot.reply_to(message, "Pakai: `/dl <url>`", parse_mode='Markdown')
    process_download(message, args[1].strip(), mode="video")

@bot.message_handler(commands=['dla'])
def cmd_dla(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        return bot.reply_to(message, "Pakai: `/dla <url>`", parse_mode='Markdown')
    process_download(message, args[1].strip(), mode="audio")

# --- HANDLER PESAN LINK OTOMATIS ---
@bot.message_handler(func=lambda message: URL_RE.search(message.text) is not None)
def handle_link(message):
    url = URL_RE.search(message.text).group(0)
    process_download(message, url, mode="video")

# --- MAIN ---
if __name__ == "__main__":
    init_db()
    print("Bot berjalan...")
    bot.infinity_polling()
