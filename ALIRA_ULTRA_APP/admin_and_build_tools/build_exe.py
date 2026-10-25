# -*- coding: utf-8 -*-
"""
TITAN/ALIRA — EXE Builder  v6  [DISTRIBUTION FIXED]
====================================================
v5 se changes:
  ✅ PortAudio DLL auto-find + bundle (dusre PC pe mic fix)
  ✅ sounddevice properly collected with all deps
  ✅ certifi SSL certs bundled
  ✅ Qt platform plugins bundled
  ✅ _tabbu_rthook.py v3 use hoti hai
  ✅ websockets legacy + asyncio properly bundled
  ✅ numpy DLLs included

Run:
    python build_exe.py            # dono EXE
    python build_exe.py --normal   # sirf TITAN_Normal.exe
    python build_exe.py --hotkey   # sirf TITAN_Hotkey.exe
    python build_exe.py --setup    # dependencies install
    python build_exe.py --check    # pre-build check only
"""
import os, sys, shutil, subprocess, time, tempfile
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.absolute()
os.chdir(BASE_DIR)
ICON = "tabbu_icon.ico"

BUILDS = {
    "hotkey": {"name": "TITAN_Hotkey", "script": "main_hotkey.py",  "desc": "Hidden + Ctrl+Alt+A"},
    "normal": {"name": "TITAN_Normal", "script": "Main_normal.py",  "desc": "Activation → Login → TITAN"},
}

# ── PortAudio DLL finder ───────────────────────────────────────────────────────
def _find_portaudio_dll():
    """sounddevice ke saath aane wala PortAudio DLL dhundho"""
    import importlib.util
    candidates = []

    # 1. sounddevice package ke andar
    try:
        sd_spec = importlib.util.find_spec("sounddevice")
        if sd_spec and sd_spec.origin:
            sd_dir = Path(sd_spec.origin).parent
            for dll in sd_dir.rglob("*.dll"):
                if "portaudio" in dll.name.lower():
                    candidates.append(dll)
            for pyd in sd_dir.rglob("_portaudio*.pyd"):
                candidates.append(pyd)
    except Exception as e:
        print(f"  [PortAudio] sounddevice search: {e}")

    # 2. _sounddevice_data package
    try:
        sd_data_spec = importlib.util.find_spec("_sounddevice_data")
        if sd_data_spec and sd_data_spec.origin:
            sd_data_dir = Path(sd_data_spec.origin).parent
            for dll in sd_data_dir.rglob("*.dll"):
                if "portaudio" in dll.name.lower():
                    candidates.append(dll)
    except Exception:
        pass

    # 3. Python site-packages global search
    try:
        import site
        for sp in site.getsitepackages():
            sp_path = Path(sp)
            for dll in sp_path.rglob("portaudio*.dll"):
                candidates.append(dll)
            for dll in sp_path.rglob("_portaudio*.pyd"):
                candidates.append(dll)
    except Exception:
        pass

    # 4. System PATH
    try:
        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        for d in path_dirs:
            for dll in Path(d).glob("portaudio*.dll") if Path(d).exists() else []:
                candidates.append(dll)
    except Exception:
        pass

    if candidates:
        print(f"  ✅ PortAudio DLL: {candidates[0]}")
        return candidates[0]

    print("  ⚠️  PortAudio DLL nahi mila — mic dusre PC pe kaam nahi karega!")
    print("     Fix: pip install sounddevice (ya pipwin32 portaudio wheel)")
    return None

# ── Data to bundle ────────────────────────────────────────────────────────────
DATA_FILES = [
    ("TABBU.py",                  "."),
    ("TABBU_ui.py",               "."),
    ("ALIRA_ui.py",               "."),
    ("ALIRA_pages.py",            "."),
    ("ALIRA_actions.py",          "."),
    ("ALIRA_quick_features.py", "alira_edge_glow.py", "alira_float_orb.py", "alira_guardian.py", "alira_autostart.py", "alira_prefs.py", "alira_slot.py", "alira_lang.py", "alira_splash.py", "alira_apps.py", "alira_spotify.py",    "."),
    ("alira_edge_glow.py", "."),
    ("alira_float_orb.py", "."),
    ("alira_guardian.py", "."),
    ("alira_autostart.py", "."),
    ("alira_prefs.py", "."),
    ("alira_splash.py", "."),
    ("alira_apps.py", "."),
    ("alira_spotify.py", "."),
    ("alira_studio.py",           "."),
    ("tabbu_modules",             "tabbu_modules"),
    ("alira",                     "alira"),
    ("website_builder",          "website_builder"),
    ("tabbu_office_manage.py",    "."),
    ("Main_normal.py",           "."),
    ("main_hotkey.py",           "."),
    ("tabbu_daemon.py",           "."),
    ("tabbu_startup.py",          "."),
    ("prompt.py",                "."),
    ("normal_prompt.py",         "."),
    ("camera_vision_module.py",  "."),
    ("screen_share_module.py",   "."),
    ("whatsapp_file_sender.py",  "."),
    ("out.wav",                  "."),
    ("tabbu_icon.ico",            "."),
    ("tabbu_memory",              "TABBU_memory"),
    ("tabbu_modules/haarcascade_frontalface_default.xml", "tabbu_modules"),
]

