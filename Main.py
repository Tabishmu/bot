import os, telebot, yt_dlp

bot = telebot.TeleBot("8822372631:AAHRDFpnQpbOkawa8Qi1bIU11MJ5HIzZpiI")


@bot.message_handler(commands=["start"])
def send_welcome(m):
    bot.reply_to(m, "سلام! لینک یوتیوب یا تیک‌تاک بفرستید.")


@bot.message_handler(func=lambda m: True)
def dl(m):
    if not m.text.startswith("http"):
        bot.reply_to(m, "لطفاً یک لینک معتبر بفرستید.")
        return

    bot.reply_to(m, "در حال دریافت...")
    filename = f"dl_{m.chat.id}.mp4"

    ydl_opts = {
        "format": "best",
        "outtmpl": filename,
        "quiet": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([m.text])

        with open(filename, "rb") as video:
            bot.send_video(m.chat.id, video)

        if os.path.exists(filename):
            os.remove(filename)

    except Exception as e:
        bot.reply_to(m, "خطا در دانلود! مطمئن شوید لینک معتبر است.")


bot.polling()
