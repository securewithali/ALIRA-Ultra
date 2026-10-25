# -*- coding: utf-8 -*-
"""
ALIRA Spotify — Spotify desktop app (Microsoft Store ya normal) par gaana SACH MEIN chalao.
Koi API key / login / hardcoded song-ID nahi.

Kaise:
  1. `spotify:search:<query>` URI kholo  -> app khud khul jaati hai (ya chalti hui mein search aa jaata hai)
  2. Windows UI Automation se search result ka "Play <gaana>" button dhoondho
     (Spotify/Chromium ko screen-reader flag se accessibility tree banane ko kaha jaata hai — kaam ke baad flag wapas)
  3. Best match (pehle gaane, warna top result — artist/album) ka Play button dabao
  4. Window title se VERIFY ("Artist - Gaana" ban gaya?) — jhoota "chal raha hai" nahi bolta

    import ALIRA_spotify
    ALIRA_spotify.play("tum hi ho arijit singh")  -> {"ok": True, "message": "...", "title": "Arijit Singh - Tum Hi Ho"}
"""

import ctypes
import difflib
import os
import re
import sys
import threading
import time
from pathlib import Path
from urllib.parse import quote

try:
    from rapidfuzz import fuzz as _rf
except Exception:
    _rf = None

_lock = threading.Lock()
SPI_GETSCREENREADER, SPI_SETSCREENREADER = 0x0046, 0x0047

_FILLER = {"spotify", "spotifi", "pe", "par", "pr", "me", "mein", "play", "chalao", "chalado", "chala", "bajao", "baja",
           "bajado", "lagao", "laga", "gaana", "gana", "gaane", "gane", "song", "songs", "music", "karo", "kar", "do", "de",
           "mere", "meri", "ka", "ki", "ke", "wala", "wali", "sunao", "suna", "please", "plz", "ek", "the", "a", "on", "app"}


def clean_query(q: str) -> str:
    words = re.sub(r"[^\w\s'&.-]", " ", q or "", flags=re.U).split()
    kept = [w for w in words if w.lower() not in _FILLER]
    return " ".join(kept).strip() or (q or "").strip()


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (s or "").lower())).strip()


def _sim(a: str, b: str) -> float:
    a, b = _norm(a), _norm(b)
    if not a or not b:
        return 0.0
    if _rf is not None:
        return float(_rf.token_set_ratio(a, b))
    return difflib.SequenceMatcher(None, a, b).ratio() * 100.0


# ── accessibility flag (Chromium ko tree banane ke liye) ─────────
# Flag ON hone par Spotify ka tree banne mein 2-4 sec lagte hain — isliye flag turant wapas nahi karte:
# 45 sec idle rehne par hi purani value restore hoti hai (agle gaane par tez).
_sr_state = {"old": None, "timer": None, "on": False}
_SR_KEEPALIVE = 45.0


def _sr_restore():
    with _sr_lock:
        if not _sr_state["on"]:
            return
        _sr_state["on"] = False
        try:
            if _sr_state["old"] is False:
                ctypes.windll.user32.SystemParametersInfoW(SPI_SETSCREENREADER, 0, None, 2)
        except Exception:
            pass


_sr_lock = threading.RLock()


class _ScreenReader:
    def __enter__(self):
        with _sr_lock:
            if _sr_state["timer"]:
                _sr_state["timer"].cancel()
            if not _sr_state["on"]:
                try:
                    v = ctypes.c_int(0)
                    if ctypes.windll.user32.SystemParametersInfoW(SPI_GETSCREENREADER, 0, ctypes.byref(v), 0):
                        _sr_state["old"] = bool(v.value)
                    ctypes.windll.user32.SystemParametersInfoW(SPI_SETSCREENREADER, 1, None, 2)
                    _sr_state["on"] = True
                except Exception:
                    pass
        return self

    def __exit__(self, *a):
        with _sr_lock:
            t = threading.Timer(_SR_KEEPALIVE, _sr_restore)
            t.daemon = True
            _sr_state["timer"] = t
            t.start()


import atexit
atexit.register(_sr_restore)                                  # app band hone par flag hamesha wapas


