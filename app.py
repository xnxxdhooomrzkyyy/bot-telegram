import os
import io
import sqlite3
from datetime import datetime
from flask import Flask, request, render_template, redirect, url_for, session, send_file, flash
from openpyxl import Workbook
import cloudinary
import cloudinary.uploader

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change_this_locally")

# Cloudinary config (dibaca dari environment variables di Render)
cloudinary.config(
    cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME"),
    api_key    = os.environ.get("CLOUDINARY_API_KEY"),
    api_secret = os.environ.get("CLOUDINARY_API_SECRET"),
    secure     = True
)

DATABASE = "pengiriman.db"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS pengiriman (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode_toko TEXT,
            nrb TEXT,
            tanggal TEXT,
            no_mobil TEXT,
            driver TEXT,
            foto TEXT,
            created_at TEXT
        )
    """)
    db.commit()
    db.close()

@app.before_first_request
def startup():
    init_db()

# contoh user sederhana
USERS = {
    "T8NR": "t8nr",
    "admin": "admin"
}

@app.route("/", methods=["GET", "POST"])
def login():
    if "kode_toko" in session:
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        kode_toko = request.form.get("kode_toko")
        password = request.form.get("password")
        if kode_toko in USERS and USERS[kode_toko] == password:
            session["kode_toko"] = kode_toko
            return redirect(url_for("dashboard"))
        else:
            error = "Kode toko / password salah"
    return render_template("login.html", error=error)

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "kode_toko" not in session:
        return redirect(url_for("login"))
    kode_toko = session["kode_toko"]
    success = None

    if request.method == "POST":
        nrb = request.form.get("nrb")
        tanggal = request.form.get("tanggal")
        no_mobil = request.form.get("no_mobil")
        driver = request.form.get("driver")
        foto = request.files.get("foto")

        foto_url = ""
        if foto and foto.filename:
            # Upload file ke Cloudinary
            # Jika error, coba cloudinary.uploader.upload(foto.stream, folder="pengiriman")
            result = cloudinary.uploader.upload(foto, folder="pengiriman")
            foto_url = result.get("secure_url", "")

        db = get_db()
        db.execute(
            "INSERT INTO pengiriman (kode_toko, nrb, tanggal, no_mobil, driver, foto, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (kode_toko, nrb, tanggal, no_mobil, driver, foto_url, datetime.utcnow().isoformat())
        )
        db.commit()
        db.close()
        success = f"Data berhasil disimpan (NRB: {nrb})"

    filter_nrb = request.args.get("filter_nrb", "").strip()
    db = get_db()
    if filter_nrb:
        rows = db.execute("SELECT * FROM pengiriman WHERE kode_toko = ? AND nrb LIKE ? ORDER BY id DESC", (kode_toko, f"%{filter_nrb}%")).fetchall()
    else:
        rows = db.execute("SELECT * FROM pengiriman WHERE kode_toko = ? ORDER BY id DESC", (kode_toko,)).fetchall()
    db.close()
    return render_template("dashboard.html", kode_toko=kode_toko, success=success, riwayat=rows, filter_nrb=filter_nrb)

@app.route("/export_excel")
def export_excel():
    if "kode_toko" not in session:
        return redirect(url_for("login"))

    kode_toko = session["kode_toko"]
    filter_nrb = request.args.get("filter_nrb", "").strip()

    db = get_db()
    if filter_nrb:
        rows = db.execute("SELECT * FROM pengiriman WHERE kode_toko = ? AND nrb LIKE ? ORDER BY id DESC", (kode_toko, f"%{filter_nrb}%")).fetchall()
    else:
        rows = db.execute("SELECT * FROM pengiriman WHERE kode_toko = ? ORDER BY id DESC", (kode_toko,)).fetchall()
    db.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Riwayat Pengiriman"
    ws.append(["NRB", "Tanggal", "No Mobil", "Driver", "Foto URL", "Created At"])
    for r in rows:
        ws.append([r["nrb"], r["tanggal"], r["no_mobil"], r["driver"], r["foto"], r["created_at"]])

    stream = io.BytesIO()
    wb.save(stream)
    stream.seek(0)
    filename = f"riwayat_{kode_toko}.xlsx"

    return send_file(
        stream,
        as_attachment=True,
        download_name=filename,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.route("/logout")
def logout():
    session.pop("kode_toko", None)
    return redirect(url_for("login"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
