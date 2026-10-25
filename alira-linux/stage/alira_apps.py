# -*- coding: utf-8 -*-
"""
ALIRA Apps — PC par install KOI BHI app (Microsoft Store/UWP, Win32, Office, games...) dhoondho aur kholo.
Koi hardcoded naam/alias list nahi (jaise phone par Lia installed apps scan karti hai):

  Index kahan se banta hai (sab dynamic):
    1. Start Menu ki poori app list  (Get-StartApps — Store/UWP + classic dono)
    2. Start Menu .lnk shortcuts     (agar upar wali list na mile)
    3. Registry "App Paths"          (winword, chrome, vlc... exe naam se bhi khule)
  Index ~/.ALIRA_data/apps_index.json mein cache hota hai (12 ghante; background mein refresh).

  Matching: exact > saare shabd mile > naam shuru hota hai > acronym (vsc) > fuzzy (typo, Hinglish spelling).
  Kholna: pehle check — app pehle se chal rahi ho to window saamne laao, warna launch + VERIFY
          (nayi window aayi ya nahi) — jhoota "khul gaya" nahi bolta.

    import ALIRA_apps
    ALIRA_apps.open_app("spotify")      # -> {"found", "ok", "status", "name", "message", "alternatives"}
    ALIRA_apps.find_apps("vs code")     # -> [(score, entry), ...]
    ALIRA_apps.list_apps("micro")       # -> ["Microsoft Edge", ...]
"""

import ctypes
import difflib
import json
import os
import re
import subprocess
import sys
import threading
import time
import unicodedata
from pathlib import Path

try:
    from rapidfuzz import fuzz as _rf
except Exception:                      # optional — difflib fallback
    _rf = None

DATA_DIR = Path.home() / ".ALIRA_data"
INDEX_FILE = DATA_DIR / "apps_index.json"
INDEX_TTL = 12 * 3600
THRESHOLD = 74.0

_lock = threading.RLock()
_apps = []                             # [{"name", "kind", "target", "aliases": [...], "n": normalized}]
_loaded_at = 0.0
_building = False

_FILLER = {"open", "launch", "start", "run", "kholo", "khol", "kholdo", "chalao", "chalu", "karo", "kar", "do", "de",
           "app", "application", "software", "program", "please", "plz", "mere", "meri", "ko", "ka", "ki", "the",
           "mujhe", "jaldi", "zara", "ek", "pe", "par", "me", "mein", "wala", "wali"}
_GENERIC = {"microsoft", "windows", "app", "the", "for", "desktop", "free", "pro", "new", "classic"}
_JUNK = re.compile(r"(uninstall|readme|release notes|licen[sc]e|documentation|user guide|manual|website|support|"
                   r"what'?s new|eula|setup log|remove)", re.I)


# ══════════════════════════════════════════════════════════════════
# NORMALIZE
# ══════════════════════════════════════════════════════════════════
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9+#]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _acronym(n: str) -> str:
    return "".join(w[0] for w in n.split() if w)


def _query_tokens(query: str):
    qn = _norm(query)
    toks = [t for t in qn.split() if t not in _FILLER]
    return " ".join(toks), toks


# ══════════════════════════════════════════════════════════════════
# INDEX BUILD
# ══════════════════════════════════════════════════════════════════
def _ps_exe() -> str:
    p = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
    return p if os.path.exists(p) else "powershell"


_NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _start_apps():
    cmd = ("[Console]::OutputEncoding=[Text.Encoding]::UTF8;"
           "Get-StartApps | Select-Object Name,AppID | ConvertTo-Json -Compress")
    try:
        r = subprocess.run([_ps_exe(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd],
                           capture_output=True, timeout=30, creationflags=_NOWIN)
        out = r.stdout.decode("utf-8", "replace").strip()
        if not out:
            return []
        data = json.loads(out)
        if isinstance(data, dict):
            data = [data]
        return [(d.get("Name") or "", d.get("AppID") or "") for d in data if d.get("Name") and d.get("AppID")]
    except Exception as e:
        print(f"[Apps] Get-StartApps: {e}")
        return []


def _start_menu_lnks():
    roots = [Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Microsoft/Windows/Start Menu/Programs",
             Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs"]
    out = []
    for root in roots:
        if not root.exists():
            continue
        for dp, _dn, fn in os.walk(root):
            for f in fn:
                if f.lower().endswith(".lnk"):
                    out.append((Path(f).stem, str(Path(dp) / f)))
    return out


def _app_paths():
    out = []
    if sys.platform != "win32":
        return out
    try:
        import winreg
        base = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for sub in (base, base.replace("SOFTWARE", r"SOFTWARE\WOW6432Node")):
                try:
                    with winreg.OpenKey(root, sub) as k:
                        i = 0
                        while True:
                            try:
                                name = winreg.EnumKey(k, i)
                            except OSError:
                                break
                            i += 1
                            try:
                                with winreg.OpenKey(k, name) as sk:
                                    path = winreg.QueryValueEx(sk, "")[0]
                                path = (path or "").strip().strip('"')
                                if path and os.path.exists(path):
                                    out.append((Path(name).stem, path))
                            except OSError:
                                continue
                except OSError:
                    continue
    except Exception as e:
        print(f"[Apps] App Paths: {e}")
    return out


def build_index():
    """Poora index naye sire se banao (2-4 sec) aur cache karo."""
    global _apps, _loaded_at, _building
    with _lock:
        _building = True
    try:
        apps, seen = [], {}

        def add(name, kind, target, alias=None):
            n = _norm(name)
            if not n or _JUNK.search(name):
                return
            if n in seen:
                e = seen[n]
                if alias and _norm(alias) not in e["aliases"]:
                    e["aliases"].append(_norm(alias))
                return
            e = {"name": name, "kind": kind, "target": target, "aliases": [_norm(alias)] if alias else [], "n": n}
            seen[n] = e
            apps.append(e)

        for name, appid in _start_apps():
            add(name, "shell", appid)
        for name, lnk in _start_menu_lnks():
            add(name, "file", lnk)
        for stem, path in _app_paths():
            n = _norm(stem)
            hit = next((e for e in apps if n == e["n"] or n in e["aliases"]), None)
            if hit is None:
                path_toks = set(_norm(path).split())
                best, best_ov = None, 0.0
                for e in apps:
                    nt = e["n"].split()
                    if n in nt or any(t == n for t in nt):
                        ov = sum(1 for t in nt if t in path_toks) / max(1, len(nt))   # exe ke folder mein naam ke shabd kitne
                        if ov > best_ov:
                            best, best_ov = e, ov
                if best is not None and best_ov >= 0.3:
                    hit = best
            if hit:                                   # exe naam ko usi app ka alias bana do (winword -> Word)
                if n not in hit["aliases"]:
                    hit["aliases"].append(n)
            else:
                add(stem, "file", path)
        with _lock:
            _apps, _loaded_at = apps, time.time()
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            INDEX_FILE.write_text(json.dumps({"ts": _loaded_at, "apps": apps}, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            print(f"[Apps] cache save: {e}")
        print(f"[Apps] index ready: {len(apps)} apps")
        return apps
    finally:
        with _lock:
            _building = False


def _load_cache():
    global _apps, _loaded_at
    try:
        d = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
        with _lock:
            _apps, _loaded_at = d.get("apps", []), float(d.get("ts", 0))
        return bool(_apps)
    except Exception:
        return False


def ensure_index(force=False):
    """Index ready karo: cache fresh to turant; purana to use karo + background refresh; na ho to abhi banao."""
    if force:
        return build_index()
    with _lock:
        have = bool(_apps)
        fresh = have and (time.time() - _loaded_at) < INDEX_TTL
    if not have:
        _load_cache()
        with _lock:
            have = bool(_apps)
            fresh = have and (time.time() - _loaded_at) < INDEX_TTL
    if not have:
        return build_index()
    if not fresh and not _building:
        threading.Thread(target=build_index, daemon=True, name="ALIRA-apps-refresh").start()
    return _apps


def warm():
    """App start par background mein index garam karo."""
    threading.Thread(target=ensure_index, daemon=True, name="ALIRA-apps-warm").start()


# ══════════════════════════════════════════════════════════════════
# MATCHING
# ══════════════════════════════════════════════════════════════════
def _fuzzy(a: str, b: str) -> float:
    """Poore string ki similarity (typo pakadne ke liye) — partial match nahi, warna Photoshop->Photos jaisa galat app khulta hai."""
    if _rf is not None:
        return float(_rf.ratio(a, b))
    return difflib.SequenceMatcher(None, a, b).ratio() * 100.0


def _compact_forms(toks):
    """['visual','studio','code'] -> {'visualstudiocode','vstudiocode','vscode','vsc'} (shuru ke shabd initials mein)."""
    forms = set()
    for j in range(len(toks)):
        forms.add("".join(w[0] for w in toks[:j]) + "".join(toks[j:]))
    forms.add("".join(w[0] for w in toks))
    return forms


def _ordered_match(qtoks, toks) -> bool:
    """Query ka har shabd order mein candidate ke shabd ka prefix ho, ya consecutive shabdon ke initials ('vs' = visual studio)."""
    def go(qi, ti):
        if qi == len(qtoks):
            return True
        if ti >= len(toks):
            return False
        q = qtoks[qi]
        for tj in range(ti, len(toks)):
            if toks[tj].startswith(q) and go(qi + 1, tj + 1):
                return True
            k = len(q)
            if k >= 2 and tj + k <= len(toks) and "".join(w[0] for w in toks[tj:tj + k]) == q and go(qi + 1, tj + k):
                return True
        return False
    return go(0, 0)


def _score(qn: str, qtoks, e) -> float:
    best = 0.0
    qtoks = [t for t in qtoks if t not in _GENERIC] or qtoks      # "microsoft word" -> "word" bhi match kare
    for cand in [e["n"]] + e.get("aliases", []):
        if not cand:
            continue
        toks = cand.split()
        if qn == cand:
            s = 100.0
        elif qtoks and all(any(x == t or x.startswith(t) for x in toks) for t in qtoks):
            s = 95.0 - min(12.0, (len(toks) - len(qtoks)) * 2.5)
        elif cand.startswith(qn):
            s = 90.0
        elif len(qn.replace(" ", "")) >= 2 and qn.replace(" ", "") in _compact_forms(toks):
            s = 91.0                                   # vscode / vs code / vsc -> Visual Studio Code
        elif qtoks and len(toks) > 1 and _ordered_match(qtoks, toks):
            s = 89.0
        elif qn.startswith(cand) and len(qn) > len(cand):
            s = 0.0                                    # "photoshop" ne "photos" extend kiya — alag app hai
        else:
            raw = _fuzzy(qn, cand)
            s = raw * 0.95 if raw >= 82.0 else 0.0     # sirf typo-level similarity
        best = max(best, s)
    return best


def find_apps(query: str, limit: int = 5, min_score: float = THRESHOLD):
    qn, qtoks = _query_tokens(query)
    if not qn:
        return []
    apps = ensure_index()
    scored = [(_score(qn, qtoks, e), e) for e in apps]
    scored = [x for x in scored if x[0] >= min_score]
    scored.sort(key=lambda x: (-x[0], len(x[1]["name"])))
    return scored[:limit]


def list_apps(filter_text: str = ""):
    apps = ensure_index()
    f = _norm(filter_text)
    names = sorted({e["name"] for e in apps if not f or f in e["n"]}, key=str.lower)
    return names


# ══════════════════════════════════════════════════════════════════
# WINDOWS: running check / focus / launch verify
# ══════════════════════════════════════════════════════════════════
def _visible_windows():
    """[(hwnd, title, exe_stem)] — visible top-level windows."""
    out = []
    if sys.platform != "win32":
        return out
    try:
        import win32gui
        import win32process
        import psutil
    except Exception:
        return out
    names = {}

    def cb(h, _):
        try:
            if not win32gui.IsWindowVisible(h):
                return
            title = win32gui.GetWindowText(h)
            if not title:
                return
            _t, pid = win32process.GetWindowThreadProcessId(h)
            if pid not in names:
                try:
                    names[pid] = Path(psutil.Process(pid).name()).stem.lower()
                except Exception:
                    names[pid] = ""
            out.append((h, title, names[pid]))
        except Exception:
            pass

    win32gui.EnumWindows(cb, None)
    return out


def _entry_tokens(e):
    toks = [t for t in e["n"].split() if t not in _GENERIC] or e["n"].split()
    return toks


def _match_windows(e, wins):
    toks = _entry_tokens(e)
    res = []
    aliases = set(e.get("aliases", []))
    for h, title, exe in wins:
        tl = _norm(title)
        if exe and (exe in aliases or exe in toks or any(t == exe or (len(t) > 3 and t in exe) for t in toks)):
            res.append(h)
        elif all(t in tl for t in toks):
            res.append(h)
    return res


def focus_window(hwnd) -> bool:
    try:
        import win32con
        import win32gui
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
        ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)          # ALT tap — foreground lock bypass
        ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception as e:
        print(f"[Apps] focus: {e}")
        return False


def _launch(e):
    if e["kind"] == "shell":
        os.startfile("shell:AppsFolder\\" + e["target"])
    else:
        os.startfile(e["target"])


def open_app(query: str, verify_secs: float = 10.0) -> dict:
    """App dhoondho + kholo. Hamesha dict deta hai (kabhi exception nahi)."""
    res = {"found": False, "ok": False, "status": "notfound", "name": "", "message": "", "alternatives": []}
    try:
        hits = find_apps(query)
        if not hits:                                   # index purana ho sakta hai (naya app install hua) — ek baar refresh
            ensure_index(force=True)
            hits = find_apps(query)
        qn, qtoks = _query_tokens(query)
        if len(qtoks) == 1 and (not hits or hits[0][0] < 99.0):
            import shutil
            exe = shutil.which(qtoks[0]) or shutil.which(qtoks[0] + ".exe")
            if exe:                                    # PATH par exe hai (cmd, python, node...) — Start Menu na ho tab bhi
                before = {h for h, _t, _x in _visible_windows()}
                try:
                    subprocess.Popen([exe], creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if exe.lower().endswith(("cmd.exe", "powershell.exe", "python.exe", "wsl.exe")) else _NOWIN)
                    res.update(found=True, ok=True, status="launched", name=Path(exe).stem, message=f"✅ {Path(exe).stem} khul gaya")
                    return res
                except Exception:
                    pass
        if not hits and "setting" in _norm(query):
            try:                                           # "bluetooth settings" jaisi cheezein — Windows Settings app ka page
                page = {"bluetooth": "bluetooth", "wifi": "network-wifi", "wi fi": "network-wifi", "display": "display",
                        "sound": "sound", "battery": "batterysaver", "update": "windowsupdate", "privacy": "privacy",
                        "apps": "appsfeatures", "network": "network", "personalization": "personalization"}
                qn2 = _norm(query)
                uri = "ms-settings:" + next((v for k, v in page.items() if k in qn2), "")
                os.startfile(uri)
                res.update(found=True, ok=True, status="launched", name="Settings", message="✅ Settings khul gayi")
                return res
            except Exception:
                pass
        if not hits:
            close = find_apps(query, limit=3, min_score=50.0)
            res["alternatives"] = [e["name"] for _s, e in close]
            sug = f" Kya ye the: {', '.join(res['alternatives'])}?" if close else ""
            res["message"] = f"❌ '{query}' naam ka koi installed app nahi mila.{sug}"
            return res
        score, e = hits[0]
        res.update(found=True, name=e["name"])
        res["alternatives"] = [x["name"] for s, x in hits[1:4] if s >= score - 6]

        before = _visible_windows()
        running = _match_windows(e, before)
        if running:                                    # pehle se khula hai — dobara launch nahi, saamne le aao
            focus_window(running[0])
            res.update(ok=True, status="focused", hwnd=running[0], message=f"✅ {e['name']} pehle se khula tha — saamne le aaya")
            return res

        _launch(e)
        before_h = {h for h, _t, _x in before}
        end = time.time() + verify_secs
        while time.time() < end:
            time.sleep(0.4)
            now = _visible_windows()
            m = _match_windows(e, now)
            new = [h for h, _t, _x in now if h not in before_h]
            if m or (new and time.time() > end - verify_secs + 2.0):
                hwnd = (m or new)[0]
                focus_window(hwnd)
                res.update(ok=True, status="launched", hwnd=hwnd, message=f"✅ {e['name']} khul gaya")
                return res
        res.update(ok=True, status="unverified",
                   message=f"⚠️ {e['name']} chalaya par abhi window dikhi nahi (load ho raha ho sakta hai)")
        return res
    except Exception as ex:
        res.update(ok=False, status="error", message=f"❌ App kholne mein error: {ex}")
        return res


# ══════════════════════════════════════════════════════════════════
# APP MEIN TEXT LIKHNA  ("notepad kholo aur ye likho")
# ══════════════════════════════════════════════════════════════════
def _clipboard_set(text: str) -> bool:
    try:
        import win32clipboard as wc
        import win32con
        for _ in range(8):                                  # clipboard kabhi dusri app ke paas locked hota hai
            try:
                wc.OpenClipboard()
                break
            except Exception:
                time.sleep(0.1)
        else:
            return False
        try:
            wc.EmptyClipboard()
            wc.SetClipboardData(win32con.CF_UNICODETEXT, text)
        finally:
            wc.CloseClipboard()
        return True
    except Exception as e:
        print(f"[Apps] clipboard: {e}")
        return False


def _find_editor(win):
    """Active editor control (Document / Edit): pehle jis par keyboard focus ho, warna sabse bada VISIBLE.
    (Win11 Notepad mein restored/purane tabs ke hidden Document bhi tree mein hote hain — unhe nahi chunna.)"""
    cands = []
    for ct in ("Document", "Edit"):
        try:
            for e in win.descendants(control_type=ct):
                try:
                    if e.element_info.element.CurrentIsOffscreen:
                        continue
                    r = e.rectangle()
                    w, h = r.width(), r.height()
                    if w < 200 or h < 60 or not e.is_enabled():
                        continue
                    focused = bool(e.element_info.element.CurrentHasKeyboardFocus)
                    cands.append((focused, w * h, e))
                except Exception:
                    continue
        except Exception:
            continue
        if cands:
            break
    if not cands:
        return None
    cands.sort(key=lambda c: (c[0], c[1]), reverse=True)
    return cands[0][2]


def _text_of(ctrl) -> str:
    try:
        return (ctrl.window_text() or "").replace("\r\n", "\n")
    except Exception:
        return ""


# ---- live typing: har akshar ek-ek karke (Unicode — Hindi/emoji bhi), insaan jaisi speed ----
_ULONGP = ctypes.POINTER(ctypes.c_ulong)


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", _ULONGP)]


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long), ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong), ("dwExtraInfo", _ULONGP)]


