import os, telebot, yt_dlp
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = "8822372631:AAEUuv5KLB1TqQ6GW18vnejr1cpD2D-kvRM"
bot = telebot.TeleBot(BOT_TOKEN)

# ذخیره اطلاعات موقت
user_urls = {}
warns = {}  # اخطارها: {chat_id_user_id: count}
locks = {}  # قفل‌ها: {chat_id: {'link': True/False}}

# بررسی ادمین بودن کاربر
def is_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except Exception:
        return False

# --- بخش ۱: مدیریت گروه (مشابه Miss Rose به فارسی) ---

# خوش‌آمدگویی
@bot.message_handler(content_types=['new_chat_members'])
def welcome(m):
    for member in m.new_chat_members:
        bot.reply_to(m, f"سلام {member.first_name} عزیز! به گروه خوش آمدی. 🌹")

# سنجاق کردن پیام (/pin)
@bot.message_handler(commands=['pin', 'سنجاق'])
def pin_msg(m):
    if not is_admin(m.chat.id, m.from_user.id):
        return bot.reply_to(m, "❌ شما ادمین نیستید!")
    if m.reply_to_message:
        bot.pin_chat_message(m.chat.id, m.reply_to_message.message_id)
        bot.reply_to(m, "📌 پیام با موفقیت سنجاق شد.")

# حذف پیام (/del)
@bot.message_handler(commands=['del', 'حذف'])
def delete_msg(m):
    if not is_admin(m.chat.id, m.from_user.id):
        return bot.reply_to(m, "❌ شما ادمین نیستید!")
    if m.reply_to_message:
        bot.delete_message(m.chat.id, m.reply_to_message.message_id)
        bot.delete_message(m.chat.id, m.message_id)

# بن کردن کاربر (/ban)
@bot.message_handler(commands=['ban', 'مسدود'])
def ban_user(m):
    if not is_admin(m.chat.id, m.from_user.id):
        return bot.reply_to(m, "❌ شما ادمین نیستید!")
    if m.reply_to_message:
        target = m.reply_to_message.from_user
        bot.ban_chat_member(m.chat.id, target.id)
        bot.reply_to(m, f"🚫 کاربر {target.first_name} از گروه اخراج و مسدود شد.")

# آنبن کردن (/unban)
@bot.message_handler(commands=['unban', 'آزاد'])
def unban_user(m):
    if not is_admin(m.chat.id, m.from_user.id):
        return bot.reply_to(m, "❌ شما ادمین نیستید!")
    if m.reply_to_message:
        target = m.reply_to_message.from_user
        bot.unban_chat_member(m.chat.id, target.id)
        bot.reply_to(m, f"✅ محدودیت کاربر {target.first_name} برداشته شد.")

# دادن اخطار (/warn)
@bot.message_handler(commands=['warn', 'اخطار'])
def warn_user(m):
    if not is_admin(m.chat.id, m.from_user.id):
        return bot.reply_to(m, "❌ شما ادمین نیستید!")
    if m.reply_to_message:
        target = m.reply_to_message.from_user
        key = f"{m.chat.id}_{target.id}"
        warns[key] = warns.get(key, 0) + 1
        
        if warns[key] >= 3:
            bot.ban_chat_member(m.chat.id, target.id)
            bot.reply_to(m, f"🚫 کاربر {target.first_name} به دلیل دریافت ۳ اخطار اخراج شد!")
            warns[key] = 0
        else:
            bot.reply_to(m, f"⚠️ به کاربر {target.first_name} اخطار داده شد. (تعداد اخطارها: {warns[key]}/3)")

# پاک کردن اخطارها (/unwarn)
@bot.message_handler(commands=['unwarn', 'حذف_اخطار'])
def unwarn_user(m):
    if not is_admin(m.chat.id, m.from_user.id):
        return bot.reply_to(m, "❌ شما ادمین نیستید!")
    if m.reply_to_message:
        target = m.reply_to_message.from_user
        key = f"{m.chat.id}_{target.id}"
        warns[key] = 0
        bot.reply_to(m, f"🧹 تمام اخطارهای {target.first_name} پاک شد.")

# قفل لینک (/lock link)
@bot.message_handler(commands=['lock', 'قفل'])
def lock_setting(m):
    if not is_admin(m.chat.id, m.from_user.id):
        return bot.reply_to(m, "❌ شما ادمین نیستید!")
    args = m.text.split()
    if len(args) > 1 and args[1] in ['link', 'لینک']:
        locks[m.chat.id] = locks.get(m.chat.id, {})
        locks[m.chat.id]['link'] = True
        bot.reply_to(m, "🔒 ارسال لینک در گروه قفل شد.")

# باز کردن قفل لینک (/unlock link)
@bot.message_handler(commands=['unlock', 'بازکردن'])
def unlock_setting(m):
    if not is_admin(m.chat.id, m.from_user.id):
        return bot.reply_to(m, "❌ شما ادمین نیستید!")
    args = m.text.split()
    if len(args) > 1 and args[1] in ['link', 'لینک']:
        locks[m.chat.id] = locks.get(m.chat.id, {})
        locks[m.chat.id]['link'] = False
        bot.reply_to(m, "🔓 ارسال لینک آزاد شد.")

# --- بخش ۲: دانلودر موزیک و ویدیو ---

@bot.message_handler(commands=["start", "راهنما"])
def send_welcome(m):
    bot.reply_to(m, "سلام! من ربات مدیریت گروه و دانلودر هستم.\nلینک یوتیوب بفرستید تا دانلود کنم یا من را ادمین گروه کنید.")

@bot.message_handler(func=lambda m: m.text and m.text.startswith("http"))
def handle_link_and_locks(m):
    # چک کردن قفل لینک برای کاربران معمولی
    chat_locks = locks.get(m.chat.id, {})
    if chat_locks.get('link', False) and not is_admin(m.chat.id, m.from_user.id):
        bot.delete_message(m.chat.id, m.message_id)
        return

    # پردازش دانلود لینک
    clean_url = m.text.split('?')[0].split('&')[0]
    user_urls[m.chat.id] = clean_url

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎬 ویدیو (MP4)", callback_data="dl_video"),
        InlineKeyboardButton("🎵 موزیک (MP3/Audio)", callback_data="dl_audio")
    )
    bot.reply_to(m, "فرمت دانلود را انتخاب کنید:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["dl_video", "dl_audio"])
def process_download(call):
    chat_id = call.message.chat.id
    url = user_urls.get(chat_id)
    
    if not url:
        bot.send_message(chat_id, "لینک پیدا نشد، دوباره ارسال کنید.")
        return

    msg = bot.send_message(chat_id, "⏳ در حال دانلود...")
    
    is_audio = call.data == "dl_audio"
    out_template = f"{chat_id}.%(ext)s"

    opts = {
        'outtmpl': out_template,
        'quiet': True,
        'nocheckcertificate': True,
        'noplaylist': True,
        'extractor_args': {'youtube': {'player_client': ['ios', 'android']}}
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
        bot.edit_message_text(f"خطا در دانلود!\nجزئیات: {str(e)[:50]}", chat_id, msg.message_id)
    finally:
        if downloaded_file and os.path.exists(downloaded_file):
            os.remove(downloaded_file)

bot.infinity_polling()