def _spotify_window():
    """(hwnd, title) — Spotify ki main window."""
    try:
        import win32gui, win32process, psutil
    except Exception:
        return None, ""
    found = []

    def cb(h, _):
        try:
            if win32gui.IsWindowVisible(h) and win32gui.GetClassName(h) == "Chrome_WidgetWin_1":
                t = win32gui.GetWindowText(h)
                if t:
                    _t, pid = win32process.GetWindowThreadProcessId(h)
                    if Path(psutil.Process(pid).name()).stem.lower() == "spotify":
                        found.append((h, t))
        except Exception:
            pass

    win32gui.EnumWindows(cb, None)
    return (found[0] if found else (None, ""))


def _is_playing_title(t: str) -> bool:
    t = (t or "").strip()
    return bool(t) and " - " in t and not t.lower().startswith("spotify")


_TYPE_MARK = (("playlist", "playlist"), ("album", "album"), ("single", "album"), ("ep", "album"), ("artist", "artist"),
              ("profile", "artist"), ("podcast", "podcast"), ("show", "podcast"), ("episode", "podcast"))
_VTABBUNT = {"remix", "lofi", "lo", "fi", "slowed", "reverb", "instrumental", "karaoke", "cover", "mashup", "teaser",
            "dance", "mix", "acoustic", "live", "sped", "speed", "version", "kannada", "tamil", "telugu", "malayalam",
            "bengali", "punjabi", "marathi", "gujarati", "reprise", "unplugged", "audio", "8d", "bass", "boosted"}
_IGNORE = {"from", "the", "a", "of", "feat", "ft", "original", "motion", "picture", "soundtrack", "movie"}


def _collect(win):
    """Search results ke Play buttons — [{title, el, type, pos}] (document order).
    type: track / playlist / album / artist / podcast  (row ke 'Playlist • owner' jaise marker se)."""
    items, cur = [], None
    for e in win.descendants():
        try:
            ct, n = e.element_info.control_type, e.window_text()
        except Exception:
            continue
        if not n:
            continue
        if ct == "Button" and n.startswith("Play ") and len(n) > 6 and not n.startswith("Play Now"):
            cur = {"title": n[5:].strip(), "el": e, "type": "track", "pos": len(items), "links": []}
            items.append(cur)
        elif cur is not None and ct == "Hyperlink" and n != cur["title"] and len(cur["links"]) < 6:
            cur["links"].append(n)                                # artist / album ke naam
        elif cur is not None and ct == "DataItem" and "\u2022" in n and cur["type"] == "track":
            head = n.split("\u2022")[0].strip().lower()
            for key, typ in _TYPE_MARK:
                if head == key:
                    cur["type"] = typ
                    break
    return items


def _tok(s):
    return [t for t in _norm(s).split() if t not in _IGNORE]


def _rank(query, it, kind):
    """Score (zyada = behtar). Query ke shabdon ka coverage, extra/vTABBUnt shabdon ka penalty, type preference."""
    q = set(_tok(query))
    t = _tok(it["title"])
    if not q or not t:
        return -999.0
    tset = set(t) | {w for l in it.get("links", []) for w in _tok(l)}      # title + artist/album
    cover = sum(1 for w in q if w in tset or any(x.startswith(w) or w.startswith(x) for x in tset if len(x) > 3 and len(w) > 3)) / len(q)
    extra = [w for w in t if w not in q]            # penalty sirf title ke extra shabdon par
    vTABBUnts = sum(1 for w in extra if w in _VTABBUNT)
    plain_extra = len(extra) - vTABBUnts
    sc = 100.0 * cover - 2.0 * plain_extra - 22.0 * vTABBUnts - 1.2 * it["pos"]
    typ = it["type"]
    if kind in ("song", "track"):
        sc += 0 if typ == "track" else -60
    elif kind in ("artist", "album", "playlist"):
        sc += 0 if typ == kind else -60
    else:                                              # auto: gaana > artist > album > playlist
        sc += {"track": 0, "artist": -3, "album": -12, "playlist": -18}.get(typ, -35)
    return sc


def _choose(query, items, kind):
    if not items:
        return None
    return max(items, key=lambda it: _rank(query, it, kind))


def _now_playing(win) -> str:
    try:
        for e in win.descendants(control_type="Group"):
            n = e.window_text()
            if n.startswith("Now playing:"):
                return n[len("Now playing:"):].strip()
    except Exception:
        pass
    return ""


