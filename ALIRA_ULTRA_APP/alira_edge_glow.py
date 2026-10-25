# -*- coding: utf-8 -*-
"""
ALIRA Edge Glow — screen ke kinaron par rang-birangi animated border (NOVA ke ListeningEdgeGlow jaisa)
=====================================================================================================
State ke hisaab se alag colors; rang kinaron par ghoomte rehte hain (conical gradient).

    glow = EdgeGlow()
    glow.set_mode("listening")   # listening / thinking / speaking / screenshare / screenread / camera / error
    glow.set_mode(None)          # fade out
    glow.set_enabled(False)      # settings se band

Design notes:
  * Poori screen ki ek bhaari window nahi — 4 patli strips (top/bottom/left/right) => repaint sasta.
  * Click-through (WindowTransparentForInput), focus nahi leti, taskbar mein nahi dikhti.
  * WDA_EXCLUDEFROMCAPTURE: glow screen-share / OCR frames mein NAHI aata (ALIRA ko saaf screen dikhti hai).
  * Timer sirf tab chalta hai jab glow visible ho.
"""

from alira_slot import slot as _alira_slot
import ctypes
import sys
import time

from PyQt5.QtCore import Qt, QObject, QTimer, QRect
from PyQt5.QtGui import (
    QColor, QPainter, QConicalGradient, QLinearGradient, QBrush, QFont, QPen,
)
from PyQt5.QtWidgets import QWidget, QApplication

# mode -> (label, colors, intensity)
PALETTES = {
    "listening":   ("Listening",      ["#8B5CF6", "#6366F1", "#27B5E6", "#B65CFF"], 0.80),
    "thinking":    ("Thinking",       ["#F5A524", "#FF4DA6", "#8B5CF6", "#FFD166"], 0.90),
    "speaking":    ("Speaking",       ["#FF6FAE", "#FF2E43", "#FF9A3C", "#FF4DA6"], 0.95),
    "screenshare": ("Screen sharing", ["#00DDFF", "#2BD66B", "#2A8BE8", "#7CF2D0"], 0.85),
    "screenread":  ("Reading screen", ["#2BD66B", "#B6F24A", "#27B5E6", "#2BD66B"], 0.85),
    "camera":      ("Camera on",      ["#FF2E43", "#FF7A45", "#FF4DA6", "#FF2E43"], 0.80),
    "error":       ("Error",          ["#FF3B4E", "#B3122A", "#FF7A85", "#FF3B4E"], 0.90),
}
BADGE_MODES = ("screenshare", "screenread", "camera")


def _lerp_color(a: QColor, b: QColor, t: float) -> QColor:
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t))


def _exclude_from_capture(widget: QWidget):
    """Windows 10 2004+: window screen-capture/OCR mein nahi aati (user ko dikhti hai)."""
    if sys.platform != "win32":
        return
    try:
        hwnd = int(widget.winId())
        ctypes.windll.user32.SetWindowDisplayAffinity(hwnd, 0x11)   # WDA_EXCLUDEFROMCAPTURE
    except Exception:
        pass


_OVERLAY_FLAGS = (Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool |
                  Qt.WindowTransparentForInput | Qt.NoDropShadowWindowHint)


def _setup_overlay(w: QWidget):
    w.setAttribute(Qt.WA_TranslucentBackground, True)
    w.setAttribute(Qt.WA_ShowWithoutActivating, True)
    w.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    w.setAttribute(Qt.WA_NoSystemBackground, True)
    w.setFocusPolicy(Qt.NoFocus)


class _Strip(QWidget):
    def __init__(self, glow, side: str):
        super().__init__(None, _OVERLAY_FLAGS)
        _setup_overlay(self)
        self._glow, self._side = glow, side
        self._excluded = False

    def paintEvent(self, _e):
        self._glow._paint_strip(self, self._side)

    def showEvent(self, e):
        super().showEvent(e)
        if not self._excluded:
            _exclude_from_capture(self)
            self._excluded = True


class _Badge(QWidget):
    """Chhota pill (top-center): 'Screen sharing' / 'Camera on' — privacy indicator."""

    def __init__(self, glow):
        super().__init__(None, _OVERLAY_FLAGS)
        _setup_overlay(self)
        self._glow = glow
        self._text, self._dot = "", QColor("#FFFFFF")
        self._opacity = 1.0
        self._excluded = False

    def set_content(self, text: str, dot: QColor, opacity: float):
        changed = (text != self._text)
        self._text, self._dot, self._opacity = text, dot, opacity
        if changed:
            fm = self.fontMetrics()
            self.resize(fm.horizontalAdvance(text) + 56, 32)
        self.update()

    def paintEvent(self, _e):
        if not self._text:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setOpacity(self._opacity)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(10, 8, 14, 215))
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 15, 15)
        pen = QPen(QColor(self._dot.red(), self._dot.green(), self._dot.blue(), 150), 1.2)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 15, 15)
        p.setPen(Qt.NoPen)
        p.setBrush(self._dot)
        p.drawEllipse(14, 11, 10, 10)
        f = QFont("Poppins")
        f.setPixelSize(13)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor("#F4F3F6"))
        p.drawText(QRect(32, 0, self.width() - 40, self.height()), Qt.AlignVCenter | Qt.AlignLeft, self._text)

    def showEvent(self, e):
        super().showEvent(e)
        if not self._excluded:
            _exclude_from_capture(self)
            self._excluded = True


