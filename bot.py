import os
import pandas as pd
import barcode
from barcode.writer import ImageWriter
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters

# Ambil token dari environment variable
TOKEN = "7694961040:AAG84xUADIXwu-U2YiZfBIsGpbNp4vU4zfg"
EXCEL_FILE = "produk.xlsx"
OUTPUT_FOLDER = "barcodes"

# Pastikan folder ada
if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

def load_excel():
    """Selalu baca file produk.xlsx terbaru"""
    return pd.read_excel(EXCEL_FILE)

def generate_barcode_image(kode_barcode: str, filename: str):
    """Buat barcode dari angka di Excel sesuai panjangnya"""
    if os.path.exists(filename):
        return filename

    if len(kode_barcode) == 13 and kode_barcode.isdigit():
        barcode_class = barcode.get_barcode_class("ean13")
    elif len(kode_barcode) == 8 and kode_barcode.isdigit():
        barcode_class = barcode.get_barcode_class("ean8")
    else:
        barcode_class = barcode.get_barcode_class("code128")  # fallback universal

    my_barcode = barcode_class(kode_barcode, writer=ImageWriter())
    my_barcode.save(filename.replace(".png", ""))  # library otomatis tambah .png
    return filename

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Halo! 👋\nKetik *PLU* atau *Nama Produk* untuk dapat barcode.\n"
        "Gunakan /list untuk lihat semua produk, atau /search <kata kunci>.",
        parse_mode="Markdown"
    )

async def list_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    df = load_excel()
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

async def cari_dan_tampilkan(update, query_text: str):
    df = load_excel()

    if query_text.isdigit():
        produk = df[df["PLU"].astype(str).str.contains(query_text)]
    else:
        produk = df[df["Nama Produk"].str.contains(query_text, case=False, na=False)]

    if produk.empty:
        await update.message.reply_text("⚠️ Produk tidak ditemukan.")
        return

    if len(produk) == 1:
        row = produk.iloc[0]
        await kirim_barcode(update, row)
    else:
        keyboard = []
        for _, row in produk.iterrows():
            keyboard.append([
                InlineKeyboardButton(f"{row['PLU']} - {row['Nama Produk']}", callback_data=str(row["Barcode"]))
            ])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🔍 Pilih produk:", reply_markup=reply_markup)

async def pilih_produk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kode_barcode = query.data
    df = load_excel()
    row = df[df["Barcode"].astype(str) == kode_barcode].iloc[0]
    await kirim_barcode(query, row, is_callback=True)

async def kirim_barcode(update_or_query, row, is_callback=False):
    plu = str(row["PLU"])
    nama = str(row["Nama Produk"])
    kode_barcode = str(row["Barcode"])
    filename = os.path.join(OUTPUT_FOLDER, f"{plu}_{nama}.png")

    # Generate barcode dari angka Excel
    generate_barcode_image(kode_barcode, filename)

    caption = f"📦 {nama}\n🔑 PLU: {plu}\n🏷️ Barcode: {kode_barcode}"

    if is_callback:
        await update_or_query.message.reply_photo(photo=open(filename, "rb"), caption=caption)
    else:
        await update_or_query.message.reply_photo(photo=open(filename, "rb"), caption=caption)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_produk))
    app.add_handler(CommandHandler("search", search_produk))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, cari_produk))
    app.add_handler(CallbackQueryHandler(pilih_produk))
    print("🤖 Bot jalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
