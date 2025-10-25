# -*- coding: utf-8 -*-
# app.py — sadece test için basit Flask arayüzü
# sweaxai.py'daki konus() fonksiyonunu web üzerinden çağırır.

from flask import Flask, render_template, request, jsonify
try:

    from app.sweax_ai import konus
except Exception:
    from sweax_ai import konus
from sweax_db import veritabani_olustur

app = Flask(__name__)
app.secret_key = "test"

# veritabanı hazırlığı (sadece bir kez)
veritabani_olustur()

@app.route("/")
def index():
    """Ana sayfa (chat kutusu)."""
    return render_template("indexx.html")

@app.post("/api/chat")
def api_chat():
    """AJAX ile metin alır, konus() fonksiyonuna yollar, cevabı döndürür."""
    data = request.get_json(force=True)
    text = (data.get("text") or "").strip()
    if not text:
        return jsonify({"error": "Boş mesaj!"}), 400

    cevap = konus(text)
    return jsonify({"answer": cevap})

if __name__ == "__main__":
    # Debug açık, port 8000
    app.run(debug=True, port=8000)
