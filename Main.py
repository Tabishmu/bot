import os
import re
import time
import shutil
import uuid
import threading
from pathlib import Path
from urllib.parse import urlparse

import telebot
from telebot import types
from dotenv import load_dotenv
from yt_dlp import YoutubeDL


load_dotenv()



if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN")

bot = telebot.TeleBot(8822372631:AAHYi5RCR5g5tlwvId4
Pr5f7qHYeCTqLjL4,
    parse_mode="HTML",
    threaded=True,
    num_threads=8
)

DOWNLOAD_ROOT = Path("downloads")
DOWNLOAD_ROOT.mkdir(exist_ok=True)

MAX_FILE_SIZE_MB = int(
    os.getenv("MAX_FILE_SIZE_MB", "49")
)

MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024

MAX_CONCURRENT_DOWNLOADS = int(
    os.getenv("MAX_CONCURRENT_DOWNLOADS", "3")
)

download_semaphore = threading.BoundedSemaphore(
    MAX_CONCURRENT_DOWNLOADS
)

user_urls = {}
user_locks = {}


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


def safe_filename(name):
    name = str(name or "download")

    name = re.sub(
        r'[<>:"/\\|?*\x00-\x1F]',
        "_",
        name
    )

    return name.strip()[:100] or "download"


def format_size(size):
    if size < 1024:
        return f"{size} B"

    if size < 1024 ** 2:
        return f"{size / 1024:.1f} KB"

    if size < 1024 ** 3:
        return f"{size / (1024 ** 2):.1f} MB"

    return f"{size / (1024 ** 3):.2f} GB"


def get_downloaded_file(folder):
    files = [
        p
        for p in folder.rglob("*")
        if p.is_file()
    ]

    if not files:
        return None

    return max(
        files,
        key=lambda p: p.stat().st_mtime
    )


def progress_hook_factory(
    chat_id,
    message_id
):
    last_update = {
        "time": 0,
        "percent": -1
    }

    def hook(data):

        if data["status"] != "downloading":
            return

        downloaded = data.get(
            "downloaded_bytes",
            0
        )

        total = (
            data.get("total_bytes")
            or data.get("total_bytes_estimate")
            or 0
        )

        if not total:
            return

        percent = int(
            downloaded * 100 / total
        )

        now = time.time()

        if (
            now - last_update["time"] >= 3
            and percent != last_update["percent"]
        ):
            last_update["time"] = now
            last_update["percent"] = percent

            speed = data.get("speed") or 0
            eta = data.get("eta")

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
                bot.edit_message_text(
                    (
                        "⬇️ <b>در حال دانلود...</b>\n\n"
                        f"📊 پیشرفت: <b>{percent}%</b>\n"
                        f"📦 حجم: "
                        f"{format_size(downloaded)} / "
                        f"{format_size(total)}\n"
                        f"⚡ سرعت: <b>{speed_text}</b>\n"
                        f"⏱ زمان باقی‌مانده: "
                        f"<b>{eta_text}</b>"
                    ),
                    chat_id,
                    message_id
                )

            except Exception:
                pass

    return hook


