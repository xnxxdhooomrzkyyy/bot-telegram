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
# Lebih aman pakai Environment Variable di Render
cloudinary.config(
    cloudinary_url=os.getenv("CLOUDINARY_URL=cloudinary://364918572677439:22BX_pQ1oz6B_cKGdx2OHVxvW1g@dghs2f716")
)

# --- fungsi untuk koneksi database ---
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
            nomor_retur TEXT,
            nomor_mobil TEXT,
            nama_driver TEXT,
            bukti TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

# panggil saat aplikasi start
init_db()

# --- route login sederhana ---
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        kode_toko = request.form["kode_toko"]
        password = request.form["password"]
        if kode_toko == "admin" and password == "123":
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
    conn = get_db_connection()
    data = conn.execute("SELECT * FROM retur ORDER BY created_at DESC").fetchall()
    conn.close()
    return render_template("dashboard.html", data=data)

# --- tambah retur (upload ke Cloudinary) ---
@app.route("/tambah", methods=["GET", "POST"])
def tambah():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        try:
            nomor_retur = request.form.get("nomor_retur")
            nomor_mobil = request.form.get("nomor_mobil")
            nama_driver = request.form.get("nama_driver")

            file_url = None
            if "bukti" in request.files:
                file = request.files["bukti"]
                if file.filename != "":
                    upload_result = cloudinary.uploader.upload(file)
                    file_url = upload_result.get("secure_url")

            conn = get_db_connection()
            conn.execute(
                "INSERT INTO retur (nomor_retur, nomor_mobil, nama_driver, bukti) VALUES (?, ?, ?, ?)",
                (nomor_retur, nomor_mobil, nama_driver, file_url),
            )
            conn.commit()
            conn.close()

            flash("Data retur berhasil ditambahkan ✅", "success")
        except Exception as e:
            print("Error saat tambah retur:", e)
            flash("Gagal menambahkan retur ❌", "danger")

        return redirect(url_for("dashboard"))

    return render_template("tambah.html")

# --- route untuk hapus data ---
@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    conn = get_db_connection()
    conn.execute("DELETE FROM retur WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    flash("Data berhasil dihapus", "danger")
    return redirect(url_for("dashboard"))

#--- download excel ---
@app.route("/export")
def export():
    if "user" not in session:
        return redirect(url_for("login"))

    try:
        conn = get_db_connection()
        data = conn.execute("SELECT * FROM retur").fetchall()
        conn.close()

        wb = Workbook()
        ws = wb.active
        ws.append(["ID", "Nomor Retur", "Nomor Mobil", "Nama Driver", "Bukti (URL)", "Created At"])

        for row in data:
            ws.append([
                row["id"],
                row["nomor_retur"],
                row["nomor_mobil"],
                row["nama_driver"],
                row["bukti"],
                row["created_at"]
            ])

        file_path = "retur_export.xlsx"
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

