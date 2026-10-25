# -*- coding: utf-8 -*-
"""
ALIRA system actions — PC Control / Files / System Monitor pages ke liye
asli (local) kaam: volume, brightness, power, screenshot, apps, processes...
Pure Python, UI-independent. Har function fail hone par (ok, message) deta hai.
"""

import os, sys, time, shutil, subprocess, webbrowser, platform, datetime, threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

try:
    import psutil
except ImportError:   # pragma: no cover
    psutil = None

_NOWIN = getattr(subprocess, "CREATE_NO_WINDOW", 0)
HOME = Path.home()


def _run(args, timeout=15):
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout, creationflags=_NOWIN)
        return r.returncode == 0, (r.stdout or r.stderr or "").strip()
    except Exception as e:
        return False, str(e)


# ── Power ─────────────────────────────────────────────────────────
def lock_pc():
    try:
        import ctypes; ctypes.windll.user32.LockWorkStation(); return True, "PC locked"
    except Exception as e:
        return False, str(e)

def sleep_pc():
    return _run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], 5)

def restart_pc(delay=15):
    ok, m = _run(["shutdown", "/r", "/t", str(delay)]); return ok, f"Restart in {delay}s" if ok else m

def shutdown_pc(delay=15):
    ok, m = _run(["shutdown", "/s", "/t", str(delay)]); return ok, f"Shutdown in {delay}s" if ok else m

def sign_out():
    return _run(["shutdown", "/l"])

def cancel_shutdown():
    ok, m = _run(["shutdown", "/a"]); return ok, "Shutdown/restart cancelled" if ok else "Koi pending shutdown nahi hai"


# ── Volume (pycaw → fallback media keys) ──────────────────────────
# ✅ Saare slow system calls (volume COM, brightness WMI, screenshot...) ek hi background thread par
# chalte hain — UI thread block nahi hota (PC Control page pehle ~4s freeze hota tha).
_EXEC = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ALIRA-act")

def submit(fn):
    return _EXEC.submit(fn)

_tls = threading.local()      # COM endpoint thread-local (apartment rules) — thread me ek baar

def _endpoint():
    ep = getattr(_tls, "ep", None)
    if ep is None:
        try:
            import comtypes; comtypes.CoInitialize()
        except Exception:
            pass
        ep = _tls.ep = _make_endpoint()
    return ep

def _make_endpoint():
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    dev = AudioUtilities.GetSpeakers()
    ev = getattr(dev, "EndpointVolume", None)
    if ev is not None:
        return ev
    iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(iface, POINTER(IAudioEndpointVolume))

def get_volume():
    try: return int(round(_endpoint().GetMasterVolumeLevelScalar() * 100))
    except Exception: return None

def set_volume(pct):
    pct = max(0, min(100, int(pct)))
    try:
        _endpoint().SetMasterVolumeLevelScalar(pct / 100.0, None); return True, f"Volume {pct}%"
    except Exception as e:
        return False, f"Volume set nahi hui: {e}"

def is_muted():
    try: return bool(_endpoint().GetMute())
    except Exception: return None

def toggle_mute():
    try:
        ep = _endpoint(); m = not bool(ep.GetMute()); ep.SetMute(1 if m else 0, None)
        return True, "Muted" if m else "Unmuted"
    except Exception:
        return media_key("volumemute")


# ── Brightness ────────────────────────────────────────────────────
def get_brightness():
    try:
        try:
            import pythoncom; pythoncom.CoInitialize()      # WMI worker thread me
        except Exception:
            pass
        import screen_brightness_control as sbc
        v = sbc.get_brightness(); return int(v[0] if isinstance(v, (list, tuple)) else v)
    except Exception:
        return None

def set_brightness(pct):
    pct = max(0, min(100, int(pct)))
    try:
        try:
            import pythoncom; pythoncom.CoInitialize()
        except Exception:
            pass
        import screen_brightness_control as sbc
        sbc.set_brightness(pct); return True, f"Brightness {pct}%"
    except Exception as e:
        return False, f"Brightness support nahi (external monitor?): {str(e)[:60]}"


