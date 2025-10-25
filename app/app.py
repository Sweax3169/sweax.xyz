# -*- coding: utf-8 -*-
# app.py — Sweax (MySQL sürümü, Türkçe ve okunaklı)
import os, sys
sys.path.append(os.path.dirname(__file__))

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import pymysql
from pymysql.cursors import DictCursor
from db_conn import get_db
# Yapay zekâ çekirdeği (senin mevcut fonksiyonun aynen kalıyor)
try:
    # Render'da paketli klasörle çalışma
    from app.sweax_ai import konus
except ModuleNotFoundError:
    # Lokal geliştirme
    from sweax_ai import konus

app = Flask(__name__)
app.secret_key = "313131"  # dilersen ENV'den al

# ------------------------------
# Veritabanı bağlantı yardımcıları


def admin_varsa_gec_yoksa_olustur():
    """Varsayılan admin yoksa oluşturur: admin / 1234"""
    with get_db() as conn, conn.cursor() as cur:
        cur.execute("SELECT id FROM admin WHERE kullaniciadi=%s", ("admin",))
        row = cur.fetchone()
        if not row:
            cur.execute(
                "INSERT INTO admin (kullaniciadi, sifre_hash) VALUES (%s, %s)",
                ("admin", generate_password_hash("1234"))
            )
            print("✅ Varsayılan admin oluşturuldu: admin / 1234")

@app.before_request
def _ilk_calistirma():
    # Tablo şemaları Railway'de hazır; burada sadece admin kontrolü yapıyoruz.
    try:
        admin_varsa_gec_yoksa_olustur()
    except Exception as e:
        print("⚠️ Admin kontrolünde hata:", e)

# ------------------------------
# Sayfalar
# ------------------------------
@app.route("/")
def ana():
    return render_template("index.html")

# ----------- ADMIN GİRİŞ -------------
@app.route("/admingiris", methods=["GET", "POST"])
def admingiris():
    if request.method == "POST":
        kullaniciadi = (request.form.get("kullaniciadi") or "").strip()
        sifre        = (request.form.get("sifre") or "").strip()

        if not kullaniciadi or not sifre:
            return render_template("admingiris.html", err="Kullanıcı adı ve şifre zorunludur.")

        with get_db() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM admin WHERE kullaniciadi=%s", (kullaniciadi,))
            row = cur.fetchone()

        if row and check_password_hash(row["sifre_hash"], sifre):
            session["admin"] = kullaniciadi
            return redirect(url_for("adminindex"))
        return render_template("admingiris.html", err="Bilgiler hatalı.")
    return render_template("admingiris.html")

@app.route("/adminindex")
def adminindex():
    if "admin" not in session:
        return redirect(url_for("admingiris"))
    return render_template("adminindex.html", user=session["admin"])

@app.post("/api/chat")
def api_chat():
    """
    Admin panelindeki AJAX çağrısı için:
    { "text": "..." } -> konus(text) -> {"answer": "..."}
    """
    if "admin" not in session:
        return jsonify({"error": "Yetkisiz erişim"}), 403

    data = request.get_json(force=True) or {}
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Boş mesaj!"}), 400

    try:
        cevap = konus(text)
        return jsonify({"answer": cevap})
    except Exception as e:
        print("⚠️ Yapay zekâ çağrısında hata:", e)
        return jsonify({"error": str(e)}), 500

@app.route("/admincikis")
def admincikis():
    session.pop("admin", None)
    return redirect(url_for("admingiris"))

# ----------- KULLANICI KISMI -------------
@app.route("/kayıt", methods=["GET", "POST"])
def kayit():
    if request.method == "POST":
        kullaniciadi = (request.form.get("kullaniciadi") or "").strip()
        email        = (request.form.get("email") or "").strip()
        sifre        = (request.form.get("sifre") or "").strip()

        # Basit doğrulama
        if not kullaniciadi or not sifre:
            return render_template("register.html", err="Kullanıcı adı ve şifre zorunludur.")
        if len(kullaniciadi) < 3:
            return render_template("register.html", err="Kullanıcı adı en az 3 karakter olmalı.")
        if len(sifre) < 4:
            return render_template("register.html", err="Şifre en az 4 karakter olmalı.")

        try:
            with get_db() as conn, conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO users (kullaniciadi, email, sifre_hash)
                    VALUES (%s, %s, %s)
                """, (kullaniciadi, email, generate_password_hash(sifre)))
        except pymysql.err.IntegrityError:
            return render_template("register.html", err="Bu kullanıcı adı zaten alınmış.")

        # Kayıttan sonra giriş sayfasına
        return redirect(url_for("giris"))

    return render_template("register.html")

@app.route("/giris", methods=["GET", "POST"])
def giris():
    if request.method == "POST":
        kullaniciadi = (request.form.get("kullaniciadi") or "").strip()
        sifre        = (request.form.get("sifre") or "").strip()

        if not kullaniciadi or not sifre:
            return render_template("login.html", err="Kullanıcı adı ve şifre zorunludur.")

        with get_db() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM users WHERE kullaniciadi=%s", (kullaniciadi,))
            row = cur.fetchone()

        if row and check_password_hash(row["sifre_hash"], sifre):
            # Oturum: hem kimlik (id) hem görünen ad (kullaniciadi)
            session["user_id"] = row["id"]
            session["user"]    = row["kullaniciadi"]
            return redirect(url_for("ai"))
        else:
            return render_template("login.html", err="Bilgiler hatalı.")

    return render_template("login.html")

@app.route("/cikis")
def cikis():
    session.pop("user_id", None)
    session.pop("user", None)
    return redirect(url_for("giris"))

@app.route("/sweax.ai")
def ai():
    """
    Girişten sonra açılan ana sohbet ekranı.
    Bu sayfanın frontend'ini bir sonraki adımda birlikte yapacağız.
    """
    if "user_id" not in session:
        return redirect(url_for("giris"))
    # Şimdilik sadece kullanıcı adını şablona geçiyoruz.
    return render_template("sweax.ai.html", user=session.get("user"))

@app.route("/hub")
def hub():
    return render_template("hub.html")

# ------------------------------
# Uygulama Çalıştırma
# ------------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
