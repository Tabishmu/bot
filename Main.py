import os
import re
import time
import shutil
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse

import telebot
from telebot import types
from dotenv import load_dotenv
from yt_dlp import YoutubeDL


# =========================================================
# CONFIG
# =========================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("8822372631:AAHYi5RCR5g5tlwvId4Pr5f7qHYeCTqLjL4")

bot = telebot.TeleBot(
    BOT_TOKEN,
    parse_mode="HTML",
    threaded=True,
    num_threads=8
)

DOWNLOAD_ROOT = Path("downloads")
DOWNLOAD_ROOT.mkdir(exist_ok=True)

# حداکثر حجم تقریبی فایل برای ارسال به تلگرام
# مقدار را متناسب با Bot API/سرورت تنظیم کن.
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "49"))

MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024

# تعداد دانلود همزمان
MAX_CONCURRENT_DOWNLOADS = int(
    os.getenv("MAX_CONCURRENT_DOWNLOADS", "3")
)

download_semaphore = threading.BoundedSemaphore(
    MAX_CONCURRENT_DOWNLOADS
)

# اطلاعات موقت کاربران
user_urls = {}
user_locks = {}
user_last_download = {}


# =========================================================
# HELPERS
# =========================================================

def get_user_lock(user_id):
    if user_id not in user_locks:
        user_locks[user_id] = threading.Lock()

    return user_locks[user_id]


def is_valid_url(url):
    try:
        parsed = urlparse(url)

        return (
            parsed.scheme in ("http", "https")
            and bool(parsed.netloc)
        )

    except Exception:
        return False


def clean_url(url):
    return url.strip()


def safe_filename(name):
    """
    حذف کاراکترهای مشکل‌ساز از نام فایل.
    """

    name = str(name or "download")

    name = re.sub(
        r'[<>:"/\\|?*\x00-\x1F]',
        "_",
        name
    )

    name = name.strip()

    if not name:
        name = "download"

    return name[:120]


def get_downloaded_file(folder):
    """
    جدیدترین فایل دانلود شده را پیدا می‌کند.
    """

    files = [
        p for p in folder.rglob("*")
        if p.is_file()
    ]

    if not files:
        return None

    return max(
        files,
        key=lambda p: p.stat().st_mtime
    )


def format_size(size):
    if size < 1024:
        return f"{size} B"

    if size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"

    if size < 1024 ** 3:
        return f"{size / (1024 ** 2):.1f} MB"

    return f"{size / (1024 ** 3):.2f} GB"


def progress_hook_factory(bot_instance, chat_id, message_id):
    """
    ساخت progress hook برای yt-dlp.
    """

    last_update = {
        "time": 0,
        "percent": -1
    }

    def hook(data):

        if data["status"] == "downloading":

            downloaded = data.get("downloaded_bytes", 0)
            total = (
                data.get("total_bytes")
                or data.get("total_bytes_estimate")
                or 0
            )

            if total:
                percent = int(
                    downloaded * 100 / total
                )

                now = time.time()

                # هر 3 ثانیه یک بار پیام را آپدیت کن
                if (
                    now - last_update["time"] >= 3
                    and percent != last_update["percent"]
                ):
                    last_update["time"] = now
                    last_update["percent"] = percent

                    speed = data.get(
                        "speed",
                        0
                    )

                    eta = data.get(
                        "eta"
                    )

                    speed_text = (
                        f"{format_size(speed)}/s"
                        if speed
                        else "..."
                    )

                    eta_text = (
                        f"{eta}s"
                        if eta is not None
                        else "..."
                    )

                    try:
                        bot_instance.edit_message_text(
                            (
                                f"⬇️ <b>در حال دانلود...</b>\n\n"
                                f"📊 پیشرفت: <b>{percent}%</b>\n"
                                f"📦 حجم: "
                                f"{format_size(downloaded)} / "
                                f"{format_size(total)}\n"
                                f"⚡ سرعت: <b>{speed_text}</b>\n"
                                f"⏱ زمان باقی‌مانده: <b>{eta_text}</b>"
                            ),
                            chat_id,
                            message_id
                        )
                    except Exception:
                        pass

        elif data["status"] == "finished":

            try:
                bot_instance.edit_message_text(
                    "🔄 دانلود تمام شد.\n"
                    "⚙️ در حال آماده‌سازی فایل...",
                    chat_id,
                    message_id
                )
            except Exception:
                pass

    return hook