class _INPUT_U(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("u", _INPUT_U)]


def _mk(vk, scan, flags):
    extra = ctypes.pointer(ctypes.c_ulong(0))
    return _INPUT(1, _INPUT_U(ki=_KEYBDINPUT(vk, scan, flags, 0, extra)))


def _send_many(inputs):
    """Saare events ek hi SendInput call mein (beech mein koi aur input nahi aa sakta — chars aapas mein nahi ulajhte)."""
    arr = (_INPUT * len(inputs))(*inputs)
    ctypes.windll.user32.SendInput(len(inputs), arr, ctypes.sizeof(_INPUT))


def _send_vk(vk):
    _send_many([_mk(vk, 0, 0), _mk(vk, 0, 0x0002)])          # down + KEYUP


def _send_chars(chars):
    """Ek ya kuch akshar Unicode keystroke se (KEYEVENTF_UNICODE) — surrogate pair (emoji) bhi."""
    ev = []
    for ch in chars:
        data = ch.encode("utf-16-le")
        for i in range(0, len(data), 2):
            unit = int.from_bytes(data[i:i + 2], "little")
            ev.append(_mk(0, unit, 0x0004))                   # UNICODE down
            ev.append(_mk(0, unit, 0x0004 | 0x0002))          # UNICODE up
    if ev:
        _send_many(ev)


