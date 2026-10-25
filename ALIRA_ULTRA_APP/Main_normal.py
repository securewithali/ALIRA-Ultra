# -*- coding: utf-8 -*-
"""
ALIRA ULTRA v8.0 — AI Assistant with ALIRA Coder
  - Straight to TITAN Window (no login / activation gate)
"""
import sys, os, ctypes
from pathlib import Path

# Windows console/terminal codepage is often NOT UTF-8 (e.g. cp1252) -
# without this, the emoji prints in TABBU.py/camera_vision_module.py/etc.
# raise UnicodeEncodeError and crash their import (surfaces as
# "[ERROR] Failed to import TABBU" further down).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure the app root is on sys.path so local modules can be imported from the exe or source tree.
_APP_ROOT = Path(__file__).resolve().parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

def _preload():
    """Bhaari imports — splash chalte waqt background thread mein (taaki splash ka bar animate hota rahe)."""
    try:
        import website_builder
        import camera_vision_module
        import screen_share_module
        import ALIRA_coder_integration
        print("[ALIRA ULTRA] All modules loaded OK")
    except Exception as e:
        print(f"[NEW MODULES] Load warning: {e}")
    try:
        import TABBU  # noqa: F401 — sabse bhaari import; yahin garam ho jata hai
    except Exception as e:
        print(f"[ALIRA] preload TABBU: {e}")

try:
    from PyQt5 import QtWebEngineWidgets   # noqa: F401 — QApplication se PEHLE import hona zaroori (Website Studio live preview)
except Exception:
    pass
from PyQt5.QtWidgets import QApplication, QMessageBox, QDialog
from PyQt5.QtCore    import Qt, QTimer, QEventLoop
from PyQt5.QtGui     import QColor, QPalette

try:
    import ALIRA_autostart as _autostart
except Exception as _e:
    _autostart = None
    print(f"[ALIRA] autostart module not available: {_e}")

BG     = "#050810"
BG2    = "#080d18"
BG3    = "#0d1525"
ACCENT = "#e8406a"
TEXT   = "#e8eaf6"

user32 = ctypes.windll.user32


class TITANAppNormal:
    def __init__(self, app: QApplication):
        self.app        = app
        self._TITAN_win  = None
        self._login_win = None
        self._user      = {}
        self._LogS      = None
        self._single    = None      # SingleInstance (dobara chalane par purani window khule)
        self.splash     = None      # ALIRASplash (startup progress)

    def _run_preload(self):
        """Imports background thread mein; main thread splash animate karta hai."""
        import threading, time
        th = threading.Thread(target=_preload, daemon=True, name="ALIRA-preload")
        th.start()
        t0 = time.monotonic()
        while th.is_alive():
            self.app.processEvents()
            if self.splash:
                self.splash.set_progress(min(66.0, 5.0 + (time.monotonic() - t0) * 12.0))
            time.sleep(0.01)
        if self.splash:
            self.splash.set_progress(70)

    def start(self):
        # Login page and access-key activation removed - launch straight
        # into TITAN. self._user / self._LogS stay empty defaults;
        # _launch_TITAN() and _save_msg() already handle that case.
        os.environ.setdefault("TITAN_USER_UID", "default_user")
        self._launch_TITAN()

    def _launch_TITAN(self):
        # Ab normal window close = app quit
        self.app.setQuitOnLastWindowClosed(True)

        self._run_preload()
        try:
            from TABBU import TITANWindow, _load_api_key, _save_config, ApiKeySetupDialog
        except Exception as e:
            print(f"[ERROR] Failed to import TABBU: {e}")
            QMessageBox.critical(None, "Import Error",
                f"Failed to load TITAN window:\n{str(e)}\n\nPlease check if all files are included in the EXE.")
            return

        # Load API key or show setup dialog
        api_key = _load_api_key()
        if not api_key:
            print("[TITAN] No API key found - showing setup dialog")
            if self.splash: self.splash.hide()            # dialog splash ke peeche na chhupe
            dlg = ApiKeySetupDialog()
            if self._single is not None: self._single.set_busy(True)
            _ok = dlg.exec_() == QDialog.Accepted
            if self._single is not None: self._single.set_busy(False)
            if self.splash: self.splash.show()
            if _ok:
                api_key = dlg.get_api_key()
                if api_key:
                    _save_config(api_key)
                    print("[TITAN] API key saved")
                else:
                    QMessageBox.critical(None, "API Key Error",
                        "API key is required to use TITAN.")
                    return
            else:
                return  # User cancelled

        name = (self._user.get("displayName","").strip()
                or self._user.get("email","").split("@")[0].strip())
        if name: name = name[0].upper() + name[1:]

        if self.splash:
            self.splash.set_progress(70); self.app.processEvents()
        try:
            import TABBU as _TABBU_mod
            if self.splash:                               # window banne ke har stage par splash progress (repaint ke saath)
                _TABBU_mod._startup_hook = lambda p, sp=self.splash: sp.jump(p)
            try:
                self._TITAN_win = TITANWindow(api_key)
            finally:
                _TABBU_mod._startup_hook = None
            self._TITAN_win.setWindowTitle(f"ALIRA ULTRA v8.0 — {name}" if name else "ALIRA ULTRA v8.0")

            try:
                w = self._TITAN_win._worker
                w.sig_user_msg.connect(lambda t: self._save_msg("user", t))
                w.sig_TITAN_msg.connect(lambda t: self._save_msg("model", t))
            except Exception:
                pass

            if self._single is not None and hasattr(self._TITAN_win, "_show_main"):
                self._single.sig_show.connect(self._TITAN_win._show_main)
            if self._single is not None:
                self._single.mark_ready()
                try:
                    import faulthandler
                    faulthandler.cancel_dump_traceback_later()
                except Exception:
                    pass

            # --background (Windows startup): window nahi, sirf mini orb + tray. API key na ho to normal setup dikhao.
            background = bool(_autostart and _autostart.is_background_launch() and api_key
                              and hasattr(self._TITAN_win, "start_in_background"))
            if background:
                self._TITAN_win.start_in_background()
                print(f"[TITAN] Background mode (orb) | User: {name}")
            else:
                win = self._TITAN_win

                def _reveal():                            # splash bar 100% hone ke BAAD hi main window dikhegi
                    win.show()
                    win.raise_()
                    win.activateWindow()
                    try:
                        hwnd = int(win.winId())
                        user32.ShowWindow(hwnd, 9)
                        user32.SetForegroundWindow(hwnd)
                    except Exception:
                        pass
                    if hasattr(win, "first_run_setup"):
                        QTimer.singleShot(3500, win.first_run_setup)
                    if hasattr(win, "ask_name_if_missing"):
                        QTimer.singleShot(4500, win.ask_name_if_missing)
                    print(f"[TITAN] Window launched | User: {name}")

                if self.splash:
                    self.splash.finish(on_full=_reveal)       # 100% -> window dikhao -> splash fade-out
                    self._splash_keep, self.splash = self.splash, None   # fade-out tak reference zinda rahe
                else:
                    _reveal()
        except Exception as e:
            print(f"[ERROR] Failed to create TITAN window: {e}")
            if self.splash: self.splash.hide()
            QMessageBox.critical(None, "Window Error",
                f"Failed to create TITAN window:\n{str(e)}")

    def _save_msg(self, role, text):
        try:
            if self._LogS: self._LogS.save_message(role, text)
        except Exception as e:
            print(f"[Firebase] {e}")


