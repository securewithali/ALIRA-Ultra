# -*- coding: utf-8 -*-
"""
alira CLI  v5  [pip-install safe]
==========================================
  alira          → app (no login, no access key)
  alira reset    → same as alira (kept for backward compatibility)
  alira upgrade  → same as alira (kept for backward compatibility)
  alira install  → Windows startup ON + abhi background (mini orb) mein chalu
  alira uninstall→ Windows startup OFF
  alira status   → startup status
  alira --background → window ke bina, sirf orb ke saath chalo
"""
import sys, os
from pathlib import Path

# Windows console/terminal codepage is often NOT UTF-8 (e.g. cp1252) -
# without this, the banner's box-drawing chars / emoji prints elsewhere
# in the app can raise UnicodeEncodeError and crash the launch.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ── sys.path fix ─────────────────────────────────────────────────────────────
_here      = Path(__file__).resolve().parent      # .../site-packages/ALIRA/
_site_pkgs = _here.parent                          # .../site-packages/
for _p in [str(_site_pkgs), str(_here)]:
    if _p not in sys.path: sys.path.insert(0, _p)


def _color():
    try:
        from colorama import Fore, Style, init; init(autoreset=True); return Fore, Style
    except ImportError:
        class _N:
            def __getattr__(self,_): return ""
        c=_N(); return c,c

def show_banner():
    F,S = _color()
    print(f"""{F.MAGENTA}
==================================================
███╗   ███╗██╗   ██╗██████╗  █████╗
████╗ ████║╚██╗ ██╔╝██╔══██╗██╔══██╗
██╔████╔██║ ╚████╔╝ ██████╔╝███████║
██║╚██╔╝██║  ╚██╔╝  ██╔══██╗██╔══██║
██║ ╚═╝ ██║   ██║   ██║  ██║██║  ██║
╚═╝     ╚═╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝{S.RESET_ALL}
{F.CYAN}        alira AI ASSISTANT{S.RESET_ALL}
{F.GREEN}        by Md Ali  @SecureWithAli{S.RESET_ALL}
{F.MAGENTA}=================================================={S.RESET_ALL}
""")

def _dirs():
    home=Path.home(); docs=home/"Documents"
    for d in [docs/"TITAN_Notes",docs/"TITAN_Recordings",docs/"TITAN_Wallpapers",
              docs/"TITAN_PDFs",home/"TITAN_Codes",home/"TABBU_Downloads",
              Path(os.environ.get("APPDATA",str(home/"AppData"/"Roaming")))/"ALIRA"]:
        try: d.mkdir(parents=True, exist_ok=True)
        except Exception: pass

def _run_app() -> int:
    try:
        from Main_normal import main as run_app
    except ImportError as e:
        print(f"[ALIRA] ❌ Main_normal not found: {e}", file=sys.stderr)
        return 1
    try:
        run_app()
    except Exception as e:
        print(f"[ALIRA] App error: {e}", file=sys.stderr)
        import traceback; traceback.print_exc(); return 1
    return 0

def _launch() -> int:
    from alira.config import load_environment
    load_environment()
    _dirs()
    return _run_app()

def reset() -> int:
    show_banner()
    return _launch()

def upgrade() -> int:
    show_banner()
    return _launch()

def install_cmd() -> int:
    """`alira install` — Windows startup ON + alira ko abhi background (orb) mein chalu karo."""
    try:
        import ALIRA_autostart as au
    except ImportError as e:
        print(f"[alira] autostart module nahi mila: {e}", file=sys.stderr)
        return 1
    ok = au.enable(True)
    print("[alira] ✅ Windows startup ON — PC start/restart par alira orb ke saath khud chalu hogi." if ok
          else "[alira] ❌ Startup ON nahi ho paya.")
    if ok:
        started = au.spawn_background()
        print("[alira] ✅ alira abhi background mein chalu ho gayi (screen par orb dikhega)." if started
              else "[alira] ⚠️  Abhi chalu nahi ho payi — `alira` command se chalao.")
    return 0 if ok else 1


def uninstall_cmd() -> int:
    """`alira uninstall` — Windows startup OFF."""
    try:
        import alira_autostart as au
    except ImportError as e:
        print(f"[alira] autostart module nahi mila: {e}", file=sys.stderr)
        return 1
    ok = au.disable()
    print("[alira] Windows startup OFF." if ok else "[alira] ❌ Startup OFF nahi ho paya.")
    return 0 if ok else 1


def status_cmd() -> int:
    try:
        import alira_autostart as au
        on = au.is_enabled()
        print(f"[alira] Windows startup: {'ON' if on else 'OFF'}")
        print(f"[alira] Registered command: {au.registered_command()}" if on else f"[alira] `alira install` se ye command register hogi: {au.launch_command(True)}")
    except ImportError as e:
        print(f"[alira] autostart module nahi mila: {e}")
    return 0


def main() -> int:
    show_banner()
    if len(sys.argv) > 1:
        a = sys.argv[1].lower()
        if a in ("install", "setup", "--install-startup"): return install_cmd()
        if a in ("uninstall", "--uninstall-startup"):      return uninstall_cmd()
        if a == "status":                                  return status_cmd()
        if a in ("reset","upgrade","re-activate"): return reset()
    return _launch()          # `alira --background` bhi yahin se: Main_normal flag padhta hai

if __name__ == "__main__":
    raise SystemExit(main())
