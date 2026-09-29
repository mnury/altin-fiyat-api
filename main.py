from __future__ import annotations

import fcntl
import json
import os
import secrets
import time
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException

SOURCE_URL = "https://erkuder.com/api/fiyatlar.php"
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))
CACHE_FILE = Path(os.getenv("CACHE_FILE", "cache/prices.json"))
API_KEY = os.getenv("API_KEY")
REQUEST_HEADERS = {
    "Referer": "https://erkuder.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
}

app = FastAPI(title="Altın, Döviz ve Ons Fiyat API", version="1.2.0")

GOLD_PRODUCTS: dict[str, dict[str, str]] = {
    "gram_altin": {"urun_kodu": "gram_altin", "urun_adi": "Gram Altın"},
    "ceyrek_altin": {"urun_kodu": "ceyrek_acik", "urun_adi": "Çeyrek Altın (Açık)", "varyant": "acik"},
    "yarim_altin": {"urun_kodu": "yarim_acik", "urun_adi": "Yarım Altın (Açık)", "varyant": "acik"},
    "tam_altin": {"urun_kodu": "tam_acik", "urun_adi": "Tam Altın (Açık)", "varyant": "acik"},
    "ata_altin": {"urun_kodu": "ata_acik", "urun_adi": "Ata Altın (Açık)", "varyant": "acik"},
    "gremese_yeni": {"urun_kodu": "gremese_acik", "urun_adi": "Gremse Altın (Açık)", "varyant": "acik"},
    "ceyrek_eski": {"urun_kodu": "ceyrek_kapali", "urun_adi": "Çeyrek Altın (Kapalı)", "varyant": "kapali"},
    "yarim_eski": {"urun_kodu": "yarim_kapali", "urun_adi": "Yarım Altın (Kapalı)", "varyant": "kapali"},
    "tam_eski": {"urun_kodu": "tam_kapali", "urun_adi": "Tam Altın (Kapalı)", "varyant": "kapali"},
    "ata_eski": {"urun_kodu": "ata_kapali", "urun_adi": "Ata Altın (Kapalı)", "varyant": "kapali"},
    "gremese_eski": {"urun_kodu": "gremese_kapali", "urun_adi": "Gremse Altın (Kapalı)", "varyant": "kapali"},
    "18_ayar": {"urun_kodu": "22_ayar_iscilik", "urun_adi": "22 Ayar İşçilik"},
    "22_ayar_sarnel": {"urun_kodu": "22_ayar_sarnel", "urun_adi": "22 Ayar Şarnel"},
    "22_ayar": {"urun_kodu": "22_ayar_bilezik", "urun_adi": "22 Ayar Bilezik"},
    "21_ayar_altin": {"urun_kodu": "21_ayar_altin", "urun_adi": "21 Ayar Altın"},
    "14_ayar": {"urun_kodu": "14_ayar_iscilik", "urun_adi": "14 Ayar İşçilik"},
    "22_ayar_1gr": {"urun_kodu": "22_ayar_1gr", "urun_adi": "22 Ayar 1 Gram"},
    "24_ayar_1gr": {"urun_kodu": "24_ayar_1gr", "urun_adi": "24 Ayar 1 Gram"},
    "kulce_altin": {"urun_kodu": "kulce_altin", "urun_adi": "Külçe Altın"},
}

MARKET_PRODUCTS: dict[str, dict[str, str]] = {
    "dolar": {"varlik_kodu": "USD", "varlik_adi": "Amerikan Doları", "varlik_turu": "doviz", "para_birimi": "TRY"},
    "euro": {"varlik_kodu": "EUR", "varlik_adi": "Euro", "varlik_turu": "doviz", "para_birimi": "TRY"},
    "ons_usd": {"varlik_kodu": "XAU_ONS_USD", "varlik_adi": "Altın Ons", "varlik_turu": "ons", "para_birimi": "USD"},
}


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if API_KEY and not secrets.compare_digest(x_api_key or "", API_KEY):
        raise HTTPException(status_code=401, detail="Geçersiz API key")


def fetch_prices_from_source() -> dict[str, Any]:
    request = urllib.request.Request(
        f"{SOURCE_URL}?t={int(time.time() * 1000)}",
        headers=REQUEST_HEADERS,
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))
    if data.get("hata"):
        raise RuntimeError(data.get("mesaj") or "Kaynak servis hata döndürdü.")
    return {"source": SOURCE_URL, "fetched_at": int(time.time()), "fiyatlar": data.get("fiyatlar", [])}


