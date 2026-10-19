# bot.py — Bot Telegram Full Fitur (V3)
import os
import re
import shutil
import sqlite3
import hashlib
import secrets
import random
import subprocess
import time
import telebot
from datetime import datetime
from pathlib import Path
import yt_dlp
from telebot import types

# --- TOKEN LANGSUNG DI SINI ---
BOT_TOKEN = "8664978056:AAGNBZAhn9QAKhdyHBNILhzMB-5YU9YfWMI"

DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "./downloads"))
MAX_FILESIZE_MB = int(os.getenv("MAX_FILESIZE_MB", "50"))
URL_RE = re.compile(r"https?://\S+")

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

bot = telebot.TeleBot(BOT_TOKEN)

# --- DATABASE SETUP ---
conn = sqlite3.connect("bot_data.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, chat_id INTEGER, text TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, chat_id INTEGER, text TEXT, done INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS quotes (id INTEGER PRIMARY KEY, text TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS autoreplies (keyword TEXT PRIMARY KEY, reply TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, chat_id INTEGER, url TEXT, time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
conn.commit()

# --- PROGRESS BAR HOOK ---
download_status = {}

def progress_hook(d):
    if d['status'] == 'downloading':
        if 'total_bytes' in d and d['total_bytes'] > 0:
            percent = int((d['downloaded_bytes'] / d['total_bytes']) * 100)
        elif 'total_bytes_estimate' in d and d['total_bytes_estimate'] > 0:
            percent = int((d['downloaded_bytes'] / d['total_bytes_estimate']) * 100)
        else:
            percent = 0
        
        if percent % 10 == 0: # update tiap 10%
            chat_id = d.get('info_dict', {}).get('chat_id')
            msg_id = d.get('info_dict', {}).get('msg_id')
            if chat_id and msg_id:
                bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))
                try:
                    bot.edit_message_text(f"Downloading... [{bar}] {percent}%", chat_id, msg_id)
                except:
                    pass

def _ydl_opts(kind: str) -> dict:
    base = {
        "outtmpl": str(DOWNLOAD_DIR / "%(title).80s-%(id)s.%(ext)s"),
        "restrictfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_FILESIZE_MB * 1024 * 1024,
        "progress_hooks": [progress_hook],
    }
    if kind == "video":
        base.update(format="bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b", merge_output_format="mp4")
    elif kind == "audio":
        base.update(format="bestaudio/best", postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"}])
    elif kind == "photo":
        base.update(format="bestaudio/best", skip_download=True, writethumbnail=True)
    return base

def _pick_thumb(info: dict) -> str | None:
    thumbs = info.get("thumbnails") or []
    imgs = [t for t in thumbs if t.get("url")]
    if not imgs: return None
    imgs.sort(key=lambda t: (t.get("width") or 0) * (t.get("height") or 0))
    return imgs[-1]["url"]

def _sync_download(url: str, kind: str, chat_id: int, msg_id: int) -> Path | None:
    try:
        opts = _ydl_opts(kind)
        opts["progress_hooks"] = [lambda d: _hook_with_ids(d, chat_id, msg_id)]
        
        with yt_dlp.YoutubeDL(opts) as ydl:
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
        print(f"download error ({kind}): {e}")
        return None

def _hook_with_ids(d, chat_id, msg_id):
    if d['status'] == 'downloading':
        if 'total_bytes' in d and d['total_bytes'] > 0:
            percent = int((d['downloaded_bytes'] / d['total_bytes']) * 100)
        elif 'total_bytes_estimate' in d and d['total_bytes_estimate'] > 0:
            percent = int((d['downloaded_bytes'] / d['total_bytes_estimate']) * 100)
        else:
            percent = 0
        if percent % 20 == 0:
            bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))
            try: bot.edit_message_text(f"Downloading... [{bar}] {percent}%", chat_id, msg_id)
            except: pass

def _process_download(message, kind: str, url: str, status_msg_id: int):
    path = _sync_download(url, kind, message.chat.id, status_msg_id)
    
    if path is None:
        return bot.edit_message_text("Gagal download. Cek link atau ukuran file.", message.chat.id, status_msg_id)

    size_mb = path.stat().st_size / (1024 * 1024)
    bot.edit_message_text(f"Uploading {path.name} ({size_mb:.1f}MB)...", message.chat.id, status_msg_id)
    
    try:
        with open(path, "rb") as f:
            if kind == "video":
                if size_mb > 50:
                    bot.send_document(message.chat.id, f, caption=path.stem)
                else:
                    bot.send_video(message.chat.id, f, caption=path.stem, supports_streaming=True)
            elif kind == "audio":
                bot.send_audio(message.chat.id, f, title=path.stem)
            else:
                bot.send_photo(message.chat.id, f, caption=path.stem)
        bot.delete_message(message.chat.id, status_msg_id)
    except Exception as e:
        print(f"upload gagal: {e}")
        bot.edit_message_text(f"Upload gagal: {type(e).__name__}", message.chat.id, status_msg_id)
    finally:
        path.unlink(missing_ok=True)