# ── Media / keys ──────────────────────────────────────────────────
def media_key(name):
    try:
        import pyautogui; pyautogui.press(name); return True, name
    except Exception as e:
        return False, str(e)


# ── Screenshot ────────────────────────────────────────────────────
SHOT_DIR = HOME / "Pictures" / "ALIRA Screenshots"

def screenshot():
    try:
        SHOT_DIR.mkdir(parents=True, exist_ok=True)
        path = SHOT_DIR / f"ALIRA_{datetime.datetime.now():%Y%m%d_%H%M%S}.png"
        from PIL import ImageGrab
        ImageGrab.grab(all_screens=True).save(path)
        return True, str(path)
    except Exception as e:
        return False, str(e)

def list_screenshots(n=12):
    if not SHOT_DIR.exists(): return []
    files = sorted(SHOT_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [str(f) for f in files[:n]]


# ── Apps / URLs / files ───────────────────────────────────────────
APP_ALIASES = {
    "notepad": "notepad.exe", "calculator": "calc.exe", "calc": "calc.exe", "paint": "mspaint.exe",
    "cmd": "cmd.exe", "terminal": "wt.exe", "powershell": "powershell.exe", "task manager": "taskmgr.exe",
    "explorer": "explorer.exe", "file explorer": "explorer.exe", "control panel": "control.exe",
    "settings": "ms-settings:", "snipping tool": "snippingtool.exe", "chrome": "chrome", "edge": "msedge",
    "firefox": "firefox", "vscode": "code", "vs code": "code", "word": "winword", "excel": "excel",
    "powerpoint": "powerpnt", "spotify": "spotify", "whatsapp": "whatsapp:", "clock": "ms-clock:",
}

def open_app(name):
    try:                                              # dynamic installed-app launcher (Store apps samet) pehle
        import alira_apps
        r = alira_apps.open_app(name)
        if r["found"]:
            return bool(r["ok"]), r["message"].replace("✅ ", "").replace("⚠️ ", "")
    except Exception as e:
        print(f"[Actions] alira_apps: {e}")
    key = (name or "").strip().lower()
    target = APP_ALIASES.get(key, key)
    try:
        if target.endswith(":"):
            os.startfile(target); return True, f"{name} khul gaya"
        exe = shutil.which(target) or shutil.which(target + ".exe")
        if exe:
            subprocess.Popen([exe], creationflags=_NOWIN); return True, f"{name} khul gaya"
        subprocess.Popen(["cmd", "/c", "start", "", target], creationflags=_NOWIN)
        return True, f"{name} kholne ki koshish ki"
    except Exception as e:
        return False, f"{name} nahi khula: {e}"

def open_path(path):
    try:
        os.startfile(str(path)); return True, str(path)
    except Exception as e:
        return False, str(e)

def reveal_in_explorer(path):
    try:
        subprocess.Popen(["explorer", "/select,", str(path)]); return True, "Explorer"
    except Exception as e:
        return False, str(e)

def open_url(url):
    try:
        webbrowser.open(url); return True, url
    except Exception as e:
        return False, str(e)

_APPS_CACHE = None
def start_menu_apps(refresh=False):
    """Start Menu ke .lnk shortcuts -> [(name, path)] sorted."""
    global _APPS_CACHE
    if _APPS_CACHE is not None and not refresh:
        return _APPS_CACHE
    roots = [Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Microsoft/Windows/Start Menu/Programs",
             Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs"]
    seen, out = set(), []
    for r in roots:
        if not r.exists(): continue
        for f in r.rglob("*.lnk"):
            nm = f.stem
            if nm.lower() in seen or "uninstall" in nm.lower(): continue
            seen.add(nm.lower()); out.append((nm, str(f)))
    _APPS_CACHE = sorted(out, key=lambda x: x[0].lower())
    return _APPS_CACHE


# ── Files ─────────────────────────────────────────────────────────
def user_dirs():
    d = {"Desktop": HOME / "Desktop", "Documents": HOME / "Documents", "Downloads": HOME / "Downloads",
         "Pictures": HOME / "Pictures", "Music": HOME / "Music", "Videos": HOME / "Videos"}
    od = HOME / "OneDrive" / "Desktop"
    if od.exists(): d["Desktop"] = od
    return {k: v for k, v in d.items() if v.exists()}

def list_dir(path, limit=400):
    """[(name, fullpath, is_dir, size, mtime)] — newest first, folders pehle."""
    out = []
    try:
        for e in os.scandir(path):
            try:
                st = e.stat(); out.append((e.name, e.path, e.is_dir(), st.st_size, st.st_mtime))
            except OSError:
                continue
    except Exception:
        return []
    out.sort(key=lambda x: (not x[2], -x[4]))
    return out[:limit]

def human_size(n):
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024: return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


# ── System info / monitoring ──────────────────────────────────────
def sys_info():
    info = {"OS": f"{platform.system()} {platform.release()}", "PC": platform.node(),
            "CPU": platform.processor() or platform.machine()}
    if psutil:
        info["Cores"] = f"{psutil.cpu_count(logical=False) or '?'} physical / {psutil.cpu_count()} logical"
        f = psutil.cpu_freq()
        if f: info["Clock"] = f"{f.current/1000:.2f} GHz"
        info["RAM"] = f"{psutil.virtual_memory().total/1024**3:.1f} GB"
        try:
            du = psutil.disk_usage(os.path.abspath(os.sep))
            info["Disk"] = f"{du.used/1024**3:.0f} / {du.total/1024**3:.0f} GB"
        except Exception: pass
        up = datetime.timedelta(seconds=int(time.time() - psutil.boot_time()))
        info["Uptime"] = str(up)
    return info


class NetSampler:
    def __init__(self):
        self._last = psutil.net_io_counters() if psutil else None
        self._t = time.time()
    def sample(self):
        """(down KB/s, up KB/s)"""
        if not psutil: return 0.0, 0.0
        now, t = psutil.net_io_counters(), time.time(); dt = max(t - self._t, 1e-3)
        d = (now.bytes_recv - self._last.bytes_recv) / 1024 / dt
        u = (now.bytes_sent - self._last.bytes_sent) / 1024 / dt
        self._last, self._t = now, t
        return d, u


def _ps_exe():
    """PowerShell ka poora path (PATH me na ho tab bhi chale)."""
    p = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    return p if os.path.exists(p) else "powershell"


class ProcSampler:
    """Top processes by CPU — PowerShell SUBPROCESS se (psutil ka process scan GIL pakad kar poori GUI ko
    3-5 second freeze karta tha). CPU% do samples ke beech cumulative CPU seconds ke delta se nikalte hain."""
    PS = ("Get-Process | Select-Object Id,ProcessName,CPU,WorkingSet64 | ConvertTo-Json -Compress")

    def __init__(self):
        self._prev = {}; self._t = None

    def top(self, n=8):
        import json
        t = time.time()
        try:
            r = subprocess.run([_ps_exe(), "-NoProfile", "-NonInteractive", "-Command", self.PS],
                               capture_output=True, text=True, timeout=25, creationflags=_NOWIN)
            data = json.loads(r.stdout or "[]")
        except Exception:
            return []
        if isinstance(data, dict): data = [data]
        ncpu = (psutil.cpu_count() if psutil else 1) or 1
        dt = (t - self._t) if self._t else None
        rows, prev = [], {}
        for d in data:
            pid = d.get("Id"); cpu_s = float(d.get("CPU") or 0.0); prev[pid] = cpu_s
            if not pid: continue                                   # Idle
            pct = max(0.0, (cpu_s - self._prev[pid]) / dt / ncpu * 100.0) if (dt and pid in self._prev) else 0.0
            rows.append((pid, (d.get("ProcessName") or "?") + ".exe", pct, float(d.get("WorkingSet64") or 0) / 1024 / 1024))
        self._prev, self._t = prev, t
        rows.sort(key=lambda r: (r[2], r[3]), reverse=True)
        return rows[:n]

def kill_process(pid):
    try:
        psutil.Process(int(pid)).terminate(); return True, f"PID {pid} band kiya"
    except Exception as e:
        return False, str(e)
