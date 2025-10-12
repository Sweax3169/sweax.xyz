from flask import Flask, render_template, request, redirect, url_for, session
from flask_mysqldb import MySQL
import os

app = Flask(__name__)

@app.route("/")
def ana():
    return render_template("index.html")
@app.route("/admingiris",methods=['POST', 'GET'])
def girisadmin():
    return render_template("admingiris.html")
    #if request.method == 'POST':
# kimlik = request.form['kimlik']
# şifre = request.form['şifre']
# if not kimlik and not şifre:
#     return render_template('giriş.html', hata="RABBİNİ SİKERİM SENİN KİMLİNİ VE ŞİFRENİ BOŞ BIRAKMA")
# if not kimlik:
#     return render_template('giriş.html', hata="LA AMINAKODUMUN SALA MALMISIN EN NİYE BIRAKIYON KİMLİNİ BOŞ")
# elif not şifre:
#     return render_template('giriş.html', hata='LAN BIRAKMASANA ŞİFRENİ BOŞ')
# #if porno2(kimlik):
# #    return render_template('giriş.html', hata="siktirla")
# #elif porno2(şifre):
# #    return render_template('giriş.html', hata="siktir la")
# #else:
# #    cursor = mysql.connection.cursor()

#     sorgu = "SELECT * FROM hesap WHERE kimlik = %s AND sifre = %s"

#     cursor.execute(sorgu, (kimlik, şifre))

#     kullanıcı = cursor.fetchone()

#     cursor.close()

#     if kullanıcı:
#         session['kimlik'] = kimlik
#         if kullanıcı[7]:
#             session['hesapseviyesi'] = 1
#         return redirect(url_for('index'))
#     else:
#         return render_template('admingiris.html', hata="kıllnıcı adı veya kimlikde bi takım sikintilar var")

    return render_template('giriş.html')
@app.route("/admin")
def admin():
    return render_template("admin.html")
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port,debug=True)

