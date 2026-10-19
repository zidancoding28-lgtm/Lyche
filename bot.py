# bot.py — Bot Telegram Full Fitur (V5 - All UI)
import os
import re
import shutil
import sqlite3
import hashlib
import secrets
import random
import time
import telebot
from datetime import datetime
from pathlib import Path
import yt_dlp
from telebot import types

BOT_TOKEN = "8664978056:AAGNBZAhn9QAKhdyHBNILhzMB-5YU9YfWMI"
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "./downloads"))
MAX_FILESIZE_MB = int(os.getenv("MAX_FILESIZE_MB", "50"))
URL_RE = re.compile(r"https?://\S+")

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
bot = telebot.TeleBot(BOT_TOKEN)

# --- DB SETUP ---
conn = sqlite3.connect("bot_data.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, chat_id INTEGER, text TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, chat_id INTEGER, text TEXT, done INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS quotes (id INTEGER PRIMARY KEY, text TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS autoreplies (keyword TEXT PRIMARY KEY, reply TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, chat_id INTEGER, url TEXT, time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
conn.commit()

# --- DOWNLOAD LOGIC ---
def _hook_with_ids(d, chat_id, msg_id):
    if d['status'] == 'downloading':
        if 'total_bytes' in d and d['total_bytes'] > 0:
            percent = int((d['downloaded_bytes'] / d['total_bytes']) * 100)
        elif 'total_bytes_estimate' in d and d['total_bytes_estimate'] > 0:
            percent = int((d['downloaded_bytes'] / d['total_bytes_estimate']) * 100)
        else: percent = 0
        if percent % 20 == 0:
            bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))
            try: bot.edit_message_text(f"Downloading... [{bar}] {percent}%", chat_id, msg_id)
            except: pass

def _ydl_opts(kind: str, chat_id: int, msg_id: int) -> dict:
    base = {
        "outtmpl": str(DOWNLOAD_DIR / "%(title).80s-%(id)s.%(ext)s"), "restrictfilenames": True,
        "noplaylist": True, "quiet": True, "no_warnings": True, "max_filesize": MAX_FILESIZE_MB * 1024 * 1024,
        "progress_hooks": [lambda d: _hook_with_ids(d, chat_id, msg_id)],
    }
    if kind == "video": base.update(format="bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b", merge_output_format="mp4")
    elif kind == "audio": base.update(format="bestaudio/best", postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}])
    elif kind == "photo": base.update(format="bestaudio/best", skip_download=True, writethumbnail=True)
    return base

def _pick_thumb(info: dict) -> str | None:
    thumbs = info.get("thumbnails") or []
    imgs = [t for t in thumbs if t.get("url")]
    if not imgs: return None
    imgs.sort(key=lambda t: (t.get("width") or 0) * (t.get("height") or 0))
    return imgs[-1]["url"]

def _sync_download(url: str, kind: str, chat_id: int, msg_id: int) -> Path | None:
    try:
        with yt_dlp.YoutubeDL(_ydl_opts(kind, chat_id, msg_id)) as ydl:
            info = ydl.extract_info(url, download=(kind != "photo"))
            if info is None: return None
            if kind == "photo":
                thumb_url = _pick_thumb(info)
                if not thumb_url: return None
                out = DOWNLOAD_DIR / f"{info.get('id', 'img')}.jpg"
                with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as d:
                    d.download([thumb_url])
                    for cand in DOWNLOAD_DIR.glob(f"{info.get('id', '')}*"):
                        if cand.is_file() and cand != out:
                            shutil.move(str(cand), str(out))
                            break
                return out if out.exists() else None
            path = Path(ydl.prepare_filename(info))
            if not path.exists():
                stem = path.with_suffix("")
                exts = (".mp4", ".mkv", ".webm") if kind == "video" else (".mp3", ".m4a", ".opus")
                for ext in exts:
                    cand = stem.with_suffix(ext)
                    if cand.exists(): return cand
                return None
            return path
    except Exception as e:
        print(f"download error ({kind}): {e}"); return None

