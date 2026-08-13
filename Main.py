import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import requirements.txt

TOKEN = "8822372631:AAEUuv5KLB1TqQ6GW18vnejr1cpD2D-kvRM"

def get_working_proxy():
    try:
        res = requests.get("https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=3000&country=all&ssl=all&anonymity=all")
        proxies = res.text.strip().split("\r\n")
        for proxy in proxies[:10]:
            proxy_url = f"http://{proxy}"
            try:
                r = requests.get("https://httpbin.org/ip", proxies={"http": proxy_url, "https": proxy_url}, timeout=3)
                if r.status_code == 200:
                    return proxy_url
            except:
                continue
    except:
        pass
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Please send the media link.")

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['url'] = update.message.text
    keyboard = [[
        InlineKeyboardButton("🎬 Video", callback_data='video'),
        InlineKeyboardButton("🎵 Audio", callback_data='audio'),
        InlineKeyboardButton("🖼 Photo", callback_data='image')
    ]]
    await update.message.reply_text("Select format:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    url = context.user_data.get('url')
    choice = query.data
    await query.edit_message_text("Fetching proxy and downloading...")

    proxy = get_working_proxy()

    ydl_opts = {'outtmpl': 'downloads/%(title)s.%(ext)s'}
    if proxy:
        ydl_opts['proxy'] = proxy

    if choice == 'video':
        ydl_opts['format'] = 'best'
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
    except Exception as e:
        await query.message.reply_text(f"Download failed: {e}")

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
app.add_handler(CallbackQueryHandler(button_click))

app.run_polling()
