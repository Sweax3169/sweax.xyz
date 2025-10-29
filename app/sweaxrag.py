# -*- coding: utf-8 -*-
# sweaxrag.py — Hafif RAM sürümü (Render 512 MB dostu)

import os, json, re, importlib
import requests
from urllib.parse import quote
from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
# ---- Konfig / modüler bayraklar ----
SWEAX_LIGHT = os.environ.get("SWEAX_LIGHT", "1") == "1"  # 1: en hafif mod
HEADERS = {"User-Agent": "SweaxAI-lite/1.0 (+educational use)"}

DATA_JSON  = "bilgi_deposu.json"
FAISS_FILE = "bilgi_index.faiss"


ALLOWED_DOMAINS = [
    "reuters.com", "bbc.com", "bbc.co.uk", "aa.com.tr", "dw.com", "tr.euronews.com", "euronews.com"
]

# JSON dosyası yoksa oluştur
if not os.path.exists(DATA_JSON):
    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)

# ====== Lazy helpers ======
def _lazy_import(name: str):
    try:
        return importlib.import_module(name)
    except Exception:
        return None

def _lazy_bs4():
    return _lazy_import("bs4")

def _lazy_sentence_model():
    st = _lazy_import("sentence_transformers")
    if not st:
        return None
    try:
        # küçük ve çok dilli model (ilk kullanımda yüklenir)
        return st.SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    except Exception:
        return None

def _lazy_faiss():
    return _lazy_import("faiss") or _lazy_import("faiss_cpu")

# ====== Metin temizlik ======
def _clean_text(text: str) -> str:
    if not text:
        return ""
    bs4 = _lazy_bs4()
    if bs4:
        text = bs4.BeautifulSoup(text, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"#{1,6}\s*", "", text)
    text = re.sub(r"\*{1,3}", "", text)
    text = text.replace("•", " ").replace("–", "-").replace("—", "-")
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text

def _limit_by_sentences(text: str, sentence_count: int) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    out = " ".join(sentences[:max(1, sentence_count)])
    if len(out) > 1500:
        out = out[:1500].rstrip() + "..."
    return out

# ====== Wikipedia REST summary ======
def _wiki_summary_for_term(term: str, lang: str = "tr") -> dict | None:
    url = f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/{quote(term)}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        return r.json()
    except Exception:
        return None

def wiki_ozet_with_meta(konu: str, cumle: int = 6) -> dict | None:
    temiz = konu.lower()
    for k in ["kimdir","nedir","hayatı","hayatını","biyografisi","tarihi","anlamı","özeti","özetle","anlat","hikayesi","kim","kimdi","kimmiş","kimin","hakkında","bilgi ver"]:
        temiz = temiz.replace(k, "")
    temiz = temiz.strip()

    for lang in ("tr", "en"):
        data = _wiki_summary_for_term(temiz, lang=lang)
        if not data or "extract" not in data:
            continue
        extract = _clean_text(data.get("extract") or "")
        if not extract:
            continue
        tp = data.get("type") or "standard"
        text = _limit_by_sentences(extract, cumle)
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
    meta = wiki_ozet_with_meta(konu, cumle=cumle)
    return meta["text"] if meta else None

