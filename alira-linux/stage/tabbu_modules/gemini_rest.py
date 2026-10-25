# -*- coding: utf-8 -*-
"""
Gemini REST helper — model fallback ke saath.

Free-tier par gemini-2.5-flash ki quota (20 req/day) jaldi khatam ho jaati hai (429), aur
2.0/1.5/2.5-pro/2.5-flash-lite naye keys ke liye retire (404) ho chuke hain. Is liye har text
call chain me chalti hai: 429/404 => agla model, 503 => ek retry phir agla.
Client-safe: sirf stdlib (urllib) use hota hai.
"""

import json, os, time
import urllib.request, urllib.error
from pathlib import Path

CHAIN = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-flash-latest",
]
_BAD = set()          # is process me 429/404 dene wale models — dobara try nahi


class GeminiError(Exception):
    pass


def get_api_key():
    k = os.getenv("GEMINI_API_KEY", "")
    if k:
        return k
    try:
        cfg = json.loads((Path.home() / ".TABBU" / "config.json").read_text(encoding="utf-8"))
        return cfg.get("api_key") or cfg.get("gemini_api_key") or ""
    except Exception:
        return ""


def generate(payload, api_key=None, timeout=60, models=None):
    """POST generateContent with fallback. Returns (response_json, model_used)."""
    key = api_key or get_api_key()
    if not key:
        raise GeminiError("API key set nahi hai")
    body = json.dumps(payload).encode()
    chain = list(models or CHAIN)
    order = [m for m in chain if m not in _BAD] or chain
    last = None
    for m in order:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=timeout) as r:
                    return json.loads(r.read()), m
            except urllib.error.HTTPError as e:
                txt = e.read().decode("utf-8", "replace")
                last = GeminiError(f"HTTP {e.code} ({m}): {txt[:200]}")
                if e.code == 503 and attempt == 0:
                    time.sleep(1.5); continue
                if e.code in (429, 404):
                    _BAD.add(m)
                if e.code not in (429, 404, 503, 500):
                    raise last
                break
            except (TimeoutError, OSError) as e:      # socket timeout / network blip
                last = GeminiError(f"{type(e).__name__}: {e}")
                if attempt == 0:
                    continue
                break
    raise last or GeminiError("koi Gemini model available nahi")


def text_of(data):
    try:
        parts = data["candidates"][0]["content"]["parts"]
        return " ".join(p.get("text", "") for p in parts).strip()
    except Exception:
        return ""


class _Resp:
    def __init__(self, text):
        self.text = text


class FallbackModel:
    """genai.GenerativeModel jaisa chhota shim: generate_content(prompt, generation_config=...) -> .text"""
    def __init__(self, api_key=None):
        self._key = api_key

    def generate_content(self, prompt, generation_config=None):
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        gc = generation_config
        if gc:
            get = (lambda k: gc.get(k)) if isinstance(gc, dict) else (lambda k: getattr(gc, k, None))
            cfg = {}
            if get("temperature") is not None: cfg["temperature"] = get("temperature")
            if get("max_output_tokens") is not None: cfg["maxOutputTokens"] = get("max_output_tokens")
            if cfg: payload["generationConfig"] = cfg
        data, _ = generate(payload, self._key, timeout=90)
        return _Resp(text_of(data))