def read_cache() -> dict[str, Any] | None:
    if not CACHE_FILE.exists():
        return None
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_cache(payload: dict[str, Any]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary_file = CACHE_FILE.with_suffix(f"{CACHE_FILE.suffix}.tmp")
    temporary_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary_file.replace(CACHE_FILE)


@contextmanager
def cache_lock():
    lock_file = CACHE_FILE.with_suffix(f"{CACHE_FILE.suffix}.lock")
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with lock_file.open("w") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def get_prices() -> dict[str, Any]:
    with cache_lock():
        cached = read_cache()
        if cached and isinstance(cached.get("fetched_at"), int) and time.time() - cached["fetched_at"] < CACHE_TTL_SECONDS:
            return {**cached, "cache": "hit"}
        try:
            fresh = fetch_prices_from_source()
        except Exception as exc:
            if cached:
                return {**cached, "cache": "stale", "warning": str(exc)}
            raise RuntimeError(str(exc)) from exc
        write_cache(fresh)
        return {**fresh, "cache": "miss"}


def protected_prices() -> dict[str, Any]:
    try:
        return get_prices()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"Fiyatlar alınamadı: {exc}") from exc


def metadata(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "source": payload.get("source"),
        "fetched_at": payload.get("fetched_at"),
        "cache": payload.get("cache"),
        "warning": payload.get("warning"),
    }


def normalize_gold(payload: dict[str, Any]) -> list[dict[str, Any]]:
    products = []
    for raw in payload.get("fiyatlar", []):
        raw_code = str(raw.get("kod", ""))
        definition = GOLD_PRODUCTS.get(raw_code)
        if definition:
            products.append({
                **definition,
                "kaynak_kodu": raw_code,
                "kategori": raw.get("kategori"),
                "alis": raw.get("alis"),
                "satis": raw.get("satis"),
                "para_birimi": "TRY",
                "degisim_yuzde": raw.get("degisim_yuzde"),
            })
    return products


def normalize_markets(payload: dict[str, Any]) -> list[dict[str, Any]]:
    products = []
    for raw in payload.get("fiyatlar", []):
        raw_code = str(raw.get("kod", ""))
        definition = MARKET_PRODUCTS.get(raw_code)
        if definition:
            products.append({
                **definition,
                "kaynak_kodu": raw_code,
                "alis": raw.get("alis"),
                "satis": raw.get("satis"),
                "degisim_yuzde": raw.get("degisim_yuzde"),
            })
    return products


@app.get("/")
def root() -> dict[str, str]:
    return {"legacy": "/fiyatlar", "altin": "/v1/altin", "doviz": "/v1/doviz", "ons": "/v1/ons", "piyasa": "/v1/piyasa", "health": "/health"}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/fiyatlar")
def legacy_prices(x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    return protected_prices()


@app.get("/v1/altin")
def gold_prices(x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    payload = protected_prices()
    return {**metadata(payload), "urunler": normalize_gold(payload)}


@app.get("/v1/altin/{product_code}")
def gold_price(product_code: str, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    payload = gold_prices(x_api_key)
    product = next((item for item in payload["urunler"] if item["urun_kodu"] == product_code), None)
    if not product:
        raise HTTPException(status_code=404, detail="Altın ürünü bulunamadı")
    return {**metadata(payload), "urun": product}


@app.get("/v1/doviz")
def currency_prices(x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    payload = protected_prices()
    currencies = [item for item in normalize_markets(payload) if item["varlik_turu"] == "doviz"]
    return {**metadata(payload), "varliklar": currencies}


@app.get("/v1/doviz/{currency_code}")
def currency_price(currency_code: str, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    payload = currency_prices(x_api_key)
    asset = next((item for item in payload["varliklar"] if item["varlik_kodu"] == currency_code.upper()), None)
    if not asset:
        raise HTTPException(status_code=404, detail="Döviz kuru bulunamadı")
    return {**metadata(payload), "varlik": asset}


@app.get("/v1/ons")
def ounce_price(x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    payload = protected_prices()
    asset = next((item for item in normalize_markets(payload) if item["varlik_turu"] == "ons"), None)
    if not asset:
        raise HTTPException(status_code=404, detail="Altın ons fiyatı bulunamadı")
    return {**metadata(payload), "varlik": asset}


@app.get("/v1/piyasa")
def market_prices(x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    payload = protected_prices()
    return {**metadata(payload), "altin": normalize_gold(payload), "doviz_ve_ons": normalize_markets(payload)}
