from flask import Flask, render_template, request, redirect, url_for, session

import os
import sqlite3

app = Flask(__name__)
app.secret_key = "313131"

veritaban = os.path.join(os.path.dirname(__file__),"sweax.db")

def veritabanbasla():
    baglan = sqlite3.connect(veritaban)

    c = baglan.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS admin (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kullaniciadi TEXT NOT NULL,
            sifre TEXT NOT NULL
    )
    
     """)
    c.execute("SELECT * FROM admin")
    if not c.fetchone():
        c.execute("INSERT INTO admin (kullaniciadi,sifre) VALUES (?,?)",("admin","1234"))
        baglan.commit()
    baglan.close()


@app.route("/")
def ana():
    return render_template("index.html")
@app.route("/admingiris",methods=['POST', 'GET'])
def girisadmin():


    if request.method == 'POST':

        kullaniciadi = request.form['kullaniciadi']
        sifre = request.form['şifre']
        if not kullaniciadi and not sifre:
            return render_template('admingiris.html', hata="RABBİNİ SİKERİM SENİN KULLANICI ADINI VE ŞİFRENİ BOŞ BIRAKMA")
        if not kullaniciadi:
            return render_template('admingiris.html', hata="LA AMINAKODUMUN SALA MALMISIN SEN NİYE BIRAKIYON KULLANICI ADINI BOŞ")
        elif not sifre:
            return render_template('admingiris.html', hata='LAN BIRAKMASANA ŞİFRENİ BOŞ')

        baglan = sqlite3.connect(veritaban)
        c = baglan.cursor()
        c.execute("SELECT * FROM admin WHERE kullaniciadi = ? AND sifre = ?",(kullaniciadi,sifre))
        adminhesap = c.fetchone()
        baglan.close()

        if adminhesap:
            session["admin"] = kullaniciadi
            return redirect(url_for("admin"))
        else:
            return render_template("admingiris.html",hata="OROSPOUNUN OĞLU BÖYLE Bİ HESAP YOK ANANI SİKEİM GİT DEVELOPER ALLAH KİTAP OLAN SWEAX LA KONUŞ O SANA ADMİN HESABI VERSİN")
    return render_template("admingiris.html")

      # else:

      #     cursor = mysql.connection.cursor()


      #     sorgu = "SELECT * FROM admin WHERE kullaniciadi = %s AND sifre = %s"

      #     cursor.execute(sorgu, (kullaniciadi, sifre))

      #     adminhesap = cursor.fetchone()

      #     cursor.close()
      #     if adminhesap:
      #         return redirect(url_for("admin"))
      #     else:
      #         return render_template("admingiris.html",hata="GARDAŞ SENİN HESABIN YOK YA")


@app.route("/admin")
def admin():
    if "admin" not in session:
        return redirect(url_for("admingiris"))

    return render_template("admin.html")
if __name__ == "__main__":
    veritabanbasla()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port,debug=True)