# =========================================================
# DOWNLOAD
# =========================================================

def download_media(
    url,
    mode,
    folder,
    bot_instance,
    chat_id,
    status_message_id
):
    """
    mode:
        video
        audio
    """

    progress_hook = progress_hook_factory(
        bot_instance,
        chat_id,
        status_message_id
    )

    output_template = str(
        folder / "%(title).100s.%(ext)s"
    )

    common = {
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [progress_hook],

        # تلاش برای رعایت محدودیت حجم
        "max_filesize": MAX_FILE_SIZE,

        # جلوگیری از دانلود Playlist
        "playlist_items": "1",
    }

    if mode == "audio":

        options = {
            **common,

            "format": (
                "bestaudio/best"
            ),

            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                },
                {
                    "key": "FFmpegMetadata",
                },
            ],
        }

    else:

        options = {
            **common,

            # کیفیت مناسب ولی نه بیش از حد سنگین
            "format": (
                "bestvideo[height<=1080]+"
                "bestaudio/"
                "best[height<=1080]/"
                "best"
            ),

            "merge_output_format": "mp4",

            "postprocessors": [
                {
                    "key": "FFmpegMetadata",
                }
            ],
        }

    with YoutubeDL(options) as ydl:

        info = ydl.extract_info(
            url,
            download=True
        )

        title = info.get(
            "title",
            "Downloaded"
        )

        uploader = info.get(
            "uploader"
        )

        duration = info.get(
            "duration"
        )

        return {
            "title": title,
            "uploader": uploader,
            "duration": duration,
            "file": get_downloaded_file(folder)
        }


# =========================================================
# START
# =========================================================

@bot.message_handler(commands=["start"])
def start_cmd(message):

    text = (
        "🤖 <b>دانلودر حرفه‌ای</b>\n\n"
        "سلام 👋\n"
        "لینک ویدیو، موزیک یا فایل موردنظرت را بفرست.\n\n"
        "🎬 ویدیو\n"
        "🎵 موزیک / MP3\n"
        "🖼 عکس از لینک مستقیم\n\n"
        "⚡ سریع و ساده"
    )

    bot.send_message(
        message.chat.id,
        text
    )


# =========================================================
# HELP
# =========================================================

@bot.message_handler(commands=["help"])
def help_cmd(message):

    bot.send_message(
        message.chat.id,
        (
            "📚 <b>راهنما</b>\n\n"
            "1️⃣ لینک را ارسال کن.\n"
            "2️⃣ نوع دانلود را انتخاب کن.\n"
            "3️⃣ منتظر آماده شدن فایل بمان.\n\n"
            "دستورها:\n"
            "/start - شروع\n"
            "/help - راهنما\n"
            "/cancel - لغو لینک فعلی"
        )
    )


# =========================================================
# CANCEL
# =========================================================

@bot.message_handler(commands=["cancel"])
def cancel_cmd(message):

    user_urls.pop(
        message.from_user.id,
        None
    )

    bot.send_message(
        message.chat.id,
        "✅ لینک فعلی پاک شد."
    )


# =========================================================
# NEW MEMBERS
# =========================================================

@bot.message_handler(
    content_types=["new_chat_members"]
)
def welcome_members(message):

    for member in message.new_chat_members:

        if member.is_bot:
            continue

        name = member.first_name or "دوست عزیز"

        bot.send_message(
            message.chat.id,
            f"👋 سلام <b>{name}</b> عزیز!\n"
            "به گروه خوش آمدی 🌹"
        )


# =========================================================
# URL RECEIVER
# =========================================================