def _process_download(message, kind: str, url: str, status_msg_id: int):
    path = _sync_download(url, kind, message.chat.id, status_msg_id)
    if path is None: return bot.edit_message_text("Gagal download.", message.chat.id, status_msg_id)
    size_mb = path.stat().st_size / (1024 * 1024)
    bot.edit_message_text(f"Uploading ({size_mb:.1f}MB)...", message.chat.id, status_msg_id)
    try:
        with open(path, "rb") as f:
            if kind == "video":
                if size_mb > 50: bot.send_document(message.chat.id, f, caption=path.stem)
                else: bot.send_video(message.chat.id, f, caption=path.stem, supports_streaming=True)
            elif kind == "audio": bot.send_audio(message.chat.id, f, title=path.stem)
            else: bot.send_photo(message.chat.id, f, caption=path.stem)
        bot.delete_message(message.chat.id, status_msg_id)
    except Exception as e:
        bot.edit_message_text(f"Upload gagal: {e}", message.chat.id, status_msg_id)
    finally: path.unlink(missing_ok=True)

# --- UI MENU ---
@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("📥 Video", callback_data="menu_video"),
        types.InlineKeyboardButton("🎵 Audio", callback_data="menu_audio"),
        types.InlineKeyboardButton("🖼 Foto", callback_data="menu_photo")
    )
    markup.row(
        types.InlineKeyboardButton("📝 Catatan", callback_data="menu_notes"),
        types.InlineKeyboardButton("📋 To-do", callback_data="menu_todos"),
        types.InlineKeyboardButton("💬 Quote", callback_data="menu_quote")
    )
    markup.row(
        types.InlineKeyboardButton("🕒 History", callback_data="menu_history"),
        types.InlineKeyboardButton("⚙️ Alat", callback_data="menu_tools")
    )
    bot.reply_to(message, "Silakan pilih menu di bawah:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("menu_"))
def callback_menu(call):
    cmd = call.data.replace("menu_", "")
    bot.answer_callback_query(call.id)
    
    if cmd in ["video", "audio", "photo"]:
        bot.send_message(call.message.chat.id, f"Tempel link {cmd} sekarang:", reply_markup=types.ForceReply(selective=True))
    
    elif cmd == "notes":
        cursor.execute("SELECT id, text FROM notes WHERE chat_id=?", (call.message.chat.id,))
        rows = cursor.fetchall()
        text = "📝 **Catatan:**\n\n" + "\n".join([f"`{r[0]}`. {r[1]}" for r in rows]) if rows else "Belum ada catatan."
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Balik", callback_data="menu_back")))
    
    elif cmd == "todos":
        cursor.execute("SELECT id, text, done FROM todos WHERE chat_id=?", (call.message.chat.id,))
        rows = cursor.fetchall()
        text = "📋 **To-do:**\n\n" + "\n".join([f"{'✅' if r[2] else '⬜'} `{r[0]}`. {r[1]}" for r in rows]) if rows else "Belum ada to-do."
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Balik", callback_data="menu_back")))
    
    elif cmd == "quote":
        cursor.execute("SELECT text FROM quotes ORDER BY RANDOM() LIMIT 1")
        res = cursor.fetchone()
        text = f"💬 \"{res[0]}\"" if res else "Belum ada quote."
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Balik", callback_data="menu_back")))
    
    elif cmd == "history":
        cursor.execute("SELECT url FROM history WHERE chat_id=? ORDER BY id DESC LIMIT 5", (call.message.chat.id,))
        rows = cursor.fetchall()
        text = "🕒 **History:**\n\n" + "\n".join([f"- {r[0]}" for r in rows]) if rows else "Belum ada history."
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Balik", callback_data="menu_back")))

    elif cmd == "tools":
        markup = types.InlineKeyboardMarkup()
        markup.row(types.InlineKeyboardButton("🎲 Roll Dadu", callback_data="tool_roll"), types.InlineKeyboardButton("🎯 Pick", callback_data="tool_pick"))
        markup.row(types.InlineKeyboardButton("🔑 Genpass", callback_data="tool_genpass"), types.InlineKeyboardButton("🕒 Time", callback_data="tool_time"))
        markup.row(types.InlineKeyboardButton("⬅️ Balik", callback_data="menu_back"))
        bot.edit_message_text("⚙️ **Menu Alat:**", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif cmd == "back":
        cmd_start(call.message)

@bot.callback_query_handler(func=lambda call: call.data.startswith("tool_"))
def callback_tool(call):
    tool = call.data.replace("tool_", "")
    bot.answer_callback_query(call.id)
    if tool == "time": bot.send_message(call.message.chat.id, f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    elif tool == "roll": bot.send_message(call.message.chat.id, "🎲 Ketik: `/roll 2d6`", parse_mode="Markdown")
    elif tool == "pick": bot.send_message(call.message.chat.id, "🎯 Ketik: `/pick opsi1 opsi2`", parse_mode="Markdown")
    elif tool == "genpass": bot.send_message(call.message.chat.id, "🔑 Ketik: `/genpass 16`", parse_mode="Markdown")

# --- TEXT HANDLERS (AUTO-DETECT & STATE) ---
@bot.message_handler(func=lambda msg: msg.text and not msg.text.startswith('/'))
def on_text(message):
    text = message.text
    if message.reply_to_message and "Tempel link" in message.reply_to_message.text:
        parent = message.reply_to_message.text
        kind = "video" if "video" in parent else ("audio" if "audio" in parent else "photo")
        match = URL_RE.search(text)
        if not match: return bot.reply_to(message, "Bukan link valid.")
        status = bot.reply_to(message, f"Downloading ({kind})... [░░░░░░░░░░] 0%")
        cursor.execute("INSERT INTO history (chat_id, url) VALUES (?, ?)", (message.chat.id, match.group(0)))
        conn.commit()
        _process_download(message, kind, match.group(0), status.message_id)
        return

    match = URL_RE.search(text)
    if match:
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📥 Video", callback_data=f"dl_url_video|{match.group(0)}"),
            types.InlineKeyboardButton("🎵 Audio", callback_data=f"dl_url_audio|{match.group(0)}"),
            types.InlineKeyboardButton("🖼 Foto", callback_data="menu_photo")
        )
        return bot.reply_to(message, "Mau jadi apa?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("dl_url_"))
def callback_dl_url(call):
    try:
        data = call.data.split("|")
        kind = data[0].replace("dl_url_", "")
        url = data[1]
        bot.answer_callback_query(call.id, f"Memproses...")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        status = bot.send_message(call.message.chat.id, f"Downloading ({kind})... [░░░░░░░░░░] 0%")
        cursor.execute("INSERT INTO history (chat_id, url) VALUES (?, ?)", (call.message.chat.id, url))
        conn.commit()
        _process_download(call.message, kind, url, status.message_id)
    except Exception as e: bot.send_message(call.message.chat.id, f"Error: {e}")

# --- UTILITY COMMANDS ---
@bot.message_handler(commands=['id'])
def cmd_id(message): bot.reply_to(message, f"ID: `{message.chat.id}`", parse_mode="Markdown")

@bot.message_handler(commands=['ping'])
def cmd_ping(message):
    start = time.time()
    msg = bot.reply_to(message, "Pong!")
    bot.edit_message_text(f"Pong! {int((time.time() - start) * 1000)}ms", message.chat.id, msg.message_id)

@bot.message_handler(commands=['roll'])
def cmd_roll(message):
    try:
        dice = message.text.split()[1]
        n, d = map(int, dice.split('d'))
        bot.reply_to(message, f"🎲 Hasil: **{sum(random.randint(1, d) for _ in range(n))}**", parse_mode="Markdown")
    except: bot.reply_to(message, "Format: /roll 2d6")

@bot.message_handler(commands=['pick'])
def cmd_pick(message):
    opts = message.text.replace('/pick ', '').split()
    if len(opts) < 2: return bot.reply_to(message, "Format: /pick a b")
    bot.reply_to(message, f"🎯 **{random.choice(opts)}**", parse_mode="Markdown")

@bot.message_handler(commands=['genpass'])
def cmd_genpass(message):
    try: length = int(message.text.split()[1])
    except: length = 16
    pwd = ''.join(secrets.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*") for _ in range(length))
    bot.reply_to(message, f"`{pwd}`", parse_mode="Markdown")

@bot.message_handler(commands=['note'])
def cmd_note(message):
    text = message.text.replace('/note ', '')
    if not text: return bot.reply_to(message, "Format: /note <teks>")
    cursor.execute("INSERT INTO notes (chat_id, text) VALUES (?, ?)", (message.chat.id, text)); conn.commit()
    bot.reply_to(message, "✅ Catatan disimpan.")

@bot.message_handler(commands=['todo'])
def cmd_todo(message):
    text = message.text.replace('/todo ', '')
    if not text: return bot.reply_to(message, "Format: /todo <teks>")
    cursor.execute("INSERT INTO todos (chat_id, text) VALUES (?, ?)", (message.chat.id, text)); conn.commit()
    bot.reply_to(message, "✅ To-do ditambahkan.")

if __name__ == "__main__":
    print("Bot running...")
    bot.infinity_polling()
