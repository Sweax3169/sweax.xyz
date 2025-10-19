# -*- coding: utf-8 -*-
# sweaxai.py  —  Konuşma Katmanı
#
# Özellikler:
# - Konu hafızası (SON_KONU): "Atatürk kimdir?" → "annesi kim?" bağlamını anlar
# - Wikipedia öncelikli bilgi modu (uzun/kısa/özet/madde madde biçimleri)
# - Matematik, Tarih/Saat, Yemek tarifleri (mevcut akış korunur)
# - Model + RAG fallback
# - Türkçe-only çıktı filtresi (Latin dışı karakter temizliği)
# - Tüm mesajlar DB'ye yazılır

import re, requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from sweaxrag import wiki_ozet, wiki_ozet_with_meta, rag_cevap_uret
from sweax_db import veritabani_olustur, mesaj_ekle, mesajlari_getir

OLLAMA = "http://localhost:11434/api/chat"

# =============== Yardımcılar ===============
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
    s = metin.lower()
    now = _simdi_ist()

    if "saat kaç" in s or "şu an saat" in s:
        return f"Şu an saat (İstanbul): {now:%H:%M}"

    if "hangi yıldayız" in s or "yıl kaç" in s:
        return f"{now.year} yılındayız."

    m = re.search(r"(\d+)\s*yıl\s*sonra", s)
    if m:
        plus = int(m.group(1))
        return f"{plus} yıl sonra: {now.year + plus}"

    if "ayın kaçı" in s:
        return f"Bugün tarih: {now:%d.%m.%Y} (İstanbul)."

    if "hangi aydayız" in s:
        ay_adlari = ["Ocak","Şubat","Mart","Nisan","Mayıs","Haziran","Temmuz","Ağustos","Eylül","Ekim","Kasım","Aralık"]
        return f"{ay_adlari[now.month-1]} ayındayız."

    if "günlerden ne" in s or "hangi gün" in s:
        gun_adlari = ["Pazartesi","Salı","Çarşamba","Perşembe","Cuma","Cumartesi","Pazar"]
        return f"Bugün {gun_adlari[now.weekday()]}."

    if "yarın tarih" in s:
        t = now + timedelta(days=1)
        return f"Yarın: {t:%d.%m.%Y}"
    if "dün tarih" in s:
        t = now - timedelta(days=1)
        return f"Dün: {t:%d.%m.%Y}"

    return None

# =============== Yemek Tarifleri ===============
YERLESIK_TARIFLER = {
    "menemen": [
        "Malzemeler: 3 domates, 3 yumurta, 2 sivri biber, 1 yemek kaşığı tereyağı, tuz.",
        "1) Biberleri küçük doğra, tereyağında 2-3 dk sotele.",
        "2) Doğranmış domatesleri ekle, suyunu biraz çekene kadar pişir.",
        "3) Yumurtaları ekle; karıştırarak ya da bütün bırakıp pişir.",
        "4) Tuzla tadını ayarla. İsteğe göre pul biber/peynir eklenebilir."
    ],
    "pilav": [
        "Malzemeler: 1 su bardağı pirinç, 1,5 su bardağı sıcak su, 1 yemek kaşığı tereyağı, 1 yemek kaşığı sıvı yağ, tuz.",
        "1) Pirinci 10-15 dk ılık suda beklet, süz.",
        "2) Tencerede yağları erit, pirinci 2-3 dk kavur.",
        "3) Sıcak su ve tuzu ekle; kısık ateşte suyunu çekene kadar pişir.",
        "4) 10 dk demlendir, kapağı açmadan beklet."
    ],
    "kuru fasulye": [
        "Malzemeler: 2 su bardağı kuru fasulye (önceden ıslatılmış), 1 soğan, 1 yemek kaşığı salça, 2 yemek kaşığı sıvı yağ, tuz.",
        "1) Soğanı yemeklik doğra, yağda pembeleştir.",
        "2) Salçayı ekle kısa kavur, fasulyeyi ekle.",
        "3) Üzerini 2-3 parmak geçecek sıcak su ekle; kısık ateşte yumuşayana kadar pişir.",
        "4) Tuz ayarla; istersen sucuk/pastırma eklenebilir."
    ]
}

def yemek_tarifi(metin: str) -> str | None:
    s = metin.lower()
    if any(k in s for k in ["tarif", "nasıl yapılır", "yapımı", "yemeği"]):
        for ad in YERLESIK_TARIFLER.keys():
            if ad in s:
                ad_goster = ad.title()
                satirlar = "\n".join(YERLESIK_TARIFLER[ad])
                return f"🍳 {ad_goster} Tarifi (kısa ve net)\n{satirlar}"
        giris = "Kısa, adım adım ve güvenilir bir tarif özeti:\n"
        return rag_cevap_uret(metin, giris)
    return None