# --- HANDLERS: DOWNLOAD & INLINE KEYBOARD ---
@bot.message_handler(commands=['start'])
def cmd_start(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("📥 Video", callback_data="dl_video"), types.InlineKeyboardButton("🎵 Audio", callback_data="dl_audio"))
    bot.reply_to(message, "Kirim link atau pilih menu di bawah:", reply_markup=markup)

@bot.message_handler(commands=['video'])
def on_video(message):
    match = URL_RE.search(message.text)
    if not match: return bot.reply_to(message, "Gak ada link.")
    status = bot.reply_to(message, "Downloading (video)... [░░░░░░░░░░] 0%")
    _process_download(message, "video", match.group(0), status.message_id)

@bot.message_handler(commands=['audio'])
def on_audio(message):
    match = URL_RE.search(message.text)
    if not match: return bot.reply_to(message, "Gak ada link.")
    status = bot.reply_to(message, "Downloading (audio)... [░░░░░░░░░░] 0%")
    _process_download(message, "audio", match.group(0), status.message_id)

@bot.message_handler(commands=['foto'])
def on_foto(message):
    match = URL_RE.search(message.text)
    if not match: return bot.reply_to(message, "Gak ada link.")
    status = bot.reply_to(message, "Mengambil foto...")
    _process_download(message, "photo", match.group(0), status.message_id)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data.startswith("dl_"):
        bot.answer_callback_query(call.id, "Kirim linknya sekarang beserta command ini.")
        cmd = call.data.split("_")[1]
        bot.send_message(call.message.chat.id, f"Format {cmd} dipilih. Silakan kirim: /{cmd} <link>")

@bot.message_handler(func=lambda msg: msg.text and not msg.text.startswith('/'))
def on_text(message):
    text = message.text
    match = URL_RE.search(text)
    if match:
        # Auto-detect link, kirim inline button
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("📥 Video", callback_data=f"dl_url_video|{match.group(0)}"),
            types.InlineKeyboardButton("🎵 Audio", callback_data=f"dl_url_audio|{match.group(0)}"),
            types.InlineKeyboardButton("🖼 Foto", callback_data=f"dl_url_photo|{match.group(0)}")
        )
        return bot.reply_to(message, "Mau download jadi apa?", reply_markup=markup)
    
    # Cek Auto-reply
    cursor.execute("SELECT reply FROM autoreplies WHERE ? LIKE '%' || keyword || '%'", (text.lower(),))
    res = cursor.fetchone()
    if res:
        return bot.reply_to(message, res[0])

@bot.callback_query_handler(func=lambda call: call.data.startswith("dl_url_"))
def callback_dl_url(call):
    try:
        data = call.data.split("|")
        kind = data[0].replace("dl_url_", "")
        url = data[1]
        bot.answer_callback_query(call.id, f"Memproses {kind}...")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        status = bot.send_message(call.message.chat.id, f"Downloading ({kind})... [░░░░░░░░░░] 0%")
        
        # Simpen history
        cursor.execute("INSERT INTO history (chat_id, url) VALUES (?, ?)", (call.message.chat.id, url))
        conn.commit()
        
        _process_download(call.message, kind, url, status.message_id)
    except Exception as e:
        bot.send_message(call.message.chat.id, f"Error: {e}")

# --- HANDLERS: UTILITAS & STORAGE ---
@bot.message_handler(commands=['id'])
def cmd_id(message):
    bot.reply_to(message, f"Chat ID: `{message.chat.id}`\nUser ID: `{message.from_user.id}`", parse_mode="Markdown")

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
        total = sum(random.randint(1, d) for _ in range(n))
        bot.reply_to(message, f"🎲 Hasil {dice}: **{total}**", parse_mode="Markdown")
    except:
        bot.reply_to(message, "Format: /roll 2d6")

@bot.message_handler(commands=['genpass'])
def cmd_genpass(message):
    try:
        length = int(message.text.split()[1])
    except:
        length = 16
    pwd = ''.join(secrets.choice("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*") for _ in range(length))
    bot.reply_to(message, f"`{pwd}`", parse_mode="Markdown")

