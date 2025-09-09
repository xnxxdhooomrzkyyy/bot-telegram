import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
import cloudinary
import cloudinary.uploader

# --- Konfigurasi Aplikasi ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecret")

DB_NAME = "database.db"

# --- Cloudinary Config (gunakan env variable untuk keamanan) ---
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)

# --- DB Helper ---
def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    # Table users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT
        )
    """)

    # Table retur (setiap data punya user_id)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS retur (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            nomor_retur TEXT,
            nomor_mobil TEXT,
            nama_driver TEXT,
            bukti TEXT,
            tanggal_manual TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)

    conn.commit()
    conn.close()

# --- Routes ---
@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE username=? AND password=?",
            (username, password)
        ).fetchone()
        conn.close()

        if user:
            session["user"] = user["username"]
            session["user_id"] = user["id"]
            flash("Login berhasil!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Username atau password salah", "danger")

    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db_connection()
        try:
            conn.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password)
            )
            conn.commit()
            flash("Registrasi berhasil! Silakan login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username sudah dipakai!", "danger")
        finally:
            conn.close()

    return render_template("register.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logout berhasil", "info")
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    q = request.args.get("q", "")
    conn = get_db_connection()
    if q:
        data = conn.execute(
            "SELECT * FROM retur WHERE user_id=? AND nomor_retur LIKE ? ORDER BY id DESC",
            (session["user_id"], f"%{q}%")
        ).fetchall()
    else:
        data = conn.execute(
            "SELECT * FROM retur WHERE user_id=? ORDER BY id DESC",
            (session["user_id"],)
        ).fetchall()
    conn.close()

    return render_template("dashboard.html", data=data, q=q)

@app.route("/tambah", methods=["GET", "POST"])
def tambah():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        nomor_retur = request.form["nomor_retur"]
        nomor_mobil = request.form["nomor_mobil"]
        nama_driver = request.form["nama_driver"]
        tanggal_manual = request.form["tanggal_manual"]

        bukti_url = None
        if "bukti" in request.files:
            file = request.files["bukti"]
            if file and file.filename != "":
                upload_result = cloudinary.uploader.upload(file)
                bukti_url = upload_result["secure_url"]

        try:
            conn = get_db_connection()
            conn.execute("""
                INSERT INTO retur (user_id, nomor_retur, nomor_mobil, nama_driver, bukti, tanggal_manual)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session["user_id"], nomor_retur, nomor_mobil, nama_driver, bukti_url, tanggal_manual))
            conn.commit()
            flash("Data retur berhasil ditambah!", "success")
        except Exception as e:
            flash(f"Error saat tambah retur: {e}", "danger")
        finally:
            conn.close()

        return redirect(url_for("dashboard"))

    return render_template("tambah.html")

@app.route("/delete/<int:id>", methods=["POST"])
def delete(id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM retur WHERE id=? AND user_id=?", (id, session["user_id"]))
        conn.commit()
        flash("Data berhasil dihapus", "success")
    except Exception as e:
        flash(f"Error saat hapus: {e}", "danger")
    finally:
        conn.close()

    return redirect(url_for("dashboard"))

# --- Main ---
if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=10000)