# =============== Konu/Format Algılayıcı ===============
def _konu_adi_bul(metin: str, fallback: str | None) -> str | None:
    """Metinden konu adını çıkartır. Büyük harf dizilerini ve genitif eklerini temizler."""

    temiz = re.sub(r"[\"'’“”]", "", metin)
    temiz = re.sub(r"\b(hayatı|hayatını|tarihi|kuruluşu|nedir|kimdir|anlat|özetle|özeti|biyografisi)\b", "", temiz, flags=re.I)
    temiz = temiz.strip().capitalize()  # 🔹 Küçük harfli girişleri düzelt
    # Büyük harfle başlayan kelime grubu
    adaylar = re.findall(r"[A-ZÇĞİÖŞÜ][a-zçğıöşü]+(?:\s+[A-ZÇĞİÖŞÜ][a-zçğıöşü]+)*", temiz)
    if adaylar:
        return adaylar[0].strip()
    # Eğer regex bulamadıysa doğrudan ilk kelimeyi döndür
    kelimeler = temiz.split()
    return kelimeler[0] if kelimeler else fallback

def _format_ayikla(metin: str) -> tuple[str, str]:
    """
    mode: normal|short|long|continue
    fmt: paragraph|list
    """
    s = metin.lower()
    mode = "normal"
    fmt = "paragraph"
    if any(k in s for k in ["kısa", "özet", "özetle"]): mode = "short"
    if any(k in s for k in ["uzun", "detaylı", "ayrıntılı"]): mode = "long"
    if any(k in s for k in ["devam", "daha fazla"]): mode = "continue"
    if "madde" in s or "liste" in s: fmt = "list"
    return mode, fmt

def _turkce_filtrele(text: str) -> str:
    """Latin dışı ve kontrol dışı karakterleri eler (Türkçe güvenli çıktı)."""
    return re.sub(r"[^a-zA-ZçğıöşüÇĞİÖŞÜ0-9 ,.\n!?;:\"'()\[\]\-]", "", text)

def _listele(text: str, max_items: int = 8) -> str:
    cumleler = re.split(r"(?<=[.!?])\s+", text)
    items = [c.strip() for c in cumleler if c.strip()]
    return "\n".join([f"- {c}" for c in items[:max_items]])

def _cumle_ayari(mode: str) -> int:
    if mode == "short": return 3
    if mode == "long": return 12
    if mode == "continue": return 15
    return 6

# =============== Model Seçimi ===============
def _model_sec(metin: str) -> str:
    if re.search(r"(\d+[\+\-\*\/])|neden|kanıtla|ispat|hesapla", metin.lower()):
        return "deepseek-r1:7b"
    return "qwen2.5:7b-instruct"

