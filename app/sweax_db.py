# -*- coding: utf-8 -*-
# sweax_db.py
# AMAÇ: Mesaj geçmişini (user/assistant) saklamak için küçük bir SQLite katmanı.
# Yalnızca "messages" tablosu var. Kullanıcı sistemi yok (ileride eklenecek).

import sqlite3
from pathlib import Path

DB_PATH = Path("sweax.db")

def db_baglan():
    """
    Veritabanına bağlanır.
    row_factory = sqlite3.Row → satırları dict benzeri okumamızı sağlar.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def veritabani_olustur():
    """
    "messages" tablosu yoksa oluşturur.
    role: 'user' / 'assistant'
    content: mesaj metni
    tarih: otomatik zaman damgası
    """
    conn = db_baglan()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT,
            tarih TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def mesaj_ekle(role: str, content: str):
    """Yeni mesajı ekler (user/assistant)."""
    conn = db_baglan()
    cur = conn.cursor()
    cur.execute("INSERT INTO messages (role, content) VALUES (?, ?)", (role, content))
    conn.commit()
    conn.close()

def mesajlari_getir(limit: int = 10):
    """Son N mesajı getirir (eski → yeni)."""
    conn = db_baglan()
    cur = conn.cursor()
    cur.execute("SELECT role, content, tarih FROM messages ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    # Ters çevirip eski→yeni sıralıyoruz
    return list(reversed([dict(r) for r in rows]))