EXCLUDES = [
    "torchaudio", "tensorflow", "keras", "sklearn", "scipy", "pandas",
    "matplotlib", "IPython", "notebook", "jupyter", "acrcloud", "pynvml",
    "PySide6", "tkinter", "test", "unittest", "_pytest", "onnxruntime", "onnx",
    "firebase_admin", "google.cloud.firestore",
]

HIDDEN = [
    # Qt
    "PyQt5.QtWidgets", "PyQt5.QtCore", "PyQt5.QtGui", "PyQt5.sip",
    "PyQt5.QtMultimedia",
    # Network
    "websockets", "websockets.legacy", "websockets.legacy.client",
    "websockets.legacy.server", "websockets.connection",
    "websockets.exceptions", "websockets.frames", "websockets.http11",
    "websockets.streams", "websockets.uri",
    "requests", "requests.adapters", "requests.auth", "requests.cookies",
    "requests.exceptions", "requests.models", "requests.sessions",
    "urllib3", "urllib3.util", "urllib3.util.retry", "urllib3.util.ssl_",
    "certifi", "aiohttp", "urllib.request", "urllib.parse",
    # Audio — CRITICAL for dusre PC
    "sounddevice", "_sounddevice_data",
    "pyaudio", "wave",
    # Async
    "asyncio", "asyncio.events", "asyncio.futures", "asyncio.tasks",
    "asyncio.streams", "asyncio.queues", "asyncio.locks",
    "asyncio.protocols", "asyncio.transports", "asyncio.selector_events",
    "asyncio.windows_events", "asyncio.windows_utils",
    # Crypto (pyrebase)
    "pyrebase", "pyrebase.pyrebase", "python_jwt", "jwcrypto", "jwcrypto.jwt",
    "cryptography", "cryptography.hazmat", "cryptography.hazmat.primitives",
    "cryptography.hazmat.primitives.asymmetric",
    "cryptography.hazmat.backends", "cryptography.hazmat.backends.openssl",
    # Vision
    "cv2", "numpy", "numpy.core", "numpy.core._multiarray_umath",
    "PIL", "PIL.Image", "PIL.ImageDraw", "PIL.ImageEnhance", "PIL.ImageFilter",
    # TTS
    "pyttsx3", "pyttsx3.drivers", "pyttsx3.drivers.sapi5",
    "win32com.client", "win32com.server", "win32api", "win32con",
    "win32gui", "win32process", "pythoncom", "winreg",
    "comtypes", "comtypes.client", "winsound",
    # Gemini
    "google.genai", "google.genai.types", "google.generativeai",
    # Tools
    "psutil", "pyperclip", "pyautogui", "pygetwindow",
    "yt_dlp", "qrcode", "qrcode.image", "qrcode.image.pil",
    "pywhatkit", "duckduckgo_search", "speedtest",
    "phonenumbers", "pypdf", "mss", "mss.windows",
    "pynput", "pynput.keyboard", "pynput.mouse",
    "openpyxl", "docx", "pptx", "win32clipboard",
    "ctypes", "sqlite3", "json", "uuid", "re", "dotenv",
    "threading", "subprocess", "glob", "shutil", "wave",
    "tempfile", "secrets", "pathlib", "datetime", "collections",
    "hashlib", "socket", "jaraco", "jaraco.packaging", "jaraco.text",
    "colorama", "ssl", "certifi",
    # ALIRA modules
    "tabbu_modules.license_client", "tabbu_modules.tabbu_activation",
    "tabbu_modules.firebase_connection", "tabbu_modules.tools",
    "tabbu_modules.cloud_database", "tabbu_modules.face_auth",
    "tabbu_modules.minibar_tabbu", "tabbu_modules.tabbu_advanced_tools",
    "tabbu_modules.TABBU_advanced_features", "tabbu_modules.tabbu_login",
    "tabbu_modules.game_install",
    "ALIRA.cli", "ALIRA.config",
    "prompt", "normal_prompt", "whatsapp_file_sender", "tabbu_office_manage",
    "camera_vision_module", "screen_share_module",
]

