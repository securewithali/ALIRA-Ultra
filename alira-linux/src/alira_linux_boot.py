# -*- coding: utf-8 -*-
"""
ALIRA Linux launcher — Windows ki app ko Linux par chalane wala chhota layer.

  * `winreg` / `ctypes.windll` ke stub (module-level imports crash na karein; asli kaam karne wali calls
    ❌ "Linux par nahi" batati hain, jhoothi success nahi)
  * sounddevice ya PortAudio na ho to app khulti hai, voice band rehti hai aur sahi install command dikhti hai
  * Windows-only tools ki jagah Linux tools (ALIRA_linux_tools)
"""
import os
import sys
import types
from pathlib import Path

LINUX_HELP = ("sudo apt install -y libportaudio2 libxcb-cursor0 libxkbcommon-x11-0 libxcb-icccm4 libxcb-image0 "
              "libxcb-keysyms1 libxcb-render-util0 libxcb-xinerama0 libgl1 libpulse0 libasound2-plugins pulseaudio-utils tesseract-ocr scrot python3-tk xclip libnotify-bin playerctl brightnessctl wmctrl xdotool network-manager")


class _WinStub:
    """ctypes.windll jaisa object — har attribute/call safe 0 return karta hai (sirf import-time ke liye)."""
    def __getattr__(self, name):
        return _WinStub()

    def __call__(self, *a, **k):
        return 0

    def __int__(self):
        return 0

    __bool__ = lambda self: False


def _shim_windows():
    import ctypes
    sys.modules.setdefault("pygetwindow", None)      # Linux par import par NotImplementedError deta hai -> ab saaf ImportError
    if not hasattr(ctypes, "windll"):
        ctypes.windll = _WinStub()
    if "winreg" not in sys.modules:
        m = types.ModuleType("winreg")
        for k in ("HKEY_CURRENT_USER", "HKEY_LOCAL_MACHINE", "HKEY_CLASSES_ROOT", "KEY_READ", "KEY_WRITE", "KEY_ALL_ACCESS",
                  "REG_SZ", "REG_DWORD", "KEY_SET_VALUE", "KEY_QUERY_VALUE"):
            setattr(m, k, 0)

        def _no(*a, **k):
            raise OSError("Windows registry Linux par nahi hai")
        for k in ("OpenKey", "CreateKey", "CreateKeyEx", "SetValueEx", "QueryValueEx", "DeleteValue", "CloseKey", "EnumKey",
                  "EnumValue", "ConnectRegistry"):
            setattr(m, k, _no)
        sys.modules["winreg"] = m


def _fix_audio():
    """PortAudio (ALSA) ko PulseAudio/PipeWire se jodo — warna mic/speaker 'No mic found' aata hai (WSL/Ubuntu)."""
    import glob
    if not sys.platform.startswith("linux"):
        return
    rc = Path.home() / ".asoundrc"
    if rc.exists() or os.path.exists("/etc/asound.conf"):
        return
    pulse = os.environ.get("PULSE_SERVER") or glob.glob("/run/user/*/pulse/native") or os.path.exists("/mnt/wslg/PulseServer")
    if not pulse:
        return
    if not glob.glob("/usr/lib/*/alsa-lib/libasound_module_pcm_pulse.so") and not glob.glob("/usr/lib/alsa-lib/libasound_module_pcm_pulse.so"):
        print("[ALIRA] ⚠️  Mic/speaker ke liye ek package chahiye:  sudo apt install libasound2-plugins pulseaudio-utils\n"
              "        (ya `ALIRA-linux deps` chalao), phir ALIRA dobara chalao.", file=sys.stderr)
        return
    try:
        rc.write_text("pcm.!default { type pulse }\nctl.!default { type pulse }\n", encoding="utf-8")
        print("[ALIRA] 🔊 Audio ko PulseAudio se joda (~/.asoundrc).", file=sys.stderr)
    except Exception:
        pass


def _tune_audio(sd):
    """Linux/WSL mein PulseAudio ke saath latency='low' speaker stream toot-toot (underrun) karta hai — buffer bada karo."""
    base = sd.OutputStream

    class _Out(base):
        def __init__(self, *a, **k):
            if k.get("latency") in (None, "low"):
                k["latency"] = "high"
            super().__init__(*a, **k)
    sd.OutputStream = _Out


def _shim_audio():
    _fix_audio()
    try:
        import sounddevice
        _tune_audio(sounddevice)
        return True
    except Exception as e:                                   # PortAudio library nahi
        sd = types.ModuleType("sounddevice")

        def _no(*a, **k):
            raise RuntimeError("Audio nahi chal sakta: PortAudio missing. Chalao: sudo apt install libportaudio2")
        sd.InputStream = sd.OutputStream = sd.RawInputStream = sd.RawOutputStream = _no
        sd.query_devices = lambda *a, **k: []
        sd.default = types.SimpleNamespace(device=(None, None), samplerate=None)
        sd.PortAudioError = RuntimeError
        sys.modules["sounddevice"] = sd
        print(f"[ALIRA] ⚠️  sounddevice/PortAudio nahi mila ({e}). Voice band rahegi.\n"
              f"        Voice ke liye ye chalao:  sudo apt install libportaudio2\n"
              f"        Poora set:  {LINUX_HELP}", file=sys.stderr)
        return False


def _check_display():
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) and not os.environ.get("QT_QPA_PLATFORM"):
        print("[ALIRA] ❌ Display nahi mila (DISPLAY/WAYLAND_DISPLAY khali). ALIRA GUI ko desktop session chahiye.\n"
              "        Server/SSH par text version chalao:  pipx install ALIRA-termux  &&  ALIRA-linux", file=sys.stderr)
        return False
    return True


