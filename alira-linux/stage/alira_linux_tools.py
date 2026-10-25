# -*- coding: utf-8 -*-
"""
ALIRA Linux tools — Windows-only tools ki jagah Linux ke asli commands.

install(tools_module) TOOL_MAP mein Linux versions daalta hai. Jo feature Linux par nahi ban sakta wo jhoothi
"✅ done" ki jagah saaf ❌ batata hai.
"""
import asyncio
import difflib
import glob
import os
import re
import shlex
import shutil
import subprocess
import time
import webbrowser
from pathlib import Path

_APP_DIRS = ["/usr/share/applications", "/usr/local/share/applications", str(Path.home() / ".local/share/applications"),
             "/var/lib/flatpak/exports/share/applications", str(Path.home() / ".local/share/flatpak/exports/share/applications"),
             "/var/lib/snapd/desktop/applications"]
_index = None


def _sh(cmd, timeout=15, stdin=None):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, input=stdin)
        return p.returncode == 0, (p.stdout or p.stderr or "").strip()
    except FileNotFoundError:
        return False, f"`{cmd[0]}` install nahi hai"
    except Exception as e:
        return False, str(e)


def _need(exe, pkg=None):
    return f"❌ `{exe}` install nahi hai — `sudo apt install {pkg or exe}` chalao."


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _build_index():
    apps = {}
    for d in _APP_DIRS:
        for f in glob.glob(os.path.join(d, "*.desktop")):
            try:
                txt = Path(f).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            if re.search(r"^(NoDisplay|Hidden)\s*=\s*true", txt, re.M | re.I):
                continue
            g = lambda k: (re.search(rf"^{k}\s*=\s*(.+)$", txt, re.M) or [None, ""])[1].strip()
            name, exe = g("Name"), g("Exec")
            if name and exe:
                apps[name] = {"id": Path(f).stem, "exec": exe, "generic": g("GenericName"), "keywords": g("Keywords"), "file": f}
    return apps


def apps(refresh=False):
    global _index
    if _index is None or refresh:
        _index = _build_index()
    return _index


def find_apps(query, limit=5):
    q = _norm(query)
    scored = []
    for name, a in apps().items():
        cands = [name, a["id"], a["generic"], a["keywords"]]
        best = 0
        for c in cands:
            n = _norm(c)
            if not n:
                continue
            if n == q:
                best = 100
            elif q and (q in n or n in q) and len(q) >= 3:
                best = max(best, 88)
            else:
                best = max(best, int(difflib.SequenceMatcher(None, q, n).ratio() * 85))
        if best >= 62:
            scored.append((best, name))
    scored.sort(reverse=True)
    return scored[:limit]


