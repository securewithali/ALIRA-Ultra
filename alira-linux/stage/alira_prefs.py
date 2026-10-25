# -*- coding: utf-8 -*-
"""
ALIRA prefs — ~/.TABBU/config.json mein chhoti settings padho/likho (API key wali wahi file).

    from ALIRA_prefs import get, set_
    get("float_orb_size", 96);  set_("float_orb_size", 120)

Thread-safe; file corrupt ho to defaults milte hain (kabhi crash nahi).
"""
import json
import threading
from pathlib import Path

_lock = threading.RLock()


def _path() -> Path:
    p = Path.home() / ".TABBU"
    try:
        p.mkdir(exist_ok=True)
    except Exception:
        pass
    return p / "config.json"


def _read() -> dict:
    try:
        return json.loads(_path().read_text(encoding="utf-8"))
    except Exception:
        return {}


def get(key: str, default=None):
    with _lock:
        return _read().get(key, default)


def set_(key: str, value) -> None:
    with _lock:
        cfg = _read()
        cfg[key] = value
        try:
            _path().write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[PREFS] save {key}: {e}")


def clamp(v, lo, hi):
    try:
        return max(lo, min(hi, int(v)))
    except Exception:
        return lo


def user_name() -> str:
    """User ka naam (Settings / pehli baar ke setup / voice se set kiya hua) — nahi hai to ''."""
    return str(get("user_name", "") or "").strip()


def clean_name(name: str) -> str:
    """Naam saaf karo: control chars hata ke, extra spaces ek, max 30 akshar."""
    import re
    n = re.sub(r"[\x00-\x1f\x7f]", "", str(name or ""))
    n = re.sub(r"\s+", " ", n).strip()
    return n[:30].strip()


def set_user_name(name: str) -> str:
    n = clean_name(name)
    set_("user_name", n)
    return n
