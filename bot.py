# bot.py — Bot Telegram Ultimate (V30d - Hardware Fix)
import os
import re
import shutil
import sqlite3
import hashlib
import secrets
import random
import time
import threading
import subprocess
import json
import socket
import telebot
import yt_dlp
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from pathlib import Path
from telebot import types

BOT_TOKEN = "8664978056:AAGNBZAhn9QAKhdyHBNILhzMB-5YU9YfWMI"
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "./downloads"))
MAX_FILESIZE_MB = int(os.getenv("MAX_FILESIZE_MB", "50"))
URL_RE = re.compile(r"https?://\S+")

DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# --- DB SETUP ---
conn = sqlite3.connect("bot_data.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, chat_id INTEGER, text TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS todos (id INTEGER PRIMARY KEY, chat_id INTEGER, text TEXT, done INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS quotes (id INTEGER PRIMARY KEY, text TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS autoreplies (keyword TEXT PRIMARY KEY, reply TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, chat_id INTEGER, url TEXT, time TIMESTAMP DEFAULT CURRENT_TIMESTAMP)")
cursor.execute("CREATE TABLE IF NOT EXISTS users (chat_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS watches (id INTEGER PRIMARY KEY, chat_id INTEGER, url TEXT, last_hash TEXT)")
conn.commit()

# --- NATIVE SYSTEM INFO FUNCTIONS ---
def get_battery_info():
    try:
        # Trik: Baca dari virtual filesystem Android yang biasanya gak di-lock
        paths = [
            '/sys/class/power_supply/battery/capacity',
            '/sys/class/power_supply/bms/capacity',
            '/sys/class/power_supply/BAT0/capacity'
        ]
        capacity = None
        for p in paths:
            if os.path.exists(p):
                with open(p, 'r') as f:
                    capacity = f.read().strip()
                break
                
        if not capacity:
            return "❌ Gagal baca baterai (file virtual sistem gak nemu)."

        status_paths = [
            '/sys/class/power_supply/battery/status',
            '/sys/class/power_supply/bms/status',
            '/sys/class/power_supply/BAT0/status'
        ]
        status = "Unknown"
        for p in status_paths:
            if os.path.exists(p):
                with open(p, 'r') as f:
                    status = f.read().strip()
                break

        temp_paths = [
            '/sys/class/power_supply/battery/temp',
            '/sys/class/power_supply/bms/temp'
        ]
        temp = "N/A"
        for p in temp_paths:
            if os.path.exists(p):
                with open(p, 'r') as f:
                    temp = f"{int(f.read().strip())/10.0}°C"
                break

        return f"🔋 **Baterai:** {capacity}%\nStatus: {status}\nSuhu: {temp}"
    except Exception as e:
        return f"❌ Gagal baca baterai: {e}"

def get_local_ip():
    try:
        # Trik Python murni: Bikin koneksi dummy buat nanya IP lokal ke OS
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return f"🌐 **IP Lokal:** `{ip}`"
    except:
        return "❌ Gagal baca IP. Pastiin jaringan nyala."

# --- QUEUE SYSTEM ---
download_queue = []
queue_lock = threading.Lock()

def process_queue():
    while True:
        time.sleep(1)
        with queue_lock:
            if not download_queue:
                continue
            task = download_queue.pop(0)
        _process_download(task['message'], task['kind'], task['url'], task['status_id'])

threading.Thread(target=process_queue, daemon=True).start()

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
        "outtmpl": str(DOWNLOAD_DIR / "%(title).80s-%(id)s.%(ext)s"),
        "restrictfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_FILESIZE_MB * 1024 * 1024,
        "progress_hooks": [lambda d: _hook_with_ids(d, chat_id, msg_id)],
        "socket_timeout": 15, 
        "retries": 5,
        "source_address": "0.0.0.0"
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

