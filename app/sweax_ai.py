# -*- coding: utf-8 -*-
# sweaxai.py — Hafif RAM sürümü (Render 512 MB dostu)
import re, requests, os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import deepl

# ============ YENİ: MySQL bağlantısı db_conn.py üzerinden ============
try:
    from app.db_conn import get_db
except ModuleNotFoundError:
    from db_conn import get_db
# ====================================================================

try:
    from app.sweaxrag import wiki_ozet, wiki_ozet_with_meta, rag_cevap_uret
except ModuleNotFoundError:
    from sweaxrag import wiki_ozet, wiki_ozet_with_meta, rag_cevap_uret

# ====== VERİTABANI FONKSİYONLARI (Railway MySQL uyumlu) ======
def veritabani_olustur():
    """
    SQLite'taki gibi dosya oluşturma yerine MySQL tablolarını kontrol eder.
    Tablolar zaten Render/Railway üzerinde oluşturulmuş olmalı.
    """
    try:
        with get_db() as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")  # Bağlantı testi
        print("✅ MySQL bağlantısı başarılı (veritabani_olustur testi).")
    except Exception as e:
        print(f"⚠️ Veritabanı bağlantısı başarısız: {e}")

def mesaj_ekle(rol: str, icerik: str):
    """
    Kullanıcı veya yapay zekâ mesajını messages tablosuna ekler.
    (Geçici: tüm mesajlar varsayılan sohbet kimliği 1 altında tutulur.)
    """
    try:
        with get_db() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO messages (conversation_id, role, content)
                VALUES (%s, %s, %s)
            """, (1, rol, icerik))
    except Exception as e:
        print(f"⚠️ mesaj_ekle hata: {e}")

def mesajlari_getir(limit: int = 5):
    """
    En son X mesajı getirir (conversation_id = 1 varsayılan sohbet).
    """
    try:
        with get_db() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT role, content FROM messages
                WHERE conversation_id = 1
                ORDER BY id DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
            return list(reversed(rows))
    except Exception as e:
        print(f"⚠️ mesajlari_getir hata: {e}")
        return []
# ===============================================================

OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/chat")
SON_KONU = None

# ===== Yardımcılar =====
def _guvenli_ifade_mi(metin: str) -> bool:
    return bool(re.fullmatch(r"[0-9\ \+\-\*\/\.\(\)]+", metin))

def _hesapla(ifade: str) -> str:
    try:
        return f"Sonuç: {eval(ifade)}"
    except Exception:
        return "Gardaş bu işlem yanlış yazılmış, bi daha bak hele."

def _simdi_ist():
    return datetime.now(ZoneInfo("Europe/Istanbul"))

def tarih_saat_cevap(metin: str) -> str | None:
    s = metin.lower(); now = _simdi_ist()
    if "saat kaç" in s or "şu an saat" in s: return f"Şu an saat (İstanbul): {now:%H:%M}"
    if "hangi yıldayız" in s or "yıl kaç" in s: return f"{now.year} yılındayız."
    m = re.search(r"(\d+)\s*yıl\s*sonra", s)
    if m: return f"{m.group(1)} yıl sonra: {now.year + int(m.group(1))}"
    if "ayın kaçı" in s: return f"Bugün tarih: {now:%d.%m.%Y} (İstanbul)."
    if "hangi aydayız" in s:
        ay = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"][now.month-1]
        return f"{ay} ayındayız."
    if "günlerden ne" in s or "hangi gün" in s:
        gun = ["Pazartesi","Salı","Çarşamba","Perşembe","Cuma","Cumartesi","Pazar"][now.weekday()]
        return f"Bugün {gun}."
    if "yarın tarih" in s:  t = now + timedelta(days=1); return f"Yarın: {t:%d.%m.%Y}"
    if "dün tarih" in s:    t = now - timedelta(days=1); return f"Dün: {t:%d.%m.%Y}"
    return None

# ===== Yerleşik tarifler =====
YERLESIK_TARIFLER = {
    "menemen": [
        "Malzemeler: 3 domates, 3 yumurta, 2 sivri biber, 1 yemek kaşığı tereyağı, tuz.",
        "1) Biberleri küçük doğra, tereyağında 2-3 dk sotele.",
        "2) Domatesleri ekle, suyunu biraz çekene kadar pişir.",
        "3) Yumurtaları ekle; karıştırarak ya da bütün bırakıp pişir.",
        "4) Tuzla tadını ayarla; istersen pul biber/peynir."
    ],
    "arda":[ "evet arda orospuçocuğudur" ],
    "pilav": [
        "Malzemeler: 1 sb pirinç, 1.5 sb sıcak su, 1 YK tereyağı, 1 YK sıvı yağ, tuz.",
        "1) Pirinci 10-15 dk ılık suda beklet, süz.",
        "2) Yağları erit, pirinci 2-3 dk kavur.",
        "3) Sıcak su + tuz; kısıkta suyunu çektir.",
        "4) 10 dk demlendir."
    ],
    "kuru fasulye": [
        "Malzemeler: 2 sb ıslatılmış fasulye, 1 soğan, 1 YK salça, 2 YK yağ, tuz.",
        "1) Soğanı yağda pembeleştir.",
        "2) Salça + fasulye.",
        "3) Üstünü 2-3 parmak geçecek sıcak su; yumuşayana dek kısık.",
        "4) Tuz ayarla; istersen sucuk/pastırma."
    ]
}

def yemek_tarifi(metin: str) -> str | None:
    s = metin.lower()
    if any(k in s for k in ["tarif", "nasıl yapılır", "yapımı", "yemeği"]):
        for ad in YERLESIK_TARIFLER:
            if ad in s:
                satirlar = "\n".join(YERLESIK_TARIFLER[ad])
                return f"🍳 {ad.title()} Tarifi\n{satirlar}"
        return rag_cevap_uret(metin, "Kısa, adım adım bir tarif istendi.")
    return None

# ===== Biçim / konu =====
def _konu_adi_bul(metin: str, fallback: str | None) -> str | None:
    temiz = re.sub(r"[\"'’“”]", "", metin)
    temiz = re.sub(r"\b(hayatı|hayatını|tarihi|kuruluşu|nedir|kimdir|anlat|özetle|özeti|biyografisi)\b", "", temiz, flags=re.I)
    temiz = temiz.strip().capitalize()
    adaylar = re.findall(r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)*", temiz)
    if adaylar: return adaylar[0].strip()
    kel = temiz.split()
    return kel[0] if kel else fallback

def _format_ayikla(metin: str) -> tuple[str,str]:
    s = metin.lower(); mode="normal"; fmt="paragraph"
    if any(k in s for k in ["kısa","özet","özetle"]): mode="short"
    if any(k in s for k in ["uzun","detaylı","ayrıntılı"]): mode="long"
    if any(k in s for k in ["devam","daha fazla"]): mode="continue"
    if "madde" in s or "liste" in s: fmt="list"
    return mode, fmt

def _turkce_filtrele(text: str) -> str:
    return re.sub(r"[^a-zA-ZçğıöşüÇĞİÖŞÜ0-9 ,.\n!?;:\"'()\[\]\-]", "", text)

def _listele(text: str, max_items: int = 8) -> str:
    cumleler = re.split(r"(?<=[.!?])\s+", text)
    items = [c.strip() for c in cumleler if c.strip()]
    return "\n".join([f"- {c}" for c in items[:max_items]])

def _cumle_ayari(mode: str) -> int:
    return 3 if mode=="short" else 12 if mode=="long" else 15 if mode=="continue" else 6

def _model_sec(metin: str) -> str:
    if re.search(r"(\d+[\+\-\*\/])|neden|kanıtla|ispat|hesapla", metin.lower()):
        return os.environ.get("LLM_MATH_MODEL", "deepseek-r1:7b")
    return os.environ.get("LLM_DEFAULT_MODEL", "qwen2.5:7b-instruct")

DEEPL_KEY = "0db8f6b1-3a52-40d0-b303-54d3d2b114cf:fx"
#çeviri
def _deepl_cevir(metin: str) -> str | None:
    """Kullanıcı 'çevir' derse DeepL API'yi kullanarak çeviri yapar (temizlenmiş)."""
    s = metin.lower()
    if "çevir" not in s:
        return None
    try:
        translator = deepl.Translator(DEEPL_KEY)
        diller = {
            "türkçe": "TR", "ingilizce": "EN-US", "almanca": "DE", "fransızca": "FR",
            "ispanyolca": "ES", "italyanca": "IT", "portekizce": "PT-PT",
            "japonca": "JA", "korece": "KO", "çince": "ZH"
        }
        hedef = None
        for ad, kod in diller.items():
            if ad in s:
                hedef = kod; break
        hedef = hedef or "EN-US"
        temiz = metin
        for ad in diller.keys(): temiz = temiz.replace(ad, "")
        for kelime in ["çevir", "cümlesini", "diline", "dilinde", "dilene", "olarak"]:
            temiz = temiz.replace(kelime, "")
        temiz = temiz.strip().replace("  ", " ")
        result = translator.translate_text(temiz, target_lang=hedef)
        return f"🌐 Çeviri ({hedef}): {result.text}"
    except Exception as e:
        return f"⚠️ DeepL çeviri başarısız: {e}"