def download_media(
    url,
    mode,
    folder,
    chat_id,
    message_id
):
    progress_hook = progress_hook_factory(
        chat_id,
        message_id
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
        "max_filesize": MAX_FILE_SIZE,
        "playlist_items": "1"
    }

    if mode == "audio":

        options = {
            **common,

            "format": "bestaudio/best",

            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192"
                },
                {
                    "key": "FFmpegMetadata"
                }
            ]
        }

    else:

        options = {
            **common,

            "format": (
                "bestvideo[height<=1080]+"
                "bestaudio/"
                "best[height<=1080]/"
                "best"
            ),

            "merge_output_format": "mp4",

            "postprocessors": [
                {
                    "key": "FFmpegMetadata"
                }
            ]
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

        return {
            "title": title,
            "file": get_downloaded_file(folder)
        }


@bot.message_handler(commands=["start"])
def start_cmd(message):

    bot.send_message(
        message.chat.id,
        (
            "🤖 <b>Downloader Bot</b>\n\n"
            "سلام 👋\n\n"
            "لینک ویدیو یا موزیک را بفرست.\n"
            "بعد نوع دانلود را انتخاب کن.\n\n"
            "🎬 Video\n"
            "🎵 MP3\n\n"
            "⚡ سریع و ساده"
        )
    )


@bot.message_handler(commands=["help"])
def help_cmd(message):

    bot.send_message(
        message.chat.id,
        (
            "📚 <b>راهنما</b>\n\n"
            "یک لینک معتبر ارسال کن.\n"
            "سپس فرمت موردنظر را انتخاب کن.\n\n"
            "/start\n"
            "/help\n"
            "/cancel"
        )
    )


@bot.message_handler(commands=["cancel"])
def cancel_cmd(message):

    user_id = message.from_user.id

    user_urls.pop(
        user_id,
        None
    )

    bot.send_message(
        message.chat.id,
        "✅ لینک فعلی حذف شد."
    )


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


@bot.message_handler(
    func=lambda message: (
        message.text
        and is_valid_url(message.text.strip())
    )
)
def get_link(message):

    user_id = message.from_user.id
    url = message.text.strip()

    user_urls[user_id] = url

    markup = types.InlineKeyboardMarkup(
        row_width=2
    )

    markup.add(
        types.InlineKeyboardButton(
            "🎬 دانلود ویدیو",
            callback_data="download_video"
        ),
        types.InlineKeyboardButton(
            "🎵 دانلود MP3",
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
            "❌ لینک پیدا نشد."
        )

        return

    lock = get_user_lock(user_id)

    if not lock.acquire(blocking=False):

        bot.answer_callback_query(
            call.id,
            "⏳ یک دانلود دیگر در حال انجام است."
        )

        return

    bot.answer_callback_query(
        call.id,
        "شروع دانلود..."
    )

    try:

        status = bot.send_message(
            chat_id,
            "⏳ <b>در حال آماده‌سازی دانلود...</b>"
        )

    except Exception:

        lock.release()
        return

    mode = (
        "audio"
        if call.data == "download_audio"
        else "video"
    )

    thread = threading.Thread(
        target=download_worker,
        args=(
            user_id,
            chat_id,
            url,
            mode,
            status.message_id,
            lock
        ),
        daemon=True
    )

    thread.start()


def download_worker(
    user_id,
    chat_id,
    url,
    mode,
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

    try:

        acquired = download_semaphore.acquire(
            timeout=60
        )

        if not acquired:

            bot.edit_message_text(
                "⏳ سرور شلوغ است. کمی بعد دوباره امتحان کن.",
                chat_id,
                status_message_id
            )

            return

        try:

            bot.edit_message_text(
                "🔎 <b>در حال بررسی لینک...</b>",
                chat_id,
                status_message_id
            )

            result = download_media(
                url,
                mode,
                folder,
                chat_id,
                status_message_id
            )

        finally:

            download_semaphore.release()

        file_path = result["file"]

        if not file_path:
            raise RuntimeError(
                "فایل دانلود شده پیدا نشد."
            )

        file_size = file_path.stat().st_size

        if file_size > MAX_FILE_SIZE:

            bot.edit_message_text(
                (
                    "❌ فایل بیش از حد مجاز است.\n\n"
                    f"حجم: {format_size(file_size)}\n"
                    f"حد مجاز: {format_size(MAX_FILE_SIZE)}"
                ),
                chat_id,
                status_message_id
            )

            return

        bot.edit_message_text(
            "📤 <b>دانلود کامل شد؛ در حال ارسال...</b>",
            chat_id,
            status_message_id
        )

        title = safe_filename(
            result["title"]
        )

        caption = (
            f"📥 <b>{title}</b>\n\n"
            "🤖 Downloader Bot"
        )

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

        try:
            bot.delete_message(
                chat_id,
                status_message_id
            )
        except Exception:
            pass

    except Exception as error:

        print(
            f"[ERROR] {repr(error)}"
        )

        error_text = str(error).lower()

        if "unsupported url" in error_text:

            text = (
                "❌ این لینک پشتیبانی نمی‌شود."
            )

        elif "private" in error_text:

            text = (
                "🔒 این محتوا خصوصی است."
            )

        elif "sign in" in error_text:

            text = (
                "🔐 این محتوا نیاز به ورود دارد."
            )

        elif "max-filesize" in error_text:

            text = (
                "❌ حجم فایل بیش از حد مجاز است."
            )

        else:

            text = (
                "❌ دانلود انجام نشد.\n\n"
                "لینک را بررسی کن و دوباره امتحان کن."
            )

        try:

            bot.edit_message_text(
                text,
                chat_id,
                status_message_id
            )

        except Exception:

            bot.send_message(
                chat_id,
                text
            )

    finally:

        user_urls.pop(
            user_id,
            None
        )

        shutil.rmtree(
            folder,
            ignore_errors=True
        )

        lock.release()


@bot.message_handler(
    func=lambda message: True,
    content_types=["text"]
)
def fallback(message):

    bot.send_message(
        message.chat.id,
        (
            "🤔 لطفاً یک لینک معتبر ارسال کن.\n\n"
            "مثال:\n"
            "https://example.com/video"
        )
    )


if __name__ == "__main__":

    print("🤖 Bot Started")

    while True:

        try:

            bot.infinity_polling(
                skip_pending=True,
                timeout=30,
                long_polling_timeout=30
            )

        except Exception as error:

            print(
                f"Polling Error: {repr(error)}"
            )

            time.sleep(5)
