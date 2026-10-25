# -*- coding: utf-8 -*-
"""
_tabbu_rthook.py  — PyInstaller Runtime Hook  v3 (EXE Distribution Fix)
=======================================================================
FIXES for dusre PC pe:
  1. PortAudio DLL path set karo (sounddevice EXE crash)
  2. API key — env vTABBUble missing ho toh config se load karo
  3. TITAN_Notes folder create karo (file-not-found fix)
  4. OpenSSL / SSL cert path fix
  5. cv2 / numpy DLL path
  6. Temp dir writable check
"""

import os
import sys
import json
import ctypes
import tempfile
from pathlib import Path


# ── 1. Base path (EXE ke andar ya source) ─────────────────────────────────────
if getattr(sys, "frozen", False):
    BASE = Path(sys._MEIPASS)          # PyInstaller extracted temp dir
    EXE_DIR = Path(sys.executable).parent  # actual EXE folder
else:
    BASE = Path(__file__).resolve().parent
    EXE_DIR = BASE


# ── 2. sys.path mein BASE add karo ────────────────────────────────────────────
for p in [str(BASE), str(EXE_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)


# ── 3. PortAudio DLL fix — sounddevice ka sabse common EXE crash ──────────────
def _fix_portaudio():
    """
    sounddevice internally loads _portaudio.pyd which needs portaudio dll.
    EXE pe ye dll missing ho sakta hai.
    """
    try:
        import sounddevice as sd
        # Test: ek quick query karo
        sd.query_devices()
        return  # OK hai
    except Exception as e:
        err = str(e).lower()
        if "portaudio" in err or "dll" in err or "found" in err:
            # Try loading from BASE
            for dll_name in ["portaudio.dll", "_portaudio.dll", "libportaudio.dll"]:
                dll_path = BASE / dll_name
                if dll_path.exists():
                    try:
                        ctypes.cdll.LoadLibrary(str(dll_path))
                        print(f"[RTHOOK] Loaded PortAudio: {dll_path}")
                        return
                    except Exception as de:
                        print(f"[RTHOOK] PortAudio load failed: {de}")
            print(f"[RTHOOK] PortAudio DLL nahi mila. Mic kaam nahi karega. Error: {e}")
        else:
            print(f"[RTHOOK] sounddevice init warning: {e}")

_fix_portaudio()


# ── 4. API Key load karo (config file se) ─────────────────────────────────────
def _load_api_key_rthook():
    if os.getenv("GEMINI_API_KEY"):
        return  # Already set

    # Search order: EXE dir → home/.TABBU → home/.TABBU_config
    search_paths = [
        EXE_DIR / "config.json",
        EXE_DIR / ".TABBU_config.json",
        Path.home() / ".TABBU" / "config.json",
        Path.home() / ".TABBU_config.json",
        Path.home() / ".TITAN_config.json",
    ]
    for cfg_path in search_paths:
        try:
            if cfg_path.exists():
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                key  = data.get("api_key") or data.get("gemini_api_key", "")
                if key:
                    os.environ["GEMINI_API_KEY"] = key
                    print(f"[RTHOOK] API key loaded from {cfg_path}")
                    return
        except Exception:
            continue

    # .env fallback
    for env_file in [EXE_DIR / ".env", EXE_DIR / ".env.local"]:
        try:
            if env_file.exists():
                for line in env_file.read_text().splitlines():
                    line = line.strip()
                    if "=" in line and not line.startswith("#"):
                        k, v = line.split("=", 1)
                        os.environ[k.strip()] = v.strip()
                if os.getenv("GEMINI_API_KEY"):
                    print(f"[RTHOOK] API key loaded from {env_file}")
                    return
        except Exception:
            continue

_load_api_key_rthook()


# ── 5. TITAN_Notes / TABBU_memory folders ──────────────────────────────────────
def _create_app_folders():
    """EXE run karte waqt zaruri folders create karo"""
    folders = [
        Path.home() / ".TABBU",
        Path.home() / "TITAN_Notes",
        EXE_DIR / "TABBU_memory",
        EXE_DIR / "logs",
    ]
    for folder in folders:
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

_create_app_folders()


# ── 6. SSL Certificate path (requests/websockets on EXE) ──────────────────────
def _fix_ssl():
    try:
        import certifi
        os.environ.setdefault("SSL_CERT_FILE",  certifi.where())
        os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())
    except ImportError:
        pass  # certifi nahi hai to theek hai

_fix_ssl()


# ── 7. Temp dir writable check ────────────────────────────────────────────────
def _fix_temp():
    try:
        tmp = Path(tempfile.gettempdir())
        test_file = tmp / "_TABBU_test.tmp"
        test_file.write_text("test")
        test_file.unlink()
    except Exception:
        # Fallback: EXE_DIR/temp
        alt_tmp = EXE_DIR / "temp"
        alt_tmp.mkdir(exist_ok=True)
        os.environ["TMPDIR"] = str(alt_tmp)
        os.environ["TEMP"]   = str(alt_tmp)
        os.environ["TMP"]    = str(alt_tmp)
        tempfile.tempdir      = str(alt_tmp)

_fix_temp()


# ── 8. cv2 DLL path (agar cv2 import fail ho) ────────────────────────────────
try:
    import cv2
except Exception:
    # cv2 ke bina camera features nahi chalenge — silently log
    print("[RTHOOK] cv2 not available — camera features disabled")


# ── 9. PyQt5 platform plugin path ─────────────────────────────────────────────
if getattr(sys, "frozen", False):
    qt_platform_dir = BASE / "PyQt5" / "Qt5" / "plugins" / "platforms"
    if qt_platform_dir.exists():
        os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(qt_platform_dir))
    # Also try direct
    for alt in [BASE / "platforms", EXE_DIR / "platforms"]:
        if alt.exists():
            os.environ.setdefault("QT_QPA_PLATFORM_PLUGIN_PATH", str(alt))
            break


# ── Done ──────────────────────────────────────────────────────────────────────
print(f"[RTHOOK] v3 init complete | frozen={getattr(sys,'frozen',False)} | base={BASE}")