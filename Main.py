import os
import glob
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import yt_dlp

TOKEN = os.getenv("BOT_TOKEN", "8822372631:AAHfWhldF3DG2mgLIiNbEh1g5LfLzM_-qcA")

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

    # اگر لینک یوتیوب بود از API واسط استفاده کن
    if "youtube.com" in url or "youtu.be" in url:
        try:
            api_url = f"https://api.cobalt.tools/api/json"
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            payload = {"url": url}
            
            if choice == 'audio':
                payload["downloadMode"] = "audio"
                payload["audioFormat"] = "mp3"
            elif choice == 'image':
                # گرفتن عکس کاور یوتیوب
                yt_id = url.split("v=")[-1].split("&")[0].split("/")[-1]
                img_url = f"https://img.youtube.com/vi/{yt_id}/maxresdefault.jpg"
                await query.message.reply_photo(photo=img_url)
                return

            res = requests.post(api_url, json=payload, headers=headers).json()
            download_link = res.get("url")

            if download_link:
                if choice == 'audio':
                    await query.message.reply_audio(audio=download_link)
                else:
                    await query.message.reply_video(video=download_link)
                return
        except Exception:
            pass # اگر API ناموفق بود برود سراغ yt-dlp

    # برای سایر سایت‌ها (اینستاگرام، تیک‌تاک و...) از yt-dlp استفاده کن
    ydl_opts = {
        'outtmpl': 'downloaded_file.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    }

    if choice == 'audio':
        ydl_opts.update({
            'format': 'bestaudio/best',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        })
    elif choice == 'image':
        ydl_opts.update({'skip_download': True, 'writethumbnail': True, 'outtmpl': 'downloaded_file'})
    else:
        ydl_opts.update({'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'})

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        files = glob.glob('downloaded_file*')
        if not files:
            await query.message.reply_text("فایلی یافت نشد.")
            return

        file_path = files[0]
        with open(file_path, 'rb') as f:
            if choice == 'audio':
                await query.message.reply_audio(audio=f)
            elif choice == 'image':
                await query.message.reply_photo(photo=f)
            else:
                await query.message.reply_video(video=f)

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
