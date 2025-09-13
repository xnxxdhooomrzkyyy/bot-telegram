import os
import pandas as pd
from reportlab.graphics.barcode import code128
from reportlab.graphics.shapes import Drawing, String
from reportlab.graphics import renderPM
from reportlab.lib.units import mm
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, CallbackQueryHandler
)
from flask import Flask
import threading

# ====== Konfigurasi ======
TOKEN = "7694961040:AAG84xUADIXwu-U2YiZfBIsGpbNp4vU4zfg"  # ganti dengan token asli dari BotFather
WORKDIR = "barcodes"
os.makedirs(WORKDIR, exist_ok=True)

# ====== Load Excel sekali saja ======
EXCEL_FILE = "produk.xlsx"
produk_df = pd.read_excel(EXCEL_FILE)

# ====== Handler Bot ======
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo! Bot Barcode siap.\n"
        "Ketik *PLU* atau *Nama Produk* untuk mencari barcode.",
        parse_mode="Markdown"
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_input = update.message.text.strip()

    if user_input.isdigit():
        row = produk_df[produk_df["PLU"] == int(user_input)]
    else:
        row = produk_df[produk_df["Nama Produk"].str.contains(user_input, case=False, na=False)]

    if row.empty:
        await update.message.reply_text(f"❌ Tidak ditemukan untuk '{user_input}'.")
        return

    if len(row) > 1:
        keyboard = [
            [InlineKeyboardButton(f"{r['Nama Produk']} (PLU {r['PLU']})", callback_data=str(r["PLU"]))]
            for _, r in row.iterrows()
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Ditemukan {len(row)} produk untuk '{user_input}'. Pilih salah satu:",
            reply_markup=reply_markup
        )
    else:
        await kirim_barcode(update, row.iloc[0])

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plu = int(query.data)
    row = produk_df[produk_df["PLU"] == plu].iloc[0]
    await kirim_barcode(query, row, from_callback=True)

async def kirim_barcode(update_or_query, row, from_callback=False):
    nama = str(row["Nama Produk"])
    plu = str(row["PLU"])
    barcode_val = str(row["Barcode"])

    barcode_obj = code128.Code128(barcode_val, barHeight=30*mm, barWidth=0.5*mm)
    drawing = Drawing(80*mm, 60*mm)
    drawing.add(String(5*mm, 50*mm, nama, fontName="Helvetica", fontSize=12))
    drawing.add(barcode_obj)
    drawing.add(String(5*mm, 5*mm, barcode_val, fontName="Helvetica", fontSize=12))

    filename = os.path.join(WORKDIR, f"{plu}_{barcode_val}.png")
    renderPM.drawToFile(drawing, filename, fmt="PNG")

    text = f"📦 {nama}\nPLU: {plu}\nBarcode: {barcode_val}"

    if from_callback:
        await update_or_query.message.reply_text(text)
        await update_or_query.message.reply_photo(photo=open(filename, "rb"))
    else:
        await update_or_query.message.reply_text(text)
        await update_or_query.message.reply_photo(photo=open(filename, "rb"))

def run_bot():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.run_polling()

# ====== Flask dummy server ======
flask_app = Flask(__name__)

@flask_app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    flask_app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    run_bot()
