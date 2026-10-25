# -*- coding: utf-8 -*-
"""
TITAN_startup.py — TITAN/MAYA ka secure entry point
===================================================
Yeh file TITAN.py / maya.py ke __main__ block ki jagah use karo.
Flow:
  1. QApplication create
  2. Face Auth (device binding + quality check)
  3. Login window
  4. TITAN/MAYA window

Import aur use:
  # TITAN.py ya maya.py ke end mein replace karo:
  from TITAN_startup import main
  if __name__ == "__main__":
      main()
"""

import sys, os

from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore    import Qt, QTimer
from PyQt5.QtGui     import QColor, QPalette

# ── Colors (same as TITAN.py / maya.py) ───────────────────────
BG     = "#020b04"   # maya green dark
BG2    = "#050f07"
BG3    = "#0d1525"
ACCENT = "#00ff41"
TEXT   = "#b0ffcc"


def _apply_palette(app):
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor(BG))
    pal.setColor(QPalette.WindowText,      QColor(TEXT))
    pal.setColor(QPalette.Base,            QColor(BG2))
    pal.setColor(QPalette.AlternateBase,   QColor(BG3))
    pal.setColor(QPalette.Text,            QColor(TEXT))
    pal.setColor(QPalette.Button,          QColor(BG3))
    pal.setColor(QPalette.ButtonText,      QColor(TEXT))
    pal.setColor(QPalette.Highlight,       QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("#000000"))
    app.setPalette(pal)


def main():
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps,   True)
    except: pass

    app = QApplication(sys.argv)
    app.setApplicationName("TITAN")
    # Auth ke dauran window close se app quit na ho
    app.setQuitOnLastWindowClosed(False)
    _apply_palette(app)

    # ── STEP 0: Activation Check ──────────────────────────────
    print("[Startup] Running activation check...")
    try:
        try:
            from TABBU_modules.TABBU_activation import launch_activation, is_already_activated, Session as ActS
        except ImportError:
            from TABBU_activation import launch_activation, is_already_activated, Session as ActS

        if not is_already_activated():
            print("[Startup] Device not activated — showing activation window")
            _act_loop = [True]
            _act_cfg  = [None]

            def _on_activated(cfg):
                _act_cfg[0] = cfg
                _act_loop[0] = False

            act_win = launch_activation(_on_activated)
            if act_win:
                act_win.show()
                # Wait for activation to complete
                while _act_loop[0]:
                    app.processEvents()

            if not is_already_activated():
                print("[Startup] Activation cancelled or failed")
                sys.exit(0)

            print("[Startup] Activation successful!")
        else:
            print("[Startup] Device already activated.")
            ActS.load_from_config()

    except ImportError as e:
        print(f"[Startup] TABBU_activation launch_activation not found: {e} — skipping activation")
    except Exception as e:
        print(f"[Startup] Activation error: {e}")

    # ── STEP 1: Face Authentication ───────────────────────────
    print("[Startup] Running face authentication...")
    face_ok = False
    try:
        try:
            from TABBU_modules.face_auth import run_face_auth
        except ImportError:
            from face_auth import run_face_auth
        face_ok = run_face_auth()
    except ImportError:
        print("[Startup] face_auth.py not found — skipping")
        face_ok = True
    except Exception as e:
        print(f"[Startup] Face auth error: {e} — allowing bypass")
        face_ok = True   # Error pe bypass (camera unavailable etc.)

    if not face_ok:
        QMessageBox.critical(
            None,
            "TITAN — Access Denied",
            "❌ Face authentication failed.\n\nTITAN is locked to a different user or device.",
        )
        sys.exit(1)

    print("[Startup] Face auth passed — loading TITAN...")

    # ── STEP 2: Login Window ──────────────────────────────────
    app.setQuitOnLastWindowClosed(False)  # login window close pe quit nahi

    _ctrl = [None]  # list trick for closure

    try:
        try:
            from TABBU_modules.TABBU_login import LoginWindow, Session as LogS
        except ImportError:
            from TABBU_login import LoginWindow, Session as LogS

        login_win = LoginWindow()

        def _on_logged_in(user):
            try:
                LogS.set(user, login_win.get_firebase())
            except Exception as e:
                print(f"[Session] {e}")
            try:
                login_win.hide()
            except: pass

            # ── STEP 3: TITAN/MAYA Window ──────────────────────
            _launch_main(app, user, LogS)

        login_win.sig_logged_in.connect(_on_logged_in)
        login_win.show()

    except ImportError:
        print("[Startup] TITAN_login not found — launching TITAN directly")
        _launch_main(app, {}, None)

    sys.exit(app.exec_())


def _launch_main(app, user: dict, LogS):
    """TITAN main window launch karo"""

    try:
        from TABBU import TITANWindow
        WinClass = TITANWindow
        win_name = "TITAN"
        print("[Startup] Using TITANWindow from TITAN.py")
    except ImportError:
        print("[Startup] ERROR: TITAN.py not found!")
        app.quit()
        return

    # User display name
    name = (
        user.get("displayName", "").strip()
        or user.get("email", "").split("@")[0].strip()
        or ""
    )
    if name: name = name[0].upper() + name[1:]

    win = WinClass()
    win.setWindowTitle(f"{win_name}  —  {name}" if name else win_name)

    # Firebase message saving
    if LogS:
        try:
            w = win._worker
            w.sig_user_msg.connect(lambda t: _safe_save(LogS, "user",  t))
            w.sig_TITAN_msg.connect(lambda t: _safe_save(LogS, "model", t))
        except Exception as e:
            print(f"[Startup] Worker signals: {e}")

    # Show window
    app.setQuitOnLastWindowClosed(True)
    win.show()
    win.raise_()
    win.activateWindow()

    try:
        import ctypes
        hwnd = int(win.winId())
        ctypes.windll.user32.ShowWindow(hwnd, 9)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
    except: pass

    print(f"[Startup] {win_name} window launched. User: {name}")


def _safe_save(LogS, role, text):
    try:
        if LogS: LogS.save_message(role, text)
    except Exception as e:
        print(f"[Firebase] {e}")


if __name__ == "__main__":
    main()