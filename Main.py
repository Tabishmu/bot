import os, telebot, yt_dlp
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8822372631:AAHfWhldF3DG2mgLIiNbEh1g5LfLzM_-qcA"
bot = telebot.TeleBot(8822372631:AAHfWhldF3DG2mgLIiNbEh1g5LfLzM_-qcA)

user_urls = {}

@bot.message_handler(commands=['start'])
def start_cmd(m):
    bot.reply_to(m, "سلام! خوش آمدید. 🌹\nلینک پست یا ویدیو را بفرستید تا برایتان دانلود کنم.")

@bot.message_handler(content_types=['new_chat_members'])
def welcome_members(m):
    for member in m.new_chat_members:
        if not member.is_bot:
            bot.reply_to(m, f"سلام {member.first_name} عزیز! به گروه خوش آمدید. 🌹")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("http"))
def get_link(m):
    clean_url = m.text.split('?')[0].split('&')[0]
    user_urls[m.chat.id] = clean_url

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎬 دانلود ویدیو", callback_data="dl_video"),
        InlineKeyboardButton("🎵 دانلود موزیک / صوتی", callback_data="dl_audio")
    )
    bot.reply_to(m, "📥 فرمت مورد نظر را انتخاب کنید:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["dl_video", "dl_audio"])
def process_download(call):
    chat_id = call.message.chat.id
    url = user_urls.get(chat_id)
    
    if not url:
        return bot.send_message(chat_id, "❌ لینک پیدا نشد، لطفا دوباره ارسال کنید.")

    msg = bot.send_message(chat_id, "⏳ در حال دانلود و پردازش...")
    is_audio = call.data == "dl_audio"
    out_tmpl = f"{chat_id}.%(ext)s"

    opts = {
        'outtmpl': out_tmpl,
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'extractor_args': {
            'youtube': {'player_client': ['ios', 'android']}
        }
    }

    if is_audio:
        opts['format'] = 'm4a/bestaudio/best'
    else:
        opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'

    file_path = None

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        with open(file_path, 'rb') as f:
            if is_audio:
                bot.send_audio(chat_id, f)
            else:
                bot.send_video(chat_id, f)

        bot.delete_message(chat_id, msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ خطا در دانلود! ممکن است لینک خصوصی یا مسدود باشد.\nجزئیات: {str(e)[:50]}", chat_id, msg.message_id)

    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

bot.infinity_polling()
