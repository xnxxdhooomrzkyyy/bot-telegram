import os
import sqlite3
import cloudinary
import cloudinary.uploader
from flask import Flask, request, render_template, redirect, url_for, session, send_file, flash
from openpyxl import Workbook

app = Flask(__name__)
app.secret_key = "rahasia123"
DB_NAME = "database.db"

# --- Konfigurasi Cloudinary ---
cloudinary.config(
    cloudinary_url=os.getenv("CLOUDINARY_URL=cloudinary://364918572677439:22BX_pQ1oz6B_cKGdx2OHVxvW1g@dghs2f716")
)

# --- fungsi koneksi database ---
def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# --- inisialisasi database ---
def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS retur (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode_toko TEXT,
            nomor_retur TEXT,
            nomor_mobil TEXT,
            nama_driver TEXT,
            bukti TEXT,
            tanggal_manual TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- daftar akun toko ---
TOKO_USERS = {
    "T8NR": "t8nr",
    #"TXMO": "txmo",
    # tambah toko lain di sini
}

# --- route login ---
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        kode_toko = request.form["kode_toko"]
        password = request.form["password"]

        if kode_toko in TOKO_USERS and TOKO_USERS[kode_toko] == password:
            session["user"] = kode_toko
            return redirect(url_for("dashboard"))
        else:
            flash("Login gagal, coba lagi!", "danger")
    return render_template("login.html")

# --- dashboard ---
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    q = request.args.get("q", "").strip()
    conn = get_db_connection()
    if q:
        data = conn.execute(
            "SELECT * FROM retur WHERE kode_toko = ? AND nomor_retur LIKE ? ORDER BY created_at DESC",
            (session["user"], "%" + q + "%"),
        ).fetchall()
    else:
        data = conn.execute(
            "SELECT * FROM retur WHERE kode_toko = ? ORDER BY created_at DESC",
            (session["user"],),
        ).fetchall()
    conn.close()
    return render_template("dashboard.html", data=data, q=q)

# --- tambah retur ---
@app.route("/tambah", methods=["GET", "POST"])
def tambah():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            nomor_retur = request.form.get("nomor_retur")
            nomor_mobil = request.form.get("nomor_mobil")
            nama_driver = request.form.get("nama_driver")
            tanggal_manual = request.form.get("tanggal_manual")

            file_url = None
            if "bukti" in request.files:
                file = request.files["bukti"]
                if file.filename != "":
                    upload_result = cloudinary.uploader.upload(file)
                    file_url = upload_result.get("secure_url")

            conn = get_db_connection()
            conn.execute(
                "INSERT INTO retur (kode_toko, nomor_retur, nomor_mobil, nama_driver, bukti, tanggal_manual) VALUES (?, ?, ?, ?, ?, ?)",
                (session["user"], nomor_retur, nomor_mobil, nama_driver, file_url, tanggal_manual),
            )
            conn.commit()
            conn.close()

            flash("Data retur berhasil ditambahkan ✅", "success")
        except Exception as e:
            print("Error saat tambah retur:", e)
            flash("Gagal menambahkan retur ❌", "danger")

        return redirect(url_for("dashboard"))

    return render_template("tambah.html")

# --- hapus retur ---
@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    if "user" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute("DELETE FROM retur WHERE id = ? AND kode_toko = ?", (id, session["user"]))
    conn.commit()
    conn.close()
    flash("Data berhasil dihapus", "danger")
    return redirect(url_for("dashboard"))

# --- export Excel ---
@app.route("/export")
def export():
    if "user" not in session:
        return redirect(url_for("login"))

    try:
        conn = get_db_connection()
        data = conn.execute("SELECT * FROM retur WHERE kode_toko = ?", (session["user"],)).fetchall()
        conn.close()

        wb = Workbook()
        ws = wb.active
        ws.append(["ID", "Kode Toko", "Nomor Retur", "Nomor Mobil", "Nama Driver", "Bukti (URL)", "Tanggal Manual", "Created At"])

        for row in data:
            ws.append([
                row["id"],
                row["kode_toko"],
                row["nomor_retur"],
                row["nomor_mobil"],
                row["nama_driver"],
                row["bukti"],
                row["tanggal_manual"],
                row["created_at"],
            ])

        file_path = f"retur_export_{session['user']}.xlsx"
        wb.save(file_path)

        return send_file(file_path, as_attachment=True)

    except Exception as e:
        print("Error saat export:", e)
        flash("Gagal mengekspor data ❌", "danger")
        return redirect(url_for("dashboard"))

# --- logout ---
@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

