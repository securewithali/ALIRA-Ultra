# -*- coding: utf-8 -*-
"""
TITAN v4 — Enhanced MiniBar (Gemini-style pill)
Drop-in replacement for MiniBar class in main_hotkey.py

Features:
  - Gemini-style dark cyberpunk pill, centered bottom of screen
  - Animated waveform bars (randomize when mic is active)
  - Pulsing mic orb with dual ring animation
  - Mute/unmute with smooth state transition
  - Cyan status dot with breathing animation
  - Hotkey hint label (Ctrl+Alt+A / Ctrl+Alt+B)
  - Top highlight glow line on pill
  - Drag anywhere
"""

from ALIRA_slot import slot as _ALIRA_slot
import sys, random, math
from PyQt5.QtWidgets import (
    QApplication, QWidget, QHBoxLayout, QVBoxLayout,
    QLabel, QPushButton, QFrame, QGraphicsDropShadowEffect,
)
from PyQt5.QtCore import (
    Qt, pyqtSignal, QTimer, QPoint, QRect, pyqtProperty,
)
from PyQt5.QtGui import (
    QColor, QPalette, QPainter, QPainterPath,
    QLinearGradient, QRadialGradient, QPen, QBrush, QFont,
)


# ══════════════════════════════════════════════════════════
#  Animated waveform
# ══════════════════════════════════════════════════════════
class WaveformWidget(QWidget):
    BAR_N   = 11
    BAR_W   = 3
    BAR_GAP = 3
    MAX_H   = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._active  = True
        self._heights = [random.randint(4, self.MAX_H) for _ in range(self.BAR_N)]
        tw = self.BAR_N * self.BAR_W + (self.BAR_N - 1) * self.BAR_GAP
        self.setFixedSize(tw, self.MAX_H + 4)
        t = QTimer(self); t.timeout.connect(_ALIRA_slot(self._tick)); t.start(360)

    def set_active(self, on):
        self._active = on
        if not on:
            self._heights = [3] * self.BAR_N
        self.update()

    def _tick(self):
        if not self._active: return
        self._heights = [random.randint(4, self.MAX_H) for _ in range(self.BAR_N)]
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        H = self.height()
        for i, h in enumerate(self._heights):
            x = i * (self.BAR_W + self.BAR_GAP)
            y = (H - h) // 2
            if self._active:
                alpha = 100 + int(155 * h / self.MAX_H)
                c = QColor(0, 212, 255, alpha)
            else:
                c = QColor(74, 82, 112, 80)
            p.setBrush(c); p.setPen(Qt.NoPen)
            p.drawRoundedRect(x, y, self.BAR_W, h, 1.5, 1.5)


