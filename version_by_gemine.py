import os
import re
import shutil
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, ConversationHandler, filters
)
from moviepy.editor import *
from PIL import Image

# ================== CONFIG ==================
# APNA NAYA TOKEN YAHA DAALEIN (Purana leak ho gaya hai)
BOT_TOKEN = "8413615296:AAGVBz3WBsdesZSjs3ICnLyrEEK8dAV5k08"

BASE_DIR = os.getcwd()
TEMP_DIR = os.path.join(BASE_DIR, "temp")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
FONTS_DIR = os.path.join(ASSETS_DIR, "fonts")

# Directory Setup
for d in [TEMP_DIR, ASSETS_DIR, FONTS_DIR]:
    os.makedirs(d, exist_ok=True)

for d in ["lyrics", "audio", "bg", "output"]:
    os.makedirs(os.path.join(TEMP_DIR, d), exist_ok=True)

# ================== STATES ==================
(LYRICS, MODE, BG, FONT, FONT_SIZE, COLOR, AUDIO, QUALITY) = range(8)

# ================== HELPERS ==================
def clear_temp():
    """Safely clears temporary files except the output folder."""
    for folder in ["lyrics", "audio", "bg"]:
        path = os.path.join(TEMP_DIR, folder)
        if os.path.exists(path):
            shutil.rmtree(path)
            os.makedirs(path)

def parse_lrc(path):
    lines = []
    if not os.path.exists(path): return lines
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            match = re.match(r"\[(\d+):(\d+\.?\d*)\](.*)", line)
            if match:
                m, s, text = match.groups()
                time = int(m)*60 + float(s)
                if text.strip(): # Only add non-empty lines
                    lines.append((time, text.strip()))
    return sorted(lines, key=lambda x: x[0])

# ================== COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_temp()
    context.user_data.clear() # Reset session
    await update.message.reply_text("🎵 Welcome! Please upload your sync lyrics (.lrc) file.")
    return LYRICS

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 Lyrics Video Maker Bot\n"
        "Create high-quality synced lyrics videos.\n\n"
        "Status: Online ✅"
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    clear_temp()
    await update.message.reply_text("❌ Process cancelled. Type /start to begin again.")
    return ConversationHandler.END

# ================== STEPS ==================
async def lyrics_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc or not doc.file_name.lower().endswith(".lrc"):
        await update.message.reply_text("❌ Please send a valid .lrc file.")
        return LYRICS

    path = os.path.join(TEMP_DIR, "lyrics", doc.file_name)
    file = await doc.get_file()
    await file.download_to_drive(path)
    context.user_data["lrc"] = path

    kb = [[InlineKeyboardButton("🎬 Landscape (16:9)", callback_data="video"),
           InlineKeyboardButton("📱 Portrait/Shorts (9:16)", callback_data="shorts")]]
    await update.message.reply_text("Select Video Mode:", reply_markup=InlineKeyboardMarkup(kb))
    return MODE

async def mode_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    context.user_data["mode"] = q.data
    await q.message.reply_text("Now upload a Background (Image or MP4 Video).")
    return BG

async def bg_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Works for both Photos and Documents
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        ext = ".jpg"
    elif update.message.document:
        file = await update.message.document.get_file()
        ext = os.path.splitext(update.message.document.file_name)[1]
    else:
        await update.message.reply_text("❌ Please upload an image or video file.")
        return BG

    path = os.path.join(TEMP_DIR, "bg", f"bg_input{ext}")
    await file.download_to_drive(path)
    context.user_data["bg"] = path

    # Font list logic
    fonts = [f for f in os.listdir(FONTS_DIR) if f.endswith(('.ttf', '.otf'))]
    buttons = [[InlineKeyboardButton(f, callback_data=f)] for f in fonts]
    buttons.append([InlineKeyboardButton("➕ Upload New Font", callback_data="add")])

    await update.message.reply_text("Select Font Style:", reply_markup=InlineKeyboardMarkup(buttons))
    return FONT

