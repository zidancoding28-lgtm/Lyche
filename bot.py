# bot.py | DanzzBot v46 (All-in-One)
import os
import io
import requests
import logging
import yt_dlp
import string
import secrets
import re
import random
import hashlib
import base64
import json
import urllib.parse
import urllib3
from bs4 import BeautifulSoup
from datetime import datetime
from PIL import Image, ImageDraw, ImageOps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BOT_TOKEN = "8965097448:AAGM6xwbkjXPRwkb-9jd2fVCdA0p_pOluKM"
ADMIN_ID = 8901247073

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
user_sessions = {}

# ═══════════════════════════════════════════════════════════
# CORE & MENU
# ═══════════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Halo! Gue DanzzBot v46. Ketik /menu.")

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📥 Media & Spotify", callback_data='menu_dl'), InlineKeyboardButton("🤖 AI Chat", callback_data='menu_ai')],
        [InlineKeyboardButton("🕸️ Scraper", callback_data='menu_scrape'), InlineKeyboardButton("📧 Temp Mail", callback_data='menu_email')],
        [InlineKeyboardButton("🎨 Gambar & Teks", callback_data='menu_img'), InlineKeyboardButton("🛠️ Dev Tools", callback_data='menu_dev')],
        [InlineKeyboardButton("🎲 Generator", callback_data='menu_gen'), InlineKeyboardButton("🌐 Network", callback_data='menu_net')],
        [InlineKeyboardButton("🎬 Cari Preset", callback_data='menu_preset')]
    ]
    await update.message.reply_text("Pilih tools:", reply_markup=InlineKeyboardMarkup(keyboard))

async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == 'menu_dl': await query.edit_message_text("📥 **Downloader:**\n`/dl [link]` (Video)\n`/spotify [link]` (Lagu)\n`/getimg [link]` (Ambil Gambar)")
    elif query.data == 'menu_ai': await query.edit_message_text("Ketik pesan bebas.")
    elif query.data == 'menu_scrape': await query.edit_message_text("`/scrape [url]` | `/scrapeimg [url]`")
    elif query.data == 'menu_email': await query.edit_message_text("Ketik `/email` lalu `/inbox`.")
    elif query.data == 'menu_img': await query.edit_message_text("`/tweet` | `/quote` | `/struk` | Kirim Foto buat Filter & ASCII.")
    elif query.data == 'menu_dev': await query.edit_message_text("`/hash` | `/b64` | `/math` | `/caesar` | `/regex` | `/time`")
    elif query.data == 'menu_gen': await query.edit_message_text("`/usn` | `/pass` | `/fake` | `/luhn` | `/cat`")
    elif query.data == 'menu_net': await query.edit_message_text("`/ip` | `/short` | `/cuaca` | `/translate` | `/loc`")
    elif query.data == 'menu_preset': await query.edit_message_text("Ketik `/caripreset [kata_kunci]`\nContoh: `/caripreset jj viral`")

# ═══════════════════════════════════════════════════════════
# FITUR DOWNLOADER, AI & GET IMAGE
# ═══════════════════════════════════════════════════════════
async def download_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/dl [link]`")
    msg = await update.message.reply_text("⏳ Memproses...")
    ydl_opts = {'format': 'best', 'outtmpl': 'downloads/%(id)s.%(ext)s', 'quiet': True}
    try:
        os.makedirs('downloads', exist_ok=True)
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(context.args[0], download=True)
            file_path = ydl.prepare_filename(info)
        await update.message.reply_video(video=open(file_path, 'rb'), caption=f"✅ {info.get('title', 'Video')}")
        os.remove(file_path)
        await msg.delete()
    except Exception as e: await msg.edit_text(f"❌ Gagal: `{str(e)}`")

async def spotify_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/spotify [link_lagu]`")
    url = context.args[0]
    if "spotify.com" not in url: return await update.message.reply_text("❌ Link harus Spotify.")
    msg = await update.message.reply_text("🎵 Mencari lagu...")
    try:
        res = requests.get(f"https://open.spotify.com/oembed?url={url}", timeout=10, verify=False).json()
        title = res.get("title", "Unknown")
        await msg.edit_text(f"⬇️ Mengunduh: **{title}**...")
        ydl_opts = {'format': 'bestaudio/best', 'outtmpl': 'downloads/%(id)s.%(ext)s', 'quiet': True, 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{title} audio", download=True)
            video = info['entries'][0]
            file_path = ydl.prepare_filename(video).replace('.webm', '.mp3').replace('.m4a', '.mp3')
        await update.message.reply_audio(audio=open(file_path, 'rb'), title=title, caption=f"✅ **{title}**")
        os.remove(file_path); await msg.delete()
    except Exception as e: await msg.edit_text(f"❌ Gagal: `{str(e)}`")

async def get_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/getimg [link_gambar/web]`")
    url = context.args[0]
    msg = await update.message.reply_text("🖼️ Mengambil gambar...")
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, timeout=15, headers=headers)
        if 'image' not in r.headers.get('Content-Type', ''):
            soup = BeautifulSoup(r.text, 'html.parser')
            img_tag = soup.find('meta', property='og:image') or soup.find('img')
            if img_tag:
                img_url = img_tag.get('content') if img_tag.name == 'meta' else img_tag.get('src')
                if img_url.startswith('//'): img_url = 'https:' + img_url
                elif img_url.startswith('/'):
                    parsed = urllib.parse.urlparse(url)
                    img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"
                r = requests.get(img_url, timeout=15, headers=headers)
            else: return await msg.edit_text("❌ Nggak nemu gambar.")
        await update.message.reply_photo(photo=r.content, caption="✅ Gambar berhasil diambil!")
        await msg.delete()
    except Exception as e: await msg.edit_text(f"❌ Gagal: `{str(e)}`")

async def ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prompt = " ".join(context.args) if context.args else update.message.text
    msg = await update.message.reply_text("🤖 Mikir...")
    try: await msg.edit_text(requests.get(f"https://text.pollinations.ai/{requests.utils.quote(prompt)}", timeout=15).text)
    except: await msg.edit_text("❌ Error AI.")

async def cari_preset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/caripreset [kata_kunci]`")
    keyword = " ".join(context.args)
    msg = await update.message.reply_text(f"🔍 Mencari preset: **{keyword}**...", parse_mode='Markdown')
    try:
        query = f"site:capcut.com template {keyword} OR site:alightmotion.com {keyword}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        results = soup.find_all('a', class_='result__url')
        if not results: return await msg.edit_text("❌ Nggak nemu link preset.")
        text = f"🎬 **Hasil Preset:**\n\n"
        count = 0
        for res in results:
            if count >= 5: break
            link = res.get('href')
            if link and link.startswith('http'):
                text += f"🔗 {link}\n\n"
                count += 1
        if count == 0: await msg.edit_text("❌ Link nggak valid.")
        else: await msg.edit_text(text, parse_mode='Markdown', disable_web_page_preview=True)
    except Exception as e: await msg.edit_text(f"❌ Gagal: `{str(e)}`")

# ═══════════════════════════════════════════════════════════
# FITUR SCRAPER & TEMP MAIL
# ═══════════════════════════════════════════════════════════
async def web_scraper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/scrape [url]`")
    url = context.args[0] if context.args[0].startswith("http") else "https://" + context.args[0]
    msg = await update.message.reply_text(f"🕸️ Scraping...")
    try:
        r = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        text = re.sub(r'\s+', ' ', BeautifulSoup(r.text, 'html.parser').get_text(separator=' ', strip=True))[:3000]
        await msg.edit_text(f"✅ **Scrape:**\n\n`{text}...`", parse_mode='Markdown')
    except: await msg.edit_text("❌ Gagal Scrape.")

async def scrape_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/scrapeimg [url]`")
    url = context.args[0]
    if not url.startswith("http"): url = "https://" + url
    msg = await update.message.reply_text("🕸️ Mencari gambar...")
    try:
        r = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        images = BeautifulSoup(r.text, 'html.parser').find_all('img')
        img_urls = []
        for img in images:
            src = img.get('src')
            if src:
                if src.startswith('//'): src = 'https:' + src
                elif src.startswith('/'): 
                    parsed = urllib.parse.urlparse(url)
                    src = f"{parsed.scheme}://{parsed.netloc}{src}"
                elif not src.startswith('http'): continue
                if src not in img_urls: img_urls.append(src)
        if not img_urls: return await msg.edit_text("❌ Nggak ada gambar.")
        await msg.edit_text(f"✅ Ditemukan {len(img_urls)} gambar. Mengirim 5...")
        for i, img_url in enumerate(img_urls[:5]):
            try: await update.message.reply_photo(photo=img_url, caption=f"Gambar {i+1}")
            except: pass
        await msg.delete()
    except Exception as e: await msg.edit_text(f"❌ Gagal: `{str(e)}`")

async def fake_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    msg = await update.message.reply_text("📧 Bikin email...")
    try:
        domain = requests.get("https://api.mail.tm/domains", timeout=10).json()['hydra:member'][0]['domain']
        email = f"{''.join(random.choices(string.ascii_lowercase + string.digits, k=10))}@{domain}"
        password = "Password123!"
        res = requests.post("https://api.mail.tm/accounts", json={"address": email, "password": password}, timeout=10)
        if res.status_code == 201:
            token = requests.post("https://api.mail.tm/token", json={"address": email, "password": password}, timeout=10).json().get('token')
            user_sessions[user_id] = {'email': email, 'token': token}
            await msg.edit_text(f"📧 **Email:** `{email}`\n**Pass:** `{password}`\n\n*Ketik `/inbox`.*", parse_mode='Markdown')
        else: await msg.edit_text("❌ API Limit.")
    except: await msg.edit_text("❌ Error.")

async def check_inbox(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_sessions: return await update.message.reply_text("❌ Ketik `/email` dulu.")
    msg = await update.message.reply_text("📥 Cek inbox...")
    try:
        res = requests.get("https://api.mail.tm/messages", headers={"Authorization": f"Bearer {user_sessions[user_id]['token']}"}, timeout=10)
        messages = res.json().get('hydra:member', [])
        if not messages: return await msg.edit_text("📭 Inbox kosong.")
        text = "📥 **Pesan:**\n\n"
        for m in messages[:3]: text += f"**Dari:** `{m['from']['address']}`\n**Isi:** {m['intro']}\n---\n"
        await msg.edit_text(text, parse_mode='Markdown')
    except: await msg.edit_text("❌ Gagal.")

# ═══════════════════════════════════════════════════════════
# FITUR GAMBAR & TEKS
# ═══════════════════════════════════════════════════════════
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🖼️ Memproses (Filter + ASCII)...")
    try:
        img_bytes = await update.message.photo[-1].get_file().download_as_bytearray()
        img_ascii = Image.open(io.BytesIO(img_bytes)).convert('L')
        img_ascii = img_ascii.resize((50, int((img_ascii.height / img_ascii.width) * 50 * 0.5)))
        ascii_str = "".join(["@%#*+=-:. "[p * 10 // 256] for p in img_ascii.getdata()])
        ascii_img = "\n".join([ascii_str[i:(i+50)] for i in range(0, len(ascii_str), 50)])
        
        img_filter = Image.open(io.BytesIO(img_bytes))
        img_filter = ImageOps.autocontrast(ImageOps.grayscale(img_filter))
        buf = io.BytesIO(); img_filter.save(buf, format='PNG'); buf.seek(0)
        
        await update.message.reply_photo(photo=buf, caption="✅ Filter Estetik (B&W)")
        await update.message.reply_text(f"```\n{ascii_img}\n```", parse_mode='Markdown')
        await msg.delete()
    except: await msg.edit_text("❌ Gagal.")

async def tweet_maker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_input = " ".join(context.args)
    if "|" not in text_input: return await update.message.reply_text("Format: `/tweet [teks] | [nama]`")
    quote, name = text_input.split("|", 1)
    msg = await update.message.reply_text("🐦 Bikin Fake Tweet...")
    try:
        img = Image.new('RGB', (600, 250), color=(21, 32, 43))
        d = ImageDraw.Draw(img)
        d.rectangle([20, 20, 80, 80], fill=(100, 100, 100))
        d.text((90, 30), name.strip(), fill=(255, 255, 255))
        d.text((90, 50), "@" + name.strip().replace(" ", "").lower(), fill=(150, 150, 150))
        words = quote.strip().split(); lines, current_line = [], ""
        for word in words:
            if len(current_line + word) < 45: current_line += word + " "
            else: lines.append(current_line); current_line = word + " "
        lines.append(current_line); y_offset = 100
        for line in lines: d.text((30, y_offset), line, fill=(255, 255, 255)); y_offset += 30
        buf = io.BytesIO(); img.save(buf, format='PNG'); buf.seek(0)
        await update.message.reply_photo(photo=buf, caption="✅ Fake Tweet!")
        await msg.delete()
    except: await msg.edit_text("❌ Gagal.")

async def quote_maker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text_input = " ".join(context.args)
    if "|" not in text_input: return await update.message.reply_text("Format: `/quote [teks] | [nama]`")
    quote, name = text_input.split("|", 1)
    msg = await update.message.reply_text("🖼️ Bikin quote...")
    try:
        img = Image.new('RGB', (600, 300), color=(21, 32, 43))
        d = ImageDraw.Draw(img); d.text((30, 30), name.strip(), fill=(255, 255, 255)); d.text((30, 120), quote.strip()[:50], fill=(255, 255, 255))
        buf = io.BytesIO(); img.save(buf, format='PNG'); buf.seek(0)
        await update.message.reply_photo(photo=buf, caption="✅ Quote."); await msg.delete()
    except: await msg.edit_text("❌ Gagal.")

async def fake_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2: return await update.message.reply_text("Format: `/struk [nominal] [nama]`")
    msg = await update.message.reply_text("🧾 Bikin struk...")
    try:
        img = Image.new('RGB', (400, 500), color=(255, 255, 255))
        d = ImageDraw.Draw(img); d.text((20, 20), "STRUK TRANSFER DANA", fill=(0, 0, 0)); d.text((20, 110), f"Penerima: {context.args[1]}", fill=(0, 0, 0)); d.text((20, 140), f"Nominal: Rp {context.args[0]}", fill=(0, 0, 0))
        buf = io.BytesIO(); img.save(buf, format='PNG'); buf.seek(0)
        await update.message.reply_photo(photo=buf, caption=f"✅ Struk."); await msg.delete()
    except: await msg.edit_text("❌ Gagal.")

# ═══════════════════════════════════════════════════════════
# FITUR DEV TOOLS & GENERATORS
# ═══════════════════════════════════════════════════════════
async def hash_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/hash [teks]`")
    text = " ".join(context.args)
    await update.message.reply_text(f"🔐 MD5: `{hashlib.md5(text.encode()).hexdigest()}`\nSHA256: `{hashlib.sha256(text.encode()).hexdigest()}`", parse_mode='Markdown')

async def b64_tool(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2: return await update.message.reply_text("Format: `/b64 [encode/decode] [teks]`")
    try:
        res = base64.b64encode(" ".join(context.args[1:]).encode()).decode() if context.args[0] == "encode" else base64.b64decode(" ".join(context.args[1:]).encode()).decode()
        await update.message.reply_text(f"📦 `{res}`", parse_mode='Markdown')
    except: await update.message.reply_text("❌ Gagal.")

async def math_calc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/math [soal]`")
    expr = " ".join(context.args).replace("x", "*").replace(":", "/")
    try:
        if not re.match(r"^[0-9+\-*/().\s]+$", expr): raise ValueError
        await update.message.reply_text(f"🧮 `{eval(expr)}`", parse_mode='Markdown')
    except: await update.message.reply_text("❌ Format salah.")

async def caesar_cipher(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2: return await update.message.reply_text("Format: `/caesar [shift] [teks]`")
    try:
        shift, text = int(context.args[0]), " ".join(context.args[1:])
        res = "".join([chr((ord(c) - (ord('A') if c.isupper() else ord('a')) + shift) % 26 + (ord('A') if c.isupper() else ord('a'))) if c.isalpha() else c for c in text])
        await update.message.reply_text(f"🔐 `{res}`", parse_mode='Markdown')
    except: await update.message.reply_text("❌ Shift harus angka.")

async def regex_tester(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2: return await update.message.reply_text("Format: `/regex [pola] [teks]`")
    try:
        matches = re.findall(context.args[0], " ".join(context.args[1:]))
        await update.message.reply_text("🔍 **Match:**\n" + "\n".join([f"• `{m}`" for m in matches[:20]]) if matches else "❌ Tidak ada match.", parse_mode='Markdown')
    except: await update.message.reply_text("❌ Regex salah.")

async def timestamp_converter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/time [timestamp/tanggal]`")
    input_str = " ".join(context.args)
    try:
        if input_str.isdigit(): await update.message.reply_text(f"⏱️ `{input_str}`\n📅 `{datetime.fromtimestamp(int(input_str)).strftime('%Y-%m-%d %H:%M:%S')}`", parse_mode='Markdown')
        else: await update.message.reply_text(f"📅 `{input_str}`\n⏱️ `{int(datetime.strptime(input_str, '%Y-%m-%d %H:%M:%S').timestamp())}`", parse_mode='Markdown')
    except: await update.message.reply_text("❌ Format salah.")

async def usn_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/usn [kata]`")
    base = context.args[0].lower(); msg = await update.message.reply_text("✨ Generate...")
    res = set()
    while len(res) < 15:
        s = random.randint(1, 3)
        if s == 1: res.add(f"real.{base}")
        elif s == 2: res.add(f"{base}{random.choice(['01','99','666','69'])}")
        else: res.add(f"{base}_id")
    await msg.edit_text("✨ **Username:**\n" + "\n".join([f"{i}. `{r}`" for i, r in enumerate(res, 1)]), parse_mode='Markdown')

async def pass_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    length = int(context.args[0]) if context.args and context.args[0].isdigit() else 16
    await update.message.reply_text(f"🔑 `{''.join(secrets.choice(string.ascii_letters + string.digits + '!@#$%^&*') for i in range(length))}`", parse_mode='Markdown')

async def fake_identity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🆔 Generate...")
    try:
        user = requests.get("https://randomuser.me/api/", timeout=10).json()['results'][0]
        await msg.edit_text(f"👤 **Nama:** `{user['name']['first']} {user['name']['last']}`\n📧 **Email:** `{user['email']}`\n📍 **Kota:** `{user['location']['city']}`", parse_mode='Markdown')
    except: await msg.edit_text("❌ Gagal.")

async def luhn_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/luhn [nomor]`")
    card = context.args[0].replace(" ", "").replace("-", "")
    if not card.isdigit(): return await update.message.reply_text("❌ Angka only.")
    try:
        digits = [int(d) for d in card]; checksum = 0; parity = len(digits) % 2
        for i, d in enumerate(digits):
            if i % 2 == parity: d *= 2; d = d - 9 if d > 9 else d
            checksum += d
        await update.message.reply_text(f"💳 **Luhn:**\n`{card}`\nStatus: **{'✅ VALID' if checksum % 10 == 0 else '❌ INVALID'}**", parse_mode='Markdown')
    except: await update.message.reply_text("❌ Gagal.")

async def random_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🐱 Nyari kucing...")
    try:
        res = requests.get("https://api.thecatapi.com/v1/images/search", timeout=10).json()
        await update.message.reply_photo(photo=res[0]['url'], caption="✅ Kucing random.")
        await msg.delete()
    except: await msg.edit_text("❌ Gagal.")

# ═══════════════════════════════════════════════════════════
# FITUR NETWORK TOOLS
# ═══════════════════════════════════════════════════════════
async def ip_tracker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/ip [ip]`")
    msg = await update.message.reply_text("🌍 Cek IP...")
    try:
        res = requests.get(f"http://ip-api.com/json/{context.args[0]}", timeout=10).json()
        if res['status'] == 'success': await msg.edit_text(f"📍 `{res['query']}`\nNegara: `{res['country']}`\nISP: `{res['isp']}`", parse_mode='Markdown')
        else: await msg.edit_text("❌ IP invalid.")
    except: await msg.edit_text("❌ Gagal.")

async def shortlink_gen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/short [link]`")
    url = context.args[0] if context.args[0].startswith("http") else "https://" + context.args[0]
    msg = await update.message.reply_text("🔗 Shortlink...")
    try:
        res = requests.get(f"https://is.gd/create.php?format=simple&url={requests.utils.quote(url)}", timeout=10)
        await msg.edit_text(f"✅ `{res.text}`", parse_mode='Markdown')
    except: await msg.edit_text("❌ Gagal.")

async def weather_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/cuaca [kota]`")
    msg = await update.message.reply_text(f"🌤️ Cek cuaca...")
    try:
        res = requests.get(f"https://wttr.in/{requests.utils.quote(' '.join(context.args))}?format=j1", timeout=10).json()
        await msg.edit_text(f"🌤️ **{' '.join(context.args)}**\nSuhu: `{res['current_condition'][0]['temp_C']}°C`", parse_mode='Markdown')
    except: await msg.edit_text("❌ Gagal.")

async def translate_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2: return await update.message.reply_text("Format: `/translate [kode] [teks]`")
    msg = await update.message.reply_text("🌐 Menerjemahkan...")
    try:
        res = requests.get(f"https://api.mymemory.translated.net/get?q={requests.utils.quote(' '.join(context.args[1:]))}&langpair=id|{context.args[0]}", timeout=10).json()
        await msg.edit_text(f"🌐 `{res['responseData']['translatedText']}`", parse_mode='Markdown')
    except: await msg.edit_text("❌ Gagal.")

async def fake_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args: return await update.message.reply_text("Format: `/loc [kota]`")
    msg = await update.message.reply_text(f"📍 Nyari lokasi...")
    try:
        res = requests.get(f"https://nominatim.openstreetmap.org/search?q={requests.utils.quote(' '.join(context.args))}&format=json&limit=1", headers={'User-Agent': 'Bot'}, timeout=10).json()
        if res: await msg.edit_text(f"📍 `{res[0]['lat']}, {res[0]['lon']}`\n[Maps](https://www.google.com/maps?q={res[0]['lat']},{res[0]['lon']})", parse_mode='Markdown')
        else: await msg.edit_text("❌ Kota tidak ada.")
    except: await msg.edit_text("❌ Gagal.")

# ═══════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(menu_callback))
    
    app.add_handler(CommandHandler("dl", download_media))
    app.add_handler(CommandHandler("spotify", spotify_download))
    app.add_handler(CommandHandler("getimg", get_image))
    app.add_handler(CommandHandler("ai", ai_chat))
    app.add_handler(CommandHandler("caripreset", cari_preset))
    app.add_handler(CommandHandler("scrape", web_scraper))
    app.add_handler(CommandHandler("scrapeimg", scrape_images))
    
    app.add_handler(CommandHandler("email", fake_email))
    app.add_handler(CommandHandler("inbox", check_inbox))
    
    app.add_handler(CommandHandler("tweet", tweet_maker))
    app.add_handler(CommandHandler("quote", quote_maker))
    app.add_handler(CommandHandler("struk", fake_receipt))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    app.add_handler(CommandHandler("hash", hash_gen))
    app.add_handler(CommandHandler("b64", b64_tool))
    app.add_handler(CommandHandler("math", math_calc))
    app.add_handler(CommandHandler("caesar", caesar_cipher))
    app.add_handler(CommandHandler("regex", regex_tester))
    app.add_handler(CommandHandler("time", timestamp_converter))
    
    app.add_handler(CommandHandler("usn", usn_gen))
    app.add_handler(CommandHandler("pass", pass_gen))
    app.add_handler(CommandHandler("fake", fake_identity))
    app.add_handler(CommandHandler("luhn", luhn_checker))
    app.add_handler(CommandHandler("cat", random_cat))
    
    app.add_handler(CommandHandler("ip", ip_tracker))
    app.add_handler(CommandHandler("short", shortlink_gen))
    app.add_handler(CommandHandler("cuaca", weather_check))
    app.add_handler(CommandHandler("translate", translate_text))
    app.add_handler(CommandHandler("loc", fake_location))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, ai_chat))

    print("[@Cancer666] Bot v46 berjalan...")
    app.run_polling()

if __name__ == '__main__':
    main()
