# -*- coding: utf-8 -*-
"""Linux ports of formerly Windows-only ALIRA tools + XDG autostart. Imported by ALIRA_linux_tools."""
import asyncio
import glob
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

from ALIRA_linux_tools import _sh, _need, _gs, open_folder, open_app, manage_window


async def get_wifi_passwords() -> str:
    if not shutil.which("nmcli"):
        return _need("nmcli", "network-manager")
    ok, out = _sh(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"])
    if not ok:
        return f"❌ {out}"
    rows = []
    for line in out.splitlines():
        name, _, typ = line.rpartition(":")
        if "wireless" in typ:
            _, pw = _sh(["nmcli", "-s", "-g", "802-11-wireless-security.psk", "connection", "show", name])
            rows.append(f"📶 {name}: {pw or '(open/password nahi mila)'}")
    return "\n".join(rows) if rows else "❌ Koi saved Wi-Fi nahi mila"


async def empty_recycle_bin() -> str:
    if shutil.which("gio") and _sh(["gio", "trash", "--empty"])[0]:
        return "✅ Trash saaf ho gaya"
    n = 0
    for sub in ("files", "info"):
        for f in glob.glob(str(Path.home() / ".local/share/Trash" / sub / "*")):
            try:
                shutil.rmtree(f) if os.path.isdir(f) else os.remove(f)
                n += 1
            except Exception:
                pass
    return f"✅ Trash saaf ho gaya ({n} items)"


async def set_system_theme(mode: str) -> str:
    m = (mode or "").lower()
    if m not in ("dark", "light"):
        return "❌ mode: dark ya light"
    ok, out = _gs("org.gnome.desktop.interface", "color-scheme", "prefer-dark" if m == "dark" else "default")
    if ok:
        _gs("org.gnome.desktop.interface", "gtk-theme", "Yaru-dark" if m == "dark" else "Yaru")
    return f"✅ Theme: {m}" if ok else f"❌ {out}"


async def toggle_desktop_icons(visible: bool = None) -> str:
    for schema, key in (("org.gnome.shell.extensions.ding", "show-home"), ("org.gnome.desktop.background", "show-desktop-icons")):
        ok, cur = _gs(schema, key)
        if ok:
            new = (cur.strip() != "true") if visible is None else bool(visible)
            ok2, out = _gs(schema, key, "true" if new else "false")
            return f"✅ Desktop icons {'dikh rahe hain' if new else 'chhup gaye'}" if ok2 else f"❌ {out}"
    return "❌ Desktop icons ka setting is desktop par nahi mila"


async def change_wallpaper(image_path: str = "") -> str:
    p = os.path.expanduser(image_path or "")
    if not p:
        pics = [f for ext in ("jpg", "jpeg", "png") for f in glob.glob(str(Path.home() / "Pictures" / f"*.{ext}"))]
        if not pics:
            return "❌ image_path do (ya ~/Pictures mein koi image rakho)"
        import random
        p = random.choice(pics)
    if not os.path.isfile(p):
        return f"❌ File nahi mili: {p}"
    uri = "file://" + p
    ok, out = _gs("org.gnome.desktop.background", "picture-uri", uri)
    _gs("org.gnome.desktop.background", "picture-uri-dark", uri)
    return f"✅ Wallpaper badal diya: {os.path.basename(p)}" if ok else f"❌ {out}"


async def snap_window(direction: str) -> str:
    d = (direction or "").lower()
    if not (shutil.which("xdotool") and shutil.which("wmctrl")):
        return _need("wmctrl xdotool")
    if d == "up":
        return await manage_window(":ACTIVE:", "maximize")
    ok, geo = _sh(["xdotool", "getdisplaygeometry"])
    if not ok:
        return f"❌ {geo}"
    W, H = [int(x) for x in geo.split()]
    boxes = {"left": (0, 0, W // 2, H), "right": (W // 2, 0, W // 2, H)}
    if d not in boxes:
        return "❌ direction: left, right, up"
    x, y, w, h = boxes[d]
    _sh(["wmctrl", "-r", ":ACTIVE:", "-b", "remove,maximized_vert,maximized_horz"])
    ok, out = _sh(["wmctrl", "-r", ":ACTIVE:", "-e", f"0,{x},{y},{w},{h}"])
    return f"✅ Window snap: {d}" if ok else f"❌ {out}"


async def read_active_window() -> str:
    if not shutil.which("xdotool"):
        return _need("xdotool")
    ok, title = _sh(["xdotool", "getactivewindow", "getwindowname"])
    return f"🪟 Active window: {title}" if ok else f"❌ {title}"


async def execute_shortcut(shortcut_name: str) -> str:
    keys = {"show_desktop": "super+d", "task_view": "super", "start_menu": "super", "screenshot_tool": "Print",
            "minimize_all": "super+d", "run": "alt+F2"}
    n = (shortcut_name or "").lower()
    if n == "file_explorer":
        return await open_folder("home")
    if n == "settings":
        return await open_app("settings")
    k = keys.get(n)
    if not k:
        return f"❌ Shortcut '{shortcut_name}' Linux par nahi hai"
    if not shutil.which("xdotool"):
        return _need("xdotool")
    ok, out = _sh(["xdotool", "key", k])
    return f"✅ {shortcut_name}" if ok else f"❌ {out}"


async def clean_system() -> str:
    n = 0
    size = 0.0
    for folder in ("/tmp", str(Path.home() / ".cache/thumbnails")):
        for f in glob.glob(os.path.join(folder, "*")):
            try:
                if os.stat(f).st_uid != os.getuid() or time.time() - os.path.getmtime(f) < 3600:
                    continue                                        # sirf apni aur 1 ghante se purani files
                if os.path.isfile(f):
                    size += os.path.getsize(f) / 1e6
                    os.remove(f)
                    n += 1
                elif os.path.isdir(f) and not os.path.islink(f):
                    shutil.rmtree(f, ignore_errors=True)
                    n += 1
            except Exception:
                pass
    return f"✅ {n} purani temp items delete | ~{size:.1f} MB free"


async def zoom_screen(action: str = "in") -> str:
    a = (action or "").lower()
    off = a in ("off", "reset", "close", "out")
    ok, _ = _gs("org.gnome.desktop.a11y.applications", "screen-magnifier-enabled", "false" if off else "true")
    if not ok:
        return "❌ Screen magnifier is desktop par available nahi"
    return "✅ Screen magnifier " + ("band" if off else "chalu")


def _wa_number(contact):
    d = re.sub(r"[^\d+]", "", contact or "")
    return d.lstrip("+") if len(re.sub(r"\D", "", d)) >= 8 else ""


async def whatsapp_send_message(message: str, contact: str = "") -> str:
    from urllib.parse import quote
    num = _wa_number(contact)
    if not num:
        return ("❌ Linux par WhatsApp ke liye contact ka poora phone number (country code ke saath) chahiye, naam se nahi chal sakta. "
                "Number batao, main WhatsApp Web chat message ke saath khol dungi.")
    webbrowser.open(f"https://web.whatsapp.com/send?phone={num}&text={quote(message)}")
    return "✅ WhatsApp Web chat message ke saath khul gaya — bas Send dabao (Linux par main khud send nahi kar sakti)."


async def whatsapp_open_chat(contact: str = "") -> str:
    num = _wa_number(contact)
    webbrowser.open(f"https://web.whatsapp.com/send?phone={num}" if num else "https://web.whatsapp.com/")
    return "✅ WhatsApp Web khol diya" + ("" if num else " (naam se chat nahi khul sakti — number do)")


async def get_system_status() -> str:
    import psutil
    try:
        cpu = psutil.cpu_percent(interval=0.2)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        return (f"📊 System Status\nCPU:  {'✅' if cpu < 50 else '🟡' if cpu < 80 else '🔴'} {cpu:.0f}%\n"
                f"RAM:  {'✅' if mem.percent < 50 else '🟡' if mem.percent < 80 else '🔴'} {mem.percent:.0f}% ({mem.used/1e9:.1f}/{mem.total/1e9:.1f} GB)\n"
                f"Disk: {'✅' if disk.percent < 80 else '🟡'} {disk.percent:.0f}% ({disk.free/1e9:.1f} GB free)")
    except Exception as e:
        return f"❌ {e}"


async def take_screenshot() -> str:
    import datetime
    folder = Path.home() / "Pictures" / "Screenshots"
    folder.mkdir(parents=True, exist_ok=True)
    path = str(folder / f"Screenshot_{datetime.datetime.now():%Y-%m-%d_%H-%M-%S}.png")
    ok = False
    if os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("ALIRA_FORCE_X11"):
        for cmd in (["grim", path], ["gnome-screenshot", "-f", path], ["spectacle", "-b", "-n", "-o", path]):
            if shutil.which(cmd[0]) and _sh(cmd, timeout=15)[0] and os.path.exists(path):
                ok = True
                break
    if not ok:
        try:
            import mss
            with mss.mss() as sct:
                sct.shot(output=path)
            ok = os.path.exists(path) and os.path.getsize(path) > 0
        except Exception:
            ok = False
    if not ok and shutil.which("scrot") and _sh(["scrot", path], timeout=15)[0]:
        ok = os.path.exists(path)
    if not ok:
        return ("❌ Screenshot nahi ho paya. Wayland par `sudo apt install grim` (ya gnome-screenshot) chahiye; "
                "WSL mein sirf Linux apps ki windows hoti hain, poora Windows desktop capture nahi hota.")
    try:
        subprocess.Popen(["xdg-open", path], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception:
        pass
    return f"✅ Screenshot liya: {path}"


FUNCS = {f.__name__: f for f in (get_system_status, take_screenshot, get_wifi_passwords, empty_recycle_bin, set_system_theme, toggle_desktop_icons, change_wallpaper,
                                 snap_window, read_active_window, execute_shortcut, clean_system, zoom_screen,
                                 whatsapp_send_message, whatsapp_open_chat)}

# ── Autostart: Windows registry ki jagah ~/.config/autostart ───────
_AUTOSTART = Path.home() / ".config/autostart/ALIRA-linux.desktop"


def _exec_cmd(background=True):
    exe = shutil.which("ALIRA-linux")
    base = f'"{exe}"' if exe else f'"{sys.executable}" -m ALIRA_linux_boot'
    return base + (" --background" if background else "")


def autostart_enable(background=True):
    try:
        _AUTOSTART.parent.mkdir(parents=True, exist_ok=True)
        _AUTOSTART.write_text("[Desktop Entry]\nType=Application\nName=ALIRA\nComment=ALIRA AI Assistant\n"
                              f"Exec={_exec_cmd(background)}\nTerminal=false\nX-GNOME-Autostart-enabled=true\n", encoding="utf-8")
        return True
    except Exception as e:
        print(f"[Autostart] {e}")
        return False


def autostart_disable():
    try:
        if _AUTOSTART.exists():
            _AUTOSTART.unlink()
        return True
    except Exception as e:
        print(f"[Autostart] {e}")
        return False


def autostart_enabled():
    return _AUTOSTART.exists()


def autostart_command():
    try:
        m = re.search(r"^Exec=(.+)$", _AUTOSTART.read_text(encoding="utf-8"), re.M)
        return m.group(1) if m else None
    except Exception:
        return None


def autostart_spawn():
    try:
        subprocess.Popen(shlex.split(_exec_cmd(True)), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
        return True
    except Exception as e:
        print(f"[Autostart] spawn: {e}")
        return False


def patch_autostart(au):
    au.enable = autostart_enable
    au.disable = autostart_disable
    au.is_enabled = autostart_enabled
    au.registered_command = autostart_command
    au.launch_command = _exec_cmd
    au.spawn_background = autostart_spawn
    return au


# ── ALIRA_apps / ALIRA_actions ke Windows-launcher ki jagah Linux ────────────
def patch_apps(apps_mod, actions_mod=None):
    import threading
    import ALIRA_linux_tools as L

    def ensure_index(force=False):
        return [{"name": n, "n": L._norm(n), **a} for n, a in L.apps(bool(force)).items()]

    def warm():
        threading.Thread(target=L.apps, daemon=True).start()

    def list_apps(filter_text=""):
        f = L._norm(filter_text)
        return sorted((n for n in L.apps() if not f or f in L._norm(n)), key=str.lower)

    def open_app(query, verify_secs=10.0):
        res = {"found": False, "ok": False, "status": "notfound", "name": "", "message": "", "alternatives": []}
        try:
            hits = L.find_apps(query)
            if not hits:
                hits = (L.apps(True) and L.find_apps(query))
            if hits:
                name = hits[0][1]
                res.update(found=True, name=name, alternatives=[h[1] for h in hits[1:]])
                if L._launch_desktop(L.apps()[name]):
                    res.update(ok=True, status="launched", message=f"✅ {name} khul gaya")
                else:
                    res.update(status="failed", message=f"⚠️ {name} khul nahi paya")
                return res
            exe = shutil.which(re.sub(r"\s+", "-", (query or "").lower())) or shutil.which((query or "").lower().replace(" ", ""))
            if exe:
                subprocess.Popen([exe], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 start_new_session=True)
                res.update(found=True, ok=True, status="launched", name=os.path.basename(exe), message=f"✅ {os.path.basename(exe)} khul gaya")
        except Exception as e:
            res.update(status="error", message=f"❌ {e}")
        return res

    def write_text(query, text, wait=15.0, animate=True):
        r = open_app(query)
        if not r["ok"]:
            return r
        time.sleep(2.5)
        if shutil.which("xdotool") and _sh(["xdotool", "type", "--delay", "35", "--", text], timeout=120)[0]:
            r["message"] += " aur text likh diya ✍️"
        else:
            if shutil.which("xclip"):
                _sh(["xclip", "-selection", "clipboard"], stdin=text)
            r["message"] += " (text clipboard mein hai — Ctrl+V karo; direct typing ke liye `sudo apt install xdotool`)"
        return r

    apps_mod.ensure_index, apps_mod.warm, apps_mod.list_apps = ensure_index, warm, list_apps
    apps_mod.open_app, apps_mod.write_text = open_app, write_text
    apps_mod.find_apps = lambda q, limit=5, min_score=0: [(s, {"name": n}) for s, n in L.find_apps(q, limit)]
    if actions_mod is not None:
        def a_open(name):
            r = open_app(name)
            return (bool(r["ok"]), r["message"].replace("✅ ", "").replace("⚠️ ", "") or f"'{name}' nahi mila")
        actions_mod.open_app = a_open
    return apps_mod


# ── Overlay windows (orb / bubble / edge glow): window manager ke bina, exact position ────
def patch_overlays():
    """WSLg / kuch X11 WMs frameless Tool windows ki position ignore karte hain (orb kone mein atak jata, drag nahi hota,
    border poori screen nahi ghera). X11BypassWindowManagerHint se position/size ab bilkul app ke haath mein."""
    from PyQt5.QtCore import Qt
    bypass = Qt.X11BypassWindowManagerHint
    import ALIRA_edge_glow as eg
    eg._OVERLAY_FLAGS = eg._OVERLAY_FLAGS | bypass
    import ALIRA_float_orb as fo
    fo._OVERLAY_FLAGS = eg._OVERLAY_FLAGS
    for cls in (fo.FloatingOrb, fo.OrbBubble):
        orig = cls.__init__

        def _init(self, *a, __orig=orig, **k):
            __orig(self, *a, **k)
            self.setWindowFlags(self.windowFlags() | bypass)
        cls.__init__ = _init
    return True


def patch_ocr(adv):
    """TABBU_advanced_tools ka Tesseract dhoondhna Windows paths + `where` par tika tha — Linux par `which`."""
    def _setup():
        exe = shutil.which("tesseract")
        adv.HAS_TESS = bool(exe)
        adv._TESS_CMD = exe or ""
        return bool(exe)
    adv._setup_tesseract = _setup
    _setup()
    return adv
