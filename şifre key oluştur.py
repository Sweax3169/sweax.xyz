#!/usr/bin/env python3
"""
Basit ama kullanışlı Fernet (AES) şifreleyici / çözücü.
Kullanım:
    - Anahtar oluştur: "g" (generate)
    - Anahtar yükle (string olarak yapıştır): "k" (key)
    - Anahtar dosyadan yükle: "f" (file)
    - Metin şifrele: "e"
    - Şifre çöz: "d"
    - Çıkış: "q"
Not: Anahtarı güvenli yerde saklayın. Anahtar olmadan şifre çözülemez.
"""
from cryptography.fernet import Fernet
import sys
import os

def generate_key():
    return Fernet.generate_key()

def save_key_to_file(key: bytes, filepath: str):
    with open(filepath, "wb") as f:
        f.write(key)

def load_key_from_file(filepath: str) -> bytes:
    with open(filepath, "rb") as f:
        return f.read()

def create_fernet_from_key(key: bytes) -> Fernet:
    return Fernet(key)

def encrypt_text(fernet: Fernet, plaintext: str) -> bytes:
    return fernet.encrypt(plaintext.encode())

def decrypt_text(fernet: Fernet, token: bytes) -> str:
    return fernet.decrypt(token).decode()

def prompt_menu():
    print("""
Seçenekler:
 g - Yeni anahtar üret (ve ekranda göster)
 k - El ile anahtar gir (base64 string)
 f - Anahtar dosyadan yükle
 e - Metin şifrele
 d - Şifre çöz
 s - Anahtarı dosyaya kaydet
 q - Çıkış
""")

def main():
    key = None
    fernet = None

    while True:
        prompt_menu()
        choice = input("Seçimin: ").strip().lower()

        if choice == "g":
            key = generate_key()
            fernet = create_fernet_from_key(key)
            print("Yeni anahtar oluşturuldu (BASE64):")
            print(key.decode())
            print("Bu anahtarı güvenli yerde saklayın. Bu anahtar olmadan şifre çözülemez.\n")

        elif choice == "k":
            k = input("Anahtarı yapıştır (base64 string): ").strip()
            try:
                key = k.encode()
                fernet = create_fernet_from_key(key)
                print("Anahtar yüklendi.\n")
            except Exception as e:
                print("Anahtar yüklenirken hata:", e)

        elif choice == "f":
            path = input("Anahtar dosya yolu: ").strip()
            if not os.path.isfile(path):
                print("Dosya bulunamadı:", path)
                continue
            try:
                key = load_key_from_file(path)
                fernet = create_fernet_from_key(key)
                print("Anahtar dosyadan yüklendi.\n")
            except Exception as e:
                print("Anahtar dosyadan yüklenirken hata:", e)

        elif choice == "s":
            if key is None:
                print("Önce bir anahtar oluşturup/ yüklemelisiniz.")
                continue
            path = input("Anahtarı kaydetmek istediğiniz dosya yolu: ").strip()
            try:
                save_key_to_file(key, path)
                print(f"Anahtar {path} dosyasına kaydedildi.\n")
            except Exception as e:
                print("Kaydetme hatası:", e)

        elif choice == "e":
            if fernet is None:
                print("Önce bir anahtar oluşturun veya yükleyin.")
                continue
            plaintext = input("Şifrelenecek metin (enter ile tamamla):\n")
            token = encrypt_text(fernet, plaintext)
            print("\nŞifreli metin (copy/paste için):")
            print(token.decode(), "\n")


        elif choice == "d":

            if fernet is None:
                print("Önce anahtarınızı oluşturun veya yükleyin.")

                continue

            token_str = input("Şifrelenmiş metni yapıştırın:\n").strip()

            try:

                token = token_str.encode()

                decrypted = decrypt_text(fernet, token)

                print("\nÇözülen metin:")

                print(">>>", decrypted, "\n")  # 🔹 Ekledik: görünür çıktı

            except Exception as e:

                print("Çözme hatası (muhtemelen yanlış anahtar veya bozuk token):", e, "\n")

        elif choice == "q":
            print("Çıkılıyor.")
            sys.exit(0)

        else:
            print("Bilinmeyen seçenek, tekrar deneyin.\n")

if __name__ == "__main__":
    main()