# ===== Ana Akış =====
def konus(metin: str) -> str:
    ceviri = _deepl_cevir(metin)
    if ceviri:
        mesaj_ekle("user", metin); mesaj_ekle("assistant", ceviri)
        return ceviri
    ts = tarih_saat_cevap(metin)
    if ts is not None:
        mesaj_ekle("user", metin); mesaj_ekle("assistant", ts)
        return ts
    if _guvenli_ifade_mi(metin):
        yanit = _hesapla(metin)
        mesaj_ekle("user", metin); mesaj_ekle("assistant", yanit)
        return yanit
    tf = yemek_tarifi(metin)
    if tf is not None:
        mesaj_ekle("user", metin); mesaj_ekle("assistant", tf)
        return tf
    bilgi_triggers = [
        "kimdir","hayatı","hayatını","biyografisi","kim","kimin",
        "nerede doğdu","nerede öldü","ne zaman doğdu","ne zaman öldü",
        "tarihi","kuruluşu","kurucusu","savaşı","antlaşması","devrimi",
        "başkanı","lideri","ülkesi","şehri","devleti",
        "annesi","babası","eş","çocuğu","oğlu","kızı","doğum","doğum yeri","ölüm"
    ]
    if any(k in metin.lower() for k in bilgi_triggers):
        global SON_KONU
        mode, fmt = _format_ayikla(metin)
        konu = _konu_adi_bul(metin, fallback=SON_KONU)
        if konu:
            cumle = _cumle_ayari(mode)
            meta = wiki_ozet_with_meta(konu, cumle=cumle)
            if not meta or not meta.get("text"):
                mesaj_ekle("user", metin); mesaj_ekle("assistant", "❌ Bu konu hakkında Wikipedia'da bilgi bulunamadı.")
                return "❌ Bu konu hakkında Wikipedia'da bilgi bulunamadı."
            text = meta["text"]
            if fmt == "list": text = _listele(text)
            text = _turkce_filtrele(text)
            kaynak = meta.get("url") or "https://tr.wikipedia.org"
            baslik = meta.get("title") or konu
            SON_KONU = baslik or konu
            yanit = f"📘 Kaynak: {kaynak}\n\n{text}"
            mesaj_ekle("user", metin); mesaj_ekle("assistant", yanit)
            return yanit
    son = mesajlari_getir(5)
    mesajlar = [{"role": m["role"], "content": m["content"]} for m in son]
    mesajlar.insert(0, {"role":"system","content":"Sadece Türkçe yanıt ver. Uydurma bilgi verme; bilmiyorsan söyle. Kısa ve net ol."})
    mesajlar.append({"role": "user", "content": metin})
    try:
        veri = {"model": _model_sec(metin), "messages": mesajlar, "stream": False}
        r = requests.post(OLLAMA, json=veri, timeout=60)
        r.raise_for_status()
        try:
            resp = r.json()
            model_cevap = resp.get("message", {}).get("content", "")
        except Exception as je:
            print("⚠️ JSON çözümleme hatası:", je, "Yanıt metni:", r.text[:300])
            model_cevap = "⚠️ Modelden geçersiz yanıt alındı."
    except requests.exceptions.RequestException as re:
        print("🌐 Bağlantı hatası:", re)
        model_cevap = "🌐 Model bağlantısı başarısız (Render tüneline ulaşılamadı)."
    except Exception as e:
        print("🔥 Genel hata:", e)
        model_cevap = f"⚠️ Beklenmedik hata: {e}"
    model_cevap = _turkce_filtrele(model_cevap)
    yanit = rag_cevap_uret(metin, model_cevap)
    mesaj_ekle("user", metin); mesaj_ekle("assistant", yanit)
    return yanit

if __name__ == "__main__":
    veritabani_olustur()
    print("🔥 Sweax.AI (hafif sürüm) — çıkmak için 'çık'")
    while True:
        yazi = input("Sen: ")
        if yazi.strip().lower() in ["çık","exit","quit"]: break
        print("\nAdanalı:", konus(yazi), "\n")