def _sync_download(url: str, kind: str, chat_id: int, msg_id: int) -> dict | None:
    try:
        with yt_dlp.YoutubeDL(_ydl_opts(kind, chat_id, msg_id)) as ydl:
            info = ydl.extract_info(url, download=(kind != "photo"))
            if info is None: return None
            
            raw_title = info.get("title", "Unknown")
            artist = info.get("artist") or info.get("uploader") or info.get("channel") or ""
            
            if artist and artist.lower() not in raw_title.lower():
                clean_name = f"{artist} - {raw_title}"
            else:
                clean_name = raw_title
                
            clean_name = re.sub(r'[\\/*?:"<>|]', "", clean_name).strip()
            clean_name = clean_name[:100]

            if kind == "photo":
                thumb_url = _pick_thumb(info)
                if not thumb_url: return None
                out = DOWNLOAD_DIR / f"{clean_name}.jpg"
                with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as d:
                    d.download([thumb_url])
                    for cand in DOWNLOAD_DIR.glob(f"{info.get('id', '')}*"):
                        if cand.is_file() and cand != out:
                            shutil.move(str(cand), str(out))
                            break
                return {"path": out, "title": clean_name} if out.exists() else None

            path = Path(ydl.prepare_filename(info))
            if not path.exists():
                stem = path.with_suffix("")
                exts = (".mp4", ".mkv", ".webm") if kind == "video" else (".mp3", ".m4a", ".opus")
                for ext in exts:
                    cand = stem.with_suffix(ext)
                    if cand.exists(): path = cand; break
                else: return None
            
            new_path = DOWNLOAD_DIR / f"{clean_name}{path.suffix}"
            try:
                path.rename(new_path)
                path = new_path
            except: pass
            return {"path": path, "title": clean_name}
    except Exception as e:
        print(f"download error ({kind}): {e}")
        return None

def _process_download(message, kind: str, url: str, status_msg_id: int):
    res = _sync_download(url, kind, message.chat.id, status_msg_id)
    if res is None: 
        return bot.edit_message_text("Gagal download. Jaringan diblokir / link invalid.", message.chat.id, status_msg_id)
    
    path = res["path"]
    title = res["title"]
    
    size_mb = path.stat().st_size / (1024 * 1024)
    bot.edit_message_text(f"Uploading ({size_mb:.1f}MB)...", message.chat.id, status_msg_id)
    
    try:
        with open(path, "rb") as f:
            if kind == "video":
                if size_mb > 50: bot.send_document(message.chat.id, f, caption=title, timeout=120)
                else: bot.send_video(message.chat.id, f, caption=title, supports_streaming=True, timeout=120)
            elif kind == "audio": bot.send_audio(message.chat.id, f, title=title, timeout=120)
            else: bot.send_photo(message.chat.id, f, caption=title, timeout=120)
        bot.delete_message(message.chat.id, status_msg_id)
    except Exception as e:
        bot.edit_message_text(f"Upload gagal: {e}", message.chat.id, status_msg_id)
    finally: path.unlink(missing_ok=True)

# --- REMINDER SYSTEM ---
def set_reminder(chat_id, delay, text):
    def send_reminder():
        try: bot.send_message(chat_id, f"⏰ **PENGINGAT:** {text}", parse_mode="Markdown")
        except: pass
    t = threading.Timer(delay, send_reminder)
    t.start()

# --- SCRAPER SYSTEM ---
def scrape_watch(chat_id, url, watch_id):
    while True:
        time.sleep(600) 
        try:
            cursor.execute("SELECT last_hash FROM watches WHERE id=?", (watch_id,))
            row = cursor.fetchone()
            if not row: break 
            last_hash = row[0]
            
            res = requests.get(url, timeout=10)
            soup = BeautifulSoup(res.text, 'html.parser')
            current_text = soup.get_text()
            current_hash = hashlib.md5(current_text.encode()).hexdigest()
            
            if current_hash != last_hash:
                bot.send_message(chat_id, f"🔔 **PERUBAHAN TERDETEKSI:**\n{url}")
                cursor.execute("UPDATE watches SET last_hash=? WHERE id=?", (current_hash, watch_id))
                conn.commit()
        except: pass

# --- UI MENU ---
@bot.message_handler(commands=['start', 'help'])
def cmd_start(message):
    cursor.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?)", (message.chat.id,))
    conn.commit()
    
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
        markup.row(types.InlineKeyboardButton("🔋 Baterai", callback_data="tool_batt"), types.InlineKeyboardButton("🌐 IP Lokal", callback_data="tool_ip"))
        markup.row(types.InlineKeyboardButton("🗑 Bersihkan Cache", callback_data="tool_clear"))
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
    elif tool == "batt": bot.send_message(call.message.chat.id, get_battery_info(), parse_mode="Markdown")
    elif tool == "ip": bot.send_message(call.message.chat.id, get_local_ip(), parse_mode="Markdown")
    elif tool == "clear":
        deleted_files = 0
        for f in DOWNLOAD_DIR.glob('*'):
            if f.is_file():
                try:
                    f.unlink()
                    deleted_files += 1
                except: pass
        
        cursor.execute("DELETE FROM history WHERE chat_id=?", (call.message.chat.id,))
        conn.commit()
        
        bot.edit_message_text(f"🗑 **Cache dibersihkan!**\n- {deleted_files} file sampah dihapus.\n- Riwayat download dikosongkan.", call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("⬅️ Balik", callback_data="menu_back")))

