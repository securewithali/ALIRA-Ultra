# -*- coding: utf-8 -*-
"""
TITAN Tools — Gemini WebSocket Compatible
Koi livekit dependency nahi hai.
Sab features ek jagah.
"""
import os, asyncio, subprocess, webbrowser, ctypes, winreg, shutil, glob
import secrets, string, datetime, json, socket, threading, time, wave, tempfile
import numpy as np, psutil
from pathlib import Path

# ── Optional imports ──────────────────────────────────────
try:    import qrcode
except: qrcode = None
try:    import pywhatkit
except: pywhatkit = None
try:    import yt_dlp
except: yt_dlp = None
try:    import cv2
except: cv2 = None
try:    import wikipedia
except: wikipedia = None
try:    import speedtest
except: speedtest = None
try:    from duckduckgo_search import DDGS
except: DDGS = None
try:    import phonenumbers; from phonenumbers import geocoder, carrier
except: phonenumbers = None
try:    import urllib.request
except: pass
try:    import requests
except: requests = None
try:    import pyaudio; PYAUDIO = True
except: PYAUDIO = False
try:    import pypdf
except: pypdf = None
try:    from PIL import Image
except: Image = None
try:    import win32com.client, pythoncom; HAS_WIN32 = True
except: HAS_WIN32 = False
try:    import pygetwindow as gw
except: gw = None
try:    import pyperclip, pyautogui
except: pass
try:    import mss
except: mss = None
try:    import pyttsx3
except: pyttsx3 = None

# Dirs
NOTES_DIR      = os.path.join(os.path.expanduser("~"), "Documents", "TITAN_Notes")
RECORDINGS_DIR = os.path.join(os.path.expanduser("~"), "Documents", "TITAN_Recordings")
WALLPAPER_DIR  = os.path.join(os.path.expanduser("~"), "Pictures", "TITANWallpapers")
PDF_OUT_DIR    = os.path.join(os.path.expanduser("~"), "Documents", "TITAN_PDFs")
for d in [NOTES_DIR, RECORDINGS_DIR, WALLPAPER_DIR, PDF_OUT_DIR]:
    os.makedirs(d, exist_ok=True)

# Security mode flag
SECURITY_ACTIVE = False

# Active timers
_timers = {}

# ══════════════════════════════════════════════════════════
# 1. SYSTEM CONTROL
# ══════════════════════════════════════════════════════════

async def play_on_youtube(topic: str) -> str:
    try:
        if pywhatkit: pywhatkit.playonyt(topic); return f"✅ YouTube pe chal raha hai: {topic}"
        webbrowser.open(f"https://www.youtube.com/results?search_query={topic}")
        return f"✅ YouTube khula: {topic}"
    except: webbrowser.open(f"https://www.youtube.com/results?search_query={topic}"); return "✅ YouTube khula"

async def search_on_google(query: str) -> str:
    webbrowser.open(f"https://www.google.com/search?q={query}")
    return f"✅ Google search: {query}"

async def system_control(command: str) -> str:
    try:
        import subprocess as _sp
        def _shutdown():
            _sp.run(["shutdown", "/s", "/t", "10"], shell=False)
        def _restart():
            _sp.run(["shutdown", "/r", "/t", "10"], shell=False)
        def _abort():
            _sp.run(["shutdown", "/a"], shell=False)
        def _sleep():
            try:
                ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
            except Exception:
                _sp.run(["rundll32", "powrprof.dll,SetSuspendState", "0,1,0"], shell=False)
        def _lock():
            ctypes.windll.user32.LockWorkStation()
        def _vol_up():
            for _ in range(2): pyautogui.press("volumeup")
        def _vol_down():
            for _ in range(2): pyautogui.press("volumedown")
        def _mute():
            pyautogui.press("volumemute")

        cmds = {
            "volume_up":      _vol_up,
            "volume_down":    _vol_down,
            "mute":           _mute,
            "lock":           _lock,
            "sleep":          _sleep,
            "shutdown":       _shutdown,
            "restart":        _restart,
            "abort_shutdown": _abort,
        }
        if command in cmds:
            await asyncio.to_thread(cmds[command])
            return f"✅ {command} ho gaya"
        return f"❌ Unknown command: {command}"
    except Exception as e: return f"❌ Error: {e}"

async def execute_shortcut(shortcut_name: str) -> str:
    shortcuts = {
        "start_menu":    lambda: pyautogui.press('win'),
        "action_center": lambda: pyautogui.hotkey('win','a'),
        "task_view":     lambda: pyautogui.hotkey('win','tab'),
        "file_explorer": lambda: pyautogui.hotkey('win','e'),
        "show_desktop":  lambda: pyautogui.hotkey('win','d'),
        "settings":      lambda: pyautogui.hotkey('win','i'),
        "run":           lambda: pyautogui.hotkey('win','r'),
        "screenshot_tool": lambda: pyautogui.hotkey('win','prtscr'),
        "minimize_all":  lambda: pyautogui.hotkey('win','m'),
        "emoji":         lambda: pyautogui.hotkey('win','.'),
        "clipboard_history": lambda: pyautogui.hotkey('win','v'),
    }
    try:
        if shortcut_name in shortcuts: shortcuts[shortcut_name](); return f"✅ Shortcut: {shortcut_name}"
        return f"❌ Unknown shortcut: {shortcut_name}"
    except Exception as e: return f"❌ Error: {e}"

async def control_media(action: str) -> str:
    keys = {"play_pause":'playpause',"next":'nexttrack',"previous":'prevtrack',"stop":'stopmedia'}
    try:
        k = keys.get(action.lower())
        if k: pyautogui.press(k); return f"✅ Media: {action}"
        return f"❌ Unknown: {action}"
    except Exception as e: return f"❌ Error: {e}"

# ══════════════════════════════════════════════════════════
# 2. DESKTOP & THEME
# ══════════════════════════════════════════════════════════

async def set_system_theme(mode: str) -> str:
    try:
        val = 0 if mode.lower() == "dark" else 1
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
              r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize", 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "AppsUseLightTheme", 0, winreg.REG_DWORD, val)
        winreg.SetValueEx(key, "SystemUsesLightTheme", 0, winreg.REG_DWORD, val)
        key.Close()
        ctypes.windll.user32.SendMessageW(0xFFFF, 0x001A, 0, "ImmersiveColorSet")
        return f"✅ Theme {mode} ho gaya"
    except Exception as e: return f"❌ Error: {e}"

async def open_folder(folder_name: str) -> str:
    """Folder kholo. Naam (e.g. 'Downloads') ya pura path de sakte hain."""
    try:
        u = os.environ.get('USERPROFILE')
        paths = {
            "downloads": os.path.join(u, "Downloads"),
            "documents": os.path.join(u, "Documents"),
            "pictures":  os.path.join(u, "Pictures"),
            "videos":    os.path.join(u, "Videos"),
            "music":     os.path.join(u, "Music"),
            "desktop":   os.path.join(u, "Desktop"),
        }

        # Add TITAN folders
        try:
            from tabbu_modules.tabbu_advanced_features import ROOT_PATH
            paths["assignments"] = str(ROOT_PATH / "TITAN_assignments")
            paths["webcam"]      = str(ROOT_PATH / "TITAN_webcam")
            paths["memory"]      = str(ROOT_PATH / "TITAN_memory")
        except:
            pass

        n = folder_name.lower().strip()

        # Check aliases
        if n in ["recycle bin", "trash"]:
            os.startfile("shell:RecycleBinFolder")
            return "✅ Recycle Bin khula"

        target = paths.get(n)
        if not target:
            # Maybe it's a direct path
            if os.path.exists(folder_name):
                target = folder_name
            else:
                # Try relative to project root
                try:
                    from tabbu_modules.tabbu_advanced_features import ROOT_PATH
                    rel = ROOT_PATH / folder_name
                    if rel.exists():
                        target = str(rel)
                except:
                    pass

        if target and os.path.exists(target):
            os.startfile(target)
            return f"✅ Folder khula: {target}"

        return f"❌ Folder nahi mila: {folder_name}"
    except Exception as e:
        return f"❌ Error: {e}"


# ══════════════════════════════════════════════════════════
# APP LAUNCHER — Start Menu search se koi bhi app kholo
# Path dene ki zaroorat NAHI — naam se dhoondhega
# ══════════════════════════════════════════════════════════

# Common app name aliases (jo user bolte hain → actual search term)
APP_ALIASES = {
    # Browsers
    "chrome":        "Google Chrome",
    "firefox":       "Firefox",
    "edge":          "Microsoft Edge",
    "browser":       "Google Chrome",
    "opera":         "Opera",
    "brave":         "Brave",
    # Office
    "word":          "Microsoft Word",
    "excel":         "Microsoft Excel",
    "powerpoint":    "Microsoft PowerPoint",
    "outlook":       "Microsoft Outlook",
    "onenote":       "OneNote",
    "teams":         "Microsoft Teams",
    # Media
    "vlc":           "VLC media player",
    "spotify":       "Spotify",
    "media player":  "Windows Media Player",
    "photos":        "Photos",
    "camera":        "Camera",
    # Dev tools
    "vs code":       "Visual Studio Code",
    "vscode":        "Visual Studio Code",
    "visual studio": "Visual Studio",
    "notepad++":     "Notepad++",
    "notepad":       "Notepad",
    "cmd":           "Command Prompt",
    "powershell":    "PowerShell",
    "terminal":      "Windows Terminal",
    "git":           "Git Bash",
    "python":        "Python",
    "pycharm":       "PyCharm",
    # System
    "settings":      "Settings",
    "control panel": "Control Panel",
    "task manager":  "Task Manager",
    "device manager":"Device Manager",
    "calculator":    "Calculator",
    "calendar":      "Calendar",
    "clock":         "Clock",
    "mail":          "Mail",
    "maps":          "Maps",
    "store":         "Microsoft Store",
    "paint":         "Paint",
    "snipping":      "Snipping Tool",
    "sticky notes":  "Sticky Notes",
    "wordpad":       "WordPad",
    "whiteboard":    "Microsoft Whiteboard",
    # Communication
    "whatsapp":      "WhatsApp",
    "telegram":      "Telegram",
    "discord":       "Discord",
    "zoom":          "Zoom",
    "skype":         "Skype",
    "slack":         "Slack",
    # Gaming
    "steam":         "Steam",
    "epic":          "Epic Games Launcher",
    "xbox":          "Xbox",
    # Utilities
    "7zip":          "7-Zip",
    "winrar":        "WinRAR",
    "anydesk":       "AnyDesk",
    "teamviewer":    "TeamViewer",
    "obs":           "OBS Studio",
    "blender":       "Blender",
    "figma":         "Figma",
    "canva":         "Canva",
    "adobe":         "Adobe",
    "photoshop":     "Adobe Photoshop",
    "premiere":      "Adobe Premiere",
}

def _find_app_in_startmenu(query: str) -> str:
    """
    Start Menu ke saare shortcuts scan karo aur matching .exe path do.
    Returns: exe path string ya "" if not found.
    """
    query_low = query.lower().strip()
    search_dirs = []

    # All Users Start Menu
    prog_data = os.environ.get("ProgramData", r"C:\ProgramData")
    search_dirs.append(os.path.join(prog_data, "Microsoft", "Windows", "Start Menu", "Programs"))

    # Current User Start Menu
    appdata = os.environ.get("APPDATA", "")
    if appdata:
        search_dirs.append(os.path.join(appdata, "Microsoft", "Windows", "Start Menu", "Programs"))

    best_match = ""
    best_score = 0

    for sdir in search_dirs:
        if not os.path.exists(sdir):
            continue
        # Walk all .lnk files
        for root, dirs, files in os.walk(sdir):
            for fname in files:
                if not fname.lower().endswith(".lnk"):
                    continue
                name_no_ext = fname[:-4].lower()
                # Score: exact match > startswith > contains
                if name_no_ext == query_low:
                    score = 100
                elif name_no_ext.startswith(query_low):
                    score = 80
                elif query_low in name_no_ext:
                    score = 60
                elif any(w in name_no_ext for w in query_low.split()):
                    score = 40
                else:
                    continue

                if score > best_score:
                    best_score = score
                    best_match = os.path.join(root, fname)

    return best_match   # .lnk shortcut path


