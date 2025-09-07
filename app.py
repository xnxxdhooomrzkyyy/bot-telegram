import os
import sqlite3
from flask import Flask, request, render_template_string, redirect, url_for, session, send_from_directory, g, send_file
from openpyxl import Workbook

app = Flask(__name__)
app.secret_key = "rahasia123"  # kunci rahasia untuk session

app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # Maks 16 MB
DATABASE = "pengiriman.db"

# Bikin folder upload kalau belum ada
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# Data login contoh
USERS = {
    "T8NR": "t8nr",
    "admin": "admin"
}

# ------------------- DATABASE -------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

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
            foto TEXT
        )
    """)
    db.commit()

# ------------------- TEMPLATE -------------------
dashboard_page = """
<!DOCTYPE html>
<html>
<head>
    <title>Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0"> 
    <style>
        body { font-family: Arial, sans-serif; background: #f8f9fa; margin: 0; padding: 15px; }
        h2 { color: #333; }
        form { margin-bottom: 20px; }
        input, button { padding: 10px; margin: 5px 0; width: 100%; max-width: 400px; box-sizing: border-box; }
        button { background: #4CAF50; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; }
        button:hover { background: #45a049; }
        .btn-danger { background: #dc3545; }
        .btn-warning { background: #ffc107; color: black; }
        .table-container { overflow-x: auto; background: white; border-radius: 8px; box-shadow: 0 2px 6px rgba(0,0,0,0.1); margin-top: 15px; }
        table { border-collapse: collapse; width: 100%; min-width: 700px; }
        th, td { border: 1px solid #ccc; padding: 10px; text-align: center; }
        th { background: #eee; }
        a { text-decoration: none; color: blue; }
    </style>
</head>
<body>
    <h2>Selamat datang, {{ kode_toko }}!</h2>
    <h2>Silahkan isi kolom dibawah ini dengan sesua!!</h2>
    <a href="{{ url_for('logout') }}">Logout</a>
    <hr>

    <p><b>Form Input Pengiriman:</b></p>
    <form method="POST" enctype="multipart/form-data">
        <input type="text" name="nrb" placeholder="Nomor NRB" required>
        <input type="date" name="tanggal" required>
        <input type="text" name="no_mobil" placeholder="No Mobil" required>
        <input type="text" name="driver" placeholder="Nama Driver" required>
        <input type="file" name="foto" accept="image/*" required>
        <button type="submit">Simpan</button>
    </form>

    {% if success %}
    <p style="color:green;">{{ success }}</p>
    {% endif %}

    <hr>
    <h3>Riwayat Pengiriman</h3>

    <form method="GET" action="{{ url_for('dashboard') }}">
        <input type="text" name="filter_nrb" value="{{ filter_nrb }}" placeholder="Cari Nomor NRB">
        <button type="submit">Filter</button>
        <a href="{{ url_for('dashboard') }}">Reset</a>
    </form>
    <br>
    <a href="{{ url_for('export_excel', filter_nrb=filter_nrb) }}">Download Excel</a>

    {% if riwayat %}
    <div class="table-container">
        <table>
            <tr>
                <th>NRB</th>
                <th>Tanggal</th>
                <th>No Mobil</th>
                <th>Driver</th>
                <th>Foto</th>
                <th>Aksi</th>
            </tr>
            {% for item in riwayat %}
            <tr>
                <td>{{ item['nrb'] }}</td>
                <td>{{ item['tanggal'] }}</td>
                <td>{{ item['no_mobil'] }}</td>
                <td>{{ item['driver'] }}</td>
                <td><a href="/uploads/{{ item['foto'] }}" target="_blank">Lihat Foto</a></td>
                <td>
                    <a href="{{ url_for('edit_data', id=item['id']) }}"><button type="button" class="btn-warning">Edit</button></a>
                    <a href="{{ url_for('hapus_data', id=item['id']) }}" onclick="return confirm('Yakin hapus data ini?')">
                        <button type="button" class="btn-danger">Hapus</button>
                    </a>
                </td>
            </tr>
            {% endfor %}
        </table>
    </div>
    {% else %}
    <p>Belum ada data pengiriman.</p>
    {% endif %}
</body>
</html>
"""

# ------------------- ROUTE -------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if "kode_toko" in session:
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        kode_toko = request.form["kode_toko"]
        password = request.form["password"]

        if kode_toko in USERS and USERS[kode_toko] == password:
            session["kode_toko"] = kode_toko
            return redirect(url_for("dashboard"))
        else:
            error = "Kode toko tidak ditemukan!!"

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login Toko</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0"> 
        <style>
            body { display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; font-family: Arial, sans-serif; background: #f4f4f9; }
            .login-box { background: white; padding: 25px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.2); width: 90%; max-width: 350px; text-align: center; }
            .login-box h2 { margin-bottom: 20px; color: #333; }
            .login-box input { width: 100%; padding: 10px; margin: 8px 0; border: 1px solid #ccc; border-radius: 6px; font-size: 16px; }
            .login-box button { width: 100%; padding: 10px; margin-top: 10px; background: #4CAF50; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; }
            .login-box button:hover { background: #45a049; }
            .error { color: red; margin-top: 10px; }
        </style>
    </head>
    <body>
        <div class="login-box">
            <h2>Login Toko</h2>
            <form method="POST">
                <input type="text" name="kode_toko" placeholder="Kode Toko" required>
                <input type="password" name="password" placeholder="Password" required>
                <button type="submit">Login</button>
            </form>
            {% if error %}
            <p class="error">{{ error }}</p>
            {% endif %}
        </div>
    </body>
    </html>
    """, error=error)

@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "kode_toko" not in session:
        return redirect(url_for("login"))

    kode_toko = session["kode_toko"]
    db = get_db()
    success = None

    if request.method == "POST":
        nrb = request.form["nrb"]
        tanggal = request.form["tanggal"]
        no_mobil = request.form["no_mobil"]
        driver = request.form["driver"]
        foto = request.files["foto"]

        if foto:
            foto_path = os.path.join(app.config["UPLOAD_FOLDER"], foto.filename)
            foto.save(foto_path)

            db.execute("INSERT INTO pengiriman (kode_toko, nrb, tanggal, no_mobil, driver, foto) VALUES (?, ?, ?, ?, ?, ?)",
                       (kode_toko, nrb, tanggal, no_mobil, driver, foto.filename))
            db.commit()

            success = f"Data berhasil disimpan! (NRB: {nrb})"

    filter_nrb = request.args.get("filter_nrb", "").strip()
    if filter_nrb:
        riwayat = db.execute("SELECT * FROM pengiriman WHERE kode_toko = ? AND nrb LIKE ?", (kode_toko, f"%{filter_nrb}%")).fetchall()
    else:
        riwayat = db.execute("SELECT * FROM pengiriman WHERE kode_toko = ?", (kode_toko,)).fetchall()

    return render_template_string(dashboard_page, kode_toko=kode_toko, success=success, riwayat=riwayat, filter_nrb=filter_nrb)

@app.route("/logout")
def logout():
    session.pop("kode_toko", None)
    return redirect(url_for("login"))

@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

@app.route("/export_excel")
def export_excel():
    if "kode_toko" not in session:
        return redirect(url_for("login"))

    kode_toko = session["kode_toko"]
    filter_nrb = request.args.get("filter_nrb", "").strip()
    db = get_db()
    if filter_nrb:
        data = db.execute("SELECT * FROM pengiriman WHERE kode_toko = ? AND nrb LIKE ?", (kode_toko, f"%{filter_nrb}%")).fetchall()
    else:
        data = db.execute("SELECT * FROM pengiriman WHERE kode_toko = ?", (kode_toko,)).fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Riwayat Pengiriman"
    ws.append(["NRB", "Tanggal", "No Mobil", "Driver", "Foto"])
    for row in data:
        ws.append([row["nrb"], row["tanggal"], row["no_mobil"], row["driver"], row["foto"]])

    filename = f"riwayat_{kode_toko}.xlsx"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    wb.save(filepath)
    return send_file(filepath, as_attachment=True)

@app.route("/hapus/<int:id>")
def hapus_data(id):
    if "kode_toko" not in session:
        return redirect(url_for("login"))
    db = get_db()
    data = db.execute("SELECT foto FROM pengiriman WHERE id = ?", (id,)).fetchone()
    if data:
        foto_path = os.path.join(app.config["UPLOAD_FOLDER"], data["foto"])
        if os.path.exists(foto_path):
            os.remove(foto_path)
        db.execute("DELETE FROM pengiriman WHERE id = ?", (id,))
        db.commit()
    return redirect(url_for("dashboard"))

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_data(id):
    if "kode_toko" not in session:
        return redirect(url_for("login"))
    db = get_db()
    data = db.execute("SELECT * FROM pengiriman WHERE id = ?", (id,)).fetchone()
    if not data:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        nrb = request.form["nrb"]
        tanggal = request.form["tanggal"]
        no_mobil = request.form["no_mobil"]
        driver = request.form["driver"]
        foto = request.files["foto"]

        if foto and foto.filename.strip():
            old_path = os.path.join(app.config["UPLOAD_FOLDER"], data["foto"])
            if os.path.exists(old_path):
                os.remove(old_path)
            foto_path = os.path.join(app.config["UPLOAD_FOLDER"], foto.filename)
            foto.save(foto_path)
            foto_name = foto.filename
        else:
            foto_name = data["foto"]

        db.execute("UPDATE pengiriman SET nrb = ?, tanggal = ?, no_mobil = ?, driver = ?, foto = ? WHERE id = ?",
                   (nrb, tanggal, no_mobil, driver, foto_name, id))
        db.commit()
        return redirect(url_for("dashboard"))

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><title>Edit Data</title><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body>
        <h2>Edit Data Pengiriman</h2>
        <form method="POST" enctype="multipart/form-data">
            <input type="text" name="nrb" value="{{ data['nrb'] }}" required>
            <input type="date" name="tanggal" value="{{ data['tanggal'] }}" required>
            <input type="text" name="no_mobil" value="{{ data['no_mobil'] }}" required>
            <input type="text" name="driver" value="{{ data['driver'] }}" required>
            <p>Foto lama: <a href="/uploads/{{ data['foto'] }}" target="_blank">{{ data['foto'] }}</a></p>
            <input type="file" name="foto" accept="image/*">
            <button type="submit">Update</button>
        </form>
        <a href="{{ url_for('dashboard') }}">Kembali</a>
    </body>
    </html>
    """, data=data)

# ------------------- INIT -------------------
if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(debug=True)