@bot.message_handler(commands=['hash'])
def cmd_hash(message):
    text = message.text.replace('/hash ', '')
    if not text: return bot.reply_to(message, "Format: /hash <teks>")
    bot.reply_to(message, f"MD5: `{hashlib.md5(text.encode()).hexdigest()}`\nSHA256: `{hashlib.sha256(text.encode()).hexdigest()}`", parse_mode="Markdown")

@bot.message_handler(commands=['note'])
def cmd_note(message):
    text = message.text.replace('/note ', '')
    if not text: return bot.reply_to(message, "Format: /note <teks>")
    cursor.execute("INSERT INTO notes (chat_id, text) VALUES (?, ?)", (message.chat.id, text))
    conn.commit()
    bot.reply_to(message, "✅ Catatan disimpan.")

@bot.message_handler(commands=['notes'])
def cmd_notes(message):
    cursor.execute("SELECT id, text FROM notes WHERE chat_id=?", (message.chat.id,))
    rows = cursor.fetchall()
    if not rows: return bot.reply_to(message, "Belum ada catatan.")
    reply = "📝 **Daftar Catatan:**\n\n" + "\n".join([f"`{r[0]}`. {r[1]}" for r in rows])
    bot.reply_to(message, reply, parse_mode="Markdown")

@bot.message_handler(commands=['todo'])
def cmd_todo(message):
    text = message.text.replace('/todo ', '')
    if not text: return bot.reply_to(message, "Format: /todo <teks>")
    cursor.execute("INSERT INTO todos (chat_id, text) VALUES (?, ?)", (message.chat.id, text))
    conn.commit()
    bot.reply_to(message, "✅ To-do ditambahkan.")

@bot.message_handler(commands=['done'])
def cmd_done(message):
    try:
        tid = int(message.text.split()[1])
        cursor.execute("UPDATE todos SET done=1 WHERE id=? AND chat_id=?", (tid, message.chat.id))
        conn.commit()
        bot.reply_to(message, "✅ To-do selesai.")
    except:
        bot.reply_to(message, "Format: /done <id>")

@bot.message_handler(commands=['todos'])
def cmd_todos(message):
    cursor.execute("SELECT id, text, done FROM todos WHERE chat_id=?", (message.chat.id,))
    rows = cursor.fetchall()
    if not rows: return bot.reply_to(message, "Belum ada to-do.")
    reply = "📋 **To-do List:**\n\n" + "\n".join([f"{'✅' if r[2] else '⬜'} `{r[0]}`. {r[1]}" for r in rows])
    bot.reply_to(message, reply, parse_mode="Markdown")

@bot.message_handler(commands=['quote'])
def cmd_quote(message):
    text = message.text.replace('/quote ', '')
    if text and text != '/quote':
        cursor.execute("INSERT INTO quotes (text) VALUES (?)", (text,))
        conn.commit()
        return bot.reply_to(message, "✅ Quote disimpan.")
    
    cursor.execute("SELECT text FROM quotes ORDER BY RANDOM() LIMIT 1")
    res = cursor.fetchone()
    if res: bot.reply_to(message, f"💬 \"{res[0]}\"")
    else: bot.reply_to(message, "Belum ada quote. Tambahin pakai /quote <teks>")

@bot.message_handler(commands=['setreply'])
def cmd_setreply(message):
    try:
        parts = message.text.replace('/setreply ', '').split('|')
        if len(parts) != 2: raise ValueError
        keyword, reply = parts[0].strip().lower(), parts[1].strip()
        cursor.execute("INSERT OR REPLACE INTO autoreplies (keyword, reply) VALUES (?, ?)", (keyword, reply))
        conn.commit()
        bot.reply_to(message, f"✅ Auto-reply '{keyword}' disimpan.")
    except:
        bot.reply_to(message, "Format: /setreply kata | balasan")

@bot.message_handler(commands=['history'])
def cmd_history(message):
    cursor.execute("SELECT url, time FROM history WHERE chat_id=? ORDER BY id DESC LIMIT 5", (message.chat.id,))
    rows = cursor.fetchall()
    if not rows: return bot.reply_to(message, "Belum ada history.")
    reply = "🕒 **History Download:**\n\n" + "\n".join([f"- {r[0]}" for r in rows])
    bot.reply_to(message, reply, parse_mode="Markdown")

if __name__ == "__main__":
    print("Bot full fitur jalan...")
    bot.infinity_polling()
