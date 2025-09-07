import os
import sqlite3
import io
from flask import Flask, request, render_template_string, redirect, url_for, session, g, send_file, abort
from openpyxl import Workbook
import cloudinary
import cloudinary.uploader
from dotenv import load_dotenv

# --- load .env saat lokal (optional) ---
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "rahasia123")  # override via env

# --- Cloudinary config (bisa pakai CLOUDINARY_URL atau individual vars) ---
# Option A: CLOUDINARY_URL=cloudinary://API_KEY:API_SECRET@CLOUD_NAME
# Option B: set CLOUDINARY_CLOUD_NAME, CLOUDINARY_API_KEY, CLOUDINARY_API_SECRET
cloudinary.config(
    cloud_name=os.getenv("dghs2f716"),
    api_key=os.getenv("364918572677439"),
    api_secret=os.getenv("22BX_pQ1oz6B_cKGdx2OHVxvW1g"),
    secure=True
)

DATABASE = "pengiriman.db"

USERS = {
    "T8NR": "t8nr",
    "admin": "admin"
}

# ------------------- DATABASE HELPERS -------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    # create table with public_id column
    db.execute("""
        CREATE TABLE IF NOT EXISTS pengiriman (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode_toko TEXT,
            nrb TEXT,
            tanggal TEXT,
            no_mobil TEXT,
            driver TEXT,
            foto TEXT,
            public_id TEXT
        )
    """)
    db.commit()
    # in case upgrading from older schema without public_id, try alter
    try:
        db.execute("SELECT public_id FROM pengiriman LIMIT 1")
    except sqlite3.OperationalError:
        try:
            db.execute("ALTER TABLE pengiriman ADD COLUMN public_id TEXT")
            db.commit()
        except Exception:
            pass

# ------------------- TEMPLATES (sama seperti sebelumnya) -------------------
# Untuk singkat, aku gunakan render_template_string dengan template singkat.
# Kamu bisa pindahkan HTML besar ke file di folder templates/ jika mau.
login_page = """..."""  # (pakai HTML login yang sama seperti sebelumnya)
# Reuse dashboard_page HTML dari mu — (bisa paste HTML lengkapmu di sini).
# Untuk kepraktisan, aku akan gunakan versi ringkas:
dashboard_page = """
<!doctype html>
<html>
<head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Dashboard</title>
<style>body{font-family:Arial;margin:15px} input,button{padding:8px;margin:6px 0}</style>
</head>
<body>
<h2>Selamat datang, {{ kode_toko }}!</h2>
<a href="{{ url_for('logout') }}">Logout</a>
<hr>
<form method="POST" enctype="multipart/form-data">
  <input name="nrb" placeholder="Nomor NRB" required><br>
  <input type="date" name="tanggal" required><br>
  <input name="no_mobil" placeholder="No Mobil" required><br>
  <input name="driver" placeholder="Driver" required><br>
  <input type="file" name="foto" accept="image/*" required><br>
  <button type="submit">Simpan</button>
</form>
{% if success %}<p style="color:green">{{ success }}</p>{% endif %}
<hr>
<form method="GET">
  <input name="filter_nrb" placeholder="Cari NRB" value="{{ filter_nrb }}">
  <button type="submit">Filter</button>
  <a href="{{ url_for('export_excel', filter_nrb=filter_nrb) }}">Download Excel</a>
</form>
<table border="1" cellpadding="6">
  <tr><th>NRB</th><th>Tanggal</th><th>No Mobil</th><th>Driver</th><th>Foto</th><th>Aksi</th></tr>
  {% for r in riwayat %}
  <tr>
    <td>{{ r['nrb'] }}</td>
    <td>{{ r['tanggal'] }}</td>
    <td>{{ r['no_mobil'] }}</td>
    <td>{{ r['driver'] }}</td>
    <td>{% if r['foto'] %}<a href="{{ r['foto'] }}" target="_blank">Lihat</a>{% else %}-{% endif %}</td>
    <td>
      <a href="{{ url_for('edit_data', id=r['id']) }}">Edit</a> |
      <a href="{{ url_for('hapus_data', id=r['id']) }}" onclick="return confirm('Yakin?')">Hapus</a>
    </td>
  </tr>
  {% endfor %}
</table>
</body>
</html>
"""

