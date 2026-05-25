import os
import subprocess
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

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
        "⚽ আপনি যদি কোনো **ফুটবল ম্যাচের** লিঙ্ক দেন, আমি নিজে থেকেই কড়া ফুটবল কপিরাইট প্রটেকশন অন করে দেবো।\n"
        "🎬 সাধারণ ভিডিওর লিঙ্ক দিলে সেটি নরমাল ফিল্টারে লাইভ হবে।\n\n"
        "⚙️ প্রথমে আপনার Stream Key পাঠান, তারপর ভিডিওর লিঙ্ক দিন।"
    )

# /stop কমান্ড
async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global active_process
    if active_process and active_process.poll() is None:
        active_process.terminate()
        active_process = None
        await update.message.reply_text("🛑 লাইভ স্ট্রিমটি সফলভাবে বন্ধ করা হয়েছে।")
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

        await update.message.reply_text("🔍 লিঙ্ক থেকে ভিডিও সোর্স খোঁজা হচ্ছে, দয়া করে অপেক্ষা করুন...")

        try:
            ydl_cmd = ['yt-dlp', '-g', '-f', 'best', user_text]
            result = subprocess.run(ydl_cmd, capture_output=True, text=True, check=True)
            direct_url = result.stdout.strip()
        except Exception as e:
            await update.message.reply_text(f"❌ এরর ডিটেইলস (yt-dlp):\n{str(e)}")
            return

        # ---- স্মার্ট ফিল্টার সিলেকশন ----
        # লিঙ্কের ভেতর ফুটবল বা স্পোর্টস জাতীয় শব্দ থাকলে কড়া প্রটেকশন অন হবে
        is_football = any(word in user_text.lower() for word in ["football", "match", "live", "sports", "fifa", "uefa", "vs", "gopal"]) 
        
        if is_football:
            await update.message.reply_text("⚽ **ফুটবল/লাইভ ম্যাচ ডিটেক্ট হয়েছে!** কড়া কপিরাইট প্রটেকশন (জুম + ক্রপ + অডিও হাই-পিচ) অন করা হচ্ছে...")
            # ফুটবল খেলার জন্য কড়া ফিল্টার: ভিডিও ৫% জুম করে চারপাশ থেকে সামান্য ক্রপ করা হবে এবং অডিওর স্পিড ও পিচ আরও বাড়ানো হবে
            video_filter = "hflip,scale=2.0*iw:-1,crop=iw/2:ih/2" 
            audio_filter = "asetrate=44100*1.08,atempo=0.92"
        else:
            await update.message.reply_text("🎬 **সাধারণ ভিডিও ডিটেক্ট হয়েছে!** নরমাল ফিল্টারে লাইভ শুরু হচ্ছে...")
            # সাধারণ ভিডিওর জন্য আপনার আগের নরমাল ফিল্টার
            video_filter = "hflip"
            audio_filter = "asetrate=44100*1.04,atempo=0.96"
        # --------------------------------

        destination = RTMP_URL + CURRENT_STREAM_KEY
        
        # পিসি এবং ক্লাউড (Render) দুই জায়গার জন্যই অটো-পাথ অ্যাডজাস্টমেন্ট
        ffmpeg_exe = "C:/ffmpeg/ffmpeg.exe" if os.path.exists("C:/ffmpeg/ffmpeg.exe") else "ffmpeg"

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
            await update.message.reply_text("🚀 সফল! ফেসবুকে লাইভ ডাটা পাঠানো শুরু হয়েছে। আপনার ফেসবুক পেজ চেক করুন।")
        except Exception as e:
            await update.message.reply_text(f"❌ লাইভ চালু করতে সমস্যা হয়েছে: {e}")

    else:
        CURRENT_STREAM_KEY = user_text
        await update.message.reply_text("✅ Stream Key সফলভাবে যুক্ত হয়েছে! এখন ভিডিওর লিঙ্কটি পাঠান।")

def main():
    print("স্মার্ট ডাবল-ফিল্টার বট চালু হচ্ছে...")
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