def main():
    # FIX (UI zoom): AA_EnableHighDpiScaling + Windows 125/150% scaling => Qt 5.15 scale factor ko 2.0 round kar deta tha,
    # screen 960x540 "dikhti" thi aur 1440x880 ki window 2880x1760 px ban kar screen se bahar phail jaati thi.
    # Ab 1:1 pixels (jaisa `python TABBU.py` mein tha). Bahut bade 4K screen par zoom chahiye to: set ALIRA_HIDPI=1
    try:
        if os.environ.get("ALIRA_HIDPI") == "1":
            try:
                QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)   # exact 1.5, 2.0 nahi
            except Exception:
                pass
            QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        else:
            QApplication.setAttribute(Qt.AA_DisableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("ALIRA ULTRA")
    # False — face auth window ke waqt app quit na ho
    app.setQuitOnLastWindowClosed(False)

    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor(BG))
    pal.setColor(QPalette.WindowText,      QColor(TEXT))
    pal.setColor(QPalette.Base,            QColor(BG2))
    pal.setColor(QPalette.AlternateBase,   QColor(BG3))
    pal.setColor(QPalette.Text,            QColor(TEXT))
    pal.setColor(QPalette.Button,          QColor(BG3))
    pal.setColor(QPalette.ButtonText,      QColor(TEXT))
    pal.setColor(QPalette.Highlight,       QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)

    # pythonw (autostart) mein console nahi hota — error/log ~/.TABBU/ALIRA.log mein jayein; 90s mein window na bani to thread dump
    try:
        if sys.stdout is None or sys.stderr is None or os.environ.get("ALIRA_LOG"):
            from pathlib import Path as _P
            _lp = _P.home() / ".TABBU" / "ALIRA.log"
            _lp.parent.mkdir(exist_ok=True)
            if _lp.exists() and _lp.stat().st_size > 1_000_000:
                _lp.replace(_lp.with_suffix(".old"))
            _lf = open(_lp, "a", encoding="utf-8", buffering=1)
            _lf.write(chr(10) + "===== ALIRA start " + __import__("time").strftime("%Y-%m-%d %H:%M:%S") + " =====" + chr(10))
            sys.stdout = sys.stdout or _lf
            sys.stderr = sys.stderr or _lf
            import faulthandler
            faulthandler.enable(_lf)
            faulthandler.dump_traceback_later(90, repeat=False, file=_lf)
    except Exception:
        pass

    ctrl = TITANAppNormal(app)
    if _autostart is not None:
        if _autostart.handle_cli_flags():          # --install-startup / --uninstall-startup
            sys.exit(0)
        ctrl._single = _autostart.make_single_instance()
        if not ctrl._single.acquire():             # ALIRA pehle se chal rahi hai — usi ko window kholne ko bol diya
            print("[ALIRA] Pehle se chal rahi hai.")
            sys.exit(0)
    # ── startup splash (background/autostart mein nahi; ALIRA_NO_SPLASH=1 ya prefs splash=false se band) ──
    background = bool(_autostart and _autostart.is_background_launch())
    try:
        import ALIRA_prefs
        want = bool(ALIRA_prefs.get("splash", True)) and not os.environ.get("ALIRA_NO_SPLASH")
    except Exception:
        want = not os.environ.get("ALIRA_NO_SPLASH")
    if want and not background:
        try:
            import ALIRA_ui
            ALIRA_ui.load_fonts()
            from ALIRA_splash import ALIRASplash
            ctrl.splash = ALIRASplash()
            ctrl.splash.show()
            app.processEvents()
        except Exception as e:
            print(f"[ALIRA] splash: {e}")
            ctrl.splash = None
    ctrl.start()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()