def type_humanlike(hwnd, text: str, max_secs: float = 22.0) -> None:
    """Text ko live type karo. Lamba text ho to speed badh jaati hai (kul ~max_secs mein poora)."""
    import random
    import win32gui
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    def base_delay(ch):
        d = random.uniform(0.014, 0.042)
        if ch in ".,;:!?":
            d += 0.09
        elif ch == "\n":
            d += 0.16
        elif ch == " ":
            d += 0.01
        return d

    est = sum(base_delay(c) for c in text[:2000]) * (len(text) / max(1, min(len(text), 2000)))
    scale = min(1.0, max_secs / est) if est > 0 else 1.0
    _type_loop(hwnd, text, base_delay, scale)


def _type_loop(hwnd, text, base_delay, scale):
    import win32gui
    group = 1 if scale >= 0.7 else (2 if scale >= 0.4 else 3)      # lamba text: chhote groups (speed); chhota: ek-ek akshar
    i, n = 0, len(text)
    while i < n:
        if i % 25 < group and hwnd and win32gui.GetForegroundWindow() != hwnd:
            for _ in range(4):                               # focus gaya to wapas lao — na mile to typing ROKO (galat window mein na likhe)
                focus_window(hwnd)
                time.sleep(0.2)
                if win32gui.GetForegroundWindow() == hwnd:
                    break
            else:
                raise RuntimeError("app window foreground mein nahi hai — typing roki")
        ch = text[i]
        if ch == "\n":
            _send_vk(0x0D)
            i += 1
            delay = base_delay(ch)
        elif ch == "\t":
            _send_vk(0x09)
            i += 1
            delay = base_delay(ch)
        else:
            j = i
            while j < n and j - i < group and text[j] not in "\n\t":
                j += 1
            _send_chars(text[i:j])
            delay = sum(base_delay(c) for c in text[i:j])
            i = j
        time.sleep(max(0.006, delay * scale))