def _launch_desktop(a):
    gtk = shutil.which("gtk-launch")
    if gtk:
        ok, _ = _sh([gtk, a["id"]], timeout=8)
        if ok:
            return True
    cmd = re.sub(r"%[a-zA-Z]", "", a["exec"]).strip()
    try:
        subprocess.Popen(shlex.split(cmd), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return True
    except Exception:
        return False


async def open_app(app_name: str, text: str = "") -> str:
    q = (app_name or "").strip()
    if not q:
        return "❌ App ka naam batao"
    hits = find_apps(q)
    if hits:
        name = hits[0][1]
        if _launch_desktop(apps()[name]):
            if text:
                return await _type_text(f"✅ {name} khul gaya", text)
            return f"✅ {name} khul gaya"
    exe = shutil.which(re.sub(r"\s+", "-", q.lower())) or shutil.which(q.lower().replace(" ", ""))
    if exe:
        subprocess.Popen([exe], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return f"✅ {Path(exe).name} khul gaya"
    return f"❌ '{q}' naam ka koi installed app nahi mila."


async def _type_text(prefix, text):
    await asyncio.sleep(2.5)
    if shutil.which("xdotool"):
        ok, out = await asyncio.get_event_loop().run_in_executor(None, lambda: _sh(["xdotool", "type", "--delay", "35", "--", text], timeout=120))
        return f"{prefix} aur text likh diya ✍️" if ok else f"{prefix}, par likh nahi paya: {out}"
    if shutil.which("wtype"):
        ok, out = await asyncio.get_event_loop().run_in_executor(None, lambda: _sh(["wtype", text], timeout=120))
        return f"{prefix} aur text likh diya ✍️" if ok else f"{prefix}, par likh nahi paya: {out}"
    await set_clipboard(text)
    return f"{prefix}. Text clipboard mein copy kar diya hai (Ctrl+V karo) — direct typing ke liye `sudo apt install xdotool` (X11) ya `wtype` (Wayland)."


async def open_app_and_do(app_name: str, action: str) -> str:
    return await open_app(app_name, action)


async def list_installed_apps(filter_text: str = "") -> str:
    names = sorted(apps())
    f = _norm(filter_text)
    if f:
        names = [n for n in names if f in _norm(n)]
    if not names:
        return "📦 Koi app nahi mila"
    return f"📦 {len(names)} apps: " + ", ".join(names[:60]) + (" ..." if len(names) > 60 else "")


async def refresh_app_list() -> str:
    return f"✅ App list refresh ho gayi — {len(apps(True))} apps"


async def play_on_spotify(query: str, kind: str = "auto") -> str:
    q = (query or "").strip()
    if not q:
        return "❌ Gaane ka naam batao"
    if shutil.which("spotify") or any("spotify" in n.lower() for n in apps()):
        subprocess.Popen(["xdg-open", "spotify:search:" + q.replace(" ", "%20")], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return (f"✅ Spotify mein '{q}' search khol diya. Linux par gaana apne aap play nahi hota — "
                f"result par click karo (ya bolo 'play' agar playerctl installed hai).")
    webbrowser.open("https://open.spotify.com/search/" + q.replace(" ", "%20"))
    return f"✅ Spotify Web mein '{q}' search khol diya (Spotify app installed nahi hai)."


async def control_media(action: str) -> str:
    m = {"play_pause": "play-pause", "play": "play", "pause": "pause", "next": "next", "previous": "previous", "stop": "stop"}
    a = m.get((action or "").lower().replace(" ", "_"))
    if not a:
        return "❌ action: play_pause, next, previous, stop"
    if not shutil.which("playerctl"):
        return _need("playerctl")
    ok, out = _sh(["playerctl", a])
    return f"✅ Media: {a}" if ok else f"❌ {out or 'koi media player nahi chal raha'}"


async def system_control(command: str) -> str:
    c = (command or "").lower().strip().replace(" ", "_")
    if c in ("volume_up", "volume_down", "mute", "unmute"):
        if shutil.which("pactl"):
            arg = {"volume_up": ["set-sink-volume", "@DEFAULT_SINK@", "+10%"], "volume_down": ["set-sink-volume", "@DEFAULT_SINK@", "-10%"],
                   "mute": ["set-sink-mute", "@DEFAULT_SINK@", "1"], "unmute": ["set-sink-mute", "@DEFAULT_SINK@", "0"]}[c]
            ok, out = _sh(["pactl"] + arg)
        elif shutil.which("amixer"):
            ok, out = _sh(["amixer", "-q", "sset", "Master", {"volume_up": "10%+", "volume_down": "10%-", "mute": "mute", "unmute": "unmute"}[c]])
        else:
            return _need("pactl", "pulseaudio-utils")
        return f"✅ {c}" if ok else f"❌ {out}"
    if c == "lock":
        for cmd in (["loginctl", "lock-session"], ["xdg-screensaver", "lock"], ["gnome-screensaver-command", "-l"]):
            if shutil.which(cmd[0]) and _sh(cmd)[0]:
                return "✅ Screen lock ho gayi"
        return "❌ Lock nahi ho paya"
    if c == "sleep":
        ok, out = _sh(["systemctl", "suspend"])
        return "✅ Sleep" if ok else f"❌ {out}"
    if c in ("shutdown", "restart"):
        ok, out = _sh(["systemctl", "poweroff" if c == "shutdown" else "reboot"])
        return f"✅ {c} ho raha hai" if ok else f"❌ {out}"
    if c == "abort_shutdown":
        return "❌ Linux par abort_shutdown available nahi (systemctl poweroff turant chalta hai)"
    return f"❌ Command samajh nahi aayi: {command}"


async def adjust_brightness(action: str = "get", level: int = 0) -> str:
    if not shutil.which("brightnessctl"):
        return _need("brightnessctl")
    a = (action or "get").lower()
    if a == "get":
        ok, cur = _sh(["brightnessctl", "-m"])
        return f"💡 Brightness: {cur.split(',')[3] if ok and cur.count(',') >= 3 else cur}"
    arg = {"set": f"{int(level)}%", "increase": f"+{int(level or 10)}%", "decrease": f"{int(level or 10)}%-"}.get(a)
    if not arg:
        return "❌ action: get/set/increase/decrease"
    ok, out = _sh(["brightnessctl", "set", arg])
    return "✅ Brightness badal di" if ok else f"❌ {out}"


async def get_battery_status() -> str:
    for d in glob.glob("/sys/class/power_supply/BAT*"):
        try:
            return f"🔋 Battery {open(d + '/capacity').read().strip()}% — {open(d + '/status').read().strip()}"
        except Exception:
            pass
    return "🔌 Battery nahi mili (desktop/PC hoga)"


async def get_clipboard() -> str:
    for c in (["wl-paste"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "-b", "-o"]):
        if shutil.which(c[0]):
            ok, out = _sh(c)
            return out if ok and out else "(clipboard khali hai)"
    return _need("xclip")


def _clip_set_sync(text):
    """xclip/wl-copy selection serve karne ke liye zinda rehte hain — subprocess.run unka intezaar karke 15s hang karta tha."""
    for c in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "-b", "-i"]):
        if shutil.which(c[0]):
            try:
                p = subprocess.Popen(c, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                p.stdin.write(text.encode("utf-8")); p.stdin.close()
                return True, ""
            except Exception as e:
                return False, str(e)
    return False, "nahi"


async def set_clipboard(text: str) -> str:
    ok, err = _clip_set_sync(text)
    if ok:
        return "✅ Clipboard mein copy ho gaya"
    return _need("xclip") if err == "nahi" else f"❌ {err}"


async def send_notification(title: str, message: str) -> str:
    if not shutil.which("notify-send"):
        return _need("notify-send", "libnotify-bin")
    ok, out = _sh(["notify-send", title, message])
    return "✅ Notification bhej di" if ok else f"❌ {out}"


async def open_folder(folder_name: str) -> str:
    n = (folder_name or "").strip().lower()
    known = {"downloads": "Downloads", "documents": "Documents", "desktop": "Desktop", "pictures": "Pictures", "music": "Music",
             "videos": "Videos", "home": ""}
    p = Path.home() / known[n] if n in known else Path(os.path.expanduser(folder_name))
    if not p.exists():
        return f"❌ Folder nahi mila: {folder_name}"
    subprocess.Popen(["xdg-open", str(p)], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    return f"✅ {p} khol diya"


async def get_open_windows() -> str:
    if not shutil.which("wmctrl"):
        return _need("wmctrl")
    ok, out = _sh(["wmctrl", "-l"])
    if not ok:
        return f"❌ {out}"
    rows = [l.split(None, 3)[-1] for l in out.splitlines() if len(l.split(None, 3)) == 4]
    return "🪟 Open windows:\n" + "\n".join(f"- {r}" for r in rows[:40])


async def manage_window(title: str, action: str) -> str:
    if not shutil.which("wmctrl"):
        return _need("wmctrl")
    a = (action or "").lower()
    flags = {"activate": ["-a", title], "close": ["-c", title], "maximize": ["-r", title, "-b", "add,maximized_vert,maximized_horz"],
             "restore": ["-r", title, "-b", "remove,maximized_vert,maximized_horz"], "minimize": ["-r", title, "-b", "add,hidden"]}
    if a not in flags:
        return "❌ action: activate, minimize, maximize, restore, close"
    ok, out = _sh(["wmctrl"] + flags[a])
    return f"✅ {a}: {title}" if ok else f"❌ {out}"


def _gs(schema, key, val=None):
    if not shutil.which("gsettings"):
        return False, "gsettings nahi hai (GNOME desktop chahiye)"
    return _sh(["gsettings", "set" if val is not None else "get", schema, key] + ([val] if val is not None else []))


def _unsupported(label):
    async def _f(*a, **k):
        return f"❌ '{label}' abhi Linux par available nahi hai (ye feature Windows ke liye bana hai)."
    return _f


_WINDOWS_ONLY = ["start_security_mode", "stop_security_mode", "whatsapp_read_last_message", "whatsapp_reply_last", "whatsapp_wait_for_reply"]

LINUX_FUNCS = {f.__name__: f for f in (open_app, open_app_and_do, list_installed_apps, refresh_app_list, play_on_spotify, control_media,
                                      system_control, adjust_brightness, get_battery_status, get_clipboard, set_clipboard,
                                      send_notification, open_folder, get_open_windows, manage_window)}


def _threaded(fn):
    """Blocking subprocess wali tool ko alag thread mein chalao — warna asyncio loop ruk jata hai aur ALIRA ki awaaz kat-kat ke aati hai."""
    import functools

    @functools.wraps(fn)
    async def _w(*a, **k):
        return await asyncio.to_thread(lambda: asyncio.run(fn(*a, **k)))
    return _w


def install(tools):
    """tools = TABBU_modules.tools — TOOL_MAP aur declarations ko Linux ke hisaab se badlo."""
    for n in _WINDOWS_ONLY:
        if n in tools.TOOL_MAP:
            tools.TOOL_MAP[n] = _unsupported(n)
    import linux_extra
    funcs = dict(LINUX_FUNCS); funcs.update(linux_extra.FUNCS)
    tools.TOOL_MAP.update({k: _threaded(v) for k, v in funcs.items() if k in tools.TOOL_MAP})
    for d in getattr(tools, "TOOL_DECLARATIONS", []):
        if d.get("name") == "send_notification":
            d["description"] = "Desktop notification bhejo"
    return tools
