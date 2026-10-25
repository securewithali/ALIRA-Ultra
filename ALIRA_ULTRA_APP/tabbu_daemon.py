# -*- coding: utf-8 -*-
"""
TITAN v3 — Background Daemon
============================
- Windows startup pe automatically launch hota hai
- Koi window nahi dikhti, koi taskbar entry nahi
- Win + Shift + A dabao → TITAN window aayegi
- Dobara dabao → window chhuup jaayegi
- System tray icon bhi nahi — completely invisible

Run automatically via:
  Windows Startup folder shortcut  OR  Registry HKCU Run key
"""

import sys, os, threading, ctypes, json, time
from pathlib import Path
from ctypes import wintypes

# ── PyQt5 ────────────────────────────────────────────────
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui     import QColor, QPalette
from PyQt5.QtCore    import QTimer, pyqtSignal, QObject

# ── TITAN modules ─────────────────────────────────────────
from TABBU_modules.TABBU_login import launch_login, Session as LoginSession
from TABBU_modules.TABBU_activation import load_config, is_already_activated
try:
    from TABBU_modules.TABBU_activation import launch_activation, Session as ActivationSession
except ImportError:
    # Activation gate removed (Main_normal jaisa) — seedha login par jao
    class ActivationSession:
        @staticmethod
        def load_from_config(): pass
        @staticmethod
        def set(cfg): pass
    def launch_activation(on_done):
        return None
from TABBU import TITANWindow

# ── Colors ───────────────────────────────────────────────
BG     = "#050810"
BG2    = "#080d18"
BG3    = "#0d1525"
ACCENT = "#e8406a"
TEXT   = "#e8eaf6"

# ── Hotkey config ────────────────────────────────────────
# Win + Shift + A
MOD_WIN   = 0x0008
MOD_SHIFT = 0x0004
VK_A      = 0x41
HOTKEY_ID = 1

# ── Windows API ──────────────────────────────────────────
user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ════════════════════════════════════════════════════════
# HOTKEY LISTENER  (runs in background thread)
# ════════════════════════════════════════════════════════
class HotkeyListener(QObject):
    sig_toggle = pyqtSignal()   # fires on Win+Shift+A

    def __init__(self):
        super().__init__()
        self._running = True

    def start(self):
        t = threading.Thread(target=self._listen, daemon=True)
        t.start()

    def stop(self):
        self._running = False

    def _listen(self):
        # Register Win+Shift+A
        ok = user32.RegisterHotKey(None, HOTKEY_ID,
                                   MOD_WIN | MOD_SHIFT | 0x4000,
                                   VK_A)
        if not ok:
            # Try without MOD_NOREPEAT if not supported
            ok = user32.RegisterHotKey(None, HOTKEY_ID,
                                       MOD_WIN | MOD_SHIFT,
                                       VK_A)

        msg = wintypes.MSG()
        while self._running:
            if user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 1):
                if msg.message == 0x0312:   # WM_HOTKEY
                    if msg.wParam == HOTKEY_ID:
                        self.sig_toggle.emit()
            time.sleep(0.05)

        user32.UnregisterHotKey(None, HOTKEY_ID)


# ════════════════════════════════════════════════════════
# TITAN DAEMON CONTROLLER
# ════════════════════════════════════════════════════════
class TITANDaemon(QObject):
    def __init__(self, app: QApplication):
        super().__init__()
        self.app             = app
        self._main_win       = None
        self._activation_win = None
        self._login_win      = None
        self._activation_cfg = {}
        self._hotkey         = HotkeyListener()
        self._ready          = False   # True after login done
        self._visible        = False

    def start(self):
        """Boot sequence: Activation → Login → Ready"""
        self._activation_win = launch_activation(self._on_activated)
        if self._activation_win is None:
            # Already activated
            self._activation_cfg = load_config()
            ActivationSession.load_from_config()
            self._launch_login()

    # ── Activation done ──────────────────────────────
    def _on_activated(self, cfg: dict):
        self._activation_cfg = cfg
        ActivationSession.set(cfg)
        if self._activation_win:
            try: self._activation_win.hide()
            except Exception: pass
        self._launch_login()

    # ── Login ────────────────────────────────────────
    def _launch_login(self):
        self._login_win = launch_login(self._on_logged_in)

    def _on_logged_in(self, user: dict):
        LoginSession.set(user, self._login_win.get_firebase())
        if self._login_win:
            try: self._login_win.hide()
            except Exception: pass

        # Inject user's Gemini API key
        api_key = self._activation_cfg.get("gemini_api_key", "")
        if api_key:
            import TABBU as TITAN_mod
            TITAN_mod._API_KEY = api_key

        # Build TITAN window (hidden)
        self._build_main_window(user)

        # Start hotkey listener
        self._hotkey.sig_toggle.connect(self._toggle_window)
        self._hotkey.start()
        self._ready = True

        # Show brief notification
        self._notify(
            "TITAN is ready",
            "Press  Win + Shift + A  to open TITAN"
        )

    # ── Build main window (keep hidden) ──────────────
    def _build_main_window(self, user: dict):
        self._main_win = TITANWindow()

        # Greet by name
        name = (user.get("displayName", "")
                or self._activation_cfg.get("display_name", ""))
        if name:
            try:
                # Replace default greeting with personalized one
                self._replace_greeting(name)
            except Exception:
                pass

        # Hide from taskbar: Qt.Tool + no taskbar button
        from PyQt5.QtCore import Qt
        self._main_win.setWindowFlags(
            self._main_win.windowFlags()
            | Qt.Tool
        )
        # Do NOT show — wait for hotkey
        self._visible = False

    def _replace_greeting(self, name: str):
        """Remove default greeting, add personalized one."""
        try:
            layout = self._main_win._msg_vl
            # Remove first 2 default bubbles
            for _ in range(2):
                item = layout.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()
            # Add personalized greeting
            self._main_win._add_sys("TITAN ONLINE — READY")
            self._main_win._add_bubble(
                "TITAN",
                f"Hey {name}! 💕 Main TITAN hoon. "
                f"Aaj kya karna hai jaan? ❤️"
            )
        except Exception:
            pass

    # ── Toggle window ────────────────────────────────
    def _toggle_window(self):
        if not self._ready or self._main_win is None:
            return

        if self._visible:
            self._main_win.hide()
            self._visible = False
        else:
            self._show_window()

    def _show_window(self):
        from PyQt5.QtCore import Qt
        win = self._main_win
        win.show()
        win.raise_()
        win.activateWindow()
        # Bring to front forcefully
        hwnd = int(win.winId())
        user32.ShowWindow(hwnd, 9)   # SW_RESTORE
        user32.SetForegroundWindow(hwnd)
        self._visible = True

    # ── Windows toast notification ───────────────────
    def _notify(self, title: str, msg: str):
        try:
            import subprocess
            ps = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
            script = f"""
[Windows.UI.Notifications.ToastNotificationManager,Windows.UI.Notifications,ContentType=WindowsRuntime]>$null
$T=[Windows.UI.Notifications.ToastTemplateType]::ToastText02
$X=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent($T)
$N=$X.GetElementsByTagName("text")
$N[0].AppendChild($X.CreateTextNode("{title}"))>$null
$N[1].AppendChild($X.CreateTextNode("{msg}"))>$null
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("TITAN").Show($X)"""
            subprocess.Popen(
                [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                creationflags=0x08000000   # CREATE_NO_WINDOW
            )
        except Exception:
            pass

    def stop(self):
        self._hotkey.stop()
        if self._main_win:
            self._main_win.close()


# ════════════════════════════════════════════════════════
# SINGLE INSTANCE LOCK
# ════════════════════════════════════════════════════════
def ensure_single_instance() -> bool:
    """Return True if this is the only running instance."""
    mutex = kernel32.CreateMutexW(None, False, "TITAN_v3_SingleInstance")
    err   = kernel32.GetLastError()
    if err == 183:   # ERROR_ALREADY_EXISTS
        # Already running — bring existing window to front via hotkey simulation
        user32.PostMessageW(user32.FindWindowW(None, "TITAN"), 0x0312, HOTKEY_ID, 0)
        return False
    return True


# ════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════
def main():
    # Single instance check
    if not ensure_single_instance():
        sys.exit(0)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("TITAN")
    app.setApplicationVersion("3.0")

    # Prevent app from quitting when all windows are hidden
    app.setQuitOnLastWindowClosed(False)

    # Dark palette
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

    daemon = TITANDaemon(app)
    daemon.start()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()