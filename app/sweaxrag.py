# -*- coding: utf-8 -*-
# sweaxrag.py  —  Bilgi Katmanı (Wikipedia + FAISS + Web)
#
# Özellikler:
# - Wikipedia REST API (TR → EN fallback), temizlenmiş kısa/uzun özet
# - Markdown/HTML/gereksiz karakter temizliği
# - FAISS tabanlı yerel bilgi deposu (isteğe bağlı)
# - Güvenilir haber kaynaklarından hafif web RAG (AA, BBC, Reuters, DW, Euronews)
# - Tamamen Türkçe kullanım için uygun

import os, json, re
import numpy as np
import faiss
import requests
from bs4 import BeautifulSoup
from urllib.parse import quote
from sentence_transformers import SentenceTransformer
from datetime import datetime
from zoneinfo import ZoneInfo

# ---- Kalıcı dosyalar ----
DATA_JSON  = "bilgi_deposu.json"    # kayıtlı metinler (konu + içerik)
FAISS_FILE = "bilgi_index.faiss"    # vektör veritabanı (anlam arama)

# ---- Embedding modeli (TR destekli, küçük ve hızlı) ----
_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# ---- Güvenilir haber kaynakları (allowlist) ----
ALLOWED_DOMAINS = [
    "reuters.com", "bbc.com", "bbc.co.uk", "aa.com.tr", "dw.com", "tr.euronews.com", "euronews.com"
]

# ---- Dosya yoksa oluştur ----
if not os.path.exists(DATA_JSON):
    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)


# =========================
# 1) YARDIMCI / TEMİZLİK
# =========================
_HEADERS = {"User-Agent": "SweaxAI/1.0 (+educational use)"}

def _clean_text(text: str) -> str:
    """Wikipedia özetinden gelen HTML/Markdown/çöpleri temizle."""
    if not text:
        return ""
    # HTML to text
    text = BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    # Markdown, gereksiz işaretler
    text = re.sub(r"#{1,6}\s*", "", text)       # başlık işaretleri
    text = re.sub(r"\*{1,3}", "", text)         # kalın/italik yıldızları
    text = text.replace("•", " ").replace("–", "-").replace("—", "-")
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text

def _limit_by_sentences(text: str, sentence_count: int) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out = " ".join(sentences[:max(1, sentence_count)])
    if len(out) > 1500:
        out = out[:1500].rstrip() + "..."
    return out


# =========================
# 2) WIKIPEDIA — REST SUMMARY
# =========================
def _wiki_summary_for_term(term: str, lang: str = "tr") -> dict | None:
    """Wikipedia REST summary çağrısı. Dönen ör: {'extract': ..., 'content_urls': {...}, 'type': ...}"""
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(term)}"
    try:
        r = requests.get(url, headers=_HEADERS, timeout=12)
        if r.status_code != 200:
            return None
        data = r.json()
        # Boş ya da disambiguation ise yine de döndürelim — üst katman karar versin.
        return data
    except Exception:
        return None

def wiki_ozet_with_meta(konu: str, cumle: int = 6) -> dict | None:
    """
    Konu için (TR → EN fallback) temiz kısa/uzun özet ve meta döndürür.
    Return:
      {
        "text": "<temizlenmiş özet>",
        "url": "https://tr.wikipedia.org/wiki/...",
        "title": "Başlık",
        "lang": "tr"|"en",
        "type": "standard"|"disambiguation"
      }
    """
    # Sorguyu sadeleştir
    temiz = konu.lower()
    # Sık gelen soru eklerini temizle
    REPLACE = [
        "kimdir", "nedir", "hayatı", "hayatını", "biyografisi", "tarihi", "anlamı", "özeti",
        "özetle", "anlat", "hikayesi", "kim", "kimdi", "kimmiş", "kimin", "ün", "ün hayatı", "ün hayatını",
        "kim", "kimdir", "anlatırmısın", "hakkında", "bilgi ver", "hakkında bilgi ver", "hakkında bilgi"
    ]

    for k in REPLACE:
        temiz = temiz.replace(k, "")
    temiz = temiz.strip()

    # Önce TR, sonra EN
    for lang in ("tr", "en"):
        data = _wiki_summary_for_term(temiz, lang=lang)
        if not data or "extract" not in data:
            continue
        extract = _clean_text(data.get("extract") or "")
        if not extract:
            continue

        # Disambiguation ise geçersiz sayabiliriz (başka dil denenir). Son çare kabul edilir.
        tp = data.get("type") or "standard"
        text = _limit_by_sentences(extract, cumle)

        # URL bul
        page_url = None
        cu = data.get("content_urls") or {}
        desktop = cu.get("desktop") or {}
        page_url = desktop.get("page")

        return {
            "text": text.strip(),
            "url": page_url or f"https://{lang}.wikipedia.org/",
            "title": data.get("title") or "",
            "lang": lang,
            "type": tp
        }

    return None

def wiki_ozet(konu: str, cumle: int = 6) -> str | None:
    """Geriye sadece metin özetini döndürür (uyumluluk için)."""
    meta = wiki_ozet_with_meta(konu, cumle=cumle)
    return meta["text"] if meta else None