# =============== Ana Akış ===============
def konus(metin: str) -> str:
    """
    Ana akış:
    1) Tarih/Saat → Doğrudan doğru cevap
    2) Matematik → Güvenli hesap
    3) Yemek tarifi → Yerleşik/RAG
    4) Bilgi modu → Wikipedia (format algısı + konu hafızası)
    5) Diğer her şey → Model + RAG fallback
    6) Her adımda DB kaydı
    """
    # ---- Bağlam hafızası
    global SON_KONU
    if not hasattr(globals(), "SON_KONU"):
        SON_KONU = None

    # 1) Tarih/Saat
    ts = tarih_saat_cevap(metin)
    if ts is not None:
        mesaj_ekle("user", metin); mesaj_ekle("assistant", ts)
        return ts

    # 2) Matematik
    if _guvenli_ifade_mi(metin):
        yanit = _hesapla(metin)
        mesaj_ekle("user", metin); mesaj_ekle("assistant", yanit)
        return yanit

    # 3) Yemek tarifi
    tf = yemek_tarifi(metin)
    if tf is not None:
        mesaj_ekle("user", metin); mesaj_ekle("assistant", tf)
        return tf

    # 4) Bilgi modu tetikleyicileri (çok geniş liste)
    bilgi_triggers = [
        "kimdir", "hayatı", "hayatını", "biyografisi", "kim", "kimin",
        "nerede doğdu", "nerede öldü", "ne zaman doğdu", "ne zaman öldü",
        "tarihi", "kuruluşu", "kurucusu", "savaşı", "antlaşması", "devrimi",
        "başkanı", "lideri", "ülkesi", "şehri", "devleti"


        # Genel bilgi
    #    "kimdir","nedir","nedemek","ne anlama gelir","ne işe yarar","nedeni","sebebi","sebep",
    #    "nasıl çalışır","nasıl oluşur","neden oluşur","önemi","özellikleri","amacı","etkisi","faydası","zararı",
    #    # Tarih/olay
    #    "tarihi","kuruluşu","kurucusu","yıkılışı","ortaya çıkışı","savaşı","antlaşması","devrimi",
    #    "ne zaman kuruldu","ne zaman oldu","hangi yılda","hangi yüzyılda",
    #    # Biyografi
       "kim","kimin","annesi","babası","eş","çocuğu","oğlu","kızı","doğum","doğum yeri","ölüm",
    #    "nerede doğdu","nerede öldü","ne zaman doğdu","ne zaman öldü","eğitimi","mezunu","mesleği","yaşamı","hayatı","hayatını","biyografisi","yaşı",
    #    # Coğrafya
    #    "nerede","nerededir","hangi ülkede","nereye bağlı","başkenti","nüfusu","konumu","iklimi","dağı","nehri","gölü","denizi","okyanusu","şehri","ülkesi",
    #    # Kültür/bilim/tek
    #    "tanımı","tanım","anlamı","terimi","kavramı","bilimi","teorisi","yasası","ilkesi","formülü","birimi","buluşu","icat","teknolojisi",
    #    "programı","dizisi","filmi","oyuncusu","yönetmeni","senaristi","yayın tarihi","karakteri",
    #    # Din/felsefe/sanat
    #    "dini","peygamberi","inancı","mezhebi","tanrısı","felsefesi","akımı","resmi","tablosu","eserleri","bestesi","romanı","hikayesi",
    #    # Kurumlar
    #    "üniversitesi","okulu","kurumu","derneği","partisi","vakfı","şirketi","markası","takımı","kulübü","başkanı","ceosu","lideri","üyeleri",
    #    # Biçim komutları
    #    "anlat","özetle","özeti","madde madde","listele"
    #
    ]

    if any(k in metin.lower() for k in bilgi_triggers):
        mode, fmt = _format_ayikla(metin)
        konu = _konu_adi_bul(metin, fallback=SON_KONU)
        if konu:
            cumle = _cumle_ayari(mode)
            meta = wiki_ozet_with_meta(konu, cumle=cumle)

            # Eğer Wikipedia'dan veri yoksa uydurma bilgi verme!
            if not meta or not meta.get("text"):
                mesaj_ekle("user", metin)
                mesaj_ekle("assistant", "❌ Bu konu hakkında Wikipedia'da bilgi bulunamadı.")
                return "❌ Bu konu hakkında Wikipedia'da bilgi bulunamadı."

            text = meta["text"]
            if fmt == "list":
                text = _listele(text)
            text = _turkce_filtrele(text)
            kaynak = meta.get("url") or "https://tr.wikipedia.org"
            baslik = meta.get("title") or konu
            yanit = f"📘 Kaynak: {kaynak}\n\n{text}"
            SON_KONU = baslik or konu
            mesaj_ekle("user", metin)
            mesaj_ekle("assistant", yanit)
            return yanit

    # 5) Model + RAG (genel)
    son = mesajlari_getir(10)
    mesajlar = [{"role": m["role"], "content": m["content"]} for m in son]
    mesajlar.insert(0, {"role": "system",
                        "content":
                            "Sen Türkçe konuşan, kısa ve net cevap veren, dobra bir asistansın. "
                            "Hakaret/nefret yok. Uydurma bilgi verme. Bilmiyorsan söyle."})
    mesajlar.append({"role": "user", "content": metin})

    try:
        veri = {
            "model": _model_sec(metin),
            "messages": [
                {"role": "system", "content": (
                    "Sadece Türkçe yanıt ver. "
                    "Yabancı dillerde kelime, karakter veya sembol kullanma. "
                    "Yanıtlarında Latin dışı harf kullanmak kesinlikle yasaktır. "
                    "Eğer soruda yabancı dil varsa, Türkçe çevir ve sadece Türkçe açıkla. "
                    "Kısa, doğru, net ol."
                )}
            ] + mesajlar,
            "stream": False
        }
        resp = requests.post(OLLAMA, json=veri, timeout=120).json()
        model_cevap = resp["message"]["content"]
        model_cevap = _turkce_filtrele(model_cevap)
    except Exception as e:
        model_cevap = f"Bir hata oluştu: {e}"

    yanit = rag_cevap_uret(metin, model_cevap)
    mesaj_ekle("user", metin); mesaj_ekle("assistant", yanit)
    return yanit


# =============== Terminal Testi ===============
if __name__ == "__main__":
    veritabani_olustur()
    print("🔥 Sweax.AI başladı (çıkmak için 'çık' yaz)")
    while True:
        yazi = input("Sen: ")
        if yazi.strip().lower() in ["çık", "exit", "quit"]:
            print("Görüşürüz 😎")
            break
        cevap = konus(yazi)
        print("\nAdanalı:", cevap, "\n")