def play(query: str, kind: str = "auto", timeout: float = 25.0) -> dict:
    """Spotify par `query` chalao. Hamesha dict: {ok, message, title}."""
    out = {"ok": False, "message": "", "title": ""}
    q = clean_query(query)
    if not q:
        out["message"] = "❌ Kaunsa gaana chalana hai? Naam batao."
        return out
    if sys.platform != "win32":
        out["message"] = "❌ Spotify control sirf Windows par."
        return out
    if not _lock.acquire(timeout=1):
        out["message"] = "⏳ Spotify ka pichla kaam chal raha hai — thodi der baad try karo."
        return out
    com = False
    try:
        try:
            import comtypes
            comtypes.CoInitialize()
            com = True
        except Exception:
            pass
        try:
            from pywinauto import Desktop
        except Exception:
            out["message"] = "❌ `pip install pywinauto` chahiye (Spotify control ke liye)."
            return out

        _h0, title_before = _spotify_window()
        try:
            os.startfile("spotify:search:" + quote(q))
        except OSError:
            out["message"] = "❌ Spotify installed nahi mila (spotify: link khul nahi raha). Microsoft Store se Spotify install karo."
            return out

        with _ScreenReader():
            end = time.time() + timeout
            hwnd, cands, stable, last_n = None, [], 0, -1
            while time.time() < end:
                time.sleep(0.6)
                hwnd, _t = _spotify_window()
                if not hwnd:
                    continue
                try:
                    win = Desktop(backend="uia").window(handle=hwnd)
                    quick = sum(1 for e in win.descendants(control_type="Button") if e.window_text().startswith("Play ") and len(e.window_text()) > 6)
                except Exception:
                    quick = 0
                if quick >= 3:
                    stable = stable + 1 if quick == last_n else 0     # results list ki ginti 2 baar ek jaisi = load ho gayi
                    last_n = quick
                    if stable >= 1 or time.time() > end - 8:
                        try:
                            cands = _collect(win)
                        except Exception:
                            cands = []
                        if any(_rank(q, c, kind) > 40 for c in cands):
                            break
                        stable = 0
            if not cands:
                out["message"] = (f"⚠️ Spotify khula par '{q}' ke search result nahi mile (login/internet check karo). "
                                  f"Search page khula hai — wahan se chala sakte ho.")
                return out
            pick = _choose(q, cands, kind)
            title, el = pick["title"], pick["el"]
            if os.environ.get("ALIRA_DEBUG"):
                for c in sorted(cands, key=lambda c: -_rank(q, c, kind))[:5]:
                    print(f"[Spotify] {_rank(q, c, kind):7.1f} {c['type']:8} {c['title'][:60]}")
            np_before = _now_playing(win)
            try:
                el.invoke()
            except Exception:
                el.click_input()
            # verify: title badla ya "Now playing" mein chuna hua gaana aaya
            vend = time.time() + 9
            now_title, np_now = "", ""
            while time.time() < vend:
                time.sleep(0.6)
                _h, now_title = _spotify_window()
                np_now = _now_playing(win)
                changed = (now_title != title_before and _is_playing_title(now_title)) or (np_now and np_now != np_before)
                matches = np_now and _sim(title, np_now) >= 70
                if changed or (matches and _is_playing_title(now_title)):
                    break
            if _is_playing_title(now_title) and (np_now != np_before or _sim(title, np_now) >= 70 or now_title != title_before):
                out.update(ok=True, title=now_title, message=f"▶️ Spotify par chal raha hai: {now_title}")
            else:
                out.update(ok=False, title=title,
                           message=f"⚠️ '{title}' ka Play dabaya par gaana shuru hota nahi dikha (ad chal raha ho sakta hai ya Spotify free limit).")
            return out
    except Exception as e:
        out["message"] = f"❌ Spotify error: {type(e).__name__}: {e}"
        return out
    finally:
        if com:
            try:
                import comtypes
                comtypes.CoUninitialize()
            except Exception:
                pass
        _lock.release()


if __name__ == "__main__":
    print(play(" ".join(sys.argv[1:]) or "tum hi ho"))