# =========================
# 3) FAISS + JSON SAKLAMA
# =========================
def _json_oku() -> list:
    """Kayıtlı (konu, içerik) metinlerini JSON’dan okur."""
    with open(DATA_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def _json_yaz(veriler: list):
    """JSON’a geri yazar."""
    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(veriler, f, ensure_ascii=False, indent=2)

def bilgi_kaydet(konu: str, metin: str):
    """Yeni metni JSON’a ekler ve embedding’ini FAISS’e yazar."""
    veriler = _json_oku()
    veriler.append({"konu": konu, "icerik": metin})
    _json_yaz(veriler)

    v = _model.encode([metin]).astype("float32")
    if os.path.exists(FAISS_FILE):
        index = faiss.read_index(FAISS_FILE)
    else:
        index = faiss.IndexFlatL2(v.shape[1])
    index.add(v)
    faiss.write_index(index, FAISS_FILE)

def bilgi_bul(soru: str, top_k: int = 2) -> list[dict]:
    """FAISS üzerinde anlam araması yapar ve en yakın K kaydı döndürür."""
    if not os.path.exists(FAISS_FILE):
        return []
    index = faiss.read_index(FAISS_FILE)
    veriler = _json_oku()
    q = _model.encode([soru]).astype("float32")
    _, idx = index.search(q, top_k)
    out = []
    for i in idx[0]:
        if 0 <= i < len(veriler):
            out.append(veriler[i])
    return out


# =========================
# 4) “GÜNCEL Mİ?” KONTROLÜ + WEB
# =========================
TR_AYLAR = {
    "ocak":1, "şubat":2, "mart":3, "nisan":4, "mayıs":5, "haziran":6,
    "temmuz":7, "ağustos":8, "eylül":9, "ekim":10, "kasım":11, "aralık":12
}

def _bugun_ist() -> datetime:
    return datetime.now(ZoneInfo("Europe/Istanbul"))

def _metinden_tarih_bul(metin: str) -> datetime | None:
    s = metin.lower()
    p = re.compile(r"(\d{1,2})\s+([a-zçğıöşü]+)(?:\s+(\d{4}))?")
    m = p.search(s)
    if not m:
        return None
    gun = int(m.group(1))
    ay_ad = m.group(2)
    yil = int(m.group(3)) if m.group(3) else _bugun_ist().year
    ay = TR_AYLAR.get(ay_ad, None)
    if not ay:
        return None
    try:
        return datetime(yil, ay, gun, tzinfo=ZoneInfo("Europe/Istanbul"))
    except Exception:
        return None

def soru_guncel_mi(soru: str) -> bool:
    s = soru.lower()
    if any(k in s for k in ["bugün", "dün", "az önce", "son dakika", "geçen hafta", "bu hafta"]):
        return True
    if _metinden_tarih_bul(soru):
        return True
    return False

def _domain_izinli_mi(url: str) -> bool:
    for d in ALLOWED_DOMAINS:
        if d in url:
            return True
    return False

def web_ara_ddg(query: str, max_results: int = 3) -> list[dict]:
    """DuckDuckGo Lite üzerinden hızlı arama yapar. [{title, url}] döner. Sadece izinli domainler."""
    url = "https://duckduckgo.com/lite/"
    try:
        params = {"q": query}
        html = requests.get(url, params=params, timeout=15, headers=_HEADERS).text
        soup = BeautifulSoup(html, "html.parser")
        links = []
        for a in soup.select("a"):
            href = a.get("href") or ""
            title = (a.text or "").strip()
            if href.startswith("http") and _domain_izinli_mi(href):
                links.append({"title": title[:120], "url": href})
            if len(links) >= max_results:
                break
        return links
    except Exception:
        return []

def sayfa_icerik_al(url: str, max_chars: int = 2000) -> str | None:
    """Haber sayfasını indirir, sade metni döndürür."""
    try:
        r = requests.get(url, timeout=15, headers=_HEADERS)
        soup = BeautifulSoup(r.text, "html.parser")
        texts = []
        for tag in soup.find_all(["h1", "h2", "p"]):
            t = (tag.get_text(" ", strip=True) or "")
            if len(t) > 0:
                texts.append(t)
        full = " ".join(texts)
        return full[:max_chars] if full else None
    except Exception:
        return None


# =========================
# 5) ANA RAG CEVAP FONKSİYONU
# =========================
def rag_cevap_uret(soru: str, model_cevap: str) -> str:
    """
    🔹 RAG sistemini modelin arka planında kullanır (kullanıcıya kaynak göstermeden).
    🔹 Wikipedia veya web sonuçlarını kullanıcıya göstermez (şu fonksiyonun görevi bu değil).
    🔹 Ek bilgi modelin cevabını desteklemek için bağlama eklenir, görünmez.
    """
    ek_bilgi = ""

    # 1) Güncel bilgi gerekiyorsa → güvenilir haberlerden özet topla
    if soru_guncel_mi(soru):
        linkler = web_ara_ddg(soru, max_results=2)
        for l in linkler:
            icerik = sayfa_icerik_al(l["url"])
            if icerik:
                ek_bilgi += " " + icerik[:600]
        # Şimdilik model cevabını aynen döndür (görünmez ek bilgi ileride kullanılabilir)
        return model_cevap

    # 2) FAISS + Wikipedia verisiyle destek (kullanıcıya göstermeden)
    kaynaklar = bilgi_bul(soru)
    if not kaynaklar:
        yeni = wiki_ozet(soru, cumle=5)
        if yeni:
            bilgi_kaydet(soru, yeni)
            ek_bilgi += " " + yeni
    else:
        ek_bilgi += " " + " ".join(k["icerik"][:300] for k in kaynaklar)

    # 3) Sadece modelin cevabını döndür
    return model_cevap
