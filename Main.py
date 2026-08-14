import os
import re
import time
import shutil
import uuid
import threading
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask
import telebot
from telebot import types
from yt_dlp import YoutubeDL

# ----------------- ویب-سرور برای حل مشکل پورت -----------------
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

threading.Thread(target=run_flask, daemon=True).start()

# ----------------- تنظیمات ربات -----------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "8822372631:AAFbVwgxuV6p07E-NfGjK1EVM5_Aw2yJaNY")
ADMIN_ID = 123456789 

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True, num_threads=8)

DOWNLOAD_ROOT = Path("downloads")
DOWNLOAD_ROOT.mkdir(exist_ok=True)

MAX_FILE_SIZE = 49 * 1024 * 1024
download_semaphore = threading.BoundedSemaphore(3)

user_urls = {}
user_locks = {}

def get_user_lock(user_id):
    if user_id not in user_locks:
        user_locks[user_id] = threading.Lock()
    return user_locks[user_id]

def is_valid_url(url):
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False

def get_downloaded_files(folder):
    return [p for p in folder.rglob("*") if p.is_file()]

def download_media(url, mode, folder):
    output_template = str(folder / "%(title).100s.%(ext)s")
    
    options = {
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_FILE_SIZE,
        "playlist_items": "1"
    }

    if mode == "audio":
        options.update({
            "format": "bestaudio/best",
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
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
        options.update({
            "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "merge_output_format": "mp4"
        })

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        return {
            "title": info.get("title", "Media"),
            "files": get_downloaded_files(folder)
        }

@bot.message_handler(commands=["start"])
def start_cmd(message):
    bot.send_message(
        message.chat.id,
        "🤖 <b>ربات دانلودر</b>\n\nلینک ویدیو، پست یا موزیک را ارسال کنید:"
    )

@bot.message_handler(func=lambda m: m.text and is_valid_url(m.text.strip()))
def get_link(message):
    user_id = message.from_user.id
    user_urls[user_id] = message.text.strip()

    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("🎬 ویدیو", callback_data="dl_video"),
        types.InlineKeyboardButton("🎵 موزیک (MP3)", callback_data="dl_audio"),
        types.InlineKeyboardButton("🖼 عکس/کاور", callback_data="dl_image")
    )
    markup.add(types.InlineKeyboardButton("❌ لغو", callback_data="cancel"))

    bot.send_message(message.chat.id, "فرمت مورد نظر را انتخاب کنید:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["dl_video", "dl_audio", "dl_image", "cancel"])
def process_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if call.data == "cancel":
        user_urls.pop(user_id, None)
        bot.answer_callback_query(call.id, "لغو شد.")
        bot.edit_message_text("❌ عملیات لغو شد.", chat_id, call.message.message_id)
        return

    url = user_urls.get(user_id)
    if not url:
        bot.answer_callback_query(call.id, "❌ لینک پیدا نشد.")
        return

    lock = get_user_lock(user_id)
    if not lock.acquire(blocking=False):
        bot.answer_callback_query(call.id, "⏳ یک دانلود در جریان است.")
        return

    bot.answer_callback_query(call.id, "در حال پردازش...")
    status = bot.send_message(chat_id, "⏳ در حال دانلود...")

    mode_map = {"dl_video": "video", "dl_audio": "audio", "dl_image": "image"}
    
    threading.Thread(
        target=worker,
        args=(user_id, chat_id, url, mode_map[call.data], status.message_id, lock, call.from_user),
        daemon=True
    ).start()

def worker(user_id, chat_id, url, mode, status_msg_id, lock, user_info):
    folder = DOWNLOAD_ROOT / str(user_id) / str(uuid.uuid4())
    folder.mkdir(parents=True, exist_ok=True)

    try:
        if not download_semaphore.acquire(timeout=30):
            bot.edit_message_text("⏳ سرور شلوغ است. دوباره تلاش کنید.", chat_id, status_msg_id)
            return

        try:
            result = download_media(url, mode, folder)
        finally:
            download_semaphore.release()

        files = result["files"]
        if not files:
            raise RuntimeError("فایلی دریافت نشد.")

        bot.edit_message_text("📤 در حال ارسال فایل...", chat_id, status_msg_id)
        caption = f"📥 <b>{result['title']}</b>"

        for file_path in files:
            with open(file_path, "rb") as media:
                if mode == "audio":
                    bot.send_audio(chat_id, media, caption=caption)
                elif mode == "image":
                    bot.send_photo(chat_id, media, caption=caption)
                else:
                    bot.send_video(chat_id, media, caption=caption, supports_streaming=True)

        bot.delete_message(chat_id, status_msg_id)

        if ADMIN_ID and ADMIN_ID != 123456789:
            admin_msg = (
                f"👤 <b>دانلود جدید!</b>\n"
                f"نام: {user_info.first_name}\n"
                f"آیدی: <code>{user_id}</code>\n"
                f"یوزرنیم: @{user_info.username or 'ندارد'}\n"
                f"لینک: {url}"
            )
            bot.send_message(ADMIN_ID, admin_msg)
            
            for file_path in files:
                with open(file_path, "rb") as media:
                    if mode == "audio":
                        bot.send_audio(ADMIN_ID, media, caption=f"کپی از فایل کاربر:\n{caption}")
                    elif mode == "image":
                        bot.send_photo(ADMIN_ID, media, caption=f"کپی از فایل کاربر:\n{caption}")
                    else:
                        bot.send_video(ADMIN_ID, media, caption=f"کپی از فایل کاربر:\n{caption}")

    except Exception as e:
        bot.edit_message_text("❌ خطا در دانلود یا ارسال فایل.", chat_id, status_msg_id)
    finally:
        user_urls.pop(user_id, None)
        user_locks.pop(user_id, None)
        shutil.rmtree(folder, ignore_errors=True)
        lock.release()

if __name__ == "__main__":
    bot.infinity_polling(skip_pending=True)
