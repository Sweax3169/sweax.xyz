# -*- coding: utf-8 -*-
# db_conn.py — Railway MySQL bağlantısı (Otomatik lokal/uzak algılama)
import os
import pymysql
from pymysql.cursors import DictCursor

def get_db():
    """
    Railway MySQL veritabanına bağlanır.
    Ortam değişkenleri yoksa (örneğin localde) otomatik olarak fallback değerlere geçer.
    """
    try:
        # Önce Render/Railway ortam değişkenlerini dene
        host = os.getenv("DB_HOST")
        port = int(os.getenv("DB_PORT", "3306"))
        user = os.getenv("DB_USER")
        password = os.getenv("DB_PASS")
        dbname = os.getenv("DB_NAME")

        # Eğer host tanımlı değilse → lokal test değerlerini kullan
        if not host:
            print("⚙️ Ortam değişkeni bulunamadı, lokal test ayarları kullanılacak.")
            host = "trolley.proxy.rlwy.net"
            port = 27988
            user = "root"
            password = "hTcqeooYFyYYOezICaMbkUvPEebvRXYb"
            dbname = "railway"

        # Bağlantıyı kur
        conn = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=dbname,
            cursorclass=DictCursor,
            autocommit=True,
            charset="utf8mb4"
        )
        return conn

    except Exception as e:
        print(f"❌ Veritabanı bağlantı hatası: {e}")
        return None
