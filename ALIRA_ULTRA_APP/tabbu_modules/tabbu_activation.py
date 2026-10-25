# -*- coding: utf-8 -*-
"""
TITAN v5 — Activation Window  [SECURE — Backend API]
======================================================
- Firebase Admin SDK / JSON: COMPLETELY REMOVED from client
- Sirf license_client.py → HTTP POST → api.SecureWithAli.in
- Config stored: C:/Users/<user>/AppData/Roaming/ALIRA/license.json
- EXE + pip install dono mein kaam karta hai
"""

from ALIRA_slot import slot as _ALIRA_slot
import sys, json, threading, math, random, time, os, re
from datetime import datetime, timezone
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFrame, QStackedWidget,
    QSizePolicy, QGraphicsOpacityEffect, QScrollArea
)
from PyQt5.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QObject, QPropertyAnimation,
    QEasingCurve, QRect, QSize, QEventLoop
)
from PyQt5.QtGui import (
    QColor, QPainter, QPen, QBrush, QLinearGradient,
    QPalette, QFont, QPixmap, QIcon
)

# ── License client (NO Firebase) ─────────────────────────────────────────────
from TABBU_modules.license_client import (
    verify_license, load_license, save_license, clear_license,
    is_activated, get_device_id, get_device_info,
    LICENSE_FILE, BACKEND_URL,
)

# ── Colors ────────────────────────────────────────────────────────────────────
BG      = "#07091a"; BG2 = "#0c1124"; BG3 = "#111830"; PANEL = "#0f1628"
ACCENT  = "#7c5cfc"; ACC2 = "#a080ff"; CYAN = "#00e5ff"; TEAL = "#00c9a7"
GOLD    = "#ffc947"; TEXT = "#e2e8f8"; MUTED = "#5a6485"; MUTED2 = "#8892b0"
GREEN   = "#00d68f"; RED = "#ff4757"; BORDER = "rgba(124,92,252,0.18)"
BORDER2 = "rgba(124,92,252,0.35)"

# ── Backward compat aliases ───────────────────────────────────────────────────
CONFIG_PATH  = LICENSE_FILE
DEVICE_ID    = get_device_id()
KEY_PATTERN  = re.compile(r'^(TITAN|ALIRA)-[A-Z0-9]{4}-[A-Z0-9]{4,6}$')

def validate_key_format(key: str) -> bool:
    return bool(KEY_PATTERN.match(key.strip().upper()))

def load_config() -> dict:
    return load_license()

def save_config(data: dict) -> None:
    save_license(data)

def is_already_activated() -> bool:
    cfg = load_license()
    return bool(
        cfg.get("access_key") and
        cfg.get("device_id") == DEVICE_ID and
        cfg.get("gemini_api_key") and
        cfg.get("display_name")
    )

# ════════════════════════════════════════════════════════════════════════════
# ACTIVATION WORKER
# ════════════════════════════════════════════════════════════════════════════
class ActivationWorker(QObject):
    sig_key_valid   = pyqtSignal()
    sig_key_invalid = pyqtSignal(str)
    sig_activated   = pyqtSignal(dict)

    def verify_key(self, key: str):
        key = key.strip().upper()
        # Already locally activated with same key?
        cfg = load_license()
        if (cfg.get("access_key", "").upper() == key and
                cfg.get("device_id") == DEVICE_ID and
                cfg.get("gemini_api_key") and cfg.get("display_name")):
            self.sig_key_valid.emit()
            return
        # Format check only (backend verify on activate)
        if not validate_key_format(key):
            self.sig_key_invalid.emit(
                f"❌ Invalid key format.\n\nRequired: TITAN-XXXX-XXXXX\nEntered: {key}"
            )
            return
        self.sig_key_valid.emit()

    def activate(self, key: str, gemini_key: str, display_name: str):
        threading.Thread(
            target=self._activate,
            args=(key, gemini_key, display_name),
            daemon=True
        ).start()

    def _activate(self, key: str, gemini_key: str, display_name: str):
        result = verify_license(
            access_key=key, gemini_api_key=gemini_key, display_name=display_name
        )
        if result.success:
            self.sig_activated.emit(load_license())
        else:
            self.sig_key_invalid.emit(result.error or "❌ Activation failed. Try again.")

