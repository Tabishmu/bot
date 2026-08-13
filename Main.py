import os, telebot, yt_dlp
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

bot = telebot.TeleBot("8822372631:AAEUuv5KLB1TqQ6GW18vnejr1cpD2D-kvRM")

user_urls = {}

@bot.message_handler(commands=["شروع"])
def send_welcome(m):
    bot.reply_to(m, "سلام خوش آمدی روان کو لینک ته زیاد گپ نزن اعصاب نیست 😒")

@bot.message_handler(func=lambda m: True)
def handle_link(m):
    if not m.text.startswith("http"):
        bot.reply_to(m, "حیف نان لینک قلاچ کدن هم یاد نداری")
        return
    
    clean_url = m.text.split('?')[0].split('&')[0]
    user_urls[m.chat.id] = clean_url

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎬 ویدیو (MP4)", callback_data="dl_video"),
        InlineKeyboardButton("🎵 صوتی (Audio)", callback_data="dl_audio")
    )
    bot.reply_to(m, "کدامش :", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["dl_video", "dl_audio"])
def process_download(call):
    chat_id = call.message.chat.id
    url = user_urls.get(chat_id)
    
    if not url:
        bot.send_message(chat_id, "گنایت نیست لینک توهم خودت واری تاریخش تیر شده .")
        return

    msg = bot.send_message(chat_id, "😒")
    
    is_audio = call.data == "dl_audio"
    out_template = f"{chat_id}.%(ext)s"

    opts = {
        'outtmpl': out_template,
        'quiet': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    if is_audio:
        opts['format'] = 'm4a/bestaudio/best'
    else:
        opts['format'] = 'best[ext=mp4]/best'

    downloaded_file = None

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            downloaded_file = ydl.prepare_filename(info)

        with open(downloaded_file, 'rb') as file:
            if is_audio:
                bot.send_audio(chat_id, file)
            else:
                bot.send_video(chat_id, file)

        bot.delete_message(chat_id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"خطا در دانلود! ممکن است IP سرور محدود شده یا لینک اشتباه باشد.\nجزییات: {str(e)[:50]}", chat_id, msg.message_id)
    finally:
        if downloaded_file and os.path.exists(downloaded_file):
            os.remove(downloaded_file)

bot.infinity_polling()