HOOK = str(BASE_DIR / "admin_and_build_tools" / "_tabbu_rthook.py")


def _security_check() -> bool:
    jsons = list(Path("tabbu_modules").glob("*adminsdk*.json")) if Path("tabbu_modules").exists() else []
    if jsons:
        print(f"\n  ⚠️  SECURITY: Firebase JSON found in tabbu_modules/:")
        for f in jsons: print(f"      DELETE: {f}")
        return False
    return True


def _pre(script: str) -> bool:
    print(f"  Checking: {script}")
    ok = True
    if not _security_check(): ok = False

    try:
        import PyInstaller
        print(f"  ✅ PyInstaller {PyInstaller.__version__}")
    except ImportError:
        print("  ❌ pip install pyinstaller")
        ok = False

    required = [
        script, "TABBU.py", "TABBU_ui.py", "alira_ui.py", "alira_pages.py", "alira_actions.py", "alira_quick_features.py", "alira_studio.py", "Main_normal.py", "main_hotkey.py",
        "tabbu_modules/license_client.py",
        "tabbu_modules/tabbu_activation.py",
        "tabbu_modules/firebase_connection.py",
        "tabbu_modules/tools.py",
        "tabbu_modules/tabbu_login.py",
        "tabbu_modules/minibar_tabbu.py",
        "tabbu_modules/face_auth.py",
        "tabbu_modules/tabbu_advanced_tools.py",
        "admin_and_build_tools/_tabbu_rthook.py",
        "website_builder/__init__.py",
    ]
    for f in required:
        ok2 = Path(f).exists()
        print(f"  {'✅' if ok2 else '❌'} {f}")
        if not ok2: ok = False

    for f in ["out.wav", "TABBU_icon.ico", "TABBU_modules/haarcascade_frontalface_default.xml"]:
        print(f"  {'✅' if Path(f).exists() else '⚠️  (optional)'} {f}")

    return ok


