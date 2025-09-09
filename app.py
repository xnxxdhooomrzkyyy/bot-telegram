import os
import sqlite3
import hashlib
import cloudinary
import cloudinary.uploader
from flask import Flask, request, redirect, url_for, render_template_string, send_file, session
from openpyxl import Workbook
from datetime import datetime
from functools import wraps

# --- Flask Setup ---
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "secret-key-anda")

# --- Cloudinary Setup ---
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

# --- Database ---
def init_db():
    with sqlite3.connect("rekap.db") as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kode_toko TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT DEFAULT 'user'
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS pengiriman (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                nrb TEXT NOT NULL,
                tgl_pengiriman TEXT NOT NULL,
                no_mobil TEXT NOT NULL,
                driver TEXT NOT NULL,
                bukti_url TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        conn.commit()

init_db()

# --- Helper ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_user_id():
    return session.get("user_id")

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

# --- Register ---
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        kode_toko = request.form["kode_toko"]
        password = hash_password(request.form["password"])
        try:
            with sqlite3.connect("rekap.db") as conn:
                c = conn.cursor()
                c.execute("INSERT INTO users (kode_toko, password) VALUES (?, ?)", (kode_toko, password))
                conn.commit()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return "❌ Kode toko sudah terdaftar!"
    return render_template_string("""
    <h2>📝 Registrasi</h2>
    <form method="POST">
        <label>Kode Toko</label><br>
        <input type="text" name="kode_toko" required><br>
        <label>Password</label><br>
        <input type="password" name="password" required><br>
        <button type="submit">Daftar</button>
        <a href="{{ url_for('login') }}">Login</a>
    </form>
    """)

# --- Login ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        kode_toko = request.form["kode_toko"]
        password = hash_password(request.form["password"])
        with sqlite3.connect("rekap.db") as conn:
            c = conn.cursor()
            c.execute("SELECT id, role FROM users WHERE kode_toko=? AND password=?", (kode_toko, password))
            user = c.fetchone()
            if user:
                session["user_id"] = user[0]
                session["kode_toko"] = kode_toko
                session["role"] = user[1]
                return redirect(url_for("index"))
        return "❌ Kode toko atau password salah!"
    return render_template_string("""
    <h2>🔑 Login</h2>
    <form method="POST">
        <label>Kode Toko</label><br>
        <input type="text" name="kode_toko" required><br>
        <label>Password</label><br>
        <input type="password" name="password" required><br>
        <button type="submit">Login</button>
        <a href="{{ url_for('register') }}">Daftar</a>
    </form>
    """)

# --- Logout ---
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# --- Index (Input + List Data) ---
@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    user_id = get_user_id()

    if request.method == "POST" and "nrb" in request.form:
        nrb = request.form["nrb"]
        tgl_pengiriman = request.form["tgl_pengiriman"]
        no_mobil = request.form["no_mobil"]
        driver = request.form["driver"]

        file = request.files["bukti"]
        bukti_url = None
        if file and file.filename != "":
            upload_result = cloudinary.uploader.upload(file, folder="pengiriman")
            bukti_url = upload_result["secure_url"]

        with sqlite3.connect("rekap.db") as conn:
            c = conn.cursor()
            c.execute("INSERT INTO pengiriman (user_id, nrb, tgl_pengiriman, no_mobil, driver, bukti_url) VALUES (?, ?, ?, ?, ?, ?)",
                      (user_id, nrb, tgl_pengiriman, no_mobil, driver, bukti_url))
            conn.commit()

        return redirect(url_for("index"))

    search_nrb = request.args.get("search_nrb", "").strip()
    with sqlite3.connect("rekap.db") as conn:
        c = conn.cursor()
        if session["role"] == "admin":
            if search_nrb:
                c.execute("SELECT u.kode_toko, p.nrb, p.tgl_pengiriman, p.no_mobil, p.driver, p.bukti_url FROM pengiriman p JOIN users u ON p.user_id=u.id WHERE p.nrb LIKE ? ORDER BY p.id DESC", (f"%{search_nrb}%",))
            else:
                c.execute("SELECT u.kode_toko, p.nrb, p.tgl_pengiriman, p.no_mobil, p.driver, p.bukti_url FROM pengiriman p JOIN users u ON p.user_id=u.id ORDER BY p.id DESC")
        else:
            if search_nrb:
                c.execute("SELECT nrb, tgl_pengiriman, no_mobil, driver, bukti_url FROM pengiriman WHERE user_id=? AND nrb LIKE ? ORDER BY id DESC", (user_id, f"%{search_nrb}%"))
            else:
                c.execute("SELECT nrb, tgl_pengiriman, no_mobil, driver, bukti_url FROM pengiriman WHERE user_id=? ORDER BY id DESC", (user_id,))
        data = c.fetchall()

    return render_template_string("""
    <h2>📦 Rekap Pengiriman - {{ session['kode_toko'] }} ({{ session['role'] }})</h2>
    <a href="{{ url_for('logout') }}">Logout</a>
    <hr>

    <form method="POST" enctype="multipart/form-data">
        NRB: <input type="text" name="nrb" required><br>
        Tanggal: <input type="date" name="tgl_pengiriman" required><br>
        Nomor Mobil: <input type="text" name="no_mobil" required><br>
        Driver: <input type="text" name="driver" required><br>
        Bukti: <input type="file" name="bukti"><br>
        <button type="submit">Simpan</button>
    </form>

    <form method="GET">
        Cari NRB: <input type="text" name="search_nrb" value="{{ request.args.get('search_nrb', '') }}">
        <button type="submit">Cari</button>
    </form>

    <table border="1" cellpadding="5">
        <tr>
            {% if session['role'] == 'admin' %}
            <th>Kode Toko</th>
            {% endif %}
            <th>NRB</th><th>Tanggal</th><th>No Mobil</th><th>Driver</th><th>Bukti</th>
        </tr>
        {% for row in data %}
        <tr>
            {% if session['role'] == 'admin' %}
            <td>{{row[0]}}</td><td>{{row[1]}}</td><td>{{row[2]}}</td><td>{{row[3]}}</td><td>{{row[4]}}</td>
            <td>{% if row[5] %}<a href="{{row[5]}}" target="_blank">Lihat</a>{% else %}-{% endif %}</td>
            {% else %}
            <td>{{row[0]}}</td><td>{{row[1]}}</td><td>{{row[2]}}</td><td>{{row[3]}}</td>
            <td>{% if row[4] %}<a href="{{row[4]}}" target="_blank">Lihat</a>{% else %}-{% endif %}</td>
            {% endif %}
        </tr>
        {% endfor %}
    </table>
    """, data=data)

# --- Export Excel ---
@app.route("/export")
@login_required
def export_excel():
    user_id = get_user_id()
    search_nrb = request.args.get("search_nrb", "").strip()

    with sqlite3.connect("rekap.db") as conn:
        c = conn.cursor()
        if session["role"] == "admin":
            if search_nrb:
                c.execute("SELECT u.kode_toko, p.nrb, p.tgl_pengiriman, p.no_mobil, p.driver, p.bukti_url FROM pengiriman p JOIN users u ON p.user_id=u.id WHERE p.nrb LIKE ? ORDER BY p.id ASC", (f"%{search_nrb}%",))
            else:
                c.execute("SELECT u.kode_toko, p.nrb, p.tgl_pengiriman, p.no_mobil, p.driver, p.bukti_url FROM pengiriman p JOIN users u ON p.user_id=u.id ORDER BY p.id ASC")
        else:
            if search_nrb:
                c.execute("SELECT nrb, tgl_pengiriman, no_mobil, driver, bukti_url FROM pengiriman WHERE user_id=? AND nrb LIKE ? ORDER BY id ASC", (user_id, f"%{search_nrb}%"))
            else:
                c.execute("SELECT nrb, tgl_pengiriman, no_mobil, driver, bukti_url FROM pengiriman WHERE user_id=? ORDER BY id ASC", (user_id,))
        data = c.fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Rekap Pengiriman"
    headers = ["NRB", "Tanggal", "No Mobil", "Driver", "Bukti"] if session["role"] != "admin" else ["Kode Toko", "NRB", "Tanggal", "No Mobil", "Driver", "Bukti"]
    ws.append(headers)
    for row in data:
        ws.append(row)

    filename = f"rekap_pengiriman_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(filename)
    return send_file(filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