@bot.message_handler(
    func=lambda m: (
        m.text
        and is_valid_url(m.text.strip())
    )
)
def get_link(message):

    user_id = message.from_user.id
    url = clean_url(message.text)

    user_urls[user_id] = url

    markup = types.InlineKeyboardMarkup(
        row_width=2
    )

    markup.add(

        types.InlineKeyboardButton(
            "🎬 ویدیو",
            callback_data="download_video"
        ),

        types.InlineKeyboardButton(
            "🎵 MP3",
            callback_data="download_audio"
        )
    )

    markup.add(

        types.InlineKeyboardButton(
            "❌ لغو",
            callback_data="cancel_download"
        )
    )

    bot.send_message(
        message.chat.id,
        (
            "🔗 <b>لینک دریافت شد.</b>\n\n"
            "فرمت موردنظر را انتخاب کن:"
        ),
        reply_markup=markup
    )


# =========================================================
# CALLBACK
# =========================================================

@bot.callback_query_handler(
    func=lambda call: call.data in [
        "download_video",
        "download_audio",
        "cancel_download"
    ]
)
def process_download(call):

    user_id = call.from_user.id
    chat_id = call.message.chat.id

    # لغو
    if call.data == "cancel_download":

        user_urls.pop(
            user_id,
            None
        )

        bot.answer_callback_query(
            call.id,
            "لغو شد."
        )

        try:
            bot.edit_message_text(
                "❌ دانلود لغو شد.",
                chat_id,
                call.message.message_id
            )
        except Exception:
            pass

        return

    url = user_urls.get(user_id)

    if not url:

        bot.answer_callback_query(
            call.id,
            "❌ لینک منقضی شده است."
        )

        return

    bot.answer_callback_query(
        call.id,
        "شروع دانلود..."
    )

    # جلوگیری از چند دانلود همزمان توسط یک کاربر
    lock = get_user_lock(user_id)

    if not lock.acquire(blocking=False):

        bot.send_message(
            chat_id,
            "⏳ یک دانلود دیگر برای شما در حال انجام است."
        )

        return

    # وضعیت دانلود
    try:

        status_message = bot.send_message(
            chat_id,
            (
                "⏳ <b>در حال آماده‌سازی...</b>\n\n"
                "ممکن است چند لحظه طول بکشد."
            )
        )

    except Exception:

        lock.release()
        return

    # اجرای دانلود در Thread جدا
    thread = threading.Thread(
        target=download_worker,
        args=(
            user_id,
            chat_id,
            url,
            call.data,
            status_message.message_id,
            lock
        ),
        daemon=True
    )

    thread.start()


# =========================================================
# WORKER
# =========================================================

