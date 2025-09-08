import os
import sqlite3
import cloudinary
import cloudinary.uploader
from flask import Flask, request, render_template, redirect, url_for, session, send_file, flash
from openpyxl import Workbook
from functools import wraps

app = Flask(__name__)
app.secret_key = "rahasia123"
DB_NAME = "database.db"

# --- Konfigurasi Cloudinary ---
cloudinary.config(
    cloudinary_url=os.getenv("CLOUDINARY_URL", "cloudinary://364918572677439:22BX_pQ1oz6B_cKGdx2OHVxvW1g@dghs2f716")
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
    # tabel retur
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
    # tabel user toko
    c.execute("""
        CREATE TABLE IF NOT EXISTS toko_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode_toko TEXT UNIQUE,
            password TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- decorator untuk proteksi admin ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "admin" not in session:
            flash("Anda harus login sebagai admin dulu!", "danger")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated_function

# ==========================
# LOGIN TOKO
# ==========================
@app.route("/", methods=["GET", "POST"])
def login():
    conn = get_db_connection()
    toko_list = conn.execute("SELECT kode_toko FROM toko_users").fetchall()

    if request.method == "POST":
        kode_toko = request.form["kode_toko"]
        password = request.form["password"]

        user = conn.execute(
            "SELECT * FROM toko_users WHERE kode_toko = ? AND password = ?",
            (kode_toko, password)
        ).fetchone()

        if user:
            session["user"] = kode_toko
            conn.close()
            return redirect(url_for("dashboard"))
        else:
            flash("Login gagal, coba lagi!", "danger")

    conn.close()
    return render_template("login.html", toko_list=[row["kode_toko"] for row in toko_list])

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

# ==========================
# DASHBOARD TOKO
# ==========================
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

# ==========================
# TAMBAH RETUR
# ==========================
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

# ==========================
# HAPUS RETUR
# ==========================
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

# ==========================
# EXPORT RETUR
# ==========================
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

# ==========================
# ADMIN LOGIN
# ==========================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        if username == "ADMIN" and password == "admin123":
            session["admin"] = True
            return redirect(url_for("manage_toko"))
        else:
            flash("Login admin gagal ❌", "danger")

    return render_template("admin_login.html")

@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    flash("Anda sudah logout dari admin ✅", "success")
    return redirect(url_for("admin_login"))

# ==========================
# ADMIN MANAJEMEN TOKO
# ==========================
@app.route("/admin/toko", methods=["GET", "POST"])
@admin_required
def manage_toko():
    if request.method == "POST":
        kode_toko = request.form["kode_toko"].strip().upper()
        password = request.form["password"].strip()

        if kode_toko and password:
            try:
                conn = get_db_connection()
                conn.execute(
                    "INSERT INTO toko_users (kode_toko, password) VALUES (?, ?)",
                    (kode_toko, password)
                )
                conn.commit()
                conn.close()
                flash(f"Toko {kode_toko} berhasil ditambahkan ✅", "success")
            except Exception as e:
                flash(f"Gagal menambah toko: {e}", "danger")

        return redirect(url_for("manage_toko"))

    conn = get_db_connection()
    toko_list = conn.execute("SELECT * FROM toko_users ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("manage_toko.html", toko_list=toko_list)

@app.route("/admin/toko/delete/<int:id>", methods=["POST"])
@admin_required
def delete_toko(id):
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM toko_users WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        flash("Toko berhasil dihapus ❌", "danger")
    except Exception as e:
        flash(f"Gagal menghapus toko: {e}", "danger")

    return redirect(url_for("manage_toko"))

# ==========================
# RENDER ENTRY POINT
# ==========================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
