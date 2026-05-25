import os
import sys
import asyncio
import logging
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
        self.wfile.write(b"Bot is running smoothly!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), DummyServer)
    logger.info(f"Dummy server started on port {port}")
    server.serve_forever()
# ---------------------------------------------------------------

# YOUR TELEGRAM BOT TOKEN
TOKEN = "8917668880:AAHE-DRbPYgWsAR33VWig3y3z_E97RIL7iQ"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚽ Football Live Bot-এ স্বাগতম! আপনার লাইভ ম্যাচ বা ভিডিও লিংকটি পাঠান।")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    await update.message.reply_text(f"🔄 আপনার লিংকটি প্রসেস করা হচ্ছে: {user_text}\nদয়া করে কিছুক্ষণ অপেক্ষা করুন...")
    
    # এখানে আপনার লাইভ স্ট্রিমিং বা ফিল্টারিং এর মূল লজিকটি কাজ করবে।

def main():
    # Start the dummy web server in a separate thread so Render doesn't crash
    Thread(target=run_dummy_server, daemon=True).start()

    # Build the application
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
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