async def font_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q:
        await q.answer()
        if q.data == "add":
            await q.message.reply_text("Please upload a .ttf or .otf font file.")
            return FONT
        context.user_data["font"] = os.path.join(FONTS_DIR, q.data)
        await q.message.reply_text("Enter font size (e.g. 50) or type 'skip':")
        return FONT_SIZE
    
    # Handle font upload
    doc = update.message.document
    if doc and doc.file_name.lower().endswith((".ttf", ".otf")):
        path = os.path.join(FONTS_DIR, doc.file_name)
        await doc.get_file().download_to_drive(path)
        await update.message.reply_text("✅ Font saved! Use /start to select it.")
        return ConversationHandler.END
    
    await update.message.reply_text("❌ Invalid file. Please upload a font.")
    return FONT

async def font_size_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text.lower()
    if txt != "skip":
        if not txt.isdigit():
            await update.message.reply_text("❌ Send a valid number.")
            return FONT_SIZE
        context.user_data["font_size"] = int(txt)
    
    await update.message.reply_text("Enter Hex Color (e.g. #ffffff) or type 'skip':")
    return COLOR

async def color_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    txt = update.message.text
    if txt.lower() != "skip":
        context.user_data["color"] = txt
    await update.message.reply_text("Upload the Audio file (MP3/WAV/M4A):")
    return AUDIO

async def audio_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.audio or update.message.document
    if not doc:
        await update.message.reply_text("❌ Please upload audio.")
        return AUDIO

    path = os.path.join(TEMP_DIR, "audio", "input_audio.mp3")
    await (await doc.get_file()).download_to_drive(path)
    context.user_data["audio"] = path

    kb = [[InlineKeyboardButton("720p", callback_data="720"),
           InlineKeyboardButton("1080p", callback_data="1080")]]
    await update.message.reply_text("Select Export Quality:", reply_markup=InlineKeyboardMarkup(kb))
    return QUALITY

async def quality_step(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    
    status_msg = await q.message.reply_text("⏳ Processing video... (This may take a minute)")

    try:
        lrc_data = parse_lrc(context.user_data["lrc"])
        audio = AudioFileClip(context.user_data["audio"])
        bg_path = context.user_data["bg"]
        
        # Base Background Setup
        is_video = bg_path.lower().endswith(".mp4")
        if is_video:
            base = VideoFileClip(bg_path).loop(duration=audio.duration)
        else:
            base = ImageClip(bg_path).set_duration(audio.duration)

        # Resizing based on mode
        size = (1280, 720) if context.user_data["mode"] == "video" else (720, 1280)
        base = base.resize(newsize=size)

        clips = [base]
        
        # Lyrics Overlay
        for i, (start_t, text) in enumerate(lrc_data):
            end_t = lrc_data[i+1][0] if i+1 < len(lrc_data) else audio.duration
            
            txt_clip = TextClip(
                text,
                fontsize=context.user_data.get("font_size", 60),
                color=context.user_data.get("color", "white"),
                font=context.user_data.get("font", "Arial"),
                method='caption',
                size=(size[0]*0.8, None)
            ).set_start(start_t).set_duration(end_t - start_t).set_position("center")
            
            clips.append(txt_clip)

        final_video = CompositeVideoClip(clips).set_audio(audio)
        out_path = os.path.join(TEMP_DIR, "output", f"final_{q.from_user.id}.mp4")
        
        # Render
        final_video.write_videofile(out_path, fps=24, codec="libx264", audio_codec="aac")

        with open(out_path, "rb") as video_file:
            await q.message.reply_video(video=video_file, caption="✅ Video Created Successfully!")
        
        await status_msg.delete()
        
    except Exception as e:
        await q.message.reply_text(f"❌ Error: {str(e)}")
    
    clear_temp()
    return ConversationHandler.END

# ================== MAIN ==================
if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LYRICS: [MessageHandler(filters.Document.ALL, lyrics_step)],
            MODE: [CallbackQueryHandler(mode_step)],
            BG: [MessageHandler(filters.Document.ALL | filters.PHOTO, bg_step)],
            FONT: [CallbackQueryHandler(font_step), MessageHandler(filters.Document.ALL, font_step)],
            FONT_SIZE: [MessageHandler(filters.TEXT & ~filters.COMMAND, font_size_step)],
            COLOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, color_step)],
            AUDIO: [MessageHandler(filters.AUDIO | filters.Document.ALL, audio_step)],
            QUALITY: [CallbackQueryHandler(quality_step)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("about", about))

    print("Bot is running...")
    app.run_polling()
