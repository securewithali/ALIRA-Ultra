# -*- coding: utf-8 -*-
"""
ALIRA Floating Orb — ALIRA minimize ho ya background mein chale to screen par ye orb aata hai.

  * Kahin bhi drag karke rakho (position yaad rehti hai)
  * Click  -> quick control menu (Open / Mic / Screen watch / Share screen / Camera / Quit)
  * Double-click -> ALIRA window kholo
  * Orb state ke saath animate hota hai (listening / speaking / thinking / muted / alert)
  * Size Settings se badal sakte ho (56–200 px)
  * Speech bubble: ALIRA ke jawab / Screen Guardian ki chetawani orb ke paas dikhti hai
  * Screen capture se bahar (Windows 10 2004+): orb screen-share / OCR frames mein nahi aata

    orb = FloatingOrb()
    orb.action.connect(handler)      # "open" | "mic" | "guardian" | "screenshare" | "camera" | "settings" | "quit"
    orb.show_orb(); orb.say("Sir, ...", kind="warn")
"""

from alira_slot import slot as _alira_slot
import math
import random
import time

from PyQt5.QtCore import Qt, QTimer, QPointF, QRectF, QPoint, pyqtSignal
from PyQt5.QtGui import (
    QColor, QPainter, QPen, QBrush, QRadialGradient, QPixmap, QFont, QPainterPath,
)
from PyQt5.QtWidgets import QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QApplication

import alira_prefs as prefs
from alira_edge_glow import _exclude_from_capture, _OVERLAY_FLAGS

try:
    from alira_ui import T, F, pill, svg_pixmap, ASSETS
    _HAS_UI = True
except Exception:
    _HAS_UI = False
    T = dict(red="#FF2E43", text="#F4F3F6", muted="#9C99A4", green="#2BD66B", panel="#0E0C11")
    ASSETS = None

    def F(w, s):
        return f"font-size:{s}px;font-weight:{int(w)};"

    def svg_pixmap(*a, **k):
        return QPixmap()

    def pill(text, icon=None, kind="ghost", h=40):
        from PyQt5.QtWidgets import QPushButton
        b = QPushButton(text)
        b.setFixedHeight(h)
        return b

MIN_SIZE, MAX_SIZE, DEFAULT_SIZE = 56, 200, 96

_STATE_COLORS = {
    "listening": (0, 217, 255),    # Neon Cyan
    "speaking": (52, 120, 255),    # Electric Blue
    "thinking": (0, 195, 255),     # Bright Cyan
    "standby": (0, 217, 255),      # Premium Cyan
    "idle": (0, 174, 255),         # Blue-Cyan
    "muted": (100, 130, 155),      # Slate Blue
    "error": (255, 75, 95),        # Error Red
    "alert": (34, 229, 139),       # Neon Green
    "screenshare": (0, 221, 255),  # Screen-share Cyan
    "webforge": (52, 120, 255),    # Building Blue
}
_STATE_LABEL = {
    "listening": "Listening", "speaking": "Speaking", "thinking": "Thinking", "standby": "Ready",
    "idle": "Ready", "muted": "Mic off", "error": "Error", "alert": "Dekho!", "screenshare": "Watching",
    "webforge": "Building",
}


