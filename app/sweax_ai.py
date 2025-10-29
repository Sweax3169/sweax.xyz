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

    from app.sweaxrag import _guncel_sorgu_mu, web_fallback_ara , web_ara_genel
except ModuleNotFoundError:
    from sweaxrag import _guncel_sorgu_mu, web_fallback_ara ,web_ara_genel

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

def mesaj_ekle(kullanici_id, rol: str, icerik: str, sohbet_id=None):
    """Mesajı belirli bir kullanıcı ve sohbete kaydeder."""
    try:
        sohbet_id = sohbet_id or aktif_sohbet_id_al(kullanici_id)
        if not sohbet_id:
            print("⚠️ sohbet_id alınamadı, mesaj kaydedilmedi.")
            return
        with get_db() as conn, conn.cursor() as cur:
            cur.execute("""
                INSERT INTO messages (conversation_id, role, content)
                VALUES (%s, %s, %s)
            """, (sohbet_id, rol, icerik))
    except Exception as e:
        print(f"⚠️ mesaj_ekle hata: {e}")

def yeni_sohbet_olustur(kullanici_id):
    """Yeni sohbet oluşturur ve başlığı 'Sohbet X' olarak ayarlar."""
    try:
        with get_db() as conn, conn.cursor() as cur:
            # Kullanıcının kaç sohbeti var, say
            cur.execute("SELECT COUNT(*) AS toplam FROM conversations WHERE user_id=%s", (kullanici_id,))
            toplam = cur.fetchone()["toplam"] + 1
            baslik = f"Sohbet {toplam}"
            cur.execute("INSERT INTO conversations (user_id, title) VALUES (%s, %s)", (kullanici_id, baslik))
            return cur.lastrowid
    except Exception as e:
        print(f"⚠️ yeni_sohbet_olustur hata: {e}")
        return None