# ====== JSON depolama ======
def _json_oku() -> list:
    with open(DATA_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def _json_yaz(veriler: list):
    """JSON’a geri yazar."""
    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(veriler, f, ensure_ascii=False, indent=2)

# ====== FAISS + Embeddings (opsiyonel) ======
_model_cache = None
def _get_model():
    global _model_cache
    if _model_cache is None:
        if SWEAX_LIGHT:
            return None  # en hafif modda hiç açma
        _model_cache = _lazy_sentence_model()
    return _model_cache

def bilgi_kaydet(konu: str, metin: str):
    # JSON'a yaz
    veriler = _json_oku()
    veriler.append({"konu": konu, "icerik": metin})
    _json_yaz(veriler)

    # Embedding/FAISS yoksa sessizce pas geç
    model = _get_model()
    faiss = _lazy_faiss()
    if not (model and faiss):
        return

    try:
        v = model.encode([metin]).astype("float32")
        if os.path.exists(FAISS_FILE):
            index = faiss.read_index(FAISS_FILE)
        else:
            index = faiss.IndexFlatL2(v.shape[1])
        index.add(v)
        faiss.write_index(index, FAISS_FILE)
    except Exception:
        pass  # RAM/bağımlılık sorunlarında sessiz geç

def bilgi_bul(soru: str, top_k: int = 2) -> list[dict]:
    # FAISS yoksa sadece JSON içinden son kayıtları döndürme stratejisi
    model = _get_model()
    faiss = _lazy_faiss()
    if not (model and faiss and os.path.exists(FAISS_FILE)):
        # hafif fallback: konu kelimesi geçen son kayıtlar
        veriler = _json_oku()
        s = soru.lower()
        return [v for v in reversed(veriler) if v["konu"].lower() in s][:top_k]

    try:
        index = faiss.read_index(FAISS_FILE)
        veriler = _json_oku()
        q = model.encode([soru]).astype("float32")
        _, idx = index.search(q, top_k)
        out = []
        for i in idx[0]:
            if 0 <= i < len(veriler):
                out.append(veriler[i])
        return out
    except Exception:
        return []

# ====== Güncellik + Web (hafif) ======
TR_AYLAR = {"ocak":1,"şubat":2,"mart":3,"nisan":4,"mayıs":5,"haziran":6,"temmuz":7,"ağustos":8,"eylül":9,"ekim":10,"kasım":11,"aralık":12}

def _bugun_ist() -> datetime:
    return datetime.now(ZoneInfo("Europe/Istanbul"))

def _metinden_tarih_bul(metin: str) -> datetime | None:
    s = metin.lower()
    m = re.search(r"(\d{1,2})\s+([a-zçğıöşü]+)(?:\s+(\d{4}))?", s)
    if not m: return None
    gun = int(m.group(1)); ay_ad = m.group(2); yil = int(m.group(3)) if m.group(3) else _bugun_ist().year
    ay = TR_AYLAR.get(ay_ad);
    if not ay: return None
    try:
        return datetime(yil, ay, gun, tzinfo=ZoneInfo("Europe/Istanbul"))
    except Exception:
        return None

def soru_guncel_mi(soru: str) -> bool:
    s = soru.lower()
    if any(k in s for k in ["bugün","dün","az önce","son dakika","geçen hafta","bu hafta"]):
        return True
    return _metinden_tarih_bul(soru) is not None

def _domain_izinli_mi(url: str) -> bool:
    return any(d in url for d in ALLOWED_DOMAINS)

def web_ara_ddg(query: str, max_results: int = 2) -> list[dict]:
    url = "https://duckduckgo.com/lite/"
    try:
        html = requests.get(url, params={"q": query}, timeout=8, headers=HEADERS).text
        bs4 = _lazy_bs4()
        if not bs4:
            return []
        soup = bs4.BeautifulSoup(html, "html.parser")
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

def sayfa_icerik_al(url: str, max_chars: int = 1600) -> str | None:
    try:
        r = requests.get(url, timeout=8, headers=HEADERS)
        bs4 = _lazy_bs4()
        if not bs4:
            return None
        soup = bs4.BeautifulSoup(r.text, "html.parser")
        texts = []
        for tag in soup.find_all(["h1","h2","p"]):
            t = (tag.get_text(" ", strip=True) or "")
            if t: texts.append(t)
        full = " ".join(texts)
        return full[:max_chars] if full else None
    except Exception:
        return None

# ====== Ana RAG cevabı ======
def rag_cevap_uret(soru: str, model_cevap: str) -> str:
    # Güncel ise kısa web özetini gizlice çek — ama RAM’e yük bindirme
    if soru_guncel_mi(soru):
        for l in web_ara_ddg(soru, max_results=2):
            _ = sayfa_icerik_al(l["url"])  # ileride iç bağlama eklenebilir
        return model_cevap

    # FAISS/JSON ile destek
    kaynaklar = bilgi_bul(soru)
    if not kaynaklar:
        yeni = wiki_ozet(soru, cumle=5)
        if yeni:
            bilgi_kaydet(soru, yeni)
    return model_cevap

# WEBDE ARAMA


def web_ara_genel(soru: str, max_results: int = 3) -> str | None:
    """
    DuckDuckGo HTML arama (GET versiyonu) – Render uyumlu, daha dayanıklı sürüm
    """
    import requests
    from bs4 import BeautifulSoup

    try:
        url = "https://duckduckgo.com/html/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/118.0.5993.70 Safari/537.36"
        }

        # GET kullanıyoruz çünkü POST bazen boş döndürüyor
        resp = requests.get(url, params={"q": soru}, headers=headers, timeout=10)
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        results = []
        for a in soup.select(".result__a"):
            title = (a.text or "").strip()
            href = a.get("href")
            if href and href.startswith("http"):
                results.append(f"🔗 [{title}]({href})")
            if len(results) >= max_results:
                break

        if not results:
            # Alternatif: Google fallback (proxy)
            g_url = f"https://www.google.com/search?q={soru.replace(' ', '+')}"
            return f"🌐 Sonuç bulunamadı. Şu sayfada aramayı deneyebilirsin:\n🔗 [Google'da Ara]({g_url})"

        return "🌐 Web sonuçları:\n" + "\n".join(results)

    except Exception as e:
        return f"⚠️ Web arama hatası: {e}"


