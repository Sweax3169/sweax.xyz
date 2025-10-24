import os, sys
os.makedirs("/data", exist_ok=True) if os.path.exists("/data") else None
sys.path.append(os.path.dirname(__file__))
from flask import Flask, render_template, request, redirect, url_for, session ,jsonify
try:
    # Render'da çalışırken
    from app.sweax_ai import konus
except ModuleNotFoundError:
    # Localde çalışırken
    from sweax_ai import konus
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
app = Flask(__name__)
app.secret_key = "313131"

# Render'da kalıcı depolama (veya localde app klasörüne)
veritabanklasor = "/data" if os.path.exists("/data") else os.path.dirname(__file__)
veritaban = os.path.join(veritabanklasor, "sweax.db")
print("Kayıt yapılacak DB yolu:", os.path.abspath(veritaban))
print("Kayıt yapılacak DB yolu:", os.path.abspath(veritaban))
def get_db():
    conn = sqlite3.connect(veritaban)
    conn.row_factory = sqlite3.Row
    return conn
# ============== USER TABLOSU ==================

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kullaniciadi TEXT UNIQUE NOT NULL,
            email TEXT,
            sifre_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
# ============== ADMIN TABLOSU ==================
def init_admin():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kullaniciadi TEXT UNIQUE NOT NULL,
            sifre_hash TEXT NOT NULL
        )
    """)
    cur.execute("SELECT * FROM admin WHERE kullaniciadi = ?", ("admin",))
    if not cur.fetchone():
        cur.execute(
            "INSERT INTO admin (kullaniciadi, sifre_hash) VALUES (?, ?)",
            ("admin", generate_password_hash("1234"))
        )
        print("✅ Varsayılan admin oluşturuldu: admin / 1234")
    conn.commit()
    conn.close()
# ============== ROUTES ==================


#def veritabanbasla():
#    baglan = sqlite3.connect(veritaban)
#
#    c = baglan.cursor()
#
#    c.execute("""
#    CREATE TABLE IF NOT EXISTS admin (
#            id INTEGER PRIMARY KEY AUTOINCREMENT,
#            kullaniciadi TEXT NOT NULL,
#            sifre TEXT NOT NULL
#    )
#
#     """)
#    c.execute("SELECT * FROM admin")
#    if not c.fetchone():
#        c.execute("INSERT INTO admin (kullaniciadi,sifre) VALUES (?,?)",("admin","1234"))
#        baglan.commit()
#    baglan.close()


@app.route("/")
def ana():
    return render_template("index.html")
# ----------- ADMIN GİRİŞ -------------
@app.route("/admingiris", methods=["GET", "POST"])
def admingiris():
    if request.method == "POST":
        k = request.form.get("kullaniciadi","").strip()
        s = request.form.get("sifre","").strip()
        conn=get_db(); cur=conn.cursor()
        cur.execute("SELECT * FROM admin WHERE kullaniciadi=?",(k,))
        row=cur.fetchone(); conn.close()
        if row and check_password_hash(row["sifre_hash"], s):
            session["admin"]=k
            return redirect(url_for("adminindex"))
        return render_template("admingiris.html", err="Bilgiler hatalı.")
    return render_template("admingiris.html")

# -------------------- Admin Panel (AI + HTML + API) --------------------
@app.route("/adminindex")
def adminindex():
    if "admin" not in session:
        return redirect(url_for("admingiris"))
    return render_template("adminindex.html", user=session["admin"])

@app.post("/api/chat")
def api_chat():
    if "admin" not in session:
        return jsonify({"error": "Yetkisiz erişim"}), 403
    data=request.get_json(force=True)
    text=(data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Boş mesaj!"}),400
    try:
        cevap=konus(text)
        return jsonify({"answer": cevap})
    except Exception as e:
        print("⚠️ Hata:",e)
        return jsonify({"error": str(e)})

@app.route("/admincikis")
def admincikis():
    session.pop("admin",None)
    return redirect(url_for("admingiris"))


# ----------- KULLANICI KISMI -------------
@app.route("/kayıt", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        kullaniciadi = (request.form.get("kullaniciadi") or "").strip()
        email       = (request.form.get("email") or "").strip()
        sifre       = (request.form.get("sifre") or "").strip()

        # basit doğrulama (aşırıya kaçmadan)
        if not kullaniciadi or not sifre:
            return render_template("register.html", err="Kullanıcı adı ve şifre zorunludur.")
        if len(kullaniciadi) < 3:
            return render_template("register.html", err="Kullanıcı adı en az 3 karakter olmalı.")
        if len(sifre) < 4:
            return render_template("register.html", err="Şifre en az 4 karakter olmalı.")

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO users (kullaniciadi, email, sifre_hash) VALUES (?, ?, ?)",
                (kullaniciadi, email, generate_password_hash(sifre))
            )
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return render_template("register.html", err="Bu kullanıcı adı zaten alınmış.")
        conn.close()

        # otomatik login
        #session["user"] = kullaniciadi
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/giris", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        kullaniciadi = (request.form.get("kullaniciadi") or "").strip()
        sifre = (request.form.get("sifre") or "").strip()

        if not kullaniciadi or not sifre:
            return render_template("giris.html", err="Kullanıcı adı ve şifre zorunludur.")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE kullaniciadi = ?", (kullaniciadi,))
        row = cur.fetchone()
        conn.close()

        if row and check_password_hash(row["sifre_hash"], sifre):
            session["user"] = kullaniciadi
            return redirect(url_for("ai"))
        else:
            return render_template("login.html", err="Bilgiler hatalı.")

    return render_template("login.html")



@app.route("/sweax.ai")
def ai():
    if "user" not in session:
        return redirect(url_for("giris"))
    return render_template("sweax.ai.html", user=session["user"])


@app.route("/hub")
def hub():
    return render_template("hub.html")



#@app.route("/admingiris",methods=['POST', 'GET'])
#def girisadmin():
#
#
#    if request.method == 'POST':
#
#        kullaniciadi = request.form['kullaniciadi']
#        sifre = request.form['şifre']
#        if not kullaniciadi and not sifre:
#            return render_template('admingiris.html', hata="RABBİNİ SİKERİM SENİN KULLANICI ADINI VE ŞİFRENİ BOŞ BIRAKMA")
#        if not kullaniciadi:
#            return render_template('admingiris.html', hata="LA AMINAKODUMUN SALA MALMISIN SEN NİYE BIRAKIYON KULLANICI ADINI BOŞ")
#        elif not sifre:
#            return render_template('admingiris.html', hata='LAN BIRAKMASANA ŞİFRENİ BOŞ')
#
#        baglan = sqlite3.connect(veritaban)
#        c = baglan.cursor()
#        c.execute("SELECT * FROM admin WHERE kullaniciadi = ? AND sifre = ?",(kullaniciadi,sifre))
#        adminhesap = c.fetchone()
#        baglan.close()
#
#        if adminhesap:
#            session["admin"] = kullaniciadi
#            return redirect(url_for("admin"))
#        else:
#            return render_template("admingiris.html",hata="OROSPOUNUN OĞLU BÖYLE Bİ HESAP YOK ANANI SİKEİM GİT DEVELOPER ALLAH KİTAP OLAN SWEAX LA KONUŞ O SANA ADMİN HESABI VERSİN")
#    return render_template("admingiris.html")




# ============== RUN ==================
if __name__ == "__main__":
    init_db()
    init_admin()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port,debug=True)