# --- TEXT HANDLERS ---
@bot.message_handler(func=lambda msg: msg.text and not msg.text.startswith('/'))
def on_text(message):
    text = message.text
    if message.reply_to_message and "Tempel link" in message.reply_to_message.text:
        parent = message.reply_to_message.text
        match = URL_RE.search(text)
        if not match: return bot.reply_to(message, "Bukan link valid.")
        
        url = match.group(0)
        cursor.execute("INSERT INTO history (chat_id, url) VALUES (?, ?)", (message.chat.id, url))
        conn.commit()
        
        kind = "video" if "video" in parent else ("audio" if "audio" in parent else "photo")
        status = bot.reply_to(message, f"Masuk antrean ({kind})...")
        
        with queue_lock:
            download_queue.append({'message': message, 'kind': kind, 'url': url, 'status_id': status.message_id})
        return

    match = URL_RE.search(text)
    if match:
        url = match.group(0)
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("📥 Video", callback_data=f"dl_url_video|{url}"),
            types.InlineKeyboardButton("🎵 Audio", callback_data=f"dl_url_audio|{url}"),
            types.InlineKeyboardButton("🖼 Foto", callback_data="menu_photo")
        )
        return bot.reply_to(message, "Mau jadi apa?", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("dl_url_"))
def callback_dl_url(call):
    try:
        data = call.data.split("|")
        kind = data[0].replace("dl_url_", "")
        url = data[1]
        bot.answer_callback_query(call.id, f"Masuk antrean...")
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        cursor.execute("INSERT INTO history (chat_id, url) VALUES (?, ?)", (call.message.chat.id, url))
        conn.commit()
        
        status = bot.send_message(call.message.chat.id, f"Masuk antrean ({kind})...")
        with queue_lock:
            download_queue.append({'message': call.message, 'kind': kind, 'url': url, 'status_id': status.message_id})
    except Exception as e: bot.send_message(call.message.chat.id, f"Error: {e}")

