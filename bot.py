import os, io, uuid
from PIL import Image, ImageDraw
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

TOKEN = os.environ["TG_TOKEN"]
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "secret-path")
APP_URL = os.environ.get("APP_URL")

app = Flask(__name__)
application = Application.builder().token(TOKEN).build()
SESSIONS = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ أرسل صورة وسأرسم عليها شبكة لتعليم النجوم والقنابل")

def render_image_with_grid(img: Image.Image, rows: int, cols: int, marks: dict):
    max_w = 900
    if img.width > max_w:
        ratio = max_w / img.width
        img = img.resize((int(img.width*ratio), int(img.height*ratio)), Image.LANCZOS)
    canvas = img.convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    cw = canvas.width / cols
    ch = canvas.height / rows
    for i in range(1, cols):
        draw.line([(i*cw,0),(i*cw,canvas.height)], fill=(255,255,255,180), width=2)
    for j in range(1, rows):
        draw.line([(0,j*ch),(canvas.width,j*ch)], fill=(255,255,255,180), width=2)
    for (r,c), t in marks.items():
        x0 = int(c*cw); y0 = int(r*ch)
        x1 = int((c+1)*cw); y1 = int((r+1)*ch)
        cx = (x0+x1)//2; cy = (y0+y1)//2
        size = int(min(cw,ch)*0.28)
        if t == 'bomb':
            draw.line([(x0+8,y0+8),(x1-8,y1-8)], fill=(255,0,0,230), width=8)
            draw.line([(x1-8,y0+8),(x0+8,y1-8)], fill=(255,0,0,230), width=8)
        else:
            draw.ellipse([(cx-size,cy-size),(cx+size,cy+size)], outline=(255,215,0,230), width=8)
    bio = io.BytesIO()
    bio.name = "marked.png"
    canvas.convert("RGB").save(bio, "PNG")
    bio.seek(0)
    return bio

def build_keyboard(session_id, rows, cols):
    kb = []
    for r in range(rows):
        row = []
        for c in range(cols):
            row.append(InlineKeyboardButton("◻️", callback_data=f"{session_id}|{r}|{c}"))
        kb.append(row)
    kb.append([
        InlineKeyboardButton("⭐/❌", callback_data=f"{session_id}|mode"),
        InlineKeyboardButton("🧽 مسح", callback_data=f"{session_id}|clear"),
    ])
    return InlineKeyboardMarkup(kb)

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.photo[-1].get_file()
    bio = io.BytesIO()
    await file.download_to_memory(out=bio)
    img = Image.open(bio)
    rows, cols = 5, 5
    session_id = str(uuid.uuid4())[:8]
    SESSIONS[session_id] = {'image': img.copy(), 'rows': rows, 'cols': cols, 'marks': {}, 'mode':'star'}
    out = render_image_with_grid(img, rows, cols, {})
    kb = build_keyboard(session_id, rows, cols)
    await update.message.reply_photo(photo=InputFile(out, filename="grid.png"), caption=f"شبكة {rows}×{cols}", reply_markup=kb)

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data.split("|")
    session_id = data[0]
    if session_id not in SESSIONS: return
    sess = SESSIONS[session_id]
    if len(data) == 2:
        if data[1] == "mode":
            sess['mode'] = 'bomb' if sess['mode']=='star' else 'star'
        elif data[1] == "clear":
            sess['marks'] = {}
    else:
        r, c = int(data[1]), int(data[2])
        key = (r,c)
        if key in sess['marks']:
            del sess['marks'][key]
        else:
            sess['marks'][key] = sess['mode']
    out = render_image_with_grid(sess['image'], sess['rows'], sess['cols'], sess['marks'])
    kb = build_keyboard(session_id, sess['rows'], sess['cols'])
    await q.message.reply_photo(photo=InputFile(out, filename="grid.png"), reply_markup=kb)

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
application.add_handler(CallbackQueryHandler(callback_handler))

@app.post(f"/{WEBHOOK_SECRET}")
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return jsonify(ok=True)

@app.get("/")
def home():
    return "Bot Running ✅", 200

if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()
    if APP_URL:
        loop.run_until_complete(application.bot.set_webhook(url=f"{APP_URL}/{WEBHOOK_SECRET}"))
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
