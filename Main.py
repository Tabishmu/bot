import os, telebot, yt_dlp

bot = telebot.TeleBot("8822372631:AAEUuv5KLB1TqQ6GW18vnejr1cpD2D-kvRM") 

@bot.message_handler(commands=["start"])
def send_welcome(m):
    bot.reply_to(m, "لینک ویدیو را بفرستید (اینستاگرام، یوتیوب، تیک‌تاک و...)")

@bot.message_handler(func=lambda m: True)
def dl(m):
    if not m.text.startswith("http"):
        bot.reply_to(m, "لطفاً یک لینک معتبر بفرستید.")
        return
    
    msg = bot.reply_to(m, "در حال دانلود...")
    out = f"{m.chat.id}.mp4"
    
    opts = {
        'format': 'b[ext=mp4]/best',
        'outtmpl': out,
        'quiet': True,
        'nocheckcertificate': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([m.text])
        
        with open(out, 'rb') as v:
            bot.send_video(m.chat.id, v)
        
        os.remove(out)
        bot.delete_message(m.chat.id, msg.message_id)
    except Exception:
        bot.edit_message_text("خطا در دانلود! لینک نامعتبر است یا ویدیو خصوصی می‌باشد.", m.chat.id, msg.message_id)
        if os.path.exists(out):
            os.remove(out)

bot.infinity_polling()