# ══════════════════════════════════════════════════════════
#  Pulsing mic orb
# ══════════════════════════════════════════════════════════
class MicOrb(QWidget):
    clicked = pyqtSignal()
    R = 26

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(52, 52)
        self.setCursor(Qt.PointingHandCursor)
        self._mic_on  = True
        self._hovered = False
        self._phase   = 0.0
        t = QTimer(self); t.timeout.connect(_ALIRA_slot(self._tick)); t.start(16)

    def set_mic(self, on):
        self._mic_on = on; self.update()

    def _tick(self):
        self._phase = (self._phase + 0.022) % 1.0
        self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        cx, cy, r = 26, 26, self.R

        # Dual pulse rings
        if self._mic_on:
            for offset in (0.0, 0.5):
                t = (self._phase + offset) % 1.0
                rr = r + 4 + t * 12
                a  = int(170 * max(0.0, 1.0 - t))
                p.setPen(QPen(QColor(232, 64, 106, a), 1.2))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(int(cx - rr), int(cy - rr), int(rr * 2), int(rr * 2))

        # Orb body
        grad = QRadialGradient(cx, cy - 6, r * 1.2)
        if self._mic_on:
            grad.setColorAt(0.0, QColor(255, 96, 122))
            grad.setColorAt(0.55, QColor(232, 64, 106))
            grad.setColorAt(1.0, QColor(110, 18, 46))
        else:
            grad.setColorAt(0.0, QColor(50, 58, 88))
            grad.setColorAt(1.0, QColor(20, 24, 46))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(grad))
        p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # Highlight
        if self._mic_on:
            hl = QRadialGradient(cx - 7, cy - 10, r * 0.55)
            hl.setColorAt(0.0, QColor(255, 255, 255, 50))
            hl.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.setBrush(QBrush(hl)); p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # Hover overlay
        if self._hovered:
            p.setBrush(QColor(255, 255, 255, 18)); p.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # Icon
        p.setFont(QFont("Segoe UI Emoji", 14))
        p.setPen(QColor(255, 255, 255, 225))
        p.drawText(QRect(cx - r, cy - r, r * 2, r * 2), Qt.AlignCenter,
                   "🎤" if self._mic_on else "🔇")

        # Status dot (breathing)
        dr = 4
        dx = cx + r - dr - 2; dy = cy + r - dr - 2
        if self._mic_on:
            a = int(180 + 75 * math.sin(self._phase * math.pi * 2))
            p.setBrush(QColor(0, 212, 255, a))
            p.setPen(QPen(QColor(6, 10, 22), 1))
        else:
            p.setBrush(QColor(60, 68, 98)); p.setPen(Qt.NoPen)
        p.drawEllipse(dx - dr, dy - dr, dr * 2, dr * 2)

    def enterEvent(self, e): self._hovered = True;  self.update()
    def leaveEvent(self, e): self._hovered = False; self.update()
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self.clicked.emit()


# ══════════════════════════════════════════════════════════
#  Pill frame (custom paint: bg gradient + border + top glow)
# ══════════════════════════════════════════════════════════
class PillFrame(QFrame):
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height(); r = H / 2

        # Background
        bg = QLinearGradient(0, 0, 0, H)
        bg.setColorAt(0, QColor(14, 20, 42, 252))
        bg.setColorAt(1, QColor(6, 10, 22, 252))
        path = QPainterPath(); path.addRoundedRect(0, 0, W, H, r, r)
        p.fillPath(path, QBrush(bg))

        # Border
        p.setPen(QPen(QColor(0, 212, 255, 44), 1.0)); p.setBrush(Qt.NoBrush)
        p.drawPath(path)

        # Top highlight line
        hl = QLinearGradient(W * 0.15, 0, W * 0.85, 0)
        hl.setColorAt(0, QColor(0, 212, 255, 0))
        hl.setColorAt(0.5, QColor(0, 212, 255, 85))
        hl.setColorAt(1, QColor(0, 212, 255, 0))
        p.setPen(QPen(QBrush(hl), 1.0))
        p.drawLine(int(W * 0.15), 0, int(W * 0.85), 0)


# ══════════════════════════════════════════════════════════
#  Helper: icon button
# ══════════════════════════════════════════════════════════
def _icon_btn(symbol, tooltip=""):
    btn = QPushButton(symbol)
    btn.setFixedSize(42, 42)
    btn.setCursor(Qt.PointingHandCursor)
    if tooltip: btn.setToolTip(tooltip)
    btn.setStyleSheet("""
        QPushButton {
            background: rgba(0,212,255,10);
            border: 1px solid rgba(0,212,255,28);
            border-radius: 21px;
            color: rgba(0,212,255,155);
            font-size: 15px;
            font-family: 'Segoe UI Emoji';
        }
        QPushButton:hover {
            background: rgba(0,212,255,38);
            border-color: rgba(0,212,255,110);
            color: rgba(0,212,255,230);
        }
        QPushButton:pressed { background: rgba(0,212,255,65); }
    """)
    return btn


def _divider():
    d = QFrame(); d.setFixedSize(1, 32)
    d.setStyleSheet("""
        QFrame {
            background: qlineargradient(x1:0,y1:0,x2:0,y2:1,
                stop:0 transparent,
                stop:0.25 rgba(0,212,255,40),
                stop:0.75 rgba(0,212,255,40),
                stop:1 transparent);
            border: none;
        }
    """)
    return d