def download_worker(
    user_id,
    chat_id,
    url,
    callback_data,
    status_message_id,
    lock
):

    folder = (
        DOWNLOAD_ROOT
        / str(user_id)
        / str(uuid.uuid4())
    )

    folder.mkdir(
        parents=True,
        exist_ok=True
    )

    mode = (
        "audio"
        if callback_data == "download_audio"
        else "video"
    )

    try:

        # صف کلی دانلودها
        acquired = download_semaphore.acquire(
            timeout=60
        )

        if not acquired:

            bot.edit_message_text(
                "⏳ سرور شلوغ است. لطفاً کمی بعد دوباره امتحان کن.",
                chat_id,
                status_message_id
            )

            return

        try:

            bot.edit_message_text(
                (
                    "🔎 <b>در حال بررسی لینک...</b>\n\n"
                    "🌐 دریافت اطلاعات رسانه..."
                ),
                chat_id,
                status_message_id
            )

            result = download_media(
                url=url,
                mode=mode,
                folder=folder,
                bot_instance=bot,
                chat_id=chat_id,
                status_message_id=status_message_id
            )

        finally:

            download_semaphore.release()

        file_path = result["file"]

        if not file_path or not file_path.exists():

            raise RuntimeError(
                "فایل خروجی پیدا نشد."
            )

        file_size = file_path.stat().st_size

        if file_size > MAX_FILE_SIZE:

            bot.edit_message_text(
                (
                    "❌ <b>فایل بیش از حد مجاز است.</b>\n\n"
                    f"حجم فایل: {format_size(file_size)}\n"
                    f"حد مجاز: {format_size(MAX_FILE_SIZE)}"
                ),
                chat_id,
                status_message_id
            )

            return

        bot.edit_message_text(
            (
                "📤 <b>دانلود کامل شد.</b>\n"
                "📦 در حال ارسال فایل به تلگرام..."
            ),
            chat_id,
            status_message_id
        )

        title = result["title"]

        caption = (
            f"📥 <b>{safe_filename(title)}</b>\n\n"
            f"⚡ دانلود شده توسط ربات"
        )

        # ارسال
        with open(file_path, "rb") as media:

            if mode == "audio":

                bot.send_audio(
                    chat_id,
                    media,
                    caption=caption,
                    title=title[:64]
                )

            else:

                bot.send_video(
                    chat_id,
                    media,
                    caption=caption,
                    supports_streaming=True
                )

        # حذف پیام وضعیت
        try:
            bot.delete_message(
                chat_id,
                status_message_id
            )
        except Exception:
            pass

    except Exception as error:

        print(
            f"[ERROR] user={user_id} "
            f"url={url} "
            f"error={repr(error)}"
        )

        error_text = str(error).lower()

        if "max-filesize" in error_text:
            message = (
                "❌ فایل بزرگ‌تر از حد مجاز است."
            )

        elif "unsupported url" in error_text:
            message = (
                "❌ این لینک توسط سیستم دانلود پشتیبانی نمی‌شود."
            )

        elif "private" in error_text:
            message = (
                "🔒 این محتوا خصوصی است و قابل دریافت نیست."
            )

        elif "sign in" in error_text:
            message = (
                "🔐 این سرویس برای این محتوا نیاز به ورود دارد."
            )

        else:
            message = (
                "❌ دانلود انجام نشد.\n\n"
                "ممکن است لینک خراب، خصوصی، منقضی "
                "یا توسط سایت مقصد محدود شده باشد."
            )

        try:
            bot.edit_message_text(
                message,
                chat_id,
                status_message_id
            )
        except Exception:
            bot.send_message(
                chat_id,
                message
            )

    finally:

        user_urls.pop(
            user_id,
            None
        )

        try:
            shutil.rmtree(
                folder,
                ignore_errors=True
            )
        except Exception:
            pass

        lock.release()


# =========================================================
# DIRECT IMAGE URL
# =========================================================

@bot.message_handler(
    func=lambda m: (
        m.text
        and is_valid_url(m.text.strip())
        and re.search(
            r"\.(jpg|jpeg|png|webp|gif)(\?.*)?$",
            m.text.strip(),
            re.IGNORECASE
        )
    )
)
def direct_image(message):

    # این handler فقط برای لینک‌های مستقیم عکس است.
    # در صورت نیاز می‌توان requests/httpx را اضافه کرد.
    bot.send_message(
        message.chat.id,
        (
            "🖼 لینک مستقیم عکس شناسایی شد.\n"
            "برای دریافت مستقیم، قابلیت image downloader "
            "را می‌توان به نسخه بعدی اضافه کرد."
        )
    )


# =========================================================
# FALLBACK
# =========================================================

@bot.message_handler(
    func=lambda m: True,
    content_types=["text"]
)
def fallback(message):

    bot.send_message(
        message.chat.id,
        (
            "🤔 متوجه نشدم.\n\n"
            "یک لینک ویدیو/موزیک بفرست تا گزینه‌های دانلود "
            "را برایت نمایش بدهم.\n\n"
            "راهنما: /help"
        )
    )


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    print("=" * 50)
    print("🤖 Downloader Bot Started")
    print("=" * 50)

    while True:

        try:

            bot.infinity_polling(
                skip_pending=True,
                timeout=30,
                long_polling_timeout=30
            )

        except Exception as error:

            print(
                "[POLLING ERROR]",
                repr(error)
            )

            time.sleep(5)
