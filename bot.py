import os
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pandas as pd
import barcode
from barcode.writer import ImageWriter
import telegram

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ===== CONFIG =====
HARD_CODED_TOKEN = None
TOKEN = os.getenv("TELEGRAM_TOKEN") or HARD_CODED_TOKEN

CSV_FILE = "produk.csv"   # file produk pakai ; sebagai delimiter
OUTPUT_FOLDER = "barcodes"
DEFAULT_PORT = 10000
# ==================

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

def safe_filename(s: str) -> str:
    s = str(s)
    s = re.sub(r"[^\w\-_\. ]", "_", s)
    s = s.replace(" ", "_")
    return s

# ===== Dummy HTTP server =====
PORT = int(os.getenv("PORT", DEFAULT_PORT))
print("Detected PORT env:", PORT)
print("PTB version:", getattr(telegram, "__version__", "unknown"))

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        return

def run_http_server():
    try:
        server = HTTPServer(("0.0.0.0", PORT), SimpleHandler)
        print(f"Starting dummy HTTP server on port {PORT}")
        server.serve_forever()
    except Exception as e:
        print("HTTP server error:", e)

def start_http_thread():
    t = threading.Thread(target=run_http_server, daemon=True)
    t.start()

# ===== CSV & barcode helpers =====
def load_csv():
    if not os.path.exists(CSV_FILE):
        raise FileNotFoundError(f"File {CSV_FILE} tidak ditemukan.")
    try:
        # coba baca dengan koma
        df = pd.read_csv(CSV_FILE)
        # kalau hasilnya cuma 1 kolom, berarti pakai delimiter ";"
        if df.shape[1] == 1:
            df = pd.read_csv(CSV_FILE, delimiter=";")
        return df
    except Exception as e:
        raise RuntimeError(f"Gagal baca {CSV_FILE}: {e}")

def generate_barcode_image(kode_barcode: str, filename: str):
    base = filename
    if base.endswith(".png"):
        base = base[:-4]
    if os.path.exists(base + ".png"):
        return base + ".png"
    try:
        if len(kode_barcode) == 13 and kode_barcode.isdigit():
            barcode_class = barcode.get_barcode_class("ean13")
        elif len(kode_barcode) == 8 and kode_barcode.isdigit():
            barcode_class = barcode.get_barcode_class("ean8")
        else:
            barcode_class = barcode.get_barcode_class("code128")
        my_barcode = barcode_class(kode_barcode, writer=ImageWriter())
        my_barcode.save(base)
        return base + ".png"
    except Exception as e:
        print("Error generating barcode:", e)
        raise

# ===== Bot Handlers =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo! Semuanya 👋\nKetik *PLU* atau *Nama Produk* untuk dapat barcode.\n",
        parse_mode="Markdown",
    )

async def list_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        df = load_csv()
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        return
    pesan = "📋 Daftar Produk:\n"
    for i, row in df.iterrows():
        pesan += f"{i+1}. {row['PLU']} - {row['Nama Produk']}\n"
    await update.message.reply_text(pesan)

async def search_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("⚠️ Format: /search <kata kunci>")
        return
    query_text = " ".join(context.args).strip()
    await cari_dan_tampilkan(update, query_text)

async def cari_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_text = str(update.message.text).strip()
    await cari_dan_tampilkan(update, query_text)

async def cari_dan_tampilkan(update_obj, query_text: str):
    try:
        df = load_csv()
    except Exception as e:
        await update_obj.message.reply_text(f"Error: {e}")
        return

    if query_text.isdigit():
        produk = df[df["PLU"].astype(str).str.contains(query_text)]
    else:
        produk = df[df["Nama Produk"].str.contains(query_text, case=False, na=False)]

    if produk.empty:
        await update_obj.message.reply_text("⚠️ Produk tidak ditemukan.")
        return

    if len(produk) == 1:
        row = produk.iloc[0]
        await kirim_barcode(update_obj, row)
    else:
        keyboard = []
        for _, row in produk.iterrows():
            keyboard.append(
                [InlineKeyboardButton(f"{row['PLU']} - {row['Nama Produk']}", callback_data=str(row["Barcode"]))]
            )
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update_obj.message.reply_text("🔍 Pilih produk:", reply_markup=reply_markup)

async def pilih_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kode_barcode = query.data
    df = load_csv()
    row = df[df["Barcode"].astype(str) == kode_barcode].iloc[0]
    await kirim_barcode(query, row, is_callback=True)

async def kirim_barcode(update_or_query, row, is_callback=False):
    plu = str(row["PLU"])
    nama = str(row["Nama Produk"])
    kode_barcode = str(row["Barcode"])
    safe_name = safe_filename(f"{plu}_{nama}")
    filename_base = os.path.join(OUTPUT_FOLDER, safe_name)
    try:
        pngfile = generate_barcode_image(kode_barcode, filename_base)
    except Exception as e:
        print("generate_barcode_image error:", e)
        await update_or_query.message.reply_text("Gagal generate barcode.")
        return

    caption = f"📦 {nama}\n🔑 PLU: {plu}\n🏷️ Barcode: {kode_barcode}"
    try:
        with open(pngfile, "rb") as photo:
            await update_or_query.message.reply_photo(photo=photo, caption=caption)
    except Exception as e:
        print("kirim_barcode error:", e)
        await update_or_query.message.reply_text("Gagal mengirim file barcode.")

# ===== Main =====
def main():
    if not TOKEN:
        raise ValueError("❌ TELEGRAM_TOKEN belum diset. Set env var TELEGRAM_TOKEN atau isi HARD_CODED_TOKEN di file.")

    start_http_thread()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_produk))
    app.add_handler(CommandHandler("search", search_produk))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, cari_produk))
    app.add_handler(CallbackQueryHandler(pilih_produk))

    print("🤖 Bot started (polling)...")
    app.run_polling()

if __name__ == "__main__":
    main()