# ══════════════════════════════════════════════════════════
#  MiniBar — main widget
# ══════════════════════════════════════════════════════════
class MiniBar(QWidget):
    sig_open_full   = pyqtSignal()
    sig_mic_toggled = pyqtSignal(bool)

    PW, PH = 400, 70    # pill dimensions
    PAD    = 10         # shadow padding

    def __init__(self):
        super().__init__(None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(self.PW + self.PAD * 2, self.PH + self.PAD * 2 + 18)

        self._mic_on   = True
        self._drag_pos = QPoint()
        self._dragging = False
        self._build()
        self._place()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(self.PAD, self.PAD, self.PAD, 0)
        outer.setSpacing(4)

        # Pill
        self._pill = PillFrame()
        self._pill.setFixedSize(self.PW, self.PH)
        try:
            shadow = QGraphicsDropShadowEffect()
            shadow.setBlurRadius(34)
            shadow.setColor(QColor(0, 0, 0, 170))
            shadow.setOffset(0, 7)
            self._pill.setGraphicsEffect(shadow)
        except Exception as _se:
            print(f"[MiniBar] Shadow effect skip: {_se}")
        outer.addWidget(self._pill)

        # Pill inner layout
        hl = QHBoxLayout(self._pill)
        hl.setContentsMargins(10, 0, 10, 0); hl.setSpacing(6)

        # + button
        plus = _icon_btn("+", "New conversation")
        plus.clicked.connect(_ALIRA_slot(self.sig_open_full.emit))
        hl.addWidget(plus)
        hl.addWidget(_divider())

        # Center
        cv = QVBoxLayout(); cv.setSpacing(2); cv.setAlignment(Qt.AlignCenter)
        lbl = QLabel("TITAN")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            "color:rgba(0,212,255,72);font-family:'Courier New';"
            "font-size:9px;letter-spacing:4px;background:transparent;")
        cv.addWidget(lbl)
        self._wave = WaveformWidget()
        cv.addWidget(self._wave, alignment=Qt.AlignCenter)
        hl.addLayout(cv, stretch=1)
        hl.addWidget(_divider())

        # Mic orb
        self._orb = MicOrb()
        self._orb.clicked.connect(_ALIRA_slot(self._toggle_mic))
        hl.addWidget(self._orb)
        hl.addWidget(_divider())

        # Open button
        open_btn = _icon_btn("▶", "Open TITAN  (Ctrl+Alt+A)")
        open_btn.clicked.connect(_ALIRA_slot(self.sig_open_full.emit))
        hl.addWidget(open_btn)

        # Hotkey hint
        hint = QLabel("Ctrl+Alt+A  ·  TITAN          Ctrl+Alt+B  ·  bar")
        hint.setAlignment(Qt.AlignCenter)
        hint.setStyleSheet(
            "color:rgba(0,212,255,38);font-family:'Courier New';"
            "font-size:9px;letter-spacing:1px;background:transparent;")
        outer.addWidget(hint)

    def _toggle_mic(self):
        self._mic_on = not self._mic_on
        self._orb.set_mic(self._mic_on)
        self._wave.set_active(self._mic_on)
        self.sig_mic_toggled.emit(self._mic_on)

    def sync_mic(self, on: bool):
        self._mic_on = on
        self._orb.set_mic(on)
        self._wave.set_active(on)

    def _place(self):
        try:
            scr = QApplication.primaryScreen().geometry()
            x = scr.width() // 2 - self.width() // 2
            y = scr.height() - self.height() - 38
            self.move(x, y)
        except Exception as e:
            print(f"[MiniBar] _place error: {e}")
            self.move(100, 100)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_pos = e.globalPos() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._dragging: self.move(e.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, e): self._dragging = False


# ══════════════════════════════════════════════════════════
#  Standalone test
# ══════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pal = QPalette(); pal.setColor(QPalette.Window, QColor("#060a16")); app.setPalette(pal)
    bar = MiniBar()
    bar.sig_open_full.connect(lambda: print("Open TITAN!"))
    bar.sig_mic_toggled.connect(lambda on: print(f"Mic: {'ON' if on else 'MUTED'}"))
    bar.show()
    sys.exit(app.exec_())