def _base_delay(ch):
    import random
    d = random.uniform(0.014, 0.042)
    if ch in ".,;:!?":
        d += 0.09
    elif ch == "\n":
        d += 0.16
    elif ch == " ":
        d += 0.01
    return d


def type_wmchar(h_edit: int, text: str, max_secs: float = 22.0, cur_nonempty: bool = False) -> None:
    """Editor ke apne window handle par WM_CHAR (SendMessage = synchronous): har akshar app process kare tabhi agla jaata hai —
    keystroke queue ki race/corruption nahi, aur app ka foreground hona zaroori nahi. Live typing animation wahi dikhti hai."""
    user32 = ctypes.windll.user32
    user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]
    user32.SendMessageW.restype = ctypes.c_ssize_t
    WM_CHAR, EM_SETSEL = 0x0102, 0x00B1
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    est = sum(_base_delay(c) for c in text[:2000]) * (len(text) / max(1, min(len(text), 2000)))
    scale = min(1.0, max_secs / est) if est > 0 else 1.0
    user32.SendMessageW(h_edit, EM_SETSEL, ctypes.c_size_t(-1).value, -1)          # caret document ke end par
    if cur_nonempty:
        user32.SendMessageW(h_edit, WM_CHAR, 13, 0)                                 # purane text ke baad nayi line
    for ch in text:
        code = 13 if ch == "\n" else ord(ch)
        if code > 0xFFFF:                                                           # emoji: surrogate pair
            data = ch.encode("utf-16-le")
            for k in range(0, len(data), 2):
                user32.SendMessageW(h_edit, WM_CHAR, int.from_bytes(data[k:k + 2], "little"), 0)
        else:
            user32.SendMessageW(h_edit, WM_CHAR, code, 0)
        time.sleep(max(0.004, _base_delay(ch) * scale))


