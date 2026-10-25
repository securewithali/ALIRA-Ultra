# -*- coding: utf-8 -*-
"""
TITAN v4 — Hotkey Version
  Ctrl+Alt+A  → TITAN show/hide
  Ctrl+Alt+B  → Mini bar show/hide
  EXE start pe → hidden (600ms baad)
"""
from ALIRA_slot import slot as _ALIRA_slot
import sys, os, threading, time, ctypes, ctypes.wintypes

try:
    from PyQt5 import QtWebEngineWidgets   # noqa: F401 — QApplication se PEHLE import (Website Studio live preview)
except Exception:
    pass
from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout,
    QLabel, QPushButton, QFrame
)
from PyQt5.QtCore  import Qt, QObject, pyqtSignal, QTimer, QPoint
from PyQt5.QtGui   import QColor, QPalette

# ── EXE ke andar bundled files ka path fix ──
# PyInstaller EXE mein files sys._MEIPASS mein hoti hain
if getattr(sys, 'frozen', False):
    _BASE = sys._MEIPASS
else:
    _BASE = os.path.dirname(os.path.abspath(__file__))

if _BASE not in sys.path:
    sys.path.insert(0, _BASE)

# Enhanced Gemini-style MiniBar
try:
    try:
        from TABBU_modules.minibar_TABBU import MiniBar
    except ImportError:
        from TABBU_modules.minibar_TABBU import MiniBar
    print("[TITAN] Enhanced MiniBar loaded ✓")
except ImportError as _e:
    print(f"[TITAN] minibar_TITAN load failed: {_e} — fallback MiniBar")
    # Fallback simple MiniBar agar import fail ho
    class MiniBar(QWidget):
        sig_open_full   = pyqtSignal()
        sig_mic_toggled = pyqtSignal(bool)
        def __init__(self):
            super().__init__(None,
                Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setAttribute(Qt.WA_ShowWithoutActivating)
            self._mic_on = True
            self._drag_pos = QPoint()
            self._dragging = False
            self._build(); self._place()
        def _build(self):
            self.setFixedSize(220, 58)
            f = QFrame(self); f.setGeometry(0,0,220,58)
            f.setStyleSheet("QFrame{background:rgba(8,13,24,0.97);border:1.5px solid rgba(232,64,106,0.55);border-radius:29px;}")
            hl = QHBoxLayout(f); hl.setContentsMargins(14,8,14,8); hl.setSpacing(10)
            d = QLabel("✦"); d.setStyleSheet("color:#e8406a;font-size:12px;background:transparent;"); d.setFixedWidth(14)
            hl.addWidget(d)
            h = QLabel("A=TITAN  B=BAR"); h.setStyleSheet("color:rgba(107,115,148,0.7);font-size:8px;font-family:'Courier New';background:transparent;")
            hl.addWidget(h)
            self._mb = QPushButton("🎤"); self._mb.setFixedSize(36,36); self._mb.setCursor(Qt.PointingHandCursor); self._mb.clicked.connect(_ALIRA_slot(self._tog)); hl.addWidget(self._mb)
            ob = QPushButton("▶"); ob.setFixedSize(36,36); ob.setCursor(Qt.PointingHandCursor)
            ob.setStyleSheet("QPushButton{background:rgba(0,212,255,0.1);border:1.5px solid rgba(0,212,255,0.45);border-radius:18px;color:#00d4ff;font-size:13px;}QPushButton:hover{background:rgba(0,212,255,0.25);}")
            ob.clicked.connect(_ALIRA_slot(self.sig_open_full.emit)); hl.addWidget(ob)
            self._ref()
        def _ref(self):
            if self._mic_on: self._mb.setText("🎤"); self._mb.setStyleSheet("QPushButton{background:rgba(232,64,106,0.15);border:1.5px solid #e8406a;border-radius:18px;font-size:16px;}QPushButton:hover{background:rgba(232,64,106,0.3);}")
            else: self._mb.setText("🔇"); self._mb.setStyleSheet("QPushButton{background:rgba(80,80,100,0.15);border:1.5px solid rgba(150,150,180,0.3);border-radius:18px;font-size:16px;}")
        def _tog(self): self._mic_on = not self._mic_on; self._ref(); self.sig_mic_toggled.emit(self._mic_on)
        def sync_mic(self, on): self._mic_on = on; self._ref()
        def _place(self):
            scr = QApplication.primaryScreen().geometry()
            self.move(scr.width()//2 - self.width()//2, scr.height()-self.height()-40)
        def mousePressEvent(self,e):
            if e.button()==Qt.LeftButton: self._dragging=True; self._drag_pos=e.globalPos()-self.frameGeometry().topLeft()
        def mouseMoveEvent(self,e):
            if self._dragging: self.move(e.globalPos()-self._drag_pos)
        def mouseReleaseEvent(self,e): self._dragging=False

BG     = "#050810"
BG2    = "#080d18"
BG3    = "#0d1525"
ACCENT = "#e8406a"
CYAN   = "#00d4ff"
TEXT   = "#e8eaf6"
MUTED  = "#6b7394"

HK_FULL = 1001
HK_MINI = 1002

MOD_CTRL     = 0x0002
MOD_ALT      = 0x0001
MOD_NOREPEAT = 0x4000
VK_A         = 0x41
VK_B         = 0x42

WM_HOTKEY  = 0x0312
WM_DESTROY = 0x0002

user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


def force_foreground(hwnd: int):
    try:
        fg_hwnd  = user32.GetForegroundWindow()
        fg_tid   = user32.GetWindowThreadProcessId(fg_hwnd, None)
        our_tid  = kernel32.GetCurrentThreadId()
        if fg_tid and fg_tid != our_tid:
            user32.AttachThreadInput(our_tid, fg_tid, True)
        user32.ShowWindow(hwnd, 9)
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
        if fg_tid and fg_tid != our_tid:
            user32.AttachThreadInput(our_tid, fg_tid, False)
    except Exception as e:
        print(f"[FG] {e}")


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style",         ctypes.c_uint),
        ("lpfnWndProc",   ctypes.c_void_p),
        ("cbClsExtra",    ctypes.c_int),
        ("cbWndExtra",    ctypes.c_int),
        ("hInstance",     ctypes.wintypes.HINSTANCE),
        ("hIcon",         ctypes.wintypes.HICON),
        ("hCursor",       ctypes.wintypes.HANDLE),
        ("hbrBackground", ctypes.wintypes.HBRUSH),
        ("lpszMenuName",  ctypes.wintypes.LPCWSTR),
        ("lpszClassName", ctypes.wintypes.LPCWSTR),
    ]

WNDPROCTYPE = ctypes.WINFUNCTYPE(
    ctypes.c_long, ctypes.wintypes.HWND, ctypes.c_uint,
    ctypes.wintypes.WPARAM, ctypes.wintypes.LPARAM,
)


class HotkeyEngine(QObject):
    sig_full = pyqtSignal()
    sig_mini = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._hwnd       = None
        self._running    = False
        self._thread     = None
        self._wndproc_cb = None

    def start(self):
        self._running = True
        self._thread  = threading.Thread(
            target=self._thread_main, daemon=True, name="TITAN-HK"
        )
        self._thread.start()

    def stop(self):
        self._running = False
        if self._hwnd:
            try: user32.PostMessageW(self._hwnd, WM_DESTROY, 0, 0)
            except: pass

    def _thread_main(self):
        def wnd_proc(hwnd, msg, wparam, lparam):
            if msg == WM_HOTKEY:
                if   wparam == HK_FULL: self.sig_full.emit()
                elif wparam == HK_MINI: self.sig_mini.emit()
                return 0
            elif msg == WM_DESTROY:
                user32.PostQuitMessage(0)
                return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc_cb = WNDPROCTYPE(wnd_proc)

        cls_name  = "TITAN_HK_V4B"
        hinstance = kernel32.GetModuleHandleW(None)
        user32.UnregisterClassW(cls_name, hinstance)

        wc = WNDCLASSW()
        wc.lpfnWndProc   = ctypes.cast(self._wndproc_cb, ctypes.c_void_p)
        wc.hInstance     = hinstance
        wc.lpszClassName = cls_name

        if not user32.RegisterClassW(ctypes.byref(wc)):
            print(f"[HK] RegisterClass failed: {kernel32.GetLastError()}")
            return

        hwnd = user32.CreateWindowExW(
            0, cls_name, "TITAN_HK", 0,
            0, 0, 0, 0, None, None, hinstance, None
        )
        if not hwnd:
            print(f"[HK] CreateWindow failed: {kernel32.GetLastError()}")
            return

        self._hwnd = hwnd

        ok1 = user32.RegisterHotKey(hwnd, HK_FULL, MOD_CTRL | MOD_ALT | MOD_NOREPEAT, VK_A)
        if not ok1:
            ok1 = user32.RegisterHotKey(hwnd, HK_FULL, MOD_CTRL | MOD_ALT, VK_A)
        print(f"[HK] Ctrl+Alt+A: {'OK' if ok1 else f'FAIL err={kernel32.GetLastError()}'}")

        ok2 = user32.RegisterHotKey(hwnd, HK_MINI, MOD_CTRL | MOD_ALT | MOD_NOREPEAT, VK_B)
        if not ok2:
            ok2 = user32.RegisterHotKey(hwnd, HK_MINI, MOD_CTRL | MOD_ALT, VK_B)
        print(f"[HK] Ctrl+Alt+B: {'OK' if ok2 else f'FAIL err={kernel32.GetLastError()}'}")

        msg_obj = ctypes.wintypes.MSG()
        print("[HK] Listening...")

        while self._running:
            if user32.PeekMessageW(ctypes.byref(msg_obj), None, 0, 0, 1):
                if msg_obj.message == WM_HOTKEY:
                    if   msg_obj.wParam == HK_FULL: self.sig_full.emit()
                    elif msg_obj.wParam == HK_MINI: self.sig_mini.emit()
                elif msg_obj.message == WM_DESTROY:
                    break
                user32.TranslateMessage(ctypes.byref(msg_obj))
                user32.DispatchMessageW(ctypes.byref(msg_obj))
            else:
                time.sleep(0.01)

        for hk_id in (HK_FULL, HK_MINI):
            try: user32.UnregisterHotKey(hwnd, hk_id)
            except: pass
        try: user32.DestroyWindow(hwnd)
        except: pass
        try: user32.UnregisterClassW(cls_name, hinstance)
        except: pass
        self._hwnd = None


class TITANApp:
    def __init__(self, app):
        self.app           = app
        self._TITAN_win     = None
        self._mini_bar     = None
        self._login_win    = None
        self._user         = {}
        self._full_visible = False
        self._mini_visible = False
        self._ready        = False
        self._hotkey       = None
        self._LogS         = None

    def start(self):
        # ── STEP 0: Activation Check ──────────────────────────
        print("[TITAN] Skipping activation check - going to login...")

        # ── STEP 1: Login ─────────────────────────────────────
        try:
            from TABBU_modules.TABBU_login import LoginWindow, Session as LogS
        except ImportError:
            from TABBU_modules.TABBU_login import LoginWindow, Session as LogS
        self._LogS = LogS
        self._login_win = LoginWindow()
        self._login_win.sig_logged_in.connect(self._on_logged_in)
        self._login_win.show()

    def _on_logged_in(self, user):
        self._user = user
        try:
            self._LogS.set(user, self._login_win.get_firebase())
        except Exception as e:
            print(f"[Session] {e}")
        try:
            self._login_win.hide()
        except:
            pass

        # Face Authentication
        try:
            try:
                from TABBU_modules.face_auth import run_face_auth
            except ImportError:
                from TABBU_modules.face_auth import run_face_auth
            if not run_face_auth():
                print("[TITAN] Face authentication failed — exiting")
                sys.exit(1)
        except Exception as e:
            print(f"[FaceAuth] Error: {e} — authentication failed")
# ... (rest of the code remains the same)
            sys.exit(1)

        self._launch_TITAN()

    def _launch_TITAN(self):
        from TABBU import TITANWindow
        name = (self._user.get("displayName", "").strip()
                or self._user.get("email", "").split("@")[0].strip())
        if name:
            name = name[0].upper() + name[1:]

        self._TITAN_win = TITANWindow()
        self._TITAN_win.setWindowTitle(f"TITAN  —  {name}" if name else "TITAN")

        w = self._TITAN_win._worker
        w.sig_user_msg.connect(lambda t: self._save_msg("user", t))
        w.sig_TITAN_msg.connect(lambda t: self._save_msg("model", t))

        self._TITAN_win.show()
        self._full_visible = True
        QTimer.singleShot(600, self._auto_hide)

        # ── MiniBar setup — try/except se crash nahi hoga ──
        try:
            self._mini_bar = MiniBar()
            self._mini_bar.sig_open_full.connect(self._show_full)
            self._mini_bar.sig_mic_toggled.connect(self._on_minibar_mic)
            self._mini_bar.hide()
            self._mini_visible = False
            print("[TITAN] MiniBar created OK")
        except Exception as _mb_err:
            print(f"[TITAN] MiniBar create FAILED: {_mb_err}")
            import traceback; traceback.print_exc()
            self._mini_bar = None
            self._mini_visible = False

        # TITAN window mic button sync
        try:
            self._TITAN_win._mic_btn.clicked.connect(_ALIRA_slot(self._on_TITANwin_mic_clicked))
        except Exception as e:
            print(f"[TITAN] mic_btn connect: {e}")

        self._ready = True

        self._hotkey = HotkeyEngine()
        self._hotkey.sig_full.connect(self._toggle_full)
        self._hotkey.sig_mini.connect(self._toggle_mini)
        self._hotkey.start()

        QTimer.singleShot(2500, self._show_toast)
        print(f"[TITAN] Ready | {name} | Ctrl+Alt+A / Ctrl+Alt+B")

    def _auto_hide(self):
        if self._TITAN_win and self._full_visible:
            self._TITAN_win.hide()
            self._full_visible = False
            print("[TITAN] Auto-hidden. Ctrl+Alt+A se kholo.")

    def _save_msg(self, role, text):
        try:
            if self._LogS:
                self._LogS.save_message(role, text)
        except Exception as e:
            print(f"[Firebase] {e}")

    # ── Mic sync ───────────────────────────────────────────

    def _on_minibar_mic(self, on: bool):
        """
        MiniBar mic button → worker + TITAN window UI dono update karo.
        on=True  → mic active (TITAN sunegi)
        on=False → mic muted (TITAN nahi sunegi)
        """
        try:
            # 1. GeminiWorker ko batao — audio capture band/chalu
            self._TITAN_win._worker.set_mic(on)

            # 2. TITAN window internal state sync
            self._TITAN_win._mic_on = on

            # 3. TITAN window mic button appearance update
            self._TITAN_win._set_mic_style(on)

            # 4. Hint text update
            self._TITAN_win._hint.setText(
                "TITAN sun rahi hai..."
                if on else "Mic muted — MiniBar se ON karo"
            )

            # 5. Mute pe status standby pe lao — waveform freeze na ho
            if not on:
                self._TITAN_win._on_status("standby", "MIC MUTED")

            print(f"[MiniBar→TITAN] Mic {'ON' if on else 'MUTED'}")

        except Exception as e:
            print(f"[MiniMic] {e}")

    def _on_TITANwin_mic_clicked(self):
        """
        TITAN window ka mic button click hua →
        MiniBar orb bhi same state pe sync karo.
        TITAN.py ka _on_mic() already _mic_on toggle + worker.set_mic() call
        kar chuka hota hai jab yeh fire hota hai.
        """
        try:
            if self._mini_bar:
                current = self._TITAN_win._mic_on
                self._mini_bar.sync_mic(current)
                print(f"[TITAN→MiniBar] Mic {'ON' if current else 'MUTED'}")
        except Exception as e:
            print(f"[TITANMic→Mini] {e}")

    # ── Window show/hide ───────────────────────────────────

    def _toggle_full(self):
        if not self._ready:
            return
        if self._full_visible:
            self._hide_full()
        else:
            self._show_full()

    def _show_full(self):
        if not self._TITAN_win:
            return
        flags = self._TITAN_win.windowFlags()
        self._TITAN_win.setWindowFlags(flags | Qt.WindowStaysOnTopHint)
        self._TITAN_win.show()
        self._TITAN_win.raise_()
        self._TITAN_win.activateWindow()
        try:
            hwnd = int(self._TITAN_win.winId())
            force_foreground(hwnd)
        except Exception as e:
            print(f"[Show] {e}")
        QTimer.singleShot(200, self._clear_topmost)
        self._full_visible = True
        print("[HK] TITAN → shown")

    def _clear_topmost(self):
        try:
            if self._TITAN_win:
                flags = self._TITAN_win.windowFlags()
                self._TITAN_win.setWindowFlags(flags & ~Qt.WindowStaysOnTopHint)
                self._TITAN_win.show()
        except Exception as e:
            print(f"[TopMost] {e}")

    def _hide_full(self):
        if self._TITAN_win:
            self._TITAN_win.hide()
        self._full_visible = False
        print("[HK] TITAN → hidden")

    def _toggle_mini(self):
        if not self._ready:
            print("[HK] Mini: not ready")
            return

        if self._mini_bar is None:
            print("[HK] Mini: MiniBar was None, creating now...")
            try:
                self._mini_bar = MiniBar()
                self._mini_bar.sig_open_full.connect(self._show_full)
                self._mini_bar.sig_mic_toggled.connect(self._on_minibar_mic)
                self._mini_visible = False
                print("[HK] Mini: MiniBar created OK")
            except Exception as e:
                print(f"[HK] Mini: MiniBar create failed: {e}")
                import traceback; traceback.print_exc()
                return

        try:
            if self._mini_visible:
                self._mini_bar.hide()
                self._mini_visible = False
                print("[HK] MiniBar → hidden")
            else:
                try:
                    self._mini_bar.sync_mic(self._TITAN_win._mic_on)
                except Exception:
                    pass
                self._mini_bar.show()
                self._mini_bar.raise_()
                self._mini_visible = True
                print("[HK] MiniBar → shown")
        except Exception as e:
            print(f"[HK] _toggle_mini error: {e}")
            import traceback; traceback.print_exc()

    def _show_toast(self):
        try:
            import subprocess
            name  = self._user.get("displayName", "").strip()
            greet = f"Hello {name}! " if name else ""
            msg   = f"{greet}Ctrl+Alt+A = TITAN  |  Ctrl+Alt+B = Mini bar"
            ps    = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
            sc = (
                "[Windows.UI.Notifications.ToastNotificationManager,"
                "Windows.UI.Notifications,ContentType=WindowsRuntime]|Out-Null;"
                "$T=[Windows.UI.Notifications.ToastTemplateType]::ToastText02;"
                "$X=[Windows.UI.Notifications.ToastNotificationManager]"
                "::GetTemplateContent($T);"
                "$N=$X.GetElementsByTagName('text');"
                "$N[0].AppendChild($X.CreateTextNode('TITAN Ready'))|Out-Null;"
                f"$N[1].AppendChild($X.CreateTextNode('{msg}'))|Out-Null;"
                "[Windows.UI.Notifications.ToastNotificationManager]"
                "::CreateToastNotifier('TITAN').Show($X)"
            )
            subprocess.Popen(
                [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", sc],
                creationflags=0x08000000
            )
        except Exception as e:
            print(f"[Toast] {e}")


def main():
    try:
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except:
        pass

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("TITAN")
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

    ctrl = TITANApp(app)
    ctrl.start()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()