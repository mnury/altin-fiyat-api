from __future__ import annotations

import json
import os
import secrets
import time
import urllib.request
from pathlib import Path
from threading import Lock
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

app = FastAPI(title="Altin ve Doviz Fiyat API", version="1.0.0")
cache_lock = Lock()


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if API_KEY and not secrets.compare_digest(x_api_key or "", API_KEY):
        raise HTTPException(status_code=401, detail="Gecersiz API key")


def fetch_prices_from_source() -> dict[str, Any]:
    url = f"{SOURCE_URL}?t={int(time.time() * 1000)}"
    req = urllib.request.Request(url, headers=REQUEST_HEADERS)

    with urllib.request.urlopen(req, timeout=15) as response:
        data = json.loads(response.read().decode("utf-8"))

    if data.get("hata"):
        message = data.get("mesaj") or "Kaynak servis hata dondu."
        raise RuntimeError(message)

    return {
        "source": SOURCE_URL,
        "fetched_at": int(time.time()),
        "fiyatlar": data.get("fiyatlar", []),
    }


def read_cache() -> dict[str, Any] | None:
    if not CACHE_FILE.exists():
        return None

    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_cache(payload: dict[str, Any]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def is_cache_fresh(payload: dict[str, Any]) -> bool:
    fetched_at = payload.get("fetched_at")
    return isinstance(fetched_at, int) and time.time() - fetched_at < CACHE_TTL_SECONDS


def get_prices() -> dict[str, Any]:
    with cache_lock:
        cached = read_cache()
        if cached and is_cache_fresh(cached):
            return {**cached, "cache": "hit"}

        try:
            fresh = fetch_prices_from_source()
        except Exception as exc:
            if cached:
                return {**cached, "cache": "stale", "warning": str(exc)}
            raise RuntimeError(str(exc)) from exc

        write_cache(fresh)
        return {**fresh, "cache": "miss"}


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": "Altin ve doviz fiyat API",
        "prices_url": "/fiyatlar",
        "health_url": "/health",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/fiyatlar")
def fiyatlar(x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)

    try:
        return get_prices()
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=f"Fiyatlar alinamadi: {exc}") from exc