def write_text(query: str, text: str, wait: float = 15.0, animate: bool = True) -> dict:
    """App kholo (ya saamne lao) aur usme `text` likho — verify karke batata hai ki sach mein likha ya nahi.
    Pehle UI Automation se seedha editor mein set (focus/clipboard par nirbhar nahi), warna paste fallback."""
    r = open_app(query)
    if not r.get("found") or not r.get("ok") or not (text or "").strip():
        return r
    out = dict(r)
    com = False
    try:
        try:
            import comtypes
            comtypes.CoInitialize()
            com = True
        except Exception:
            pass
        from pywinauto import Desktop
        import win32gui

        hwnd = r.get("hwnd")
        end = time.time() + wait
        win = ctrl = None
        while time.time() < end:                              # app ka editor ready hone tak ruko (fresh launch slow ho sakta hai)
            if not hwnd or not win32gui.IsWindow(hwnd):
                hit = [e for e in ensure_index() if e["name"] == r["name"]]
                ws = _match_windows(hit[0], _visible_windows()) if hit else []
                hwnd = ws[0] if ws else None
            if hwnd:
                win = Desktop(backend="uia").window(handle=hwnd)
                ctrl = _find_editor(win)
                if ctrl is not None:
                    break
            time.sleep(0.5)
        if ctrl is None:
            out.update(ok=False, status="no_editor",
                       message=f"⚠️ {r['name']} khul gaya par usme likhne ki jagah (editor) nahi mili — ye app text-editor nahi lagta.")
            return out

        focus_window(hwnd)
        cur = _text_of(ctrl)
        if cur.strip() and "notepad" in _norm(r["name"]):     # Notepad mein purana text ho to naya tab — kisi ka document na bigde
            try:
                import pyautogui
                pyautogui.hotkey("ctrl", "n")
                time.sleep(0.9)
                ctrl = _find_editor(win) or ctrl
                cur = _text_of(ctrl)
            except Exception:
                pass
        new_val = (cur + ("\n" if cur and not cur.endswith("\n") else "") + text)

        def _squash(x):                                       # Unicode-safe (Hindi/emoji) — sirf whitespace hata ke compare
            return re.sub(r"\s+", "", x or "").casefold()

        def _verify():
            want = _squash(text)
            if not want:
                return False
            if want in _squash(_text_of(ctrl)):                    # tez raasta
                return True
            c = _find_editor(win)                                  # warna fresh active editor (purana UIA element stale ho sakta hai)
            return c is not None and want in _squash(_text_of(c))

        # 0a) LIVE TYPING via WM_CHAR (editor ke HWND par, synchronous) — sabse bharosemand
        msg_tried = False
        if animate:
            try:
                h_edit = int(getattr(ctrl, "handle", 0) or 0)
            except Exception:
                h_edit = 0
            if h_edit:
                msg_tried = True
                try:
                    type_wmchar(h_edit, text, cur_nonempty=bool(cur.strip()))
                    vend = time.time() + min(14.0, 3.0 + len(text) / 90.0)
                    while time.time() < vend:
                        if _verify():
                            break
                        time.sleep(0.4)
                    if _verify():
                        out.update(ok=True, status="written", message=f"✍️ {r['name']} mein type kar diya ({len(text)} akshar)")
                        return out
                    print("[Apps] WM_CHAR typing verify fail — UIA se theek kar raha hoon")
                    if os.environ.get("ALIRA_DEBUG"):
                        c2 = _find_editor(win)
                        print("[Apps][debug] expected:", repr(text[:60]))
                        print("[Apps][debug] got     :", repr(_text_of(c2)[:80]) if c2 is not None else None)
                except Exception as e:
                    print(f"[Apps] WM_CHAR typing: {e}")

        # 0b) LIVE TYPING via SendInput — jab editor ka apna HWND na ho (WM_CHAR try na hua ho tabhi)
        if animate and not msg_tried:
            try:
                for _ in range(8):                                  # pehle pakka karo ki app hi foreground mein hai
                    focus_window(hwnd)
                    time.sleep(0.25)
                    if win32gui.GetForegroundWindow() == hwnd:
                        break
                else:
                    raise RuntimeError("app foreground mein nahi aayi")
                try:
                    ctrl.set_focus()
                except Exception:
                    pass
                import pyautogui
                pyautogui.hotkey("ctrl", "end")                     # caret document ke end par
                time.sleep(0.15)
                if cur.strip():                                     # purane text ke baad nayi line se
                    _send_vk(0x0D)
                type_humanlike(hwnd, text)
                vend = time.time() + min(14.0, 3.0 + len(text) / 90.0)    # app ko keystroke queue process karne do (lamba text)
                while time.time() < vend:
                    time.sleep(0.4)
                    if _verify():
                        break
                if _verify():
                    out.update(ok=True, status="written", message=f"✍️ {r['name']} mein type kar diya ({len(text)} akshar)")
                    return out
                print("[Apps] live typing verify fail — UIA se theek kar raha hoon")
                if os.environ.get("ALIRA_DEBUG"):
                    c2 = _find_editor(win)
                    print("[Apps][debug] expected:", repr(text[:60]))
                    print("[Apps][debug] got     :", repr(_text_of(c2)[:80]) if c2 is not None else None)
            except Exception as e:
                print(f"[Apps] live typing: {e}")

        # 1) UI Automation — seedha value set (typing fail ho to repair: poora content replace, duplicate nahi)
        try:
            try:
                ctrl.iface_value.SetValue(new_val)
            except Exception:
                ctrl.set_edit_text(new_val)
            time.sleep(0.4)
            if _verify():
                out.update(ok=True, status="written", message=f"✍️ {r['name']} mein likh diya ({len(text)} akshar)")
                return out
        except Exception as e:
            print(f"[Apps] UIA set: {e}")

        # 2) fallback — clipboard paste (window focused check ke saath)
        import pyautogui
        if _clipboard_set(text):
            for _ in range(3):
                focus_window(hwnd)
                time.sleep(0.4)
                try:
                    ctrl.set_focus()
                except Exception:
                    pass
                pyautogui.hotkey("ctrl", "end")
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.7)
                if _verify():
                    out.update(ok=True, status="written", message=f"✍️ {r['name']} mein likh diya ({len(text)} akshar)")
                    return out
        out.update(ok=False, status="not_written",
                   message=f"⚠️ {r['name']} khul gaya par text likha nahi ja saka (app text-input allow nahi kar rahi?)")
        return out
    except Exception as e:
        out.update(ok=False, status="error", message=f"❌ Likhne mein error: {type(e).__name__}: {e}")
        return out
    finally:
        if com:
            try:
                import comtypes
                comtypes.CoUninitialize()
            except Exception:
                pass


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "spotify"
    print(open_app(q))
