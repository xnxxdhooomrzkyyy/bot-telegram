import os
import sqlite3
from flask import Flask, request, render_template, redirect, url_for, session, send_file
from openpyxl import Workbook
import cloudinary
import cloudinary.uploader
import cloudinary.api

# Konfigurasi Flask
app = Flask(__name__)
app.secret_key = "secret_toko"

# Konfigurasi Cloudinary dari Environment Variables
cloudinary.config(
    cloud_name=os.getenv("dghs2f716"),
    api_key=os.getenv("364918572677439"),
    api_secret=os.getenv("22BX_pQ1oz6B_cKGdx2OHVxvW1g")
)

# Database SQLite
DB_NAME = "database.db"

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        kode = request.form["kode_toko"]
        password = request.form["password"]

        if kode == "toko123" and password == "admin":  
            session["user"] = kode
            return redirect(url_for("dashboard"))
        return "Login gagal!"
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    conn = get_db()
    data = conn.execute("SELECT * FROM retur").fetchall()
    return render_template("dashboard.html", data=data)

@app.route("/upload", methods=["POST"])
def upload():
    file = request.files["bukti"]
    if file:
        result = cloudinary.uploader.upload(file)
        url = result["secure_url"]

        conn = get_db()
        conn.execute("INSERT INTO retur (nomor_retur, bukti_url) VALUES (?, ?)",
                     (request.form["nomor_retur"], url))
        conn.commit()
        return redirect(url_for("dashboard"))
    return "Gagal upload!"

@app.route("/export")
def export():
    conn = get_db()
    data = conn.execute("SELECT * FROM retur").fetchall()

    wb = Workbook()
    ws = wb.active
    ws.append(["Nomor Retur", "Bukti URL"])

    for row in data:
        ws.append([row["nomor_retur"], row["bukti_url"]])

    filename = "data.xlsx"
    wb.save(filename)
    return send_file(filename, as_attachment=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