# --- EKSTRAK AUDIO LOKAL ---
@bot.message_handler(content_types=['video', 'video_note'])
def handle_video_local(message):
    status = bot.reply_to(message, "Mengekstrak audio...")
    file_info = bot.get_file(message.video.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    
    temp_vid = DOWNLOAD_DIR / f"temp_{message.video.file_id}.mp4"
    temp_mp3 = DOWNLOAD_DIR / f"audio_{message.video.file_id}.mp3"
    with open(temp_vid, 'wb') as f: f.write(downloaded_file)
    
    try:
        subprocess.run(['ffmpeg', '-y', '-i', str(temp_vid), '-q:a', '0', '-map', 'a', str(temp_mp3)], check=True, capture_output=True)
        with open(temp_mp3, 'rb') as f:
            bot.send_audio(message.chat.id, f, title="Audio Extract")
        bot.delete_message(message.chat.id, status.message_id)
    except Exception as e:
        bot.edit_message_text(f"Gagal ekstrak: {e}", message.chat.id, status.message_id)
    finally:
        temp_vid.unlink(missing_ok=True)
        temp_mp3.unlink(missing_ok=True)

# --- OCR LOKAL ---
@bot.message_handler(content_types=['photo'])
def handle_ocr(message):
    status = bot.reply_to(message, "Membaca teks (OCR)...")
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        temp_img = DOWNLOAD_DIR / f"ocr_{message.photo[-1].file_id}.jpg"
        temp_upscaled = DOWNLOAD_DIR / f"ocr_up_{message.photo[-1].file_id}.jpg"
        
        with open(temp_img, 'wb') as f: f.write(downloaded_file)
        
        subprocess.run(['ffmpeg', '-y', '-i', str(temp_img), '-vf', 'scale=iw*2:ih*2', str(temp_upscaled)], check=True, capture_output=True)
        
        result = subprocess.run(['tesseract', str(temp_upscaled), 'stdout', '-l', 'eng'], capture_output=True, text=True)
        text = result.stdout.strip()
        
        if text: 
            bot.edit_message_text(f"📄 **Hasil OCR:**\n\n{text}", message.chat.id, status.message_id)
        else: 
            bot.edit_message_text("Teks tidak terdeteksi. Pastiin gambar gak burem.", message.chat.id, status.message_id)
    except Exception as e:
        bot.edit_message_text(f"Gagal OCR: {e}", message.chat.id, status.message_id)
    finally:
        temp_img.unlink(missing_ok=True)
        temp_upscaled.unlink(missing_ok=True)

# --- UTILITY COMMANDS ---
@bot.message_handler(commands=['baterai'])
def cmd_batt(message):
    bot.reply_to(message, get_battery_info(), parse_mode="Markdown")

@bot.message_handler(commands=['ip'])
def cmd_ip(message):
    bot.reply_to(message, get_local_ip(), parse_mode="Markdown")

@bot.message_handler(commands=['remind'])
def cmd_remind(message):
    try:
        parts = message.text.split(' ', 2)
        time_str, text = parts[1], parts[2]
        unit = time_str[-1].lower()
        val = int(time_str[:-1])
        
        if unit == 'm': delay = val * 60
        elif unit == 'h': delay = val * 3600
        else: return bot.reply_to(message, "Format: /remind 10m <teks>")
        
        set_reminder(message.chat.id, delay, text)
        bot.reply_to(message, f"⏰ Pengingat disetel dalam {time_str}.")
    except: bot.reply_to(message, "Format: /remind 10m <teks>")

@bot.message_handler(commands=['watch'])
def cmd_watch(message):
    match = URL_RE.search(message.text)
    if not match: return bot.reply_to(message, "Format: /watch <url>")
    url = match.group(0)
    
    res = requests.get(url, timeout=10)
    soup = BeautifulSoup(res.text, 'html.parser')
    current_hash = hashlib.md5(soup.get_text().encode()).hexdigest()
    
    cursor.execute("INSERT INTO watches (chat_id, url, last_hash) VALUES (?, ?, ?)", (message.chat.id, url, current_hash))
    conn.commit()
    watch_id = cursor.lastrowid
    
    threading.Thread(target=scrape_watch, args=(message.chat.id, url, watch_id), daemon=True).start()
    bot.reply_to(message, "✅ Memantau halaman. Akan diberitahu jika ada perubahan.")

@bot.message_handler(commands=['clear'])
def cmd_clear(message):
    deleted_files = 0
    for f in DOWNLOAD_DIR.glob('*'):
        if f.is_file():
            try:
                f.unlink()
                deleted_files += 1
            except: pass
            
    cursor.execute("DELETE FROM history WHERE chat_id=?", (message.chat.id,))
    conn.commit()
    bot.reply_to(message, f"🗑 **Cache dibersihkan!**\n- {deleted_files} file sampah dihapus.\n- Riwayat download dikosongkan.", parse_mode="Markdown")

@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    text = message.text.replace('/broadcast ', '')
    if not text: return bot.reply_to(message, "Format: /broadcast <pesan>")
    
    cursor.execute("SELECT chat_id FROM users")
    rows = cursor.fetchall()
    success = 0
    for r in rows:
        try:
            bot.send_message(r[0], f"📢 **PENGUMUMAN:**\n\n{text}", parse_mode="Markdown")
            success += 1
        except: pass
    bot.reply_to(message, f"Broadcast terkirim ke {success} user.")

@bot.message_handler(commands=['stats'])
def cmd_stats(message):
    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM history")
    downloads = cursor.fetchone()[0]
    total_size = sum(f.stat().st_size for f in DOWNLOAD_DIR.glob('**/*') if f.is_file()) / (1024 * 1024)
    bot.reply_to(message, f"📊 **Stats Bot:**\nUser: {users}\nTotal Download: {downloads}\nDisk: {total_size:.1f} MB")

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
    print("Bot running (V30d - Hardware Fix)...")
    while True:
        try:
            bot.infinity_polling(timeout=20, long_polling_timeout=15, none_stop=True)
        except Exception as e:
            print(f"Koneksi terputus: {e}")
            print("Nyoba nyambung lagi dalam 5 detik...")
            time.sleep(5)
