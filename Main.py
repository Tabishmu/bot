import os
import glob
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

TOKEN = os.getenv("8822372631:AAEUuv5KLB1TqQ6GW18vnejr1cpD2D-kvRM", "YOUR_TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لینک مورد نظرت رو بفرست!")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    context.user_data['url'] = url
    
    keyboard = [
        [
            InlineKeyboardButton("🎬 ویدیو", callback_data='video'),
            InlineKeyboardButton("🎵 موزیک (MP3)", callback_data='audio'),
            InlineKeyboardButton("🖼 عکس / کاور", callback_data='image')
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("فرمت درخواستی رو انتخاب کن:", reply_markup=reply_markup)

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    url = context.user_data.get('url')
    if not url:
        await query.edit_message_text("لطفاً دوباره لینک را ارسال کنید.")
        return

    choice = query.data
    await query.edit_message_text("در حال دانلود و ارسال...")

    ydl_opts = {
        'outtmpl': 'downloaded_file.%(ext)s',
        'quiet': True,
        'no_warnings': True,
    }

    if choice == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        })
    elif choice == 'image':
        ydl_opts.update({
            'skip_download': True,
            'writethumbnail': True,
            'outtmpl': 'downloaded_file',
        })
    else: # video
        ydl_opts.update({
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        })

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # پیدا کردن فایل دانلود شده
        files = glob.glob('downloaded_file*')
        if not files:
            await query.message.reply_text("فایلی یافت نشد.")
            return

        file_path = files[0]

        # ارسال فایل
        with open(file_path, 'rb') as f:
            if choice == 'audio':
                await query.message.reply_audio(audio=f)
            elif choice == 'image':
                await query.message.reply_photo(photo=f)
            else:
                await query.message.reply_video(video=f)

        # پاکسازی
        for file in files:
            os.remove(file)

    except Exception as e:
        await query.message.reply_text(f"خطا در دانلود: {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_click))
    app.run_polling()