def web_ara_serper(soru: str, max_results: int = 3) -> str | None:
    """
    Serper.dev Google Search API — Markdown tabanlı ChatGPT tarzı kart stili sonuç
    """
    import requests, os
    SERPER_KEY = os.getenv("SERPER_KEY", "60616d6ea2b6da230c1930c4817a755439d44cba")

    try:
        headers = {"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}
        payload = {"q": soru, "gl": "tr", "hl": "tr"}
        r = requests.post("https://google.serper.dev/search", json=payload, headers=headers, timeout=10)
        data = r.json()

        if "organic" not in data:
            return None

        results = data["organic"][:max_results]
        if not results:
            return "🔍 Üzgünüm, bu konuda güncel bilgi bulunamadı."

        # Başlık
        yanit = [f"💎 **{soru.title()} (Güncel Bilgiler)**", "─────────────────────────────"]

        # Sonuçları düzenle
        for r in results:
            baslik = r.get("title", "Kaynak").strip()
            link = r.get("link", "")
            aciklama = r.get("snippet", "").replace("\n", " ").strip()
            if len(aciklama) > 220:
                aciklama = aciklama[:220] + "…"

            # Basit domain çıkarımı
            domain = ""
            if "://" in link:
                domain = link.split("/")[2].replace("www.", "")

            yanit.append(
                f"📍 **{domain}**\n"
                f"📰 [{baslik}]({link})\n"
                f"💬 {aciklama}\n"
                "─────────────────────────────"
            )
        # Sonuçları birleştirirken kısa özet üret
        joined = " ".join(r.get("snippet", "") for r in results if r.get("snippet"))
        if joined:
            yanit += ["\n🧠 **Kısa Özet:** " + joined[:600] + "…"]
        return "\n".join(yanit)

    except Exception as e:
        return f"⚠️ Web arama hatası: {e}"



def _guncel_sorgu_mu(soru: str) -> bool:
    s = soru.lower()
    anahtarlar = [
        "bugün", "şu an", "güncel", "fiyat", "nerede", "hangi", "trend", "popüler",
        "oyunlar", "hava", "puan", "menü", "yeni çıkan", "en iyi", "yakın", "restoran"
    ]
    return any(k in s for k in anahtarlar)

def web_fallback_ara(soru: str) -> str:

    sonuc = web_ara_serper(soru)
    if sonuc:
        return sonuc
    sonuc = web_ara_genel(soru)
    if sonuc:
        return sonuc
    return "🌐 Bu konuda güvenilir bir kaynak bulunamadı."