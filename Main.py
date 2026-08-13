import os, telebot, yt_dlp
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

bot = telebot.TeleBot("8822372631:AAEUuv5KLB1TqQ6GW18vnejr1cpD2D-kvRM")

user_urls = {}

@bot.message_handler(commands=["start"])
def send_welcome(m):
    bot.reply_to(m, "سلام خوش آمدی روان کو لینک ته زیاد گپ نزن اعصاب نیست 😒")

@bot.message_handler(func=lambda m: True)
def handle_link(m):
    if not m.text.startswith("http"):
        bot.reply_to(m, "حیف نان لینک قلاچ کدن هم یاد نداری")
        return
    
    clean_url = m.text.split('?')[0]
    user_urls[m.chat.id] = clean_url

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎬 ویدیو (MP4)", callback_data="dl_video"),
        InlineKeyboardButton("🎵 صوتی (MP3)", callback_data="dl_audio")
    )
    bot.reply_to(m, "فرمت مورد نظر را انتخاب کنید:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["dl_video", "dl_audio"])
def process_download(call):
    chat_id = call.message.chat.id
    url = user_urls.get(chat_id)
    
    if not url:
        bot.send_message(chat_id, "لینک یافت نشد، دوباره ارسال کنید.")
        return

    msg = bot.send_message(chat_id, ". دردته به قراری بخور خدا زده 😒")
    
    is_audio = call.data == "dl_audio"
    ext = "mp3" if is_audio else "mp4"
    out = f"{chat_id}.{ext}"

    opts = {
        'outtmpl': out,
        'quiet': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
    }

    if is_audio:
        opts['format'] = 'bestaudio/best'
        opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]
    else:
        opts['format'] = 'b[ext=mp4]/best'

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])

        with open(out, 'rb') as file:
            if is_audio:
                bot.send_audio(chat_id, file)
            else:
                bot.send_video(chat_id, file)

        bot.delete_message(chat_id, msg.message_id)
    except Exception as e:
        bot.edit_message_text("خطا در دانلود! لینک نامعتبر است یا ویدیو خصوصی می‌باشد.", chat_id, msg.message_id)
    finally:
        if os.path.exists(out):
            os.remove(out)

bot.infinity_polling()
