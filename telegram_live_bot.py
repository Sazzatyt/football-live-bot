import os
import sys
import asyncio
import logging
import subprocess
from threading import Thread
from http.server import SimpleHTTPRequestHandler, HTTPServer
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Logging setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------- DUMMY WEB SERVER FOR RENDER -----------------
# Render Web Service requires a port to be bound, otherwise it fails with "status 1"
class DummyServer(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Football Live Bot is running smoothly!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyServer)
    logger.info(f"Dummy server started on port {port}")
    server.serve_forever()
# ---------------------------------------------------------------

# --- কনফিগারেশন ---
TELEGRAM_BOT_TOKEN = "8917668880:AAHE-DRbPYgWsAR33VWig3y3z_E97RIL7iQ"
RTMP_URL = "rtmps://live-api-s.facebook.com:443/rtmp/"
# --------------------

CURRENT_STREAM_KEY = ""
active_process = None

# /start কমান্ড
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 আমি আপনার অল-ইন-ওয়ান লাইভ স্ট্রিমিং বট।\n\n"
        "🤖 **আমার বিশেষত্ব:**\n"
        "⚽ আপনি যদি কোনো **ফুটবল ম্যাচের** লিঙ্ক দেন, আমি নিজে থেকেই কড়া ফুটবল কপিরাইট প্রটেকশন অন করে দেবো。\n"
        "🎬 সাধারণ ভিডিওর লিঙ্ক দিলে সেটি নরমাল ফিল্টারে লাইভ হবে。\n\n"
        "⚙️ প্রথমে আপনার Stream Key পাঠান, তারপর ভিডিওর লিঙ্ক দিন।"
    )

# /stop কমান্ড
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_process
    if active_process and active_process.poll() is None:
        active_process.terminate()
        active_process = None
        await update.message.reply_text("🛑 লাইভ স্ট্রিমটি সফলভাবে বন্ধ করা হয়েছে।")
    else:
        await update.message.reply_text("ℹ️ বর্তমানে কোনো লাইভ স্ট্রিম চলছে না।")

# মেসেজ হ্যান্ডলার
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_process, CURRENT_STREAM_KEY
    user_text = update.message.text.strip()
    
    if "http://" in user_text or "https://" in user_text:
        if not CURRENT_STREAM_KEY:
            await update.message.reply_text("❌ প্রথমে আপনার ফেসবুক Stream Key-টি মেসেজ আকারে পাঠান।")
            return

        if active_process and active_process.poll() is None:
            await update.message.reply_text("⚠️ অলরেডি একটি লাইভ চলছে! নতুন লাইভ শুরু করতে প্রথমে /stop লিখুন।")
            return

        await update.message.reply_text("🔍 লিঙ্ক থেকে ভিডিও সোর্স খোঁজা হচ্ছে, দয়া করে অপেক্ষা করুন...")

        try:
            ydl_cmd = ['yt-dlp', '-g', '-f', 'best', user_text]
            result = subprocess.run(ydl_cmd, capture_output=True, text=True, check=True)
            direct_url = result.stdout.strip()
        except Exception as e:
            await update.message.reply_text(f"❌ এরর ডিটেইলস (yt-dlp):\n{str(e)}")
            return

        # ---- スマート ফিল্টার সিলেকশন ----
        is_football = any(word in user_text.lower() for word in ["football", "match", "live", "sports", "fifa", "uefa", "vs", "gopal"]) 
        
        if is_football:
            await update.message.reply_text("⚽ **ফুটবল/লাইভ ম্যাচ ডিটেক্ট হয়েছে!** কড়া কপিরাইট প্রটেকশন (জুম + ক্রপ + অডিও হাই-পিচ) অন করা হচ্ছে...")
            video_filter = "hflip,scale=2.0*iw:-1,crop=iw/2:ih/2" 
            audio_filter = "asetrate=44100*1.08,atempo=0.92"
        else:
            await update.message.reply_text("🎬 **সাধারণ ভিডিও ডিটেক্ট হয়েছে!** নরমাল ফিল্টারে লাইভ শুরু হচ্ছে...")
            video_filter = "hflip"
            audio_filter = "asetrate=44100*1.04,atempo=0.96"
        # --------------------------------

        destination = RTMP_URL + CURRENT_STREAM_KEY
        ffmpeg_exe = "ffmpeg"

        command = [
            ffmpeg_exe, '-re', '-i', direct_url,
            '-filter_complex', f"[0:v]{video_filter}[v];[0:a]{audio_filter}[a]",
            '-map', '[v]', '-map', '[a]',
            '-c:v', 'libx264', '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-b:v', '2000k', '-maxrate', '2500k', '-bufsize', '4000k',
            '-pix_fmt', 'yuv420p', '-g', '60',
            '-c:a', 'aac', '-b:a', '128k', '-ar', '44100',
            '-f', 'flv', destination
        ]

        try:
            active_process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            await update.message.reply_text("🚀 সফল! ফেসবুকে লাইভ ডাটা পাঠানো শুরু হয়েছে। আপনার ফেসবুক পেজ চেক করুন।")
        except Exception as e:
            await update.message.reply_text(f"❌ লাইভ চালু করতে সমস্যা হয়েছে: {e}")

    else:
        CURRENT_STREAM_KEY = user_text
        await update.message.reply_text("✅ Stream Key সফলভাবে যুক্ত হয়েছে! এখন ভিডিওর লিঙ্কটি পাঠান।")

def main():
    # Start the dummy web server in a separate thread so Render doesn't crash
    Thread(target=run_dummy_server, daemon=True).start()

    logger.info("স্মার্ট ডাবল-ফিল্টার বট চালু হচ্ছে...")
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Asyncio loop fix for Python 3.11+ and Render background execution
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    logger.info("Initializing Telegram Bot...")
    loop.run_until_complete(application.initialize())
    loop.run_until_complete(application.start())
    
    if application.updater:
        loop.run_until_complete(application.updater.start_polling())
        
    logger.info("Bot started successfully and is now live!")
    loop.run_forever()

if __name__ == '__main__':
    main()