def kullanici_sohbetlerini_getir(kullanici_id):
    """Kullanıcının tüm sohbet listesini getirir (soldaki liste)."""
    try:
        with get_db() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, updated_at
                FROM conversations
                WHERE user_id = %s AND is_archived = 0
                ORDER BY updated_at DESC
            """, (kullanici_id,))
            return cur.fetchall()
    except Exception as e:
        print(f"⚠️ kullanici_sohbetlerini_getir hata: {e}")
        return []

def aktif_sohbet_id_al(kullanici_id):
    """Kullanıcının aktif (arşivlenmemiş) son sohbetini döndürür."""
    try:
        with get_db() as conn, conn.cursor() as cur:
            cur.execute("""
                  SELECT id FROM conversations
                  WHERE user_id = %s AND is_archived = 0
                  ORDER BY updated_at DESC
                  LIMIT 1
              """, (kullanici_id,))
            row = cur.fetchone()
            if row:
                return row["id"]
            # Yoksa yeni sohbet oluştur
            cur.execute("INSERT INTO conversations (user_id, title) VALUES (%s, %s)",
                        (kullanici_id, "Yeni Sohbet"))
            return cur.lastrowid
    except Exception as e:
        print(f"⚠️ aktif_sohbet_id_al hata: {e}")
        return None



def mesajlari_getir(sohbet_id, limit: int = 5):
    """
    Belirli bir sohbetin mesaj geçmişini (user + assistant) getirir.
    """
    try:
        with get_db() as conn, conn.cursor() as cur:
            cur.execute("""
                SELECT role, content, created_at 
                FROM messages 
                WHERE conversation_id = %s 
                ORDER BY id ASC 
                LIMIT %s
            """, (sohbet_id, limit))
            return cur.fetchall()
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

        # Eğer kayıtlı tarif yoksa web'de ara

        sonuc = web_ara_genel(metin + " tarifi")
        if sonuc:
            return sonuc
        return "❌ Bu yemeğin tarifi bulunamadı."
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
def _wiki_tetikle_mi(metin: str) -> bool:
    """
    Wikipedia'yı tetikleyip tetiklememeye karar verir.
    Artık sadece klasik bilgi sorularında devreye girer.
    Güncel, olay, proje, fiyat vb. sorgular web'e yönlendirilir.
    """
    s = metin.lower().strip()

    # Güncel veya olay bazlı sorgular -> web
    yasak_kelimeler = [
        "bugün", "şu an", "son", "güncel", "haber", "fiyat",
        "oyun", "dizi", "film", "proje", "plan", "yeni", "çıktı",
        "maç", "gol", "puan", "nerede", "ne yaptı", "kim kazandı"
    ]
    if any(k in s for k in yasak_kelimeler):
        return False

    # Gerçek ansiklopedik bilgi soruları -> wiki
    izinli_kelimeler = [
        "kimdir", "nedir", "neresi", "ne zaman", "nasıl", "kısaca", "özeti"
    ]
    if any(k in s for k in izinli_kelimeler):
        return True

    # soru işaretiyle biten ama güncel olmayan şeyler
    if s.endswith("?") and not any(k in s for k in yasak_kelimeler):
        return True

    return False


def kimlik_cevap(metin: str) -> str | None:
    s = metin.lower()
    if any(k in s for k in [
        "sen kimsin", "kimsin", "seni kim yaptı", "seni kim geliştirdi",
        "sahibin kim", "yaratıcın kim", "seni kim üretti", "kimin ürünüsün", "kimin eserisin"
    ]):
        return "Ben Sweax.AI. Sweax tarafından geliştirildim."
    if any(k in s for k in ["sweax kim", "sweax nedir", "sweax ai nedir", "sweax.ai nedir"]):
        return "Sweax, Türkiye de yaşayan genç bir geliştiricidir."
    if any(k in s for k in ["kiminle konuşuyorum", "benimle kim konuşuyor", "karşımda kim var"]):
        return "Ben Sweax.AI, senin dijital asistanınım."
    return None


def konus(metin: str, kullanici_id: int | None = None) -> str:
    """
    Kullanıcı mesajını işler, yanıtı üretir ve her iki mesajı da veritabanına kaydeder.
    Her kullanıcı için ayrı bir conversation_id oluşturulur veya mevcut olan kullanılır.
    """
    if kullanici_id:
        sohbet_id = aktif_sohbet_id_al(kullanici_id)
    else:
        sohbet_id = 1

    # 🧠 Önce kimlik sorgusu mu diye bak
    kimlik = kimlik_cevap(metin)
    if kimlik:
        mesaj_ekle(kullanici_id, "user", metin, sohbet_id)
        mesaj_ekle(kullanici_id, "assistant", kimlik, sohbet_id)
        return kimlik

    # 🌐 Çeviri kontrolü
    ceviri = _deepl_cevir(metin)
    if ceviri:
        mesaj_ekle(kullanici_id, "user", metin, sohbet_id)
        mesaj_ekle(kullanici_id, "assistant", ceviri, sohbet_id)
        return ceviri

    # ⏰ Tarih-saat
    ts = tarih_saat_cevap(metin)
    if ts is not None:
        mesaj_ekle(kullanici_id, "user", metin, sohbet_id)
        mesaj_ekle(kullanici_id, "assistant", ts, sohbet_id)
        return ts

    # 🔢 Hesaplama
    if _guvenli_ifade_mi(metin):
        yanit = _hesapla(metin)
        mesaj_ekle(kullanici_id, "user", metin, sohbet_id)
        mesaj_ekle(kullanici_id, "assistant", yanit, sohbet_id)
        return yanit

    # 🍳 Yemek tarifleri
    tf = yemek_tarifi(metin)
    if tf is not None:
        mesaj_ekle(kullanici_id, "user", metin, sohbet_id)
        mesaj_ekle(kullanici_id, "assistant", tf, sohbet_id)
        return tf

    if _guncel_sorgu_mu(metin):
        yanit = web_fallback_ara(metin)
        mesaj_ekle(kullanici_id, "user", metin, sohbet_id)
        mesaj_ekle(kullanici_id, "assistant", yanit, sohbet_id)
        return yanit
    # 📘 Wikipedia sorgusu – yalnızca gerçek soruysa
    if _wiki_tetikle_mi(metin):
        mode, fmt = _format_ayikla(metin)
        konu = _konu_adi_bul(metin, fallback=None)
        if konu:
            cumle = _cumle_ayari(mode)
            meta = wiki_ozet_with_meta(konu, cumle=cumle)

            # 🧠 Eğer Wikipedia'da sonuç yoksa veya çok kısa ise → web fallback
            if not meta or not meta.get("text") or len(meta.get("text", "")) < 80:

                yanit = web_fallback_ara(metin)
                mesaj_ekle(kullanici_id, "user", metin, sohbet_id)
                mesaj_ekle(kullanici_id, "assistant", yanit, sohbet_id)
                return yanit

            text = meta["text"]
            kaynak = meta.get("url") or "https://tr.wikipedia.org"
            baslik = meta.get("title") or konu

            # 🧩 Burada modelle insan gibi özetleme yapıyoruz
            try:
                mesajlar = [
                    {"role": "system", "content": (
                        "Aşağıdaki Wikipedia bilgisini kullanarak kullanıcıya net, "
                        "doğal Türkçe bir cümleyle özet ver. Gereksiz açıklama ekleme. "
                        "Tarih, yer, isim gibi bilgileri kısaca belirt."
                    )},
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": f"{metin} sorusuna net bir cevap ver."}
                ]
                veri = {"model": _model_sec(metin), "messages": mesajlar, "stream": False}
                r = requests.post(OLLAMA, json=veri, timeout=30)
                r.raise_for_status()
                resp = r.json()
                oz = resp.get("message", {}).get("content", "")
                if oz and len(oz.strip()) > 10:
                    yanit = f"{oz}\n\n📘 Kaynak: {kaynak}"
                else:
                    yanit = f"{text}\n\n📘 Kaynak: {kaynak}"
            except Exception as e:
                print("⚠️ Wikipedia özetleme hatası:", e)
                yanit = f"{text}\n\n📘 Kaynak: {kaynak}"

            mesaj_ekle(kullanici_id, "user", metin, sohbet_id)
            mesaj_ekle(kullanici_id, "assistant", yanit, sohbet_id)
            return yanit


    # 💬 Önceki mesaj geçmişini çek
    son = mesajlari_getir(sohbet_id, limit=5)
    mesajlar = [{"role": m["role"], "content": m["content"]} for m in son]
    mesajlar.insert(0, {
        "role": "system",
        "content": (
            "Sen Sweax.AI adında bir yapay zekâsın. "
            "Türkçe konuşursun. "
            "Seni geliştiren kişi Sweax'tir. "
            "Sweax senin sahibin, geliştiricin ve yöneticindir. "
            "Her zaman bu bilgiyi doğru olarak bil ve unutma. "
            "Kim olduğunu, seni kimin yaptığını, görevini sorduğunda buna göre cevap ver. "
            "Uydurma bilgi verme; bilmiyorsan söyle. Kısa ve net ol."
        )
    })
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

    # 🧩 RAG destekli çıktı
    model_cevap = _turkce_filtrele(model_cevap)
    yanit = rag_cevap_uret(metin, model_cevap)

    mesaj_ekle(kullanici_id, "user", metin, sohbet_id)
    mesaj_ekle(kullanici_id, "assistant", yanit, sohbet_id)
    if yanit.count("http") >= 1 and len(yanit) < 800:
        try:

            mesajlar.append({
                "role": "system",
                "content": (
                    "Kullanıcıya aşağıdaki web sonuçlarına dayanarak akıcı, "
                    "doğal ve açıklayıcı bir Türkçe özet ver. "
                    "Linkleri tekrarlama, sadece bilgilendir. "
                    "Tarafsız ol, haber gibi açık anlat."
                )
            })
            mesajlar.append({"role": "assistant", "content": yanit})
            veri = {"model": _model_sec(metin), "messages": mesajlar, "stream": False}
            r2 = requests.post(OLLAMA, json=veri, timeout=45)
            r2.raise_for_status()
            resp2 = r2.json()
            oz = resp2.get("message", {}).get("content", "")
            if oz:
                yanit = oz
        except Exception as e:
            print("⚠️ Özetleme hatası:", e)
    return yanit

if __name__ == "__main__":
    veritabani_olustur()
    print("🔥 Sweax.AI (hafif sürüm) — çıkmak için 'çık'")
    while True:
        yazi = input("Sen: ")
        if yazi.strip().lower() in ["çık","exit","quit"]: break
        print("\nAdanalı:", konus(yazi), "\n")