def _resolve_lnk(lnk_path: str) -> str:
    """Windows shortcut (.lnk) ka actual target path nikalo."""
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(lnk_path)
        return shortcut.Targetpath
    except Exception:
        pass
    # PowerShell fallback
    try:
        ps = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        r = subprocess.run(
            [ps, "-NoProfile", "-Command",
             f"(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk_path}').TargetPath"],
            capture_output=True, text=True, timeout=5
        )
        return r.stdout.strip()
    except Exception:
        return ""


def _launch_via_shell(lnk_or_exe: str) -> bool:
    """Launch karo .lnk ya .exe — Windows Shell se (Start Menu jaisa)."""
    try:
        # Shell open — EXACTLY jaise Start Menu se kholte hain
        ctypes.windll.shell32.ShellExecuteW(
            None, "open", lnk_or_exe, None, None, 1
        )
        return True
    except Exception:
        pass
    try:
        os.startfile(lnk_or_exe)
        return True
    except Exception:
        return False


def _search_installed_apps_registry(query: str) -> str:
    """
    Windows Registry mein installed apps dhoondhо.
    Returns exe path ya "".
    """
    query_low = query.lower()
    reg_paths = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths",
    ]
    for hive in [winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER]:
        for reg_path in reg_paths:
            try:
                key = winreg.OpenKey(hive, reg_path)
                for i in range(winreg.QueryInfoKey(key)[0]):
                    sub_name = winreg.EnumKey(key, i)
                    if query_low in sub_name.lower():
                        try:
                            sub = winreg.OpenKey(key, sub_name)
                            val, _ = winreg.QueryValueEx(sub, "")
                            if val and os.path.exists(val):
                                return val
                        except Exception:
                            pass
            except Exception:
                pass
    return ""


