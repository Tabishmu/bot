import os, telebot, yt_dlp
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ChatPermissions

BOT_TOKEN = "8822372631:AAEUuv5KLB1TqQ6GW18vnejr1cpD2D-kvRM"
bot = telebot.TeleBot(8822372631:AAEUuv5KLB1TqQ6GW18vnejr1cpD2D-kvRM)

# دیتابیس در حافظه
user_urls = {}
warns = {}          # {chat_id_user_id: count}
locks = {}          # {chat_id: {'link': True, 'photo': False, 'sticker': False, 'tglink': True}}
captcha_users = {}  # {chat_id_user_id: answer}

def is_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ['creator', 'administrator']
    except Exception:
        return False

# --- ۱. سیستم احراز هویت (کپچا) و خوش‌آمدگویی ---

@bot.message_handler(content_types=['new_chat_members'])
def welcome_and_captcha(m):
    for member in m.new_chat_members:
        if member.is_bot: continue
        
        # محدود کردن کاربر تا زمان حل کپچا
        bot.restrict_chat_member(m.chat.id, member.id, permissions=ChatPermissions(can_send_messages=False))
        
        # ایجاد دکمه شیشه‌ای تایید
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ من ربات نیستم (تایید)", callback_data=f"verify_{member.id}"))
        
        bot.send_message(
            m.chat.id, 
            f"سلام {member.first_name} عزیز! 🌹\nبه گروه خوش آمدید. برای ارسال پیام لطفا روی دکمه زیر بزنید:",
            reply_markup=markup
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith("verify_"))
def verify_captcha(call):
    target_id = int(call.data.split("_")[1])
    if call.from_user.id != target_id:
        return bot.answer_callback_query(call.id, "❌ این دکمه مخصوص شما نیست!", show_alert=True)
    
    # آزادسازی دسترسی
    bot.restrict_chat_member(
        call.message.chat.id, 
        target_id, 
        permissions=ChatPermissions(
            can_send_messages=True, 
            can_send_media_messages=True, 
            can_send_other_messages=True,
            can_add_web_page_previews=True
        )
    )
    bot.answer_callback_query(call.id, "✅ حساب شما . تایید شد.")
    bot.delete_message(call.message.chat.id, call.message.message_id)

# --- ۲. دستورات مدیریتی دیجی آنتی ---

# قفل‌ها: /lock link | /lock photo | /lock sticker
@bot.message_handler(commands=['lock', 'قفل'])
def lock_features(m):
    if not is_admin(m.chat.id, m.from_user.id): return
    args = m.text.split()
    if len(args) > 1:
        feature = args[1].lower()
        locks.setdefault(m.chat.id, {})[feature] = True
        bot.reply_to(m, f"🔒 قابلیت **{feature}** قفل شد.")

# بازکردن قفل: /unlock link | /unlock photo
@bot.message_handler(commands=['unlock', 'بازکردن'])
def unlock_features(m):
    if not is_admin(m.chat.id, m.from_user.id): return
    args = m.text.split()
    if len(args) > 1:
        feature = args[1].lower()
        locks.setdefault(m.chat.id, {})[feature] = False
        bot.reply_to(m, f"🔓 قابلیت **{feature}** آزاد شد.")

# سکوت کاربر (/mute)
@bot.message_handler(commands=['mute', 'سکوت'])
def mute_user(m):
    if not is_admin(m.chat.id, m.from_user.id) or not m.reply_to_message: return
    target = m.reply_to_message.from_user
    bot.restrict_chat_member(m.chat.id, target.id, permissions=ChatPermissions(can_send_messages=False))
    bot.reply_to(m, f"🔇 کاربر {target.first_name} سکوت شد.")

# لغو سکوت (/unmute)
@bot.message_handler(commands=['unmute', 'باطل_سکوت'])
def unmute_user(m):
    if not is_admin(m.chat.id, m.from_user.id) or not m.reply_to_message: return
    target = m.reply_to_message.from_user
    bot.restrict_chat_member(m.chat.id, target.id, permissions=ChatPermissions(can_send_messages=True, can_send_media_messages=True))
    bot.reply_to(m, f"🔊 سکوت کاربر {target.first_name} برداشته شد.")

# بن (/ban)
@bot.message_handler(commands=['ban', 'مسدود'])
def ban_user(m):
    if not is_admin(m.chat.id, m.from_user.id) or not m.reply_to_message: return
    target = m.reply_to_message.from_user
    bot.ban_chat_member(m.chat.id, target.id)
    bot.reply_to(m, f"🚫 کاربر {target.first_name} اخراج شد.")

# اخطار (/warn)
@bot.message_handler(commands=['warn', 'اخطار'])
def warn_user(m):
    if not is_admin(m.chat.id, m.from_user.id) or not m.reply_to_message: return
    target = m.reply_to_message.from_user
    key = f"{m.chat.id}_{target.id}"
    warns[key] = warns.get(key, 0) + 1
    if warns[key] >= 3:
        bot.ban_chat_member(m.chat.id, target.id)
        bot.reply_to(m, f"🚫 کاربر {target.first_name} به علت ۳ اخطار اخراج شد.")
        warns[key] = 0
    else:
        bot.reply_to(m, f"⚠️ اخطار به {target.first_name} ({warns[key]}/3)")

# --- ۳. فیلتر هوشمند پیام‌ها و دانلودر ---

@bot.message_handler(func=lambda m: True, content_types=['text', 'photo', 'sticker'])
def monitor_and_download(m):
    chat_locks = locks.get(m.chat.id, {})
    admin = is_admin(m.chat.id, m.from_user.id)

    # بررسی قفل‌ها (برای غیر ادمین)
    if not admin:
        if chat_locks.get('photo') and m.content_type == 'photo':
            return bot.delete_message(m.chat.id, m.message_id)
        if chat_locks.get('sticker') and m.content_type == 'sticker':
            return bot.delete_message(m.chat.id, m.message_id)
        if chat_locks.get('link') and m.text and ("http" in m.text or "t.me" in m.text or "@" in m.text):
            return bot.delete_message(m.chat.id, m.message_id)

    # دانلودر لینک‌های یوتیوب
    if m.text and m.text.startswith("http"):
        clean_url = m.text.split('?')[0].split('&')[0]
        user_urls[m.chat.id] = clean_url
        markup = InlineKeyboardMarkup()
        markup.add(
            InlineKeyboardButton("🎬 دانلود ویدیو", callback_data="dl_video"),
            InlineKeyboardButton("🎵 دانلود موزیک", callback_data="dl_audio")
        )
        bot.reply_to(m, "📥 فرمت دانلود را انتخاب کنید:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ["dl_video", "dl_audio"])
def process_download(call):
    chat_id = call.message.chat.id
    url = user_urls.get(chat_id)
    if not url: return

    msg = bot.send_message(chat_id, "⏳ در حال پردازش...")
    is_audio = call.data == "dl_audio"
    out_tmpl = f"{chat_id}.%(ext)s"

    opts = {
        'outtmpl': out_tmpl,
        'quiet': True,
        'cookiefile': 'cookies.txt' if os.path.exists('cookies.txt') else None,
        'extractor_args': {'youtube': {'player_client': ['ios', 'android']}}
    }
    opts['format'] = 'm4a/bestaudio/best' if is_audio else 'best[ext=mp4]/best'

    file_path = None
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        with open(file_path, 'rb') as f:
            if is_audio: bot.send_audio(chat_id, f)
            else: bot.send_video(chat_id, f)
        bot.delete_message(chat_id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"خطا: {str(e)[:40]}", chat_id, msg.message_id)
    finally:
        if file_path and os.path.exists(file_path): os.remove(file_path)

bot.infinity_polling()