def _build(key: str) -> bool:
    cfg    = BUILDS[key]
    name   = cfg["name"]
    script = cfg["script"]

    print(f"\n{'=' * 58}")
    print(f"  Building: {name}.exe — {cfg['desc']}")
    print(f"{'=' * 58}")

    if not _pre(script):
        print("  ❌ Pre-checks failed")
        return False

    # ── Find PortAudio DLL ─────────────────────────────────────────────────────
    portaudio_dll = _find_portaudio_dll()

    bdir = Path(tempfile.gettempdir()) / f"TITAN_{key}"
    bdir.mkdir(exist_ok=True)

    for n in [f"{name}.exe"]:
        try: subprocess.run(["taskkill", "/F", "/IM", n], capture_output=True)
        except: pass
    time.sleep(1)

    for d in ["build", "__pycache__"]:
        shutil.rmtree(d, ignore_errors=True)
    for s in Path(".").glob("*.spec"):
        try: s.unlink()
        except: pass

    sep = ";" if sys.platform == "win32" else ":"

    # ── Data files ────────────────────────────────────────────────────────────
    da = []
    print("\n  Bundling files:")
    for src, dst in DATA_FILES:
        if Path(src).exists():
            da += ["--add-data", f"{src}{sep}{dst}"]
            print(f"  + {src}")
        else:
            print(f"  ~ {src} (skip)")

    # PortAudio DLL add karo
    if portaudio_dll and portaudio_dll.exists():
        da += ["--add-binary", f"{portaudio_dll}{sep}."]
        print(f"  + PortAudio: {portaudio_dll.name}")

    # certifi certs add karo (SSL fix)
    try:
        import certifi
        cert_file = Path(certifi.where())
        da += ["--add-data", f"{cert_file}{sep}certifi"]
        print(f"  + SSL certs: {cert_file.name}")
    except ImportError:
        print("  ~ certifi not found (SSL might fail)")

    hi = [x for h in HIDDEN for x in ["--hidden-import", h]]
    ex = [x for e in EXCLUDES for x in ["--exclude-module", e]]
    ic = ["--icon", ICON] if Path(ICON).exists() else []

    cmd = (
        [sys.executable, "-m", "PyInstaller",
         "--name", name,
         "--onefile",
         "--windowed",
         "--noconfirm",
         "--clean",
         "--log-level", "WARN",
         "--distpath", str(bdir / "dist"),
         "--workpath", str(bdir / "work"),
         "--runtime-hook", HOOK]
        + ic + da + hi + ex
        + [
            # Audio — CRITICAL: collect-all sounddevice
            "--collect-all", "sounddevice",
            "--collect-all", "_sounddevice_data",
            # Network
            "--collect-submodules", "websockets",
            "--collect-all", "certifi",
            "--collect-submodules", "requests",
            "--collect-submodules", "urllib3",
            # Auth
            "--collect-all", "pyrebase",
            "--collect-all", "python_jwt",
            "--collect-all", "jwcrypto",
            "--collect-all", "cryptography",
            # AI
            "--collect-submodules", "google.genai",
            # Vision
            "--collect-submodules", "PIL",
            "--collect-submodules", "cv2",
            "--collect-submodules", "mss",
            # Tools
            "--collect-all", "duckduckgo_search",
            "--collect-all", "yt_dlp",
            "--collect-all", "pywhatkit",
            "--collect-all", "pyttsx3",
            "--collect-all", "jaraco",
            "--collect-submodules", "win32com",
            "--collect-submodules", "pyautogui",
            "--collect-submodules", "TABBU_modules",
            "--collect-all", "TABBU_modules",
            "--collect-submodules", "ALIRA",
            "--collect-submodules", "website_builder",
            "--collect-all", "website_builder",
            "--collect-submodules", "numpy",
            "--collect-submodules", "asyncio",
            script,
        ]
    )

    print(f"\n  Building {name}.exe (7-12 min)...")
    res = subprocess.run(cmd)
    exe = bdir / "dist" / f"{name}.exe"

    if res.returncode == 0 and exe.exists():
        out = Path("dist_output")
        out.mkdir(exist_ok=True)
        dst = out / f"{name}.exe"
        shutil.copy2(str(exe), str(dst))
        size_mb = dst.stat().st_size / 1e6
        print(f"\n  ✅ {name}.exe — {size_mb:.0f} MB → {dst}")
        return True

    print(f"  ❌ {name}.exe FAILED")
    return False


def build_all(which):
    print("=" * 58)
    print(f"  TITAN/ALIRA Builder v6  |  Distribution Fixed")
    print("=" * 58)
    results = {k: _build(k) for k in which}
    print("\n  SUMMARY:")
    for k, ok in results.items():
        print(f"  {'✅' if ok else '❌'} {BUILDS[k]['name']}.exe — {BUILDS[k]['desc']}")
    if any(results.values()):
        out = Path("dist_output")
        print(f"\n  Output: {out.absolute()}")
        try:
            subprocess.Popen(
                ["explorer.exe", str(out)],
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except:
            pass


def setup():
    print("Installing deps...")
    pkgs = [
        "pyrebase4", "python-jwt", "jwcrypto", "cryptography",
        "pyinstaller", "pyinstaller-hooks-contrib",
        "PyQt5", "pyautogui", "pygetwindow", "mss", "Pillow",
        "opencv-python", "pyttsx3", "jaraco.packaging", "numpy",
        "sounddevice", "pyaudio", "websockets", "aiohttp", "requests",
        "urllib3", "certifi", "psutil", "pyperclip", "pynput",
        "yt-dlp", "qrcode", "pywhatkit", "duckduckgo_search",
        "speedtest-cli", "phonenumbers", "pypdf", "python-docx",
        "python-pptx", "pywin32", "openpyxl", "colorama",
        "python-dotenv", "google-generativeai", "wikipedia",
    ]
    subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade"] + pkgs)
    print("Done! Run: python build_exe.py")


def check_only():
    """Sirf pre-checks run karo, build nahi"""
    print("=" * 58)
    print("  Pre-build check only")
    print("=" * 58)
    _find_portaudio_dll()
    for key, cfg in BUILDS.items():
        print(f"\n  [{key.upper()}]")
        _pre(cfg["script"])


if __name__ == "__main__":
    if "--setup"  in sys.argv: setup(); sys.exit(0)
    elif "--check"  in sys.argv: check_only(); sys.exit(0)
    elif "--hotkey" in sys.argv: build_all(["hotkey"])
    elif "--normal" in sys.argv: build_all(["normal"])
    else: build_all(["hotkey", "normal"])