def _launch_by_start_menu(app_name: str) -> tuple:
    """
    App launch karo — 5 methods try karta hai order mein.
    """
    name_low = app_name.lower().strip()

    # ── Method 1: Start Menu .lnk scan (most reliable) ───
    lnk = _find_app_in_startmenu(app_name)
    if lnk:
        ok = _launch_via_shell(lnk)
        if ok:
            return True, f"✅ {app_name} khul gaya (Start Menu)"

    # ── Method 2: Registry App Paths ─────────────────────
    exe = _search_installed_apps_registry(app_name)
    if exe:
        ok = _launch_via_shell(exe)
        if ok:
            return True, f"✅ {app_name} khul gaya"

    # ── Method 3: PowerShell Get-StartApps ───────────────
    try:
        ps = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        r = subprocess.run(
            [ps, "-NoProfile", "-Command",
             f"(Get-StartApps | Where-Object {{$_.Name -like '*{app_name}*'}} | Select-Object -First 1).AppID"],
            capture_output=True, text=True, timeout=8
        )
        app_id = r.stdout.strip()
        if app_id:
            subprocess.run(
                [ps, "-NoProfile", "-Command",
                 f"Start-Process 'shell:AppsFolder\\{app_id}'"],
                capture_output=True, timeout=5
            )
            return True, f"✅ {app_name} khul gaya"
    except Exception:
        pass

    # ── Method 4: cmd /c start (PATH-based) ──────────────
    try:
        # cmd /c start "" "appname" — Windows PATH + assoc check karta hai
        subprocess.Popen(
            f'start "" "{app_name}"',
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        time.sleep(0.8)
        return True, f"✅ {app_name} khul raha hai..."
    except Exception:
        pass

    # ── Method 5: Win key + type + Enter (last resort) ───
    try:
        pyautogui.press('win')
        time.sleep(0.8)
        pyperclip.copy(app_name)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(1.8)
        pyautogui.press('enter')
        time.sleep(0.5)
        return True, f"✅ {app_name} Start Menu se khol raha hoon..."
    except Exception as e:
        return False, f"❌ {app_name} nahi mila: {e}"


async def _open_app_legacy(app_name: str) -> str:
    """
    PURANA launcher (fallback): Get-StartApps -like + lnk + registry + Win-key search.
    Naya dynamic launcher ALIRA_apps.py pehle chalta hai (open_app) — ye sirf tab jab wo app na dhoond paye.
    """
    def _open():
        name = app_name.strip().lower()
        search_name = APP_ALIASES.get(name, app_name.strip())
        ps = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"

        # ── Step 1: Built-in Windows EXEs ────────────────
        builtins = {
            "notepad":        "notepad.exe",
            "calculator":     "calc.exe",
            "cmd":            "cmd.exe",
            "command prompt": "cmd.exe",
            "powershell":     "powershell.exe",
            "task manager":   "taskmgr.exe",
            "control panel":  "control.exe",
            "device manager": "devmgmt.msc",
            "regedit":        "regedit.exe",
            "paint":          "mspaint.exe",
            "wordpad":        "wordpad.exe",
            "file explorer":  "explorer.exe",
            "explorer":       "explorer.exe",
        }
        if name in builtins:
            try:
                subprocess.Popen(
                    [builtins[name]],
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                return f"✅ {app_name} khul gaya"
            except Exception:
                pass

        # ── Step 2: PowerShell Get-StartApps se dhoondhо ─
        # Yeh ACTUALLY Start Menu search karta hai
        try:
            r = subprocess.run(
                [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                 f"Get-StartApps | Where-Object {{$_.Name -like '*{search_name}*'}} "
                 f"| Select-Object -First 1 | ConvertTo-Json"],
                capture_output=True, text=True, timeout=10
            )
            out = r.stdout.strip()
            if out and out != "null" and "{" in out:
                import json as _j
                data   = _j.loads(out)
                app_id = data.get("AppID", "")
                aname  = data.get("Name", search_name)
                if app_id:
                    # shell:AppsFolder\AppID se open karo
                    subprocess.Popen(
                        [ps, "-NoProfile", "-Command",
                         f"Start-Process 'shell:AppsFolder\\{app_id}'"],
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    return f"✅ {aname} khul gaya"
        except Exception as e:
            print(f"[OpenApp PS] {e}")

        # ── Step 3: Start Menu .lnk scan ─────────────────
        lnk = _find_app_in_startmenu(search_name)
        if lnk:
            try:
                os.startfile(lnk)
                return f"✅ {app_name} khul gaya"
            except Exception:
                pass

        # ── Step 4: Registry App Paths ───────────────────
        exe = _search_installed_apps_registry(search_name)
        if exe:
            try:
                subprocess.Popen([exe], creationflags=subprocess.CREATE_NO_WINDOW)
                return f"✅ {app_name} khul gaya"
            except Exception:
                pass

        # ── Step 5: Win key simulation ────────────────────
        try:
            pyautogui.press('win')
            time.sleep(1.0)
            # Clipboard se paste — no IME conversion
            _set_clipboard_raw(search_name)
            pyautogui.hotkey('ctrl', 'v')
            time.sleep(2.0)
            pyautogui.press('enter')
            time.sleep(0.8)
            return f"✅ {app_name} Start Menu se khol raha hoon..."
        except Exception as e:
            return f"❌ {app_name} nahi khul saka: {e}"

    return await asyncio.to_thread(_open)


async def open_app(app_name: str, text: str = "") -> str:
    """
    PC par install KOI BHI app (Store/UWP + normal) naam se kholo — text diya ho to usme likh bhi do — hardcoded list nahi, installed apps scan hote hain
    (ALIRA_apps.py). Pehle se khula ho to saamne le aata hai; launch ke baad window aayi ya nahi verify karta hai.
    """
    try:
        import alira_apps
        if (text or "").strip():                           # "notepad kholo aur ye likho" — open + likho + verify
            r = await asyncio.to_thread(alira_apps.write_text, app_name, text)
            return r["message"]
        r = await asyncio.to_thread(alira_apps.open_app, app_name)
        if r["found"]:
            msg = r["message"]
            if r.get("alternatives") and r["status"] != "focused":
                msg += f"  (milte-julte apps: {', '.join(r['alternatives'][:3])})"
            return msg
        return r["message"]                                 # installed nahi — saaf bata do (Win-key typing wala jhoota fallback nahi)
    except Exception as e:
        print(f"[OpenApp] launcher error: {e}")
        return await _open_app_legacy(app_name)


async def list_installed_apps(filter_text: str = "") -> str:
    """PC par install apps ki list (naam ka filter optional)."""
    try:
        import alira_apps
        names = await asyncio.to_thread(alira_apps.list_apps, filter_text)
        if not names:
            return f"❌ '{filter_text}' se milta koi installed app nahi mila." if filter_text else "❌ App list nahi mili."
        shown = ", ".join(names[:60]) + (f" … (+{len(names) - 60} aur)" if len(names) > 60 else "")
        return f"📦 {len(names)} apps{(' (' + filter_text + ')') if filter_text else ''}: {shown}"
    except Exception as e:
        return f"❌ App list error: {e}"


async def refresh_app_list() -> str:
    """Naya app install kiya ho to list dobara scan karo."""
    try:
        import alira_apps
        apps = await asyncio.to_thread(alira_apps.ensure_index, True)
        return f"✅ {len(apps)} apps scan hue"
    except Exception as e:
        return f"❌ Scan error: {e}"


async def play_on_spotify(query: str, kind: str = "auto") -> str:
    """Spotify app par gaana / artist / album / playlist SACH MEIN chalao (search + play + verify)."""
    try:
        import alira_spotify
        r = await asyncio.to_thread(alira_spotify.play, query, (kind or "auto").lower())
        return r["message"]
    except Exception as e:
        return f"❌ Spotify error: {e}"


async def set_language(language: str) -> str:
    """User ki pasand ki language set karo (duniya ki koi bhi) — ab ALIRA usi mein sunegi aur bolegi."""
    try:
        import alira_lang
        it = alira_lang.set_language(language)
        if not it:
            return "✅ Language Auto/Hinglish par set ho gayi. Ab se pehle jaise Hinglish mein bolo."
        return (f"✅ Language set: {it[1]} ({it[2]}). Ab SE ABHI SE sirf {it[1]} mein bolo — is jawab se hi {it[1]} mein "
                f"confirm karo. Aage ki har baat {it[1]} mein.")
    except Exception as e:
        return f"❌ Ye language nahi mili ({e}). User se language ka poora naam pucho."


async def set_user_name(name: str) -> str:
    """User ka naam yaad rakho (Settings mein bhi dikhega, ALIRA naam se bulayegi)."""
    try:
        import alira_prefs
        n = alira_prefs.set_user_name(name)
        return f"✅ Naam save ho gaya: {n}" if n else "❌ Naam khali hai"
    except Exception as e:
        return f"❌ Naam save nahi hua: {e}"


async def open_app_and_do(app_name: str, action: str = "") -> str:
    """App kholo aur usme `action` (jo text likhna hai) likho — jaise notepad kholo aur ye likho.
    Verify karta hai ki text sach mein likha gaya."""
    return await open_app(app_name, action)

async def snap_window(direction: str) -> str:
    try:
        pyautogui.keyDown('win'); pyautogui.press(direction); pyautogui.keyUp('win')
        return f"✅ Window snap: {direction}"
    except Exception as e: return f"❌ Error: {e}"

async def empty_recycle_bin() -> str:
    try:
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 0x00000007)
        return "✅ Recycle Bin saaf ho gaya"
    except Exception as e: return f"❌ Error: {e}"

async def toggle_desktop_icons(visible: bool = None) -> str:
    try:
        u32 = ctypes.windll.user32
        pg = u32.FindWindowW("Progman", None)
        dv = u32.FindWindowExW(pg, 0, "SHELLDLL_DefView", None)
        if not dv:
            ww = 0
            while True:
                ww = u32.FindWindowExW(0, ww, "WorkerW", None)
                if not ww: break
                dv = u32.FindWindowExW(ww, 0, "SHELLDLL_DefView", None)
                if dv: break
        if not dv: return "❌ Desktop icons nahi mile"
        slv = u32.FindWindowExW(dv, 0, "SysListView32", None)
        if not slv: return "❌ SysListView32 nahi mila"
        cur = u32.IsWindowVisible(slv) != 0
        state = (0 if cur else 5) if visible is None else (5 if visible else 0)
        u32.ShowWindow(slv, state)
        return "✅ Desktop icons toggle ho gaye"
    except Exception as e: return f"❌ Error: {e}"

# ══════════════════════════════════════════════════════════
# 3. CLIPBOARD
# ══════════════════════════════════════════════════════════

async def get_clipboard() -> str:
    try:
        c = pyperclip.paste(); return f"📋 Clipboard: {c}" if c else "📋 Clipboard khali hai"
    except Exception as e: return f"❌ Error: {e}"

async def set_clipboard(text: str) -> str:
    try: pyperclip.copy(text); return "✅ Clipboard mein copy ho gaya"
    except Exception as e: return f"❌ Error: {e}"

async def edit_text(action: str) -> str:
    acts = {"copy":('ctrl','c'),"paste":('ctrl','v'),"cut":('ctrl','x'),
            "undo":('ctrl','z'),"redo":('ctrl','y'),"select_all":('ctrl','a')}
    try:
        keys = acts.get(action.lower())
        if keys: await asyncio.sleep(0.1); pyautogui.hotkey(*keys); return f"✅ {action} kiya"
        return f"❌ Unknown action: {action}"
    except Exception as e: return f"❌ Error: {e}"

# ══════════════════════════════════════════════════════════
# 4. DIGITAL TOOLS
# ══════════════════════════════════════════════════════════

async def generate_password(length: int = 12) -> str:
    c = string.ascii_letters + string.digits + "!@#$%^&*()"
    return f"🔐 Password: {''.join(secrets.choice(c) for _ in range(length))}"

async def create_qr_code(text: str = "") -> str:
    if not qrcode: return "❌ pip install qrcode[pil]"
    if not text:
        pyautogui.hotkey('ctrl','c'); await asyncio.sleep(0.3); text = pyperclip.paste()
    if not text: return "❌ Koi text nahi mila"
    try:
        path = os.path.join(os.getcwd(), "latest_qr.png")
        qrcode.make(text).save(path); os.startfile(path)
        return f"✅ QR bana: {path}"
    except Exception as e: return f"❌ Error: {e}"

# ══════════════════════════════════════════════════════════
# 5. FILE TOOLS
# ══════════════════════════════════════════════════════════

async def find_file(filename: str, folder: str = None, file_type: str = None, newest: bool = False, **kwargs) -> str:
    """
    System mein file dhoondo.
    filename: File ka naam ya part.
    folder: Specific folder path (optional).
    file_type: Extension (optional, e.g. '.pdf').
    newest: Agar True, toh latest files pehle dikhayega.
    """
    try:
        u = os.path.expanduser("~")
        search_dirs = [
            os.path.join(u, "Desktop"),
            os.path.join(u, "Documents"),
            os.path.join(u, "Downloads")
        ]

        # Project root
        try:
            from tabbu_modules.tabbu_advanced_features import ROOT_PATH
            if str(ROOT_PATH) not in search_dirs:
                search_dirs.append(str(ROOT_PATH))
        except ImportError:
            pass

        if folder:
            if os.path.exists(folder):
                search_dirs.insert(0, folder)
            else:
                alt = os.path.join(u, folder)
                if os.path.exists(alt): search_dirs.insert(0, alt)

        found_files = []
        for d in search_dirs:
            if not os.path.exists(d): continue
            try:
                for root, _, files in os.walk(d):
                    for f in files:
                        if filename.lower() in f.lower():
                            # Extension filter
                            if file_type and not f.lower().endswith(file_type.lower()):
                                continue
                            found_files.append(os.path.join(root, f))
                        if len(found_files) > 30: break
                    if len(found_files) > 30: break
            except Exception as walk_err:
                print(f"[FindFile] Skip {d}: {walk_err}")
                continue

        if not found_files:
            return f"❌ '{filename}' nahi mila. Koshish karein ki naam sahi ho."

        # Sort by date if requested
        if newest:
            found_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

        lines = [f"🔍 Found {len(found_files)} matching files:"]
        for r in found_files[:8]:
            lines.append(f"• {r}")

        if len(found_files) > 8:
            lines.append(f"...aur {len(found_files)-8} aur mile.")

        return "\n".join(lines)
    except Exception as e:
        return f"❌ Error in find_file: {str(e)}"


async def organize_downloads() -> str:
    """Downloads folder ko file type ke hisab se folders mein baanto."""
    try:
        u = os.path.expanduser("~")
        dl_path = os.path.join(u, "Downloads")
        if not os.path.exists(dl_path):
            return "❌ Downloads folder nahi mila."

        types = {
            "Images":    [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
            "Documents": [".pdf", ".docx", ".doc", ".txt", ".xlsx", ".pptx", ".csv"],
            "Videos":    [".mp4", ".mkv", ".mov", ".avi", ".wmv"],
            "Music":     [".mp3", ".wav", ".aac", ".flac", ".m4a"],
            "Archives":  [".zip", ".rar", ".7z", ".tar", ".gz"],
            "Code":      [".py", ".js", ".html", ".css", ".json", ".cpp", ".java"],
            "Installers":[".exe", ".msi"]
        }

        count = 0
        skipped = 0

        # Get all files first to avoid modification during iteration issues
        try:
            files = [f for f in os.listdir(dl_path) if os.path.isfile(os.path.join(dl_path, f))]
        except Exception as e:
            return f"❌ Access Error: {e}"

        for f in files:
            fp = os.path.join(dl_path, f)
            ext = os.path.splitext(f)[1].lower()

            cat = None
            for c, exts in types.items():
                if ext in exts:
                    cat = c
                    break

            if not cat: continue
            if f.startswith("~$"): continue   # Office temp/lock files — move nahi hote

            target_dir = os.path.join(dl_path, cat)
            try:
                try:
                    os.makedirs(target_dir, exist_ok=True)
                except PermissionError:
                    # ✅ Downloads mein folder banane ki permission hi nahi — har file pe
                    # same error spam karne ki jagah ek saaf message do aur ruk jao.
                    print(f"[Organize] Permission denied creating {target_dir}")
                    return ("❌ Downloads folder mein naya folder banane ki permission nahi hai. "
                            "Windows mein Downloads → Properties → Security mein apne user ko Modify do, "
                            "ya CMD mein chalao: icacls \"%USERPROFILE%\\Downloads\" /grant \"%USERNAME%\":(OI)(CI)M")
                dest = os.path.join(target_dir, f)

                # If file already exists in target, rename it
                if os.path.exists(dest):
                    base, ext = os.path.splitext(f)
                    dest = os.path.join(target_dir, f"{base}_{int(time.time())}{ext}")

                shutil.move(fp, dest)
                count += 1
            except Exception as e:
                print(f"[Organize] Error moving {f}: {e}")
                skipped += 1
                continue

        res = f"✅ {count} files organize ho gayi Downloads mein."
        if skipped > 0:
            res += f" ({skipped} files skip ki gayi kyunki wo use mein thi ya permission nahi thi)"
        return res
    except Exception as e:
        return f"❌ Error in organize_downloads: {str(e)}"

# ══════════════════════════════════════════════════════════
# 6. SCREENSHOT & CAMERA
# ══════════════════════════════════════════════════════════

async def take_screenshot() -> str:
    try:
        folder = os.path.join(os.path.expanduser("~"), "Pictures", "Screenshots")
        os.makedirs(folder, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(folder, f"Screenshot_{ts}.png")
        pyautogui.screenshot(path)
        subprocess.Popen(f'explorer /select,"{path}"')
        return f"✅ Screenshot liya: {path}"
    except Exception as e: return f"❌ Error: {e}"

async def open_camera() -> str:
    if not cv2: return "❌ pip install opencv-python"
    def _cam():
        cap = cv2.VideoCapture(0)
        if not cap.isOpened(): return "❌ Camera nahi khula"
        win = "TITAN Camera (Q ya ESC se band karo)"
        while True:
            ret, frame = cap.read()
            if not ret: break
            cv2.imshow(win, frame)
            k = cv2.waitKey(1) & 0xFF
            if k in [ord('q'), 27]: break
            if cv2.getWindowProperty(win, cv2.WND_PROP_VISIBLE) < 1: break
        cap.release(); cv2.destroyAllWindows()
        return "✅ Camera band ho gaya"
    return await asyncio.to_thread(_cam)

# ══════════════════════════════════════════════════════════
# 7. YOUTUBE DOWNLOAD
# ══════════════════════════════════════════════════════════

async def download_youtube(url_or_query: str = "") -> str:
    if not yt_dlp: return "❌ pip install yt-dlp"
    if not url_or_query:
        pyautogui.hotkey('ctrl','l'); await asyncio.sleep(0.2)
        pyautogui.hotkey('ctrl','c'); await asyncio.sleep(0.2)
        url_or_query = pyperclip.paste()
        if "youtube.com" not in url_or_query and "youtu.be" not in url_or_query:
            return "❌ Browser mein YouTube video kholo aur dobara bolo"
    def _dl():
        dest = os.path.join(os.path.expanduser("~"), "Downloads", "TITAN_Downloads")
        os.makedirs(dest, exist_ok=True)
        with yt_dlp.YoutubeDL({'format':'18/best','outtmpl':os.path.join(dest,'%(title)s.%(ext)s'),
                                'quiet':True,'noplaylist':True,'default_search':'ytsearch'}) as ydl:
            ydl.download([url_or_query])
        subprocess.Popen(f'explorer "{dest}"')
        return f"✅ Download ho gaya: {dest}"
    try: return await asyncio.to_thread(_dl)
    except Exception as e: return f"❌ Error: {e}"

# ══════════════════════════════════════════════════════════
# 8. NETWORK & INFO
# ══════════════════════════════════════════════════════════

async def get_ip_info(ip: str = "") -> str:
    def _f():
        url = f"http://ip-api.com/json/{ip}" if ip else "http://ip-api.com/json/"
        with urllib.request.urlopen(url) as r:
            d = json.loads(r.read().decode())
        return f"🌍 IP: {d.get('query')} | ISP: {d.get('isp')}\n📍 {d.get('city')}, {d.get('regionName')}, {d.get('country')}"
    try: return await asyncio.to_thread(_f)
    except Exception as e: return f"❌ Error: {e}"

async def check_internet_speed() -> str:
    if not speedtest: return "❌ pip install speedtest-cli"
    def _t():
        st = speedtest.Speedtest(secure=True); st.get_best_server()
        return f"📥 {st.download()/1e6:.1f} Mbps | 📤 {st.upload()/1e6:.1f} Mbps | 📶 {st.results.ping:.0f}ms"
    try: return await asyncio.wait_for(asyncio.to_thread(_t), 45)
    except: return "❌ Speed test timeout"

async def get_news(topic: str = "") -> str:
    if not DDGS: return "❌ pip install duckduckgo-search"
    try:
        results = list(DDGS().news(keywords=topic or "India latest news", max_results=4))
        return "📰 " + topic + "\n" + "\n".join(f"{i+1}. {r['title']} — {r['source']}" for i,r in enumerate(results))
    except Exception as e: return f"❌ Error: {e}"

async def search_wikipedia(query: str) -> str:
    if not wikipedia: return "❌ pip install wikipedia"
    try: return f"📚 {query}:\n{wikipedia.summary(query, sentences=3)}"
    except Exception as e: return f"❌ Error: {e}"

async def get_wifi_passwords() -> str:
    def _w():
        out = subprocess.check_output(["netsh","wlan","show","profiles"], encoding="utf-8", errors="ignore")
        profiles = [l.split(":")[-1].strip() for l in out.split("\n") if "All User Profile" in l]
        results = []
        for p in profiles:
            info = subprocess.check_output(["netsh","wlan","show","profile",f"name={p}","key=clear"],
                                           encoding="utf-8", errors="ignore")
            pwd = next((l.split(":")[-1].strip() for l in info.split("\n") if "Key Content" in l), "N/A")
            results.append(f"📶 {p}: {pwd}")
        path = os.path.join(os.path.expanduser("~"), "Documents", "TITAN_WiFi.txt")
        with open(path,"w") as f: f.write("\n".join(results))
        os.startfile(path)
        return "\n".join(results)
    try: return await asyncio.to_thread(_w)
    except Exception as e: return f"❌ Error: {e}"

# ══════════════════════════════════════════════════════════
# 9. NOTES
# ══════════════════════════════════════════════════════════

async def create_note(content: str, filename: str = "") -> str:
    try:
        ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        fn = filename or f"Note_{ts}.txt"
        if not fn.endswith(".txt"): fn += ".txt"
        path = os.path.join(NOTES_DIR, fn)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"[{ts}]\n{'-'*20}\n{content}")
        return f"✅ Note save ho gaya: {fn}"
    except Exception as e: return f"❌ Error: {e}"

async def read_latest_note() -> str:
    try:
        files = [os.path.join(NOTES_DIR,f) for f in os.listdir(NOTES_DIR) if f.endswith(".txt")]
        if not files: return "❌ Koi note nahi hai"
        latest = max(files, key=os.path.getctime)
        with open(latest, encoding="utf-8") as f: return f"📄 {os.path.basename(latest)}:\n{f.read()}"
    except Exception as e: return f"❌ Error: {e}"

# ══════════════════════════════════════════════════════════
# 10. NOTIFICATION
# ══════════════════════════════════════════════════════════

async def send_notification(title: str, message: str) -> str:
    def _n():
        ps = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        script = f"""
[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]>$null
$T=[Windows.UI.Notifications.ToastTemplateType]::ToastText02
$X=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($T)
$N=$X.GetElementsByTagName("text")
$N[0].AppendChild($X.CreateTextNode("{title.replace('"','`"')}"))>$null
$N[1].AppendChild($X.CreateTextNode("{message.replace('"','`"')}"))>$null
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("TITAN").Show($X)"""
        subprocess.run([ps,"-NoProfile","-ExecutionPolicy","Bypass","-Command",script],
                       capture_output=True, text=True)
    try: await asyncio.to_thread(_n); return f"✅ Notification bheja: {title}"
    except Exception as e: return f"❌ Error: {e}"

# ══════════════════════════════════════════════════════════
# 11. PROCESS TOOLS
# ══════════════════════════════════════════════════════════

async def list_processes(filter_name: str = "") -> str:
    def _l():
        procs = []
        for p in psutil.process_iter(['pid','name']):
            try:
                if not filter_name or filter_name.lower() in p.info['name'].lower():
                    procs.append(p.info)
            except: pass
        lines = [f"{'PID':<8} Name"] + [f"{p['pid']:<8} {p['name']}" for p in procs[:20]]
        if len(procs) > 20: lines.append(f"...aur {len(procs)-20} more")
        return "\n".join(lines)
    return await asyncio.to_thread(_l)

async def terminate_process(process_name: str) -> str:
    def _k():
        n = 0
        for p in psutil.process_iter(['pid','name']):
            try:
                if process_name.lower() in p.info['name'].lower():
                    p.terminate(); n += 1
            except: pass
        return f"✅ {n} process terminate kiya: {process_name}" if n else f"❌ Process nahi mila: {process_name}"
    return await asyncio.to_thread(_k)

# ══════════════════════════════════════════════════════════
# 12. TIMER
# ══════════════════════════════════════════════════════════

async def set_timer(seconds: int, label: str = "Timer") -> str:
    def _run():
        time.sleep(seconds)
        asyncio.run(send_notification(f"⏰ {label}", f"Timer khatam ho gaya!"))
    t = threading.Thread(target=_run, daemon=True); t.start()
    m, s = divmod(seconds, 60)
    dur = f"{m} min {s} sec" if m else f"{s} sec"
    return f"✅ Timer set: {dur} ({label})"

async def list_timers() -> str:
    return f"⏱️ Active timers: {len(_timers)}" if _timers else "Koi active timer nahi"

# ══════════════════════════════════════════════════════════
# 13. RECORDING
# ══════════════════════════════════════════════════════════

async def record_voice(duration_seconds: int = 10) -> str:
    if not PYAUDIO: return "❌ pip install pyaudio"
    def _r():
        import pyaudio as pa
        p = pa.PyAudio()
        s = p.open(format=pa.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
        frames = [s.read(1024) for _ in range(int(44100/1024*duration_seconds))]
        s.stop_stream(); s.close(); p.terminate()
        fn = f"Voice_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.wav"
        fp = os.path.join(RECORDINGS_DIR, fn)
        wf = wave.open(fp,'wb'); wf.setnchannels(1)
        wf.setsampwidth(p.get_sample_size(pa.paInt16))
        wf.setframerate(44100); wf.writeframes(b''.join(frames)); wf.close()
        os.startfile(RECORDINGS_DIR)
        return f"✅ Voice record ho gaya: {fn}"
    return await asyncio.to_thread(_r)

async def record_screen(duration_seconds: int = 10) -> str:
    if not cv2 or not mss: return "❌ pip install opencv-python mss"
    def _r():
        fn = f"Screen_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.avi"
        fp = os.path.join(RECORDINGS_DIR, fn)
        with mss.mss() as sc:
            m = sc.monitors[1]; w,h = m["width"],m["height"]
            out = cv2.VideoWriter(fp, cv2.VideoWriter_fourcc(*'XVID'), 20.0, (w,h))
            end = time.time() + duration_seconds
            while time.time() < end:
                img = np.array(sc.grab(m))
                out.write(cv2.cvtColor(img, cv2.COLOR_BGRA2BGR))
            out.release()
        os.startfile(RECORDINGS_DIR)
        return f"✅ Screen record ho gaya: {fn}"
    return await asyncio.to_thread(_r)

# ══════════════════════════════════════════════════════════
# 14. WALLPAPER
# ══════════════════════════════════════════════════════════

WALLPAPERS = [
    "https://images.unsplash.com/photo-1518770660439-4636190af475?w=1920&q=80",
    "https://images.unsplash.com/photo-1535868463750-c78d9543614f?w=1920&q=80",
    "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=1920&q=80",
    "https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=1920&q=80",
    "https://picsum.photos/1920/1080",
]

async def change_wallpaper(image_path: str = "") -> str:
    if not requests: return "❌ pip install requests"
    def _w():
        if not image_path:
            import random
            fn = os.path.join(WALLPAPER_DIR, f"wp_{int(time.time())}.jpg")
            for url in random.sample(WALLPAPERS, len(WALLPAPERS)):
                try:
                    r = requests.get(url, timeout=10)
                    if r.status_code == 200:
                        with open(fn,'wb') as f: f.write(r.content)
                        break
                except: continue
            path = fn
        else:
            path = os.path.abspath(image_path)
        if not os.path.exists(path): return f"❌ File nahi mili: {path}"
        ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)
        return f"✅ Wallpaper badal gaya"
    return await asyncio.to_thread(_w)

# ══════════════════════════════════════════════════════════
# 15. WINDOW MANAGER
# ══════════════════════════════════════════════════════════

async def get_open_windows() -> str:
    if not gw: return "❌ pip install pygetwindow"
    wins = [w.title for w in gw.getAllWindows() if w.title.strip()]
    return "🪟 Open windows:\n" + "\n".join(wins[:15])

async def manage_window(title: str, action: str) -> str:
    if not gw: return "❌ pip install pygetwindow"
    try:
        wins = gw.getWindowsWithTitle(title)
        if not wins: return f"❌ Window nahi mili: {title}"
        w = wins[0]
        acts = {"activate": w.activate,"minimize": w.minimize,"maximize": w.maximize,
                "restore": w.restore,"close": w.close}
        fn = acts.get(action.lower())
        if fn: fn(); return f"✅ Window {action}: {title}"
        return f"❌ Unknown action: {action}"
    except Exception as e: return f"❌ Error: {e}"

async def zoom_screen(action: str) -> str:
    acts = {"in":('win','='),"out":('win','-'),"reset":('win','esc')}
    try:
        keys = acts.get(action.lower())
        if keys: pyautogui.hotkey(*keys); return f"✅ Zoom {action}"
        return f"❌ Unknown: {action}"
    except Exception as e: return f"❌ Error: {e}"

# ══════════════════════════════════════════════════════════
# 16. SECURITY MODE
# ══════════════════════════════════════════════════════════

async def start_security_mode() -> str:
    global SECURITY_ACTIVE
    if SECURITY_ACTIVE: return "⚠️ Security mode pehle se active hai"
    SECURITY_ACTIVE = True
    asyncio.create_task(asyncio.to_thread(_security_loop))
    return "✅ Security mode ON — motion detect ho rahi hai"

async def stop_security_mode() -> str:
    global SECURITY_ACTIVE
    SECURITY_ACTIVE = False
    return "🛑 Security mode OFF"

def _security_loop():
    global SECURITY_ACTIVE
    save = os.path.join(os.path.expanduser("~"), "Pictures", "TITAN_Security")
    os.makedirs(save, exist_ok=True)
    cap = cv2.VideoCapture(0) if cv2 else None
    if not cap or not cap.isOpened(): SECURITY_ACTIVE = False; return
    ret, f1 = cap.read(); ret, f2 = cap.read()
    last_t = 0
    while SECURITY_ACTIVE and cap.isOpened():
        diff = cv2.absdiff(f1, f2)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(cv2.GaussianBlur(gray,(5,5),0), 20, 255, cv2.THRESH_BINARY)
        cnts, _ = cv2.findContours(cv2.dilate(thresh,None,iterations=3), cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        if any(cv2.contourArea(c) > 5000 for c in cnts):
            if time.time() - last_t > 5:
                ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                cv2.imwrite(os.path.join(save, f"Motion_{ts}.jpg"), f1)
                last_t = time.time()
        f1 = f2; ret, f2 = cap.read()
        if not ret: break
        time.sleep(0.1)
    cap.release()

# ══════════════════════════════════════════════════════════
# 17. SYSTEM CLEANER
# ══════════════════════════════════════════════════════════

async def clean_system() -> str:
    def _c():
        count = 0; size = 0.0
        for folder in [tempfile.gettempdir(), os.path.join(os.environ.get("SystemRoot","C:\\Windows"),"Temp")]:
            if not os.path.exists(folder): continue
            for f in glob.glob(os.path.join(folder,"*")):
                try:
                    if os.path.isfile(f): size += os.path.getsize(f)/1e6; os.remove(f); count += 1
                    elif os.path.isdir(f): shutil.rmtree(f, ignore_errors=True); count += 1
                except: pass
        ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
        return f"✅ {count} files delete | ~{size:.1f} MB free | Recycle Bin saaf"
    return await asyncio.to_thread(_c)

# ══════════════════════════════════════════════════════════
# 18. PDF TOOLS
# ══════════════════════════════════════════════════════════

async def read_pdf(file_path: str) -> str:
    if not pypdf: return "❌ pip install pypdf"
    def _r():
        search = [os.getcwd()] + [os.path.join(os.environ.get('USERPROFILE',''), d)
                                   for d in ['Desktop','Documents','Downloads']]
        path = file_path
        if not os.path.exists(path):
            for d in search:
                p = os.path.join(d, file_path)
                if os.path.exists(p): path = p; break
        if not os.path.exists(path): return f"❌ PDF nahi mila: {file_path}"
        with open(path,'rb') as f:
            r = pypdf.PdfReader(f)
            text = "\n".join(r.pages[i].extract_text() or "" for i in range(min(5,len(r.pages))))
        return f"📄 PDF ({len(r.pages)} pages):\n{text[:2000]}..."
    return await asyncio.to_thread(_r)

async def merge_pdfs(folder: str, output_name: str = "merged.pdf") -> str:
    if not pypdf: return "❌ pip install pypdf"
    def _m():
        u = os.environ.get('USERPROFILE','')
        fd = folder
        for d in [folder, os.path.join(u,folder)]:
            if os.path.isdir(d): fd = d; break
        pdfs = sorted([os.path.join(fd,f) for f in os.listdir(fd) if f.lower().endswith('.pdf')])
        if not pdfs: return "❌ Koi PDF nahi mila"
        m = pypdf.PdfMerger()
        for p in pdfs: m.append(p)
        out = os.path.join(PDF_OUT_DIR, output_name)
        m.write(out); m.close()
        os.startfile(PDF_OUT_DIR)
        return f"✅ {len(pdfs)} PDFs merge ho gayi: {out}"
    return await asyncio.to_thread(_m)

async def images_to_pdf(folder: str, output_name: str = "output.pdf") -> str:
    if not Image: return "❌ pip install Pillow"
    def _i():
        u = os.environ.get('USERPROFILE','')
        fd = folder
        for d in [folder, os.path.join(u,folder)]:
            if os.path.isdir(d): fd = d; break
        exts = ('.png','.jpg','.jpeg','.bmp','.webp')
        imgs = sorted([os.path.join(fd,f) for f in os.listdir(fd) if f.lower().endswith(exts)])
        if not imgs: return "❌ Koi image nahi mili"
        pil_imgs = [Image.open(i).convert("RGB") for i in imgs]
        out = os.path.join(PDF_OUT_DIR, output_name)
        pil_imgs[0].save(out, save_all=True, append_images=pil_imgs[1:])
        return f"✅ {len(imgs)} images PDF ban gayi: {out}"
    return await asyncio.to_thread(_i)


# ══════════════════════════════════════════════════════════
# 19. WHATSAPP TOOLS — Keyboard only, no mouse coordinates
# ══════════════════════════════════════════════════════════

WA_APP_ID = r"shell:AppsFolder\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"

def _set_clipboard_raw(text: str) -> bool:
    """
    Clipboard mein text set karo — IME completely bypass.
    Win32 OpenClipboard API directly use karo — pyperclip/IME se nahi.
    Yeh ensure karta hai ki English text hindi mein convert na ho.
    """
    try:
        # Win32 direct clipboard — IME ka koi role nahi
        import ctypes
        from ctypes import wintypes

        CF_UNICODETEXT = 13
        GMEM_MOVEABLE  = 0x0002

        user32   = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        # 64-bit: argtypes/restype zaroori (warna handle 32-bit mein kat jaata hai)
        kernel32.GlobalAlloc.argtypes  = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype   = ctypes.c_void_p
        kernel32.GlobalLock.argtypes   = [ctypes.c_void_p]
        kernel32.GlobalLock.restype    = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalFree.argtypes   = [ctypes.c_void_p]
        user32.OpenClipboard.argtypes  = [ctypes.c_void_p]
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        user32.SetClipboardData.restype  = ctypes.c_void_p

        # Unicode bytes prepare karo
        encoded = (text + '\0').encode('utf-16-le')
        n_bytes  = len(encoded)

        # Global memory allocate karo
        h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, n_bytes)
        if not h_mem:
            raise RuntimeError("GlobalAlloc failed")

        # Memory mein text copy karo
        p_mem = kernel32.GlobalLock(h_mem)
        if not p_mem:
            kernel32.GlobalFree(h_mem)
            raise RuntimeError("GlobalLock failed")

        ctypes.memmove(p_mem, encoded, n_bytes)
        kernel32.GlobalUnlock(h_mem)

        # Clipboard open → clear → set → close
        if not user32.OpenClipboard(None):
            kernel32.GlobalFree(h_mem)
            raise RuntimeError("OpenClipboard failed")

        user32.EmptyClipboard()
        user32.SetClipboardData(CF_UNICODETEXT, h_mem)
        user32.CloseClipboard()

        return True

    except Exception as e:
        print(f"[Clip] Win32 failed: {e}, trying pyperclip...")
        try:
            pyperclip.copy(text)
            return True
        except Exception as e2:
            print(f"[Clip] pyperclip also failed: {e2}")
            return False


async def _focus_or_open_whatsapp() -> bool:
    """WhatsApp focus karo ya open karo. Returns True if success."""
    if gw:
        for w in gw.getAllWindows():
            if "WhatsApp" in w.title:
                try:
                    if w.isMinimized: w.restore()
                    await asyncio.sleep(0.3)
                    w.activate()
                    if not w.isMaximized:
                        w.maximize()
                    await asyncio.sleep(0.8)
                    return True
                except Exception:
                    pass

    # Open karo — UWP App ID se
    try:
        ps = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        subprocess.Popen(
            [ps, "-NoProfile", "-Command",
             f"Start-Process '{WA_APP_ID}'"],
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        await asyncio.sleep(3.5)
    except Exception:
        try:
            subprocess.Popen(["cmd", "/c", "start", "whatsapp:"],
                             creationflags=subprocess.CREATE_NO_WINDOW)
            await asyncio.sleep(3.5)
        except Exception:
            pass

    if gw:
        for w in gw.getAllWindows():
            if "WhatsApp" in w.title:
                try:
                    w.activate()
                    if not w.isMaximized: w.maximize()
                    await asyncio.sleep(0.8)
                    return True
                except Exception:
                    pass

    # Win key fallback
    try:
        pyautogui.press('win')
        await asyncio.sleep(0.8)
        pyperclip.copy("WhatsApp")
        pyautogui.hotkey('ctrl', 'v')
        await asyncio.sleep(1.5)
        pyautogui.press('enter')
        await asyncio.sleep(3.0)
        return True
    except Exception:
        pass
    return False


async def _wa_search_contact(contact: str):
    """
    Contact search karo — pyautogui.write() se directly type karo.
    write() IME bypass karta hai — clipboard/paste nahi use hota.
    Exactly wahi approach jo whatsapp.py mein kaam karta hai.
    """
    # Step 1: Search bar open karo
    pyautogui.hotkey('ctrl', 'f')
    await asyncio.sleep(0.8)

    # Step 2: Clear previous search
    pyautogui.hotkey('ctrl', 'a')
    await asyncio.sleep(0.1)
    pyautogui.press('backspace')
    await asyncio.sleep(0.2)

    # Step 3: Contact naam directly type karo — IME bypass, English guaranteed
    # interval=0.07 se slow type hota hai — results load ho jaate hain
    pyautogui.write(contact, interval=0.07)
    await asyncio.sleep(2.0)   # Search results load hone ka wait

    # Step 4: First result select karo
    pyautogui.press('down')
    await asyncio.sleep(0.3)
    pyautogui.press('enter')
    await asyncio.sleep(2.0)   # Chat load hone ka wait


async def whatsapp_send_message(message: str, contact: str = "") -> str:
    """WhatsApp pe message bhejo contact ko — English contact naam, English message."""
    try:
        ok = await _focus_or_open_whatsapp()
        if not ok:
            return "❌ WhatsApp nahi khul saka"
        await asyncio.sleep(0.8)

        if contact:
            await _wa_search_contact(contact)
            await asyncio.sleep(0.5)

        # Message paste karo — pyperclip + ctrl+v
        # Note: message mein Hindi bhi ho sakta hai (user ka message)
        # toh clipboard use karo, contact search ke liye write() use kiya
        if pyperclip:
            pyperclip.copy(message)
            await asyncio.sleep(0.2)
            pyautogui.hotkey('ctrl', 'v')
        else:
            pyautogui.write(message, interval=0.02)
        await asyncio.sleep(0.6)

        # Send
        pyautogui.press('enter')
        await asyncio.sleep(0.8)

        who = f"'{contact}'" if contact else "current chat"
        return f"✅ {who} ko message bheja: {message}"
    except Exception as e:
        return f"❌ Error: {e}"


async def whatsapp_open_chat(contact: str) -> str:
    """Kisi contact ka WhatsApp chat kholo"""
    try:
        ok = await _focus_or_open_whatsapp()
        if not ok: return "❌ WhatsApp nahi khul saka"
        await asyncio.sleep(0.5)
        await _wa_search_contact(contact)
        return f"✅ {contact} ka chat khul gaya"
    except Exception as e:
        return f"❌ Error: {e}"


async def whatsapp_reply_last(reply: str) -> str:
    """Current WhatsApp chat mein reply karo"""
    try:
        ok = await _focus_or_open_whatsapp()
        if not ok: return "❌ WhatsApp nahi mila"
        await asyncio.sleep(0.3)
        pyautogui.press('tab')
        await asyncio.sleep(0.3)
        _set_clipboard_raw(reply)
        pyautogui.hotkey('ctrl', 'v')
        await asyncio.sleep(0.3)
        pyautogui.press('enter')
        return f"✅ Reply bheja: {reply}"
    except Exception as e:
        return f"❌ Error: {e}"


async def whatsapp_read_last_message() -> str:
    """WhatsApp screen se last message padho"""
    try:
        ok = await _focus_or_open_whatsapp()
        if not ok: return "❌ WhatsApp nahi mila"
        await asyncio.sleep(0.4)
        text = await asyncio.to_thread(_ocr_screen)
        if not text or len(text.strip()) < 5:
            return "❌ WhatsApp screen pe koi text nahi mila"
        skip = ["type a message","online","typing...","search","today","yesterday",
                "end-to-end encrypted","archived","filter","emoji","attach"]
        lines = [l.strip() for l in text.splitlines()
                 if len(l.strip()) > 2 and not any(x in l.lower() for x in skip)]
        return "📱 WhatsApp:\n" + "\n".join(lines[-12:]) if lines else "❌ Koi message nahi mila"
    except Exception as e:
        return f"❌ Error: {e}"


async def whatsapp_wait_for_reply(wait_seconds: int = 30) -> str:
    """New message aane ka wait karo"""
    try:
        await _focus_or_open_whatsapp()
        initial = await whatsapp_read_last_message()
        for _ in range(max(1, wait_seconds // 3)):
            await asyncio.sleep(3)
            current = await whatsapp_read_last_message()
            if current != initial and "❌" not in current:
                return f"🔔 Naya message aaya!\n\n{current}"
        return f"ℹ️ {wait_seconds}s mein koi naya message nahi aaya"
    except Exception as e:
        return f"❌ Error: {e}"

# ══════════════════════════════════════════════════════════
# 21. CODE WRITER — koi bhi code likho, file save karo, run karo
# ══════════════════════════════════════════════════════════

CODE_DIR = os.path.join(os.path.expanduser("~"), "Documents", "TITAN_Code")
os.makedirs(CODE_DIR, exist_ok=True)

# Language → file extension + run command
LANG_CONFIG = {
    "python":     {"ext": ".py",   "run": ["python", "{file}"]},
    "py":         {"ext": ".py",   "run": ["python", "{file}"]},
    "javascript": {"ext": ".js",   "run": ["node",   "{file}"]},
    "js":         {"ext": ".js",   "run": ["node",   "{file}"]},
    "html":       {"ext": ".html", "run": None},   # browser mein khulega
    "css":        {"ext": ".css",  "run": None},
    "java":       {"ext": ".java", "run": ["java",  "{file}"]},
    "c":          {"ext": ".c",    "run": None},
    "cpp":        {"ext": ".cpp",  "run": None},
    "csharp":     {"ext": ".cs",   "run": None},
    "cs":         {"ext": ".cs",   "run": None},
    "batch":      {"ext": ".bat",  "run": ["{file}"]},
    "bat":        {"ext": ".bat",  "run": ["{file}"]},
    "powershell": {"ext": ".ps1",  "run": ["powershell", "-File", "{file}"]},
    "ps1":        {"ext": ".ps1",  "run": ["powershell", "-File", "{file}"]},
    "sql":        {"ext": ".sql",  "run": None},
    "text":       {"ext": ".txt",  "run": None},
    "txt":        {"ext": ".txt",  "run": None},
}

def _detect_editor():
    """VS Code, Notepad++, Notepad — properly detect karo."""
    # VS Code paths
    vscode_paths = [
        os.path.join(os.environ.get("LOCALAPPDATA",""), "Programs","Microsoft VS Code","Code.exe"),
        r"C:\Program Files\Microsoft VS Code\Code.exe",
        r"C:\Program Files (x86)\Microsoft VS Code\Code.exe",
    ]
    for vp in vscode_paths:
        if os.path.exists(vp):
            return "VS Code", [vp, "{file}"]

    # VS Code via PATH
    try:
        result = subprocess.run(["where","code"], capture_output=True, text=True, timeout=3)
        if result.returncode == 0 and result.stdout.strip():
            return "VS Code", ["code", "{file}"]
    except Exception: pass

    # Notepad++
    npp_paths = [
        r"C:\Program Files\Notepad++\notepad++.exe",
        r"C:\Program Files (x86)\Notepad++\notepad++.exe",
        os.path.join(os.environ.get("PROGRAMFILES",""), "Notepad++","notepad++.exe"),
    ]
    for np in npp_paths:
        if os.path.exists(np):
            return "Notepad++", [np, "{file}"]

    # Windows Notepad (always exists)
    notepad = os.path.join(os.environ.get("SystemRoot","C:\\Windows"),
                           "System32","notepad.exe")
    return "Notepad", [notepad, "{file}"]

async def write_code(
    code: str,
    language: str = "python",
    filename: str = "",
    run_after: bool = True,
    open_editor: bool = True
) -> str:
    """
    Koi bhi code likho aur file mein save karo.
    Automatically editor (VS Code / Notepad) mein khulega.
    run_after=True hone par code bhi run ho jaata hai.

    Parameters:
      code        — likhna wala code
      language    — python / javascript / html / java / batch etc
      filename    — file ka naam (optional, auto-generate hota hai)
      run_after   — code run karo? (True/False)
      open_editor — editor mein kholo? (True/False)
    """
    def _write():
        lang = language.lower().strip()
        cfg  = LANG_CONFIG.get(lang, {"ext": f".{lang}", "run": None})
        ext  = cfg["ext"]
        run_cmd_template = cfg["run"]

        # Filename decide karo
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        if filename:
            fname = filename if filename.endswith(ext) else filename + ext
        else:
            # Auto name from first comment or timestamp
            first_line = code.strip().splitlines()[0] if code.strip() else ""
            safe = "".join(c if c.isalnum() or c in "-_" else "_"
                           for c in first_line.replace("#","").replace("//","").strip()[:30])
            fname = f"{safe or 'TITAN_code'}_{ts}{ext}"

        fpath = os.path.join(CODE_DIR, fname)

        # Code file save karo
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(code)

        result_lines = [f"✅ Code saved: {fpath}"]

        # Editor mein kholo
        if open_editor:
            editor_name, editor_cmd = _detect_editor()
            cmd = [c.replace("{file}", fpath) for c in editor_cmd]
            opened = False
            try:
                subprocess.Popen(cmd)
                result_lines.append(f"📝 Opened in {editor_name}")
                opened = True
            except Exception:
                try:
                    # Guaranteed fallback: Windows shell open
                    os.startfile(fpath)
                    result_lines.append("📝 Opened in default editor")
                    opened = True
                except Exception as e2:
                    result_lines.append(f"⚠️ Could not open editor: {e2}")

        # HTML → browser mein kholo
        if ext == ".html":
            try:
                import webbrowser
                webbrowser.open(f"file:///{fpath.replace(os.sep, '/')}")
                result_lines.append("🌐 Opened in browser")
            except Exception: pass
            run_after_local = False
        else:
            run_after_local = run_after

        # Code run karo
        if run_after_local and run_cmd_template:
            try:
                cmd_run = [c.replace("{file}", fpath) for c in run_cmd_template]
                # New terminal window mein run karo
                subprocess.Popen(
                    ["cmd", "/k"] + cmd_run,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    cwd=CODE_DIR
                )
                result_lines.append(f"▶️ Running in terminal: {' '.join(cmd_run)}")
            except Exception as e:
                result_lines.append(f"⚠️ Run error: {e}")

        # Show folder
        subprocess.Popen(
            f'explorer /select,"{fpath}"',
            shell=True,
            creationflags=subprocess.CREATE_NO_WINDOW
        )
        return "\n".join(result_lines)

    return await asyncio.to_thread(_write)


async def run_code_file(filename: str) -> str:
    """Pehle se save ki gayi code file run karo"""
    def _run():
        candidates = list(Path(CODE_DIR).glob(f"*{filename}*"))
        if not candidates:
            for d in ["Desktop", "Downloads", "Documents"]:
                p = Path(os.path.expanduser("~")) / d
                candidates.extend(p.glob(f"*{filename}*"))
        if not candidates:
            return f"❌ File nahi mili: {filename}"

        fpath = str(candidates[0])
        ext   = Path(fpath).suffix.lower()
        ext_to_lang = {
            ".py":"python", ".js":"javascript", ".bat":"batch",
            ".ps1":"powershell", ".java":"java", ".html":"html"
        }
        lang = ext_to_lang.get(ext)
        if not lang:
            os.startfile(fpath)
            return f"✅ Opened: {fpath}"

        cfg = LANG_CONFIG.get(lang, {})
        run_cmd_template = cfg.get("run")
        if not run_cmd_template:
            os.startfile(fpath)
            return f"✅ Opened: {fpath}"

        cmd_run = [c.replace("{file}", fpath) for c in run_cmd_template]
        subprocess.Popen(
            ["cmd", "/k"] + cmd_run,
            creationflags=subprocess.CREATE_NEW_CONSOLE,
            cwd=str(Path(fpath).parent)
        )
        return f"▶️ Running: {Path(fpath).name}"

    return await asyncio.to_thread(_run)


# ══════════════════════════════════════════════════════════
# 22. SCREEN READER — Windows.Media.Ocr (built-in, no install)
# ══════════════════════════════════════════════════════════
# Windows 10/11 mein built-in OCR hai — Tesseract ki zaroorat nahi
# pip install mss  (fast screenshot)

_ocr_engine = None   # cached engine

def _get_windows_ocr_engine():
    """Windows.Media.Ocr engine — ek baar banao, cache karo."""
    global _ocr_engine
    if _ocr_engine is not None:
        return _ocr_engine
    try:
        import winrt.windows.media.ocr as _ocr
        import winrt.windows.globalization as _glob
        # English engine
        lang = _glob.Language("en-US")
        if _ocr.OcrEngine.is_language_supported(lang):
            _ocr_engine = _ocr.OcrEngine.try_create_from_language(lang)
        else:
            _ocr_engine = _ocr.OcrEngine.try_create_from_user_profile_languages()
        return _ocr_engine
    except Exception:
        return None


def _take_screenshot_bytes(region=None):
    """
    Fast screenshot — mss (fastest) ya pyautogui fallback.
    region: None = full screen, ya (left, top, width, height)
    Returns PIL Image.
    """
    try:
        import mss, mss.tools
        from PIL import Image as _PIL
        with mss.mss() as sct:
            if region:
                l, t, w, h = region
                mon = {"left": l, "top": t, "width": w, "height": h}
            else:
                mon = sct.monitors[1]   # primary monitor
            shot = sct.grab(mon)
            img  = _PIL.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            return img
    except ImportError:
        pass
    # Fallback: pyautogui
    import pyautogui as _pag
    img = _pag.screenshot()
    if region:
        l, t, w, h = region
        img = img.crop((l, t, l+w, t+h))
    return img


async def _ocr_image_windows(pil_img) -> str:
    """
    Windows.Media.Ocr se image ka text nikalo.
    Pure async — UI block nahi hoti.
    """
    def _run_ocr(img):
        try:
            import asyncio as _asyncio
            import winrt.windows.media.ocr as _ocr
            import winrt.windows.graphics.imaging as _img_mod
            import winrt.windows.storage.streams as _streams
            import io

            engine = _get_windows_ocr_engine()
            if not engine:
                return None

            # PIL → bytes → SoftwareBitmap
            buf = io.BytesIO()
            img.save(buf, format="BMP")
            buf.seek(0)
            bmp_bytes = buf.read()

            # Use winrt to create SoftwareBitmap from BMP bytes
            # Run inner async in new loop
            async def _inner():
                ra_stream  = _streams.InMemoryRandomAccessStream()
                writer     = _streams.DataWriter(ra_stream)
                writer.write_bytes(list(bmp_bytes))
                await writer.store_async()
                ra_stream.seek(0)

                decoder = await _img_mod.BitmapDecoder.create_async(ra_stream)
                soft_bmp = await decoder.get_software_bitmap_async()

                result = await engine.recognize_async(soft_bmp)
                return result.text if result else ""

            loop = _asyncio.new_event_loop()
            text = loop.run_until_complete(_inner())
            loop.close()
            return text

        except Exception as e:
            return None   # fallback to other method

    return await asyncio.to_thread(_run_ocr, pil_img)


def _ocr_fallback_pywin32(pil_img) -> str:
    """
    pytesseract se OCR — 3 strategies, dark screen bhi handle karta hai.
    Tesseract path auto-detect karta hai.
    """
    if not pil_img:
        return ""

    # Auto-find Tesseract
    tess_paths = [
        r"C:\Users\Ali\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.join(os.environ.get("LOCALAPPDATA",""),
                     "Programs","Tesseract-OCR","tesseract.exe"),
        os.path.join(os.environ.get("USERPROFILE",""),
                     "AppData","Local","Tesseract-OCR","tesseract.exe"),
    ]

    try:
        import pytesseract

        # Tesseract path set karo
        tess_found = ""
        for tp in tess_paths:
            if os.path.exists(tp):
                tess_found = tp
                break
        if not tess_found:
            try:
                r = subprocess.run(["where","tesseract"],
                                   capture_output=True, text=True, timeout=3)
                if r.returncode == 0:
                    tess_found = r.stdout.strip().splitlines()[0]
            except Exception:
                pass

        if tess_found:
            pytesseract.pytesseract.tesseract_cmd = tess_found
        else:
            return ""

        results = []

        # Strategy 1: Original RGB — UI text ke liye
        try:
            t = pytesseract.image_to_string(
                pil_img, config="--psm 6 --oem 3"
            ).strip()
            if t: results.append(t)
            if len(max(results, key=len)) >= 120:   # kaafi text mil gaya — bhaari strategies skip (8s -> ~2s)
                return max(results, key=len)
        except Exception:
            pass

        # Strategy 2: 3x scale + dark-bg invert
        try:
            from PIL import ImageEnhance, ImageOps, Image as _I
            w, h = pil_img.size
            big  = pil_img.resize((w * 3, h * 3), _I.LANCZOS)
            gray = big.convert("L")
            import numpy as _np
            if _np.array(gray).mean() < 100:   # dark background
                gray = ImageOps.invert(gray)
            gray = ImageEnhance.Contrast(gray).enhance(2.5)
            t = pytesseract.image_to_string(
                gray, config="--psm 6 --oem 3"
            ).strip()
            if t: results.append(t)
            if len(max(results, key=len)) >= 120:   # kaafi text mil gaya — bhaari strategies skip (8s -> ~2s)
                return max(results, key=len)
        except Exception:
            pass

        # Strategy 3: Binary threshold
        try:
            from PIL import Image as _I
            w, h   = pil_img.size
            big    = pil_img.resize((w * 2, h * 2), _I.LANCZOS)
            gray   = big.convert("L")
            thresh = gray.point(lambda x: 0 if x < 128 else 255, "L")
            t = pytesseract.image_to_string(
                thresh, config="--psm 6 --oem 3"
            ).strip()
            if t: results.append(t)
        except Exception:
            pass

        if not results:
            return ""
        # Sabse lamba result best hota hai
        return max(results, key=lambda x: len(x))

    except ImportError:
        print("[OCR] pytesseract not installed: pip install pytesseract")
        return ""
    except Exception as e:
        print(f"[OCR] Error: {e}")
        return ""


async def read_screen(region: str = "full") -> str:
    """
    Screen pe jo text dikh raha hai wo padho.
    Windows built-in OCR use karta hai — koi install nahi chahiye.
    region: full | top | bottom | left | right | center
    """
    try:
        # Screenshot
        def _shot():
            try:
                import mss
                from PIL import Image as _PIL
                with mss.mss() as sct:
                    m = sct.monitors[1]
                    s = sct.grab(m)
                    return _PIL.frombytes("RGB", s.size, s.bgra, "raw", "BGRX")
            except Exception:
                return pyautogui.screenshot()

        img = await asyncio.to_thread(_shot)

        # Crop
        w, h = img.size
        crops = {
            "full":   (0,    0,    w,   h),
            "top":    (0,    0,    w,   h//2),
            "bottom": (0,    h//2, w,   h),
            "left":   (0,    0,    w//2,h),
            "right":  (w//2, 0,    w,   h),
            "center": (w//4, h//4, 3*w//4, 3*h//4),
        }
        img = img.crop(crops.get(region.lower(), (0, 0, w, h)))

        # OCR
        text = await asyncio.to_thread(_ocr_fallback_pywin32, img)

        # Pytesseract fallback
        if not text:
            try:
                import pytesseract
                for tp in [
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                ]:
                    if os.path.exists(tp):
                        pytesseract.pytesseract.tesseract_cmd = tp
                        break
                text = pytesseract.image_to_string(img, config="--psm 6")
            except Exception:
                pass

        if not text or len(text.strip()) < 3:
            return "❌ Screen pe koi text nahi mila. Kya screen pe kuch likha hua hai?"

        lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 1]
        return f"🖥️ Screen ({region}):\n" + "\n".join(lines[:80])

    except Exception as e:
        return f"❌ Screen read error: {e}"


async def read_active_window() -> str:
    """Jo window abhi active hai uska text padho."""
    try:
        buf  = ctypes.create_unicode_buffer(512)
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
        title = buf.value.strip()

        class RECT(ctypes.Structure):
            _fields_ = [("left",   ctypes.c_long), ("top",    ctypes.c_long),
                        ("right",  ctypes.c_long), ("bottom", ctypes.c_long)]
        rect = RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))

        l = max(0, rect.left);   t = max(0, rect.top)
        w = max(100, rect.right - rect.left)
        h = max(100, rect.bottom - rect.top)

        def _shot_win():
            try:
                import mss
                from PIL import Image as _PIL
                with mss.mss() as sct:
                    m = {"left": l, "top": t, "width": w, "height": h}
                    s = sct.grab(m)
                    return _PIL.frombytes("RGB", s.size, s.bgra, "raw", "BGRX")
            except Exception:
                img = pyautogui.screenshot()
                return img.crop((l, t, l+w, t+h))

        img  = await asyncio.to_thread(_shot_win)
        text = await asyncio.to_thread(_ocr_fallback_pywin32, img)

        if not text or len(text.strip()) < 3:
            return await read_screen("full")

        lines = [l2.strip() for l2 in text.splitlines() if len(l2.strip()) > 1]
        return f"🪟 {title}:\n" + "\n".join(lines[:80])

    except Exception as e:
        return f"❌ Error: {e}"


def _ocr_screen():
    """
    WhatsApp aur baaki jagah use hone wala sync OCR.
    Windows.Media.Ocr PowerShell fallback.
    """
    try:
        img  = _take_screenshot_bytes()
        # PowerShell OCR (sync)
        text = _ocr_fallback_pywin32(img)
        if not text:
            # pytesseract last resort
            try:
                import pytesseract
                for tp in [
                    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                ]:
                    if os.path.exists(tp):
                        pytesseract.pytesseract.tesseract_cmd = tp
                        break
                import numpy as _np, cv2 as _cv2
                from PIL import Image as _P
                arr = _np.array(img.convert("L"))
                _, b = _cv2.threshold(arr, 0, 255,
                    _cv2.THRESH_BINARY + _cv2.THRESH_OTSU)
                text = pytesseract.image_to_string(b, config="--psm 6")
            except Exception:
                pass
        return text or ""
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════
# 20. BRIGHTNESS & SYSTEM STATUS  (Fixed — no wmi needed)
# ══════════════════════════════════════════════════════════

async def adjust_brightness(action: str = "get", level: int = 50) -> str:
    """Screen brightness adjust karo: get/set/increase/decrease"""
    def _get():
        try:
            import wmi
            c = wmi.WMI(namespace='wmi')
            return c.WmiMonitorBrightness()[0].CurrentBrightness
        except: return -1
    def _set(lv):
        try:
            import wmi
            c = wmi.WMI(namespace='wmi')
            c.WmiMonitorBrightnessMethods()[0].WmiSetBrightness(lv, 0)
            return True
        except:
            # Fallback: PowerShell se brightness set karo
            try:
                lv = max(0, min(100, lv))
                script = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{lv})"
                subprocess.run(["powershell","-Command", script], capture_output=True, timeout=3)
                return True
            except: return False
    try:
        action = action.lower().strip()
        if action == "get":
            v = await asyncio.to_thread(_get)
            return f"💡 Brightness: {v}%" if v >= 0 else "💡 Brightness read nahi ho saki"
        elif action == "set":
            level = max(0, min(100, level))
            ok = await asyncio.to_thread(_set, level)
            return f"✅ Brightness {level}% set ho gayi" if ok else "❌ Brightness set nahi ho saki"
        elif action == "increase":
            cur = await asyncio.to_thread(_get)
            new = min(100, (cur if cur>=0 else 50) + 15)
            ok  = await asyncio.to_thread(_set, new)
            return f"✅ Brightness badh ke {new}% ho gayi" if ok else "❌ Failed"
        elif action == "decrease":
            cur = await asyncio.to_thread(_get)
            new = max(0, (cur if cur>=0 else 50) - 15)
            ok  = await asyncio.to_thread(_set, new)
            return f"✅ Brightness ghath ke {new}% ho gayi" if ok else "❌ Failed"
        return "❌ Action: get/set/increase/decrease"
    except Exception as e: return f"❌ Error: {e}"

async def get_battery_status() -> str:
    """Battery level aur charging status dekho"""
    def _bat():
        try:
            bat = psutil.sensors_battery()
            if not bat: return "⚠️ Battery info nahi mili (desktop ho sakta hai)"
            pct = bat.percent
            chg = bat.power_plugged
            em  = "✅" if pct>80 else "🟢" if pct>50 else "🟡" if pct>20 else "🔴"
            return f"{em} Battery: {pct:.0f}% | {'🔌 Charging' if chg else '🔋 Battery pe chal raha hai'}"
        except Exception as e: return f"❌ {e}"
    return await asyncio.to_thread(_bat)

async def get_system_status() -> str:
    """CPU, RAM, Disk ka status dekho"""
    def _sys():
        try:
            cpu  = psutil.cpu_percent(interval=0.1)
            mem  = psutil.virtual_memory()
            disk = psutil.disk_usage("C:\\")
            return (f"📊 System Status\n"
                    f"CPU:  {'✅' if cpu<50 else '🟡' if cpu<80 else '🔴'} {cpu:.0f}%\n"
                    f"RAM:  {'✅' if mem.percent<50 else '🟡' if mem.percent<80 else '🔴'} "
                    f"{mem.percent:.0f}% ({mem.used/1e9:.1f}/{mem.total/1e9:.1f} GB)\n"
                    f"Disk: {'✅' if disk.percent<80 else '🟡'} {disk.percent:.0f}% "
                    f"({disk.free/1e9:.1f} GB free)")
        except Exception as e: return f"❌ {e}"
    return await asyncio.to_thread(_sys)


# ══════════════════════════════════════════════════════════
# GEMINI TOOL DECLARATIONS
# ══════════════════════════════════════════════════════════

def _p(props: dict, req: list = []):
    return {"type":"object","properties":{k:{"type":v} for k,v in props.items()},"required":req}

TOOL_DECLARATIONS = [
  # System
  {"name":"play_on_youtube",      "description":"YouTube pe video/song chalao",                    "parameters":_p({"topic":"string"},["topic"])},
  {"name":"search_on_google",     "description":"Google pe search karo",                           "parameters":_p({"query":"string"},["query"])},
  {"name":"system_control",       "description":"System control: volume_up/down, mute, lock, sleep, shutdown, restart, abort_shutdown", "parameters":_p({"command":"string"},["command"])},
  {"name":"execute_shortcut",     "description":"Windows shortcut: file_explorer, settings, screenshot_tool, show_desktop, emoji, clipboard_history", "parameters":_p({"shortcut_name":"string"},["shortcut_name"])},
  # App Launcher — path ki zaroorat nahi, naam se khulega
  {"name":"open_app",             "description":"PC par install KOI BHI app (Microsoft Store apps samet) sirf naam se kholo — installed apps khud dhoondhe jaate hain. Pehle se khula ho to saamne aata hai.", "parameters":_p({"app_name":"string","text":"string"},["app_name"])},
  {"name":"play_on_spotify",     "description":"Spotify APP par gaana/artist/album/playlist chalao (Spotify ka naam aaye ya user Spotify pe sunna chahe). query = sirf gaane/artist ka naam (jaise 'tum hi ho arijit singh'). kind: auto|song|artist|album|playlist.", "parameters":_p({"query":"string","kind":"string"},["query"])},
  {"name":"set_language",       "description":"User jis language mein baat karna chahe wo set karo (duniya ki koi bhi: Hindi, English, Spanish, Japanese, Tamil, Arabic...). 'English mein baat karo', 'speak Spanish', 'tamil mein bolo', 'Hinglish' jaise kehne par call karo. language = language ka naam; 'auto' = wapas Hinglish.", "parameters":_p({"language":"string"},["language"])},
  {"name":"set_user_name",       "description":"User ka naam save karo jab wo apna naam bataye ('mera naam Ali hai', 'mujhe Ali bulao'). name = sirf naam.", "parameters":_p({"name":"string"},["name"])},
  {"name":"list_installed_apps",  "description":"PC par kaun-kaun se apps install hain unki list (optional naam filter)", "parameters":_p({"filter_text":"string"})},
  {"name":"refresh_app_list",     "description":"Naya app install kiya ho to installed apps ki list dobara scan karo", "parameters":_p({})},
  {"name":"open_app_and_do",      "description":"App kholo AUR usme text likho (notepad/word/wordpad etc.). action = jo POORA text likhna hai — user ne text bataya ho to wahi, na bataya ho ('kuch likho') to khud accha text banakar do. Khali mat chhodo.", "parameters":_p({"app_name":"string","action":"string"},["app_name","action"])},
  {"name":"control_media",        "description":"Media: play_pause, next, previous, stop",         "parameters":_p({"action":"string"},["action"])},
  # Desktop
  {"name":"set_system_theme",     "description":"Theme badlo: dark ya light",                      "parameters":_p({"mode":"string"},["mode"])},
  {"name":"open_folder",          "description":"Folder kholo: downloads, documents, desktop etc","parameters":_p({"folder_name":"string"},["folder_name"])},
  {"name":"snap_window",          "description":"Window snap: left, right, up, down",              "parameters":_p({"direction":"string"},["direction"])},
  {"name":"empty_recycle_bin",    "description":"Recycle Bin saaf karo",                           "parameters":_p({})},
  {"name":"toggle_desktop_icons", "description":"Desktop icons show/hide karo",                   "parameters":_p({"visible":"boolean"})},
  {"name":"zoom_screen",          "description":"Screen zoom: in, out, reset",                     "parameters":_p({"action":"string"},["action"])},
  # Clipboard
  {"name":"get_clipboard",        "description":"Clipboard content dekho",                         "parameters":_p({})},
  {"name":"set_clipboard",        "description":"Text clipboard mein copy karo",                   "parameters":_p({"text":"string"},["text"])},
  {"name":"edit_text",            "description":"Text edit: copy, paste, cut, undo, redo, select_all","parameters":_p({"action":"string"},["action"])},
  # Digital
  {"name":"generate_password",    "description":"Strong password banao",                           "parameters":_p({"length":"integer"})},
  {"name":"create_qr_code",       "description":"QR code banao kisi text ya URL ka",               "parameters":_p({"text":"string"})},
  # Files
  {"name":"find_file",            "description":"File dhoondo. filename, folder (optional), file_type (optional, e.g. .pdf), newest (boolean) parameters do.", "parameters":_p({"filename":"string","folder":"string","file_type":"string","newest":"boolean"},["filename"])},
  {"name":"organize_downloads",   "description":"Downloads folder organize karo",                  "parameters":_p({})},
  # Screenshot & Camera
  {"name":"take_screenshot",      "description":"Screenshot lo",                                   "parameters":_p({})},
  {"name":"open_camera",          "description":"Webcam kholo",                                    "parameters":_p({})},
  # Download
  {"name":"download_youtube",     "description":"YouTube video download karo",                     "parameters":_p({"url_or_query":"string"})},
  # Network
  {"name":"get_ip_info",          "description":"IP aur location info",                            "parameters":_p({"ip":"string"})},
  {"name":"check_internet_speed", "description":"Internet speed check karo",                       "parameters":_p({})},
  {"name":"get_wifi_passwords",   "description":"Saved WiFi passwords dekho",                      "parameters":_p({})},
  {"name":"get_news",             "description":"Latest news lo",                                  "parameters":_p({"topic":"string"})},
  {"name":"search_wikipedia",     "description":"Wikipedia pe search karo",                        "parameters":_p({"query":"string"},["query"])},
  # Notes
  {"name":"create_note",          "description":"Quick note banao",                                "parameters":_p({"content":"string","filename":"string"},["content"])},
  {"name":"read_latest_note",     "description":"Sabse latest note padho",                         "parameters":_p({})},
  # Notifications
  {"name":"send_notification",    "description":"Windows desktop notification bhejo",              "parameters":_p({"title":"string","message":"string"},["title","message"])},
  # Processes
  {"name":"list_processes",       "description":"Running processes list karo",                     "parameters":_p({"filter_name":"string"})},
  {"name":"terminate_process",    "description":"Process band karo",                               "parameters":_p({"process_name":"string"},["process_name"])},
  # Timer
  {"name":"set_timer",            "description":"Timer set karo",                                  "parameters":_p({"seconds":"integer","label":"string"},["seconds"])},
  # Recording
  {"name":"record_voice",         "description":"Voice record karo",                               "parameters":_p({"duration_seconds":"integer"})},
  {"name":"record_screen",        "description":"Screen record karo",                              "parameters":_p({"duration_seconds":"integer"})},
  # Wallpaper
  {"name":"change_wallpaper",     "description":"Wallpaper badlo",                                 "parameters":_p({"image_path":"string"})},
  # Window Manager
  {"name":"get_open_windows",     "description":"Sab open windows ki list",                        "parameters":_p({})},
  {"name":"manage_window",        "description":"Window manage karo: activate, minimize, maximize, restore, close","parameters":_p({"title":"string","action":"string"},["title","action"])},
  # Security
  {"name":"start_security_mode",  "description":"Security/motion detection mode shuru karo",       "parameters":_p({})},
  {"name":"stop_security_mode",   "description":"Security mode band karo",                         "parameters":_p({})},
  # Cleaner
  {"name":"clean_system",         "description":"Temp files aur junk saaf karo",                   "parameters":_p({})},
  # PDF
  {"name":"read_pdf",             "description":"PDF file padho",                                  "parameters":_p({"file_path":"string"},["file_path"])},
  {"name":"merge_pdfs",           "description":"Ek folder ke sab PDFs merge karo",                "parameters":_p({"folder":"string","output_name":"string"},["folder"])},
  {"name":"images_to_pdf",        "description":"Images ko PDF mein convert karo",                 "parameters":_p({"folder":"string","output_name":"string"},["folder"])},
  # System Status & Brightness
  {"name":"get_battery_status",    "description":"Battery level aur charging status dekho",            "parameters":_p({})},
  {"name":"get_system_status",     "description":"CPU RAM Disk ka system status dekho",                 "parameters":_p({})},
  {"name":"adjust_brightness",     "description":"Screen brightness: get/set/increase/decrease",        "parameters":_p({"action":"string","level":"integer"})},
  # WhatsApp
  {"name":"whatsapp_read_last_message","description":"WhatsApp ka last message padho",                 "parameters":_p({})},
  {"name":"whatsapp_send_message",     "description":"WhatsApp pe message bhejo — contact naam do toh search karega in english text", "parameters":_p({"message":"string","contact":"string"},["message"])},
  {"name":"whatsapp_reply_last",       "description":"Current WhatsApp chat mein reply karo",          "parameters":_p({"reply":"string"},["reply"])},
  {"name":"whatsapp_wait_for_reply",   "description":"WhatsApp mein naya message aane ka wait karo",   "parameters":_p({"wait_seconds":"integer"})},
  {"name":"whatsapp_open_chat",        "description":"WhatsApp mein contact ka chat kholo",            "parameters":_p({"contact":"string"},["contact"])},
  # Code Writer
  {"name":"write_code", "description":"Koi bhi code likho (Python/JS/HTML/batch etc) aur VS Code ya Notepad mein kholo. User jo bhi banane ko bole — login page, calculator, game, tool — seedha file mein likh ke run karo.",
   "parameters":_p({"code":"string","language":"string","filename":"string","run_after":"boolean","open_editor":"boolean"},["code"])},
  {"name":"run_code_file", "description":"Pehle se save ki hui code file run karo",
   "parameters":_p({"filename":"string"},["filename"])},
  # Screen Reader
  {"name":"read_screen", "description":"Screen pe jo kuch bhi dikh raha hai uska text padho — kisi bhi app ka content, error message, webpage text. region: full/top/bottom/left/right/center",
   "parameters":_p({"region":"string"})},
  {"name":"read_active_window", "description":"Jo window abhi active/foreground mein hai uska title aur content padho",
   "parameters":_p({})},
]

# ══════════════════════════════════════════════════════════
# TOOL DISPATCHER
# ══════════════════════════════════════════════════════════

TOOL_MAP = {
    "play_on_youtube":play_on_youtube,"search_on_google":search_on_google,
    "system_control":system_control,"execute_shortcut":execute_shortcut,
    "open_app":open_app,"open_app_and_do":open_app_and_do,
    "set_user_name":set_user_name,"set_language":set_language,"play_on_spotify":play_on_spotify,"list_installed_apps":list_installed_apps,"refresh_app_list":refresh_app_list,
    "control_media":control_media,"set_system_theme":set_system_theme,
    "open_folder":open_folder,"snap_window":snap_window,
    "empty_recycle_bin":empty_recycle_bin,"toggle_desktop_icons":toggle_desktop_icons,
    "zoom_screen":zoom_screen,"get_clipboard":get_clipboard,
    "set_clipboard":set_clipboard,"edit_text":edit_text,
    "generate_password":generate_password,"create_qr_code":create_qr_code,
    "find_file":find_file,"organize_downloads":organize_downloads,
    "take_screenshot":take_screenshot,"open_camera":open_camera,
    "download_youtube":download_youtube,"get_ip_info":get_ip_info,
    "check_internet_speed":check_internet_speed,"get_wifi_passwords":get_wifi_passwords,
    "get_news":get_news,"search_wikipedia":search_wikipedia,
    "create_note":create_note,"read_latest_note":read_latest_note,
    "send_notification":send_notification,"list_processes":list_processes,
    "terminate_process":terminate_process,"set_timer":set_timer,
    "record_voice":record_voice,"record_screen":record_screen,
    "change_wallpaper":change_wallpaper,"get_open_windows":get_open_windows,
    "manage_window":manage_window,"start_security_mode":start_security_mode,
    "stop_security_mode":stop_security_mode,"clean_system":clean_system,
    "read_pdf":read_pdf,"merge_pdfs":merge_pdfs,"images_to_pdf":images_to_pdf,
    "get_battery_status":get_battery_status,"get_system_status":get_system_status,
    "adjust_brightness":adjust_brightness,
    "whatsapp_read_last_message":whatsapp_read_last_message,
    "whatsapp_send_message":whatsapp_send_message,
    "whatsapp_reply_last":whatsapp_reply_last,
    "whatsapp_wait_for_reply":whatsapp_wait_for_reply,
    "whatsapp_open_chat":whatsapp_open_chat,
    "write_code":write_code,
    "run_code_file":run_code_file,
    "read_screen":read_screen,
    "read_active_window":read_active_window,
}

async def dispatch(name: str, args: dict) -> str:
    fn = TOOL_MAP.get(name)
    if fn: return await fn(**args)
    return f"❌ Tool nahi mila: {name}"