# ════════════════════════════════════════════════════════════════════════════
# ANIMATED BACKGROUND
# ════════════════════════════════════════════════════════════════════════════
class AnimatedBg(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._particles = [
            {"x": random.uniform(0,1), "y": random.uniform(0,1),
             "vx": random.uniform(-0.0003, 0.0003),
             "vy": random.uniform(-0.0003, 0.0003),
             "r": random.uniform(1,3), "a": random.uniform(0.2, 0.7)}
            for _ in range(55)
        ]
        self._t = 0
        t = QTimer(self); t.timeout.connect(_ALIRA_slot(self._tick)); t.start(33)

    def _tick(self):
        self._t += 1
        for p in self._particles:
            p["x"] = (p["x"] + p["vx"]) % 1.0
            p["y"] = (p["y"] + p["vy"]) % 1.0
        self.update()

    def paintEvent(self, _):
        W, H = self.width(), self.height()
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        g = QLinearGradient(0,0,0,H); g.setColorAt(0,QColor("#07091a")); g.setColorAt(1,QColor("#0c0e1f"))
        p.fillRect(0,0,W,H,g)
        pen = QPen()
        for pt in self._particles:
            x,y = int(pt["x"]*W), int(pt["y"]*H)
            c = QColor(ACCENT); c.setAlphaF(pt["a"]*(0.5+0.5*math.sin(self._t*0.04)))
            pen.setColor(c); p.setPen(pen); p.setBrush(QBrush(c))
            # ✅ FIX: r is a float (random.uniform) — x-r/r*2 become floats too,
            # and PyQt5's drawEllipse(x,y,w,h) overload requires ints, so this
            # raised TypeError on every paint (crashed the activation window).
            r = pt["r"]; p.drawEllipse(int(x-r), int(y-r), int(r*2), int(r*2))
        p.end()

# ════════════════════════════════════════════════════════════════════════════
# UI HELPERS
# ════════════════════════════════════════════════════════════════════════════
def _lbl(text, color=TEXT, size=14, bold=False, align=Qt.AlignLeft):
    l = QLabel(text)
    l.setStyleSheet(f"color:{color};font-size:{size}px;font-weight:{'700' if bold else '400'};background:transparent;")
    l.setAlignment(align); return l

def _inp(placeholder="", echo=False):
    e = QLineEdit(); e.setPlaceholderText(placeholder)
    if echo: e.setEchoMode(QLineEdit.Password)
    e.setStyleSheet(f"""
        QLineEdit{{background:{BG3};border:1.5px solid {BORDER2};border-radius:10px;
            color:{TEXT};font-size:14px;padding:10px 14px;}}
        QLineEdit:focus{{border:1.5px solid {ACCENT};background:#131a2e;}}
        QLineEdit::placeholder{{color:{MUTED};}}""")
    e.setMinimumHeight(44); return e

def _btn(text, primary=True):
    b = QPushButton(text)
    if primary:
        b.setStyleSheet(f"""
            QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {ACCENT},stop:1 {ACC2});
                color:#fff;font-size:14px;font-weight:700;border:none;border-radius:10px;padding:12px 32px;}}
            QPushButton:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {ACC2},stop:1 {ACCENT});}}
            QPushButton:disabled{{background:{MUTED};color:#333;}}""")
    else:
        b.setStyleSheet(f"QPushButton{{background:transparent;color:{MUTED2};font-size:12px;border:none;padding:6px;}}QPushButton:hover{{color:{ACC2};}}")
    b.setCursor(Qt.PointingHandCursor); return b

# ════════════════════════════════════════════════════════════════════════════
# PANELS
# ════════════════════════════════════════════════════════════════════════════
class PanelWelcome(QWidget):
    sig_next = pyqtSignal()
    def __init__(self):
        super().__init__(); self.setAttribute(Qt.WA_TranslucentBackground)
        v = QVBoxLayout(self); v.setContentsMargins(40,40,40,40); v.setSpacing(18)
        v.addStretch(1)
        v.addWidget(_lbl("🤖", ACCENT, 52, align=Qt.AlignCenter))
        v.addWidget(_lbl("WELCOME TO", MUTED2, 13, align=Qt.AlignCenter))
        v.addWidget(_lbl("ALIRA AI ASSISTANT", ACCENT, 28, bold=True, align=Qt.AlignCenter))
        v.addWidget(_lbl("Your intelligent desktop companion", MUTED2, 13, align=Qt.AlignCenter))
        v.addSpacing(12)
        v.addWidget(_lbl(f"🔗 {BACKEND_URL}", MUTED2, 11, align=Qt.AlignCenter))
        v.addSpacing(20)
        btn = _btn("Get Started →"); btn.setFixedWidth(220); btn.clicked.connect(_ALIRA_slot(self.sig_next))
        h = QHBoxLayout(); h.addStretch(); h.addWidget(btn); h.addStretch(); v.addLayout(h)
        v.addStretch(1)

class PanelKey(QWidget):
    sig_back = pyqtSignal(); sig_verified = pyqtSignal(str)
    def __init__(self):
        super().__init__(); self.setAttribute(Qt.WA_TranslucentBackground)
        self._worker = ActivationWorker()
        self._worker.sig_key_valid.connect(self._on_valid)
        self._worker.sig_key_invalid.connect(self._on_invalid)
        v = QVBoxLayout(self); v.setContentsMargins(40,40,40,40); v.setSpacing(14)
        v.addStretch(1)
        v.addWidget(_lbl("🔑", GOLD, 36, align=Qt.AlignCenter))
        v.addWidget(_lbl("Enter Access Key", TEXT, 22, bold=True, align=Qt.AlignCenter))
        v.addWidget(_lbl("Format: TITAN-XXXX-XXXXX  or  ALIRA-XXXX-XXXXX", MUTED2, 12, align=Qt.AlignCenter))
        v.addSpacing(10)
        self._inp = _inp("TITAN-XXXX-XXXXX"); self._inp.setAlignment(Qt.AlignCenter)
        self._inp.textChanged.connect(_ALIRA_slot(self._on_text)); v.addWidget(self._inp)
        self._err = _lbl("", RED, 12, align=Qt.AlignCenter); self._err.setWordWrap(True); v.addWidget(self._err)
        self._btn = _btn("Verify Key"); self._btn.setFixedWidth(200); self._btn.setEnabled(False)
        self._btn.clicked.connect(_ALIRA_slot(self._verify))
        bh = QHBoxLayout(); bh.addStretch(); bh.addWidget(self._btn); bh.addStretch(); v.addLayout(bh)
        back = _btn("← Back", False); back.clicked.connect(_ALIRA_slot(self.sig_back))
        bh2 = QHBoxLayout(); bh2.addStretch(); bh2.addWidget(back); bh2.addStretch(); v.addLayout(bh2)
        v.addStretch(1)

    def _on_text(self, t): self._err.setText(""); self._btn.setEnabled(len(t.strip()) >= 5)
    def _verify(self):
        self._btn.setEnabled(False); self._btn.setText("Checking…"); self._err.setText("")
        self._worker.verify_key(self._inp.text().strip().upper())
    def _on_valid(self):
        self._btn.setText("Verify Key"); self._btn.setEnabled(True)
        self.sig_verified.emit(self._inp.text().strip().upper())
    def _on_invalid(self, msg):
        self._err.setText(msg); self._btn.setText("Verify Key"); self._btn.setEnabled(True)

class PanelProfile(QWidget):
    sig_back = pyqtSignal(); sig_activated = pyqtSignal(); sig_error = pyqtSignal(str)
    def __init__(self):
        super().__init__(); self.setAttribute(Qt.WA_TranslucentBackground)
        self._key = ""; self._worker = ActivationWorker()
        self._worker.sig_activated.connect(lambda _: self.sig_activated.emit())
        self._worker.sig_key_invalid.connect(self._on_error)
        v = QVBoxLayout(self); v.setContentsMargins(40,40,40,40); v.setSpacing(12)
        v.addStretch(1)
        v.addWidget(_lbl("👤", CYAN, 36, align=Qt.AlignCenter))
        v.addWidget(_lbl("Complete Your Profile", TEXT, 20, bold=True, align=Qt.AlignCenter))
        v.addWidget(_lbl("Fill in your details to activate.", MUTED2, 12, align=Qt.AlignCenter))
        v.addSpacing(8)
        v.addWidget(_lbl("Display Name", MUTED2, 12))
        self._name = _inp("Your Name (e.g. Alih)"); v.addWidget(self._name)
        v.addWidget(_lbl("Gemini API Key", MUTED2, 12))
        self._api = _inp("AIzaSy..."); v.addWidget(self._api)
        lnk = _btn("🔗 Get free API key → aistudio.google.com", False)
        lnk.clicked.connect(lambda: __import__("webbrowser").open("https://aistudio.google.com/app/apikey"))
        v.addWidget(lnk)
        self._err = _lbl("", RED, 12, align=Qt.AlignCenter); self._err.setWordWrap(True); v.addWidget(self._err)
        self._btn = _btn("🚀 Activate ALIRA"); self._btn.setFixedWidth(220); self._btn.clicked.connect(_ALIRA_slot(self._activate))
        bh = QHBoxLayout(); bh.addStretch(); bh.addWidget(self._btn); bh.addStretch(); v.addLayout(bh)
        back = _btn("← Back", False); back.clicked.connect(_ALIRA_slot(self.sig_back))
        bh2 = QHBoxLayout(); bh2.addStretch(); bh2.addWidget(back); bh2.addStretch(); v.addLayout(bh2)
        v.addStretch(1)

    def set_key(self, k): self._key = k
    def _activate(self):
        name = self._name.text().strip(); api = self._api.text().strip()
        if not name: self._err.setText("⚠️ Please enter your display name."); return
        if not api:  self._err.setText("⚠️ Please enter your Gemini API key."); return
        self._btn.setEnabled(False); self._btn.setText("Activating…"); self._err.setText("")
        self._worker.activate(self._key, api, name)
    def _on_error(self, msg):
        self._err.setText(msg); self._btn.setText("🚀 Activate ALIRA"); self._btn.setEnabled(True)

class PanelSuccess(QWidget):
    sig_launch = pyqtSignal()
    def __init__(self):
        super().__init__(); self.setAttribute(Qt.WA_TranslucentBackground)
        v = QVBoxLayout(self); v.setContentsMargins(40,40,40,40); v.setSpacing(16)
        v.addStretch(1)
        v.addWidget(_lbl("✅", GREEN, 52, align=Qt.AlignCenter))
        v.addWidget(_lbl("Activation Successful!", GREEN, 22, bold=True, align=Qt.AlignCenter))
        self._welcome = _lbl("Welcome!", CYAN, 16, align=Qt.AlignCenter); v.addWidget(self._welcome)
        v.addWidget(_lbl("ALIRA is ready. Let's go!", MUTED2, 13, align=Qt.AlignCenter))
        v.addSpacing(20)
        self._btn = _btn("🚀 Launch ALIRA"); self._btn.setFixedWidth(200); self._btn.clicked.connect(_ALIRA_slot(self.sig_launch))
        bh = QHBoxLayout(); bh.addStretch(); bh.addWidget(self._btn); bh.addStretch(); v.addLayout(bh)
        v.addStretch(1)

    def set_user(self, name): self._welcome.setText(f"Welcome, {name}! 🎉")

# ════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ════════════════════════════════════════════════════════════════════════════
class ActivationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ALIRA AI — Activation")
        self.setFixedSize(480, 580)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag_pos = None

        self._bg = AnimatedBg(self); self._bg.setGeometry(0,0,480,580)
        card = QFrame(self); card.setGeometry(24,24,432,532)
        card.setStyleSheet(f"QFrame{{background:rgba(12,17,36,0.92);border:1.5px solid {BORDER2};border-radius:20px;}}")

        self._stack = QStackedWidget(card); self._stack.setGeometry(0,0,432,532)
        self._stack.setStyleSheet("background:transparent;")

        self._p_welcome = PanelWelcome()
        self._p_key     = PanelKey()
        self._p_profile = PanelProfile()
        self._p_success = PanelSuccess()
        for p in [self._p_welcome, self._p_key, self._p_profile, self._p_success]:
            self._stack.addWidget(p)

        self._p_welcome.sig_next.connect(lambda: self._stack.setCurrentIndex(1))
        self._p_key.sig_back.connect(lambda: self._stack.setCurrentIndex(0))
        self._p_key.sig_verified.connect(self._on_key_verified)
        self._p_profile.sig_back.connect(lambda: self._stack.setCurrentIndex(1))
        self._p_profile.sig_activated.connect(self._on_activated)
        self._p_success.sig_launch.connect(self.close)

        close_btn = QPushButton("✕", self); close_btn.setGeometry(440,8,32,32)
        close_btn.setStyleSheet(f"QPushButton{{background:rgba(255,71,87,0.15);color:{RED};border:1px solid rgba(255,71,87,0.3);border-radius:16px;font-size:14px;}}QPushButton:hover{{background:{RED};color:white;}}")
        close_btn.clicked.connect(_ALIRA_slot(self.close))

    def _on_key_verified(self, key):
        self._p_profile.set_key(key); self._stack.setCurrentIndex(2)
    def _on_activated(self):
        cfg = load_license()
        self._p_success.set_user(cfg.get("display_name", cfg.get("user_name", "User")))
        self._stack.setCurrentIndex(3)
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.LeftButton: self.move(e.globalPos() - self._drag_pos)
    def mouseReleaseEvent(self, e): self._drag_pos = None

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setStyle("Fusion")
    win = ActivationWindow(); win.show(); sys.exit(app.exec_())
