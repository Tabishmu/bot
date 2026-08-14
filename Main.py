import os
import shutil
import uuid
import threading
from pathlib import Path
from urllib.parse import urlparse
from flask import Flask
import telebot
from telebot import types
from yt_dlp import YoutubeDL

# ویب‌سرور برای زنده نگه داشتن در Render
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

threading.Thread(target=run_flask, daemon=True).start()

# تنظیمات ربات
BOT_TOKEN = os.getenv("BOT_TOKEN", "8822372631:AAHYdu3WSQB11WBlDsshcxUHlj5SGDeIsoU")
ADMIN_ID = 7939442809
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True)

DOWNLOAD_ROOT = Path("downloads")
DOWNLOAD_ROOT.mkdir(exist_ok=True)

# فقط ۱ دانلود در لحظه برای جلوگیری از پر شدن رم ۵۱۲ مگابایتی
download_semaphore = threading.BoundedSemaphore(1)
user_urls = {}

def is_valid_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False

def download_media(url, mode, folder):
    output_template = str(folder / "%(title).50s.%(ext)s")
    
    options = {
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "playlist_items": "1"
    }

    if mode == "audio":
        options.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128"
            }]
        })
    elif mode == "image":
        options.update({
            "skip_download": True,
            "writethumbnail": True,
            "postprocessors": [{
                "key": "FFmpegThumbnailsConvertor",
                "format": "jpg"
            }]
        })
    else:
        # کیفیت محدود به 480p برای مصرف رم بسیار کم
        options.update({
            "format": "bestvideo[height<=480]+bestaudio/best[height<=480]/best",
            "merge_output_format": "mp4"
        })

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        files = [p for p in folder.rglob("*") if p.is_file()]
        return {"title": info.get("title", "Media"), "files": files}

@bot.message_handler(commands=["start"])
def start_cmd(message):
    bot.send_message(message.chat.id, "🤖 :")

@bot.message_handler(func=lambda m: m.text and is_valid_url(m.text.strip()))
def get_link(message):
    user_urls[message.from_user.id] = message.text.strip()
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🎬 ویدیو (کم حجم)", callback_data="dl_video"),
        types.InlineKeyboardButton("🎵 موزیک", callback_data="dl_audio")
    )
    bot.send_message(message.chat.id, "فرمت را انتخاب کنید:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["dl_video", "dl_audio"])
def process_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    url = user_urls.get(user_id)

    if not url:
        bot.answer_callback_query(call.id, "❌ لینک یافت نشد.")
        return

    bot.answer_callback_query(call.id, "در حال پردازش...")
    status = bot.send_message(chat_id, "⏳ در حال دانلود (لطفاً صبور باشید)...")
    mode = "video" if call.data == "dl_video" else "audio"

    threading.Thread(
        target=worker,
        args=(user_id, chat_id, url, mode, status.message_id),
        daemon=True
    ).start()

def worker(user_id, chat_id, url, mode, status_msg_id):
    folder = DOWNLOAD_ROOT / str(user_id) / str(uuid.uuid4())
    folder.mkdir(parents=True, exist_ok=True)

    try:
        # قفل برای دانلود یک‌به‌یک جهت عدم پر شدن رم
        with download_semaphore:
            result = download_media(url, mode, folder)

        files = result["files"]
        if not files:
            raise RuntimeError("فایل یافت نشد.")

        bot.edit_message_text("📤 در حال ارسال به تلگرام...", chat_id, status_msg_id)

        for file_path in files:
            with open(file_path, "rb") as media:
                if mode == "audio":
                    bot.send_audio(chat_id, media, caption=result['title'])
                else:
                    bot.send_video(chat_id, media, caption=result['title'])

        bot.delete_message(chat_id, status_msg_id)

    except Exception:
        bot.edit_message_text("❌ خطا در دانلود! ویدیو خیلی سنگین است یا لینک معتبر نیست.", chat_id, status_msg_id)
    finally:
        user_urls.pop(user_id, None)
        shutil.rmtree(folder, ignore_errors=True)

if __name__ == "__main__":
    bot.infinity_polling(skip_pending=True)