def prepare():
    _shim_windows()
    _shim_audio()
    os.environ.setdefault("ALIRA_PLATFORM", "linux")
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")


HELP = """ALIRA for Linux — commands

  ALIRA-linux                 ALIRA chalao (window + voice)
  ALIRA-linux --background    sirf floating orb ke saath chalao
  ALIRA-linux install         login par apne aap chalu (autostart ON) + abhi background mein start
  ALIRA-linux uninstall       autostart OFF
  ALIRA-linux status          version, autostart, audio/display ka haal
  ALIRA-linux deps            zaroori system libraries install karo (sudo apt)
  ALIRA-linux update          naya version install karo
  ALIRA-linux remove [--purge]  ALIRA hata do (--purge: settings/chat data bhi)
  ALIRA-linux --version | --help-deps
"""


def _installer():
    """pipx se install hai ya pip se — update/remove ke liye."""
    import shutil
    p = sys.prefix.replace("\\", "/")
    if "/pipx/venvs/" in p and shutil.which("pipx"):
        return ["pipx"], "pipx"
    return [sys.executable, "-m", "pip"], "pip"


def _status():
    from importlib.metadata import version
    import ALIRA_autostart as au
    print(f"ALIRA Linux {version('ALIRA-linux')}")
    print(f"Autostart : {'ON' if au.is_enabled() else 'OFF'}" + (f"  ({au.registered_command()})" if au.is_enabled() else ""))
    print(f"Display   : {os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DISPLAY') or 'NAHI MILA'}")
    _fix_audio()
    ndev = 0
    try:
        import sounddevice as _sd
        ndev = len(_sd.query_devices())
    except Exception:
        pass
    print(f"Audio     : {'OK (%d devices)' % ndev if ndev else 'koi audio device nahi -> ALIRA-linux deps (libasound2-plugins)'}")
    return 0


def _cmd(argv):
    import shutil
    import subprocess
    c = argv[0].lower()
    if c in ("-h", "--help", "help"):
        print(HELP); return 0
    if c == "deps":
        if not shutil.which("apt"):
            print("apt nahi mila. Apne distro mein ye packages install karo (names alag ho sakte hain): " + LINUX_HELP.replace("sudo apt install -y ", "")); return 1
        print("$ " + LINUX_HELP); return subprocess.call(LINUX_HELP.split())
    if c in ("install", "uninstall", "status"):
        import ALIRA_autostart as au
        import linux_extra
        linux_extra.patch_autostart(au)
        if c == "status":
            return _status()
        if c == "install":
            ok = au.enable(True)
            print("[ALIRA] ✅ Autostart ON — login par ALIRA orb ke saath khud chalu hogi." if ok else "[ALIRA] ❌ Autostart ON nahi ho paya.")
            if ok and au.spawn_background():
                print("[ALIRA] ✅ ALIRA abhi background mein chalu ho gayi (screen par orb dikhega).")
            return 0 if ok else 1
        ok = au.disable()
        print("[ALIRA] Autostart OFF." if ok else "[ALIRA] ❌ Autostart OFF nahi ho paya.")
        return 0 if ok else 1
    if c == "update":
        base, kind = _installer()
        cmd = base + (["upgrade", "ALIRA-linux"] if kind == "pipx" else ["install", "--upgrade", "ALIRA-linux"])
        print("$ " + " ".join(cmd)); return subprocess.call(cmd)
    if c == "remove":
        import ALIRA_autostart as au
        import linux_extra
        linux_extra.patch_autostart(au); au.disable()
        if "--purge" in argv:
            for d in (Path.home() / ".TABBU", Path.home() / ".ALIRA_data"):
                shutil.rmtree(d, ignore_errors=True)
            print("[ALIRA] Settings/data hata diya.")
        base, kind = _installer()
        cmd = base + (["uninstall", "ALIRA-linux"] if kind == "pipx" else ["uninstall", "-y", "ALIRA-linux"])
        print("$ " + " ".join(cmd)); return subprocess.call(cmd)
    return None


def main():
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    args = sys.argv[1:]
    if args and not args[0].startswith("--") or (args and args[0] in ("--help", "-h")):
        r = _cmd(args)
        if r is not None:
            return r
    if "--help-deps" in args:
        print(LINUX_HELP); return 0
    if "--version" in args:
        from importlib.metadata import version
        print(version("ALIRA-linux")); return 0
    if not _check_display():
        return 1
    prepare()
    from pathlib import Path
    from ALIRA.config import load_environment
    load_environment()
    for d in ("Documents/TITAN_Notes", "Documents/TITAN_Recordings", "Documents/TITAN_PDFs", "TITAN_Codes", "TABBU_Downloads"):
        try:
            (Path.home() / d).mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    import TABBU_modules.tools as tools
    import ALIRA_linux_tools
    import ALIRA_autostart
    import linux_extra
    ALIRA_linux_tools.install(tools)
    linux_extra.patch_autostart(ALIRA_autostart)
    import ALIRA_apps, ALIRA_actions
    linux_extra.patch_apps(ALIRA_apps, ALIRA_actions)
    try:
        import TABBU_modules.TABBU_advanced_tools as _adv
        linux_extra.patch_ocr(_adv)
    except Exception as e:
        print(f"[ALIRA] ocr patch: {e}", file=sys.stderr)
    try:
        linux_extra.patch_overlays()
    except Exception as e:
        print(f"[ALIRA] overlay patch: {e}", file=sys.stderr)
    from Main_normal import main as run_app
    run_app()
    return 0


if __name__ == "__main__":
    sys.exit(main())