edit_page = """
<!doctype html><html><body>
<h2>Edit</h2>
<form method="POST" enctype="multipart/form-data">
  <input name="nrb" required value="{{ data['nrb'] }}"><br>
  <input type="date" name="tanggal" required value="{{ data['tanggal'] }}"><br>
  <input name="no_mobil" required value="{{ data['no_mobil'] }}"><br>
  <input name="driver" required value="{{ data['driver'] }}"><br>
  {% if data['foto'] %}Foto saat ini: <a href="{{ data['foto'] }}" target="_blank">Lihat</a><br>{% endif %}
  <input type="file" name="foto"><br>
  <button type="submit">Update</button>
</form>
<a href="{{ url_for('dashboard') }}">Kembali</a>
</body></html>
"""

# ------------------- ROUTES -------------------
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
    return render_template_string(
        """
        <!doctype html><html><body>
        <h2>Login</h2>
        <form method="POST">
          <input name="kode_toko" placeholder="Kode Toko" required><br>
          <input type="password" name="password" placeholder="Password" required><br>
          <button type="submit">Login</button>
        </form>
        {% if error %}<p style="color:red">{{ error }}</p>{% endif %}
        </body></html>
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
        foto = request.files.get("foto")
        if foto:
            # upload ke Cloudinary, simpan secure_url dan public_id
            res = cloudinary.uploader.upload(foto, folder="pengiriman")
            foto_url = res.get("secure_url")
            public_id = res.get("public_id")
            db.execute(
                "INSERT INTO pengiriman (kode_toko, nrb, tanggal, no_mobil, driver, foto, public_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (kode_toko, nrb, tanggal, no_mobil, driver, foto_url, public_id)
            )
            db.commit()
            success = f"Data berhasil disimpan! (NRB: {nrb})"
    filter_nrb = request.args.get("filter_nrb", "").strip()
    if filter_nrb:
        rows = db.execute("SELECT * FROM pengiriman WHERE kode_toko = ? AND nrb LIKE ? ORDER BY id DESC", (kode_toko, f"%{filter_nrb}%")).fetchall()
    else:
        rows = db.execute("SELECT * FROM pengiriman WHERE kode_toko = ? ORDER BY id DESC", (kode_toko,)).fetchall()
    return render_template_string(dashboard_page, kode_toko=kode_toko, success=success, riwayat=rows, filter_nrb=filter_nrb)

@app.route("/logout")
def logout():
    session.pop("kode_toko", None)
    return redirect(url_for("login"))

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

    wb = Workbook()
    ws = wb.active
    ws.title = "Riwayat Pengiriman"
    ws.append(["NRB", "Tanggal", "No Mobil", "Driver", "Foto URL"])
    for r in rows:
        ws.append([r["nrb"], r["tanggal"], r["no_mobil"], r["driver"], r["foto"] or ""])

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    filename = f"riwayat_{kode_toko}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/hapus/<int:id>")
def hapus_data(id):
    if "kode_toko" not in session:
        return redirect(url_for("login"))
    db = get_db()
    row = db.execute("SELECT * FROM pengiriman WHERE id = ?", (id,)).fetchone()
    if row:
        public_id = row["public_id"]
        if public_id:
            try:
                cloudinary.uploader.destroy(public_id)
            except Exception:
                pass
        db.execute("DELETE FROM pengiriman WHERE id = ?", (id,))
        db.commit()
    return redirect(url_for("dashboard"))

@app.route("/edit/<int:id>", methods=["GET", "POST"])
def edit_data(id):
    if "kode_toko" not in session:
        return redirect(url_for("login"))
    db = get_db()
    row = db.execute("SELECT * FROM pengiriman WHERE id = ?", (id,)).fetchone()
    if not row:
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        nrb = request.form["nrb"]
        tanggal = request.form["tanggal"]
        no_mobil = request.form["no_mobil"]
        driver = request.form["driver"]
        foto = request.files.get("foto")
        foto_url = row["foto"]
        public_id = row["public_id"]
        if foto and foto.filename.strip():
            # hapus foto lama di Cloudinary jika ada
            if public_id:
                try:
                    cloudinary.uploader.destroy(public_id)
                except Exception:
                    pass
            res = cloudinary.uploader.upload(foto, folder="pengiriman")
            foto_url = res.get("secure_url")
            public_id = res.get("public_id")
        db.execute("UPDATE pengiriman SET nrb=?, tanggal=?, no_mobil=?, driver=?, foto=?, public_id=? WHERE id=?",
                   (nrb, tanggal, no_mobil, driver, foto_url, public_id, id))
        db.commit()
        return redirect(url_for("dashboard"))
    return render_template_string(edit_page, data=row)

# ------------------- INIT -------------------
if __name__ == "__main__":
    with app.app_context():
        init_db()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)
