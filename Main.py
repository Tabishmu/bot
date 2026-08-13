import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

TOKEN = "8822372631:AAEUuv5KLB1TqQ6GW18vnejr1cpD2D-kvRM"
TOR_PROXY = "socks5://127.0.0.1:9050"  # آدرس پراکسی Tor

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لینک را بفرستید.")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['url'] = update.message.text
    keyboard = [
        [InlineKeyboardButton("🎬 ویدیو", callback_data='video')],
        [InlineKeyboardButton("🎵 موزیک", callback_data='audio')],
        [InlineKeyboardButton("🖼 عکس", callback_data='image')]
    ]
    await update.message.reply_text("فرمت را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    url = context.user_data.get('url')
    choice = query.data
    await query.edit_message_text("در حال دانلود با آی‌پی جدید...")

    # تنظیمات yt-dlp همراه با پراکسی برای تغییر آی‌پی
    ydl_opts = {
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'proxy': TOR_PROXY,  # تغییر آی‌پی از طریق Tor
        'source_address': '0.0.0.0',
    }

    if choice == 'video':
        ydl_opts['format'] = 'bestvideo+bestaudio/best'
    elif choice == 'audio':
        ydl_opts['format'] = 'bestaudio/best'
        ydl_opts['postprocessors'] = [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}]
    elif choice == 'image':
        ydl_opts['writethumbnail'] = True
        ydl_opts['skip_download'] = True

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)

        if choice == 'image':
            file_path = os.path.splitext(file_path)[0] + ".jpg"

        await query.message.reply_document(document=open(file_path, 'rb'))
        os.remove(file_path)
    except Exception:
        await query.message.reply_text("خطا در دانلود!")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
app.add_handler(CallbackQueryHandler(button_click))

app.run_polling()
