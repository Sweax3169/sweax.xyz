from werkzeug.security import generate_password_hash
from db_conn import get_db

def yeni_admin_ekle(kullaniciadi, sifre):
    with get_db() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO admin (kullaniciadi, sifre_hash) VALUES (%s, %s)",
            (kullaniciadi, generate_password_hash(sifre))
        )
        conn.commit()
        print(f"✅ Yeni admin eklendi: {kullaniciadi}")

# Örnek kullanım:
yeni_admin_ekle("yusuf", "1!HmP?t_h%o//v")