class EdgeGlow(QObject):
    DEPTH = 30          # px — patla border, poori screen par wash nahi
    SPEED = 70.0        # degrees/sec — ek chakkar ~5 sec
    FADE_SEC = 0.45

    def __init__(self):
        super().__init__()
        first = PALETTES["listening"]
        self._enabled   = True
        self._mode      = None
        self._visible   = False
        self._presence  = 0.0
        self._inten     = 0.0
        self._cols      = [QColor(c) for c in first[1]]
        self._phase     = 0.0
        self._last      = time.monotonic()
        self._geom      = QRect(0, 0, 1920, 1080)
        self._strips    = {s: _Strip(self, s) for s in ("top", "bottom", "left", "right")}
        self._badge     = _Badge(self)
        self._timer     = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(_alira_slot(self._tick))

    # ── public API ───────────────────────────────────────────────
    @property
    def mode(self):
        return self._mode

    def set_enabled(self, on: bool):
        self._enabled = bool(on)
        self._wake()

    def set_mode(self, mode):
        if mode not in PALETTES:
            mode = None
        if mode == self._mode:
            return
        self._mode = mode
        self._wake()

    # ── internals ────────────────────────────────────────────────
    def _wake(self):
        if (self._enabled and self._mode) or self._presence > 0.0:
            if not self._timer.isActive():
                self._last = time.monotonic()
                self._timer.start()

    def _layout(self):
        scr = QApplication.primaryScreen()
        if scr is None:
            return
        g = scr.geometry()
        self._geom = g
        D = self.DEPTH
        self._strips["top"].setGeometry(g.x(), g.y(), g.width(), D)
        self._strips["bottom"].setGeometry(g.x(), g.y() + g.height() - D, g.width(), D)
        self._strips["left"].setGeometry(g.x(), g.y() + D, D, max(1, g.height() - 2 * D))
        self._strips["right"].setGeometry(g.x() + g.width() - D, g.y() + D, D, max(1, g.height() - 2 * D))

    def _show_all(self):
        self._layout()
        for s in self._strips.values():
            s.show()
        self._visible = True

    def _hide_all(self):
        for s in self._strips.values():
            s.hide()
        self._badge.hide()
        self._visible = False

    def _tick(self):
        now = time.monotonic()
        dt = min(0.1, max(0.001, now - self._last))
        self._last = now
        active = self._enabled and self._mode is not None

        step = dt / self.FADE_SEC
        self._presence = min(1.0, self._presence + step) if active else max(0.0, self._presence - step)

        if active:
            _label, cols, inten = PALETTES[self._mode]
            k = min(1.0, dt * 6.0)                      # rang smooth crossfade hote hain
            self._cols = [_lerp_color(c, QColor(t), k) for c, t in zip(self._cols, cols)]
            self._inten += (inten - self._inten) * k
        self._phase = (self._phase + self.SPEED * dt) % 360.0

        if self._presence <= 0.0 and not active:
            if self._visible:
                self._hide_all()
            self._timer.stop()
            return
        if not self._visible:
            self._show_all()

        for s in self._strips.values():
            s.update()
        self._update_badge()

    def _update_badge(self):
        if self._mode in BADGE_MODES and self._presence > 0.02:
            label = PALETTES[self._mode][0]
            self._badge.set_content(label, self._cols[0], self._presence)
            g = self._geom
            self._badge.move(g.x() + (g.width() - self._badge.width()) // 2, g.y() + self.DEPTH + 8)
            if not self._badge.isVisible():
                self._badge.show()
        elif self._badge.isVisible():
            self._badge.hide()

    def _paint_strip(self, w: QWidget, side: str):
        p = QPainter(w)
        rect = w.rect()
        cx = self._geom.center().x() - w.x()
        cy = self._geom.center().y() - w.y()
        cg = QConicalGradient(cx, cy, self._phase)
        n = len(self._cols)
        for i, c in enumerate(self._cols):
            cg.setColorAt(i / n, c)
        cg.setColorAt(1.0, self._cols[0])
        p.fillRect(rect, QBrush(cg))

        # kinare par tez, andar ki taraf fade — mask (DestinationIn)
        a = max(0.0, min(1.0, self._presence * self._inten))
        W, H = rect.width(), rect.height()
        if side == "top":
            lg = QLinearGradient(0, 0, 0, H)
        elif side == "bottom":
            lg = QLinearGradient(0, H, 0, 0)
        elif side == "left":
            lg = QLinearGradient(0, 0, W, 0)
        else:
            lg = QLinearGradient(W, 0, 0, 0)
        for pos, f in ((0.0, 1.0), (0.3, 0.5), (0.65, 0.14), (1.0, 0.0)):
            lg.setColorAt(pos, QColor(0, 0, 0, int(255 * a * f)))
        p.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        p.fillRect(rect, QBrush(lg))
        p.end()
