from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
import os

app = Flask(__name__)
app.secret_key = "313131"
app.config["MYSQL_HOST"] = "localhost"
app.config["MYSQL_USER"] = "root"
app.config["MYSQL_PASSWORD"] = ""
app.config["MYSQL_DB"] = "sweax"

mysql = MySQL(app)
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
# #if porno2(kullaniciad):
# #    return render_template('giriş.html', hata="siktirla")
# #elif porno2(şifre):
# #    return render_template('giriş.html', hata="siktir la")
        else:


            cursor = mysql.connection.cursor()


            sorgu = "SELECT * FROM admin WHERE kullaniciadi = %s AND sifre = %s"

            cursor.execute(sorgu, (kullaniciadi, sifre))

            adminhesap = cursor.fetchone()

            cursor.close()
            if adminhesap:
                return redirect(url_for("admin"))
            else:
                return render_template("admingiris.html",hata="GARDAŞ SENİN HESABIN YOK YA")
#     if kullanıcı:
#         session['kimlik'] = kimlik
#         if kullanıcı[7]:
#             session['hesapseviyesi'] = 1
#         return redirect(url_for('index'))
#     else:
#         return render_template('admingiris.html', hata="kıllnıcı adı veya kimlikde bi takım sikintilar var")

    return render_template('admingiris.html')
@app.route("/admin")
def admin():
    return render_template("admin.html")
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port,debug=True)