# ══════════════════════════════════════════════════════════════════
# QUICK CONTROL MENU
# ══════════════════════════════════════════════════════════════════
class OrbMenu(QFrame):
    action = pyqtSignal(str)

    ITEMS = (
        ("open",        "home",       "ALIRA kholo"),
        ("mic",         "mic",        "Mic"),
        ("guardian",    "shield",     "Screen Guardian"),
        ("screenshare", "screenshot", "Screen share"),
        ("camera",      "camera",     "Camera"),
        ("settings",    "gear",       "Settings"),
        ("quit",        "power",      "ALIRA band karo"),
    )

    def __init__(self):
        super().__init__(None, Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setObjectName("orbmenu")
        self.setStyleSheet("QLabel{background:transparent;}")
        self._flags = {"mic": True, "guardian": False, "screenshare": False, "camera": False}
        self._btns = {}
        vl = QVBoxLayout(self)
        vl.setContentsMargins(12, 12, 12, 12)
        vl.setSpacing(6)
        head = QHBoxLayout()
        self._title = QLabel("ALIRA")
        self._title.setStyleSheet(f"color:#fff;{F(800, 16)}")
        self._state = QLabel("Ready")
        self._state.setStyleSheet(f"color:{T['green']};{F(600, 12)}")
        head.addWidget(self._title)
        head.addStretch(1)
        head.addWidget(self._state)
        vl.addLayout(head)
        for key, icon, text in self.ITEMS:
            b = pill(text, icon, "ghost", 38)
            b.clicked.connect(lambda _=False, k=key: self._pick(k))
            b.setMinimumWidth(220)
            self._btns[key] = b
            vl.addWidget(b)
        hint = QLabel("Orb par double-click: ALIRA kholo · drag: kahin bhi rakho")
        hint.setStyleSheet(f"color:{T['muted']};{F(400, 10)}")
        hint.setWordWrap(True)
        vl.addWidget(hint)
        self._refresh()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        p.setBrush(QColor(14, 12, 17, 248))
        p.setPen(QPen(QColor(255, 46, 67, 140), 1.4))
        p.drawRoundedRect(r, 18, 18)

    def set_flags(self, **flags):
        self._flags.update({k: bool(v) for k, v in flags.items() if k in self._flags})
        self._refresh()

    def set_state_text(self, text: str, color: str = None):
        self._state.setText(text)
        self._state.setStyleSheet(f"color:{color or T['green']};{F(600, 12)}")

    def _refresh(self):
        from alira_ui import css3d
        for key, icon, text in self.ITEMS:
            b = self._btns[key]
            on = self._flags.get(key)
            if key in self._flags:
                b.setText(f"  {text}: {'ON' if on else 'OFF'}")
                b.setStyleSheet(css3d("QPushButton", "active" if on else "ghost", 14, F(600 if on else 500, 13), None, "padding:0 16px;text-align:left;"))
            elif key == "quit":
                b.setStyleSheet(css3d("QPushButton", "danger", 14, F(600, 13), None, "padding:0 16px;text-align:left;"))
            else:
                b.setStyleSheet(css3d("QPushButton", "primary" if key == "open" else "ghost", 14, F(600 if key == "open" else 500, 13), None, "padding:0 16px;text-align:left;"))

    def _pick(self, key):
        self.hide()
        self.action.emit(key)

    def show_near(self, orb_rect, screen_geo):
        self.adjustSize()
        w, h = self.sizeHint().width(), self.sizeHint().height()
        x = orb_rect.center().x() - w // 2
        above = orb_rect.center().y() > screen_geo.center().y()
        y = orb_rect.top() - h - 8 if above else orb_rect.bottom() + 8
        x = max(screen_geo.left() + 8, min(x, screen_geo.right() - w - 8))
        y = max(screen_geo.top() + 8, min(y, screen_geo.bottom() - h - 8))
        self.move(x, y)
        self.show()


# ══════════════════════════════════════════════════════════════════
# SPEECH BUBBLE
# ══════════════════════════════════════════════════════════════════
class OrbBubble(QWidget):
    def __init__(self):
        super().__init__(None, _OVERLAY_FLAGS)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setFocusPolicy(Qt.NoFocus)
        self._kind = "info"
        self._lbl = QLabel("")
        self._lbl.setWordWrap(True)
        self._lbl.setMaximumWidth(320)
        self._lbl.setStyleSheet(f"color:#F4F3F6;{F(500, 13)}background:transparent;")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.addWidget(self._lbl)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(_alira_slot(self.hide))
        self._excluded = False

    def show_text(self, text: str, kind: str, ms: int):
        self._kind = kind
        self._lbl.setText(text)
        self.adjustSize()
        self.update()
        self._timer.start(ms)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        warn = self._kind == "warn"
        border = QColor(245, 165, 36, 230) if warn else QColor(255, 46, 67, 190)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        p.setPen(QPen(border, 1.6))
        p.setBrush(QColor(14, 12, 17, 238))
        p.drawRoundedRect(r, 16, 16)

    def showEvent(self, e):
        super().showEvent(e)
        if not self._excluded:
            _exclude_from_capture(self)
            self._excluded = True


# ══════════════════════════════════════════════════════════════════
# THE ORB
# ══════════════════════════════════════════════════════════════════
class FloatingOrb(QWidget):
    action        = pyqtSignal(str)
    open_requested = pyqtSignal()

    def __init__(self):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("ALIRA — click: controls · double-click: kholo · drag: move")

        self._core = prefs.clamp(prefs.get("float_orb_size", DEFAULT_SIZE), MIN_SIZE, MAX_SIZE)
        self._state, self._energy, self._t = "standby", 0.0, 0.0
        self._cur = QColor(*_STATE_COLORS["standby"])
        self._alert_until = 0.0
        self._muted = False
        self._guardian = False
        self._press = None            # (global pos, window pos)
        self._dragging = False
        self._excluded = False

        logo = ASSETS / "alira_logo.png" if ASSETS else None
        self._logo = QPixmap(str(logo)) if logo and logo.exists() else QPixmap()

        self._menu = OrbMenu()
        self._menu.action.connect(self.action)
        self._bubble = OrbBubble()
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(_alira_slot(self._tick))
        self._apply_size()

    # ── geometry ─────────────────────────────────────────────────
    def _pad(self):
        return max(12, int(self._core * 0.16))

    def _apply_size(self):
        c = self.geometry().center() if self.isVisible() else None
        side = self._core + 2 * self._pad()
        self.setFixedSize(side, side)
        if c is not None:
            self.move(c.x() - side // 2, c.y() - side // 2)
            self._clamp_to_screen()
        self.update()

    def set_size(self, px: int):
        self._core = prefs.clamp(px, MIN_SIZE, MAX_SIZE)
        prefs.set_("float_orb_size", self._core)
        self._apply_size()

    def size_px(self) -> int:
        return self._core

    def _screen_geo(self):
        scr = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        return scr.availableGeometry()

    def _clamp_to_screen(self):
        g = self._screen_geo()
        x = max(g.left(), min(self.x(), g.right() - self.width() + 1))
        y = max(g.top(), min(self.y(), g.bottom() - self.height() + 1))
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    def _restore_position(self):
        pos = prefs.get("float_orb_pos")
        if isinstance(pos, (list, tuple)) and len(pos) == 2:
            pt = QPoint(int(pos[0]), int(pos[1]))
            for scr in QApplication.screens():
                if scr.availableGeometry().contains(pt):
                    self.move(pt)
                    self._clamp_to_screen()
                    return
        g = QApplication.primaryScreen().availableGeometry()
        self.move(g.right() - self.width() - 28, g.bottom() - self.height() - 28)

    # ── public api ───────────────────────────────────────────────
    def show_orb(self):
        self._restore_position()
        self.show()
        self.raise_()
        if not self._excluded:
            _exclude_from_capture(self)
            self._excluded = True
        self._timer.start()

    def hide_orb(self):
        self._timer.stop()
        self._menu.hide()
        self._bubble.hide()
        self.hide()

    def set_state(self, s: str):
        self._state = s if s in _STATE_COLORS else "standby"

    def set_energy(self, e: float):
        self._energy = max(0.0, min(1.0, float(e) / 90.0))

    def set_menu_state(self, **flags):
        if "mic" in flags:
            self._muted = not flags["mic"]
        if "guardian" in flags:
            self._guardian = bool(flags["guardian"])
        self._menu.set_flags(**flags)
        self.update()

    def alert(self, seconds: float = 6.0):
        self._alert_until = time.time() + seconds

    def say(self, text: str, kind: str = "info", ms: int = 7000):
        text = (text or "").strip()
        if not text or not self.isVisible():
            return
        if len(text) > 260:
            text = text[:257] + "…"
        self._bubble.show_text(text, kind, ms)
        self._place_bubble()
        self._bubble.show()
        self._bubble.raise_()
        if kind == "warn":
            self.alert(ms / 1000.0)

    def _place_bubble(self):
        g = self._screen_geo()
        b = self._bubble
        b.adjustSize()
        right_side = self.geometry().center().x() < g.center().x()
        x = self.geometry().right() + 6 if right_side else self.geometry().left() - b.width() - 6
        y = self.geometry().center().y() - b.height() // 2
        x = max(g.left() + 6, min(x, g.right() - b.width() - 6))
        y = max(g.top() + 6, min(y, g.bottom() - b.height() - 6))
        b.move(x, y)

    # ── animation ────────────────────────────────────────────────
    def _eff_state(self):
        if time.time() < self._alert_until:
            return "alert"
        if self._muted and self._state in ("standby", "idle", "listening"):
            return "muted"
        return self._state

    def _tick(self):
        self._t += 0.033
        tgt = QColor(*_STATE_COLORS.get(self._eff_state(), _STATE_COLORS["standby"]))
        k = 0.18
        self._cur = QColor(int(self._cur.red() + (tgt.red() - self._cur.red()) * k),
                           int(self._cur.green() + (tgt.green() - self._cur.green()) * k),
                           int(self._cur.blue() + (tgt.blue() - self._cur.blue()) * k))
        self.update()

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        W = self.width()
        cx = cy = W / 2.0
        R = self._core / 2.0
        st = self._eff_state()
        base = self._cur
        active = st in ("listening", "speaking", "thinking", "alert", "webforge")
        pulse = 0.5 + 0.5 * math.sin(self._t * (7.0 if st == "alert" else 2.4))

        # glow
        g = QRadialGradient(QPointF(cx, cy), W / 2.0)
        a = int((70 + 70 * pulse) if active else 45)
        c0 = QColor(base); c0.setAlpha(0)
        c1 = QColor(base); c1.setAlpha(a)
        g.setColorAt(0.0, c0); g.setColorAt(R / (W / 2.0) * 0.96, c1); g.setColorAt(1.0, QColor(base.red(), base.green(), base.blue(), 0))
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), W / 2.0, W / 2.0)

               # premium glass reflection
        p.save()
        p.setPen(Qt.NoPen)

        shine = QRadialGradient(
            QPointF(cx - R * 0.28, cy - R * 0.42),
            R * 0.95
        )
        shine.setColorAt(0.0, QColor(210, 250, 255, 105))
        shine.setColorAt(0.38, QColor(0, 217, 255, 34))
        shine.setColorAt(1.0, QColor(0, 217, 255, 0))

        p.setBrush(QBrush(shine))
        p.drawEllipse(
            QPointF(cx, cy),
            R * 0.86,
            R * 0.86
        )

        # small glossy highlight near the top-left
        p.setBrush(QColor(225, 252, 255, 125))
        p.drawEllipse(
            QPointF(cx - R * 0.30, cy - R * 0.43),
            max(1.5, R * 0.075),
            max(1.0, R * 0.035)
        )
        p.restore()

        # arcs
        speed = {"listening": 1.0, "speaking": 1.9, "thinking": 2.6, "alert": 3.0}.get(st, 0.4)
        rect = QRectF(cx - R * 0.78, cy - R * 0.78, R * 1.56, R * 1.56)
        for width, alpha in ((self._core * 0.065, 45), (self._core * 0.034, 255)):
            col = QColor(base); col.setAlpha(alpha if active else alpha // 2)
            pen = QPen(col, width); pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            for k, (start, span) in enumerate(((20, 120), (170, 80), (290, 40))):
                p.drawArc(rect, int((start + self._t * 55 * speed * (1 if k % 2 == 0 else -1)) * 16), span * 16)

        # centre: waveform when active, logo otherwise
        if active and st != "alert":
            n = 7
            bw = self._core * 0.045
            gap = self._core * 0.032
            total = n * bw + (n - 1) * gap
            x0 = cx - total / 2
            amp = {"listening": 0.3, "speaking": 0.8, "thinking": 0.45}.get(st, 0.3)
            col = QColor(base); col.setAlpha(240)
            p.setPen(Qt.NoPen)
            p.setBrush(col)
            for i in range(n):
                env = math.sin((i + 0.5) / n * math.pi)
                hh = (0.10 + env * (amp + 0.7 * self._energy) * (0.55 + 0.45 * math.sin(self._t * 7 + i * 1.1))) * R * 1.1
                hh = max(self._core * 0.04, hh)
                p.drawRoundedRect(QRectF(x0 + i * (bw + gap), cy - hh / 2, bw, hh), bw / 2, bw / 2)
        elif not self._logo.isNull():
            s = int(self._core * 0.46)
            lg = self._logo.scaledToHeight(s, Qt.SmoothTransformation)
            if st == "muted":
                p.setOpacity(0.45)
            p.drawPixmap(int(cx - lg.width() / 2), int(cy - lg.height() / 2), lg)
            p.setOpacity(1.0)
        else:
            p.setPen(QColor("#FFFFFF"))
            f = QFont("Poppins"); f.setPixelSize(int(self._core * 0.36)); f.setWeight(QFont.Bold)
            p.setFont(f)
            p.drawText(self.rect(), Qt.AlignCenter, "M")

        # guardian dot (screen watch ON)
        if self._guardian:
            dr = max(5.0, self._core * 0.075)
            p.setPen(QPen(QColor(14, 12, 17), 1.5))
            p.setBrush(QColor(43, 214, 107))
            p.drawEllipse(QPointF(cx + R * 0.70, cy - R * 0.70), dr, dr)

    # ── mouse: drag / click / double-click ───────────────────────
    def mousePressEvent(self, e):
        if e.button() in (Qt.LeftButton, Qt.RightButton):
            self._press = (e.globalPos(), self.pos(), e.button())
            self._dragging = False
            self._menu.hide()

    def mouseMoveEvent(self, e):
        if not self._press or not (e.buttons() & Qt.LeftButton):
            return
        d = e.globalPos() - self._press[0]
        if not self._dragging and (abs(d.x()) + abs(d.y())) > 5:
            self._dragging = True
            self.setCursor(Qt.ClosedHandCursor)
        if self._dragging:
            self.move(self._press[1] + d)
            if self._bubble.isVisible():
                self._place_bubble()

    def mouseReleaseEvent(self, e):
        if not self._press:
            return
        was_drag, btn = self._dragging, self._press[2]
        self._press, self._dragging = None, False
        self.setCursor(Qt.OpenHandCursor)
        if was_drag:
            self._clamp_to_screen()
            prefs.set_("float_orb_pos", [self.x(), self.y()])
            if self._bubble.isVisible():
                self._place_bubble()
        else:
            self._menu.show_near(self.geometry(), self._screen_geo())

    def mouseDoubleClickEvent(self, e):
        self._menu.hide()
        self.open_requested.emit()
        self.action.emit("open")
