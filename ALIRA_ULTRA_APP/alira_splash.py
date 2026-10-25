# -*- coding: utf-8 -*-
"""
ALIRA OS — startup splash (mini UI)
==================================
Background: TABBU_modules/assets/splash_bg.jpg ("ALIRA OS" sunset scene)
Overlay (reference design ke exact positions): "Starting ALIRA OS…" + progress bar 0–100% + 5 feature tiles
(THINKS / LISTENS / AUTOMATES / CONTROLS / PROTECTS) jo progress ke saath ek-ek karke "power on" hote hain.

    splash = ALIRASplash(); splash.show()
    splash.set_progress(40)            # bar smoothly wahan tak chalta hai
    splash.finish()                    # 100% tak le jao, thoda ruko, fade-out, close

Progress kaise chalta hai: real loading stages par target set hota hai (modules load -> window banana ->
ready); beech mein bar halka sa aage creep karta hai taaki atka hua na lage. 100% sirf tab jab ALIRA ready ho.
"""

from alira_slot import slot as _ALIRA_slot
import time
from pathlib import Path

from PyQt5.QtCore import Qt, QTimer, QRectF, QPointF, QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QPixmap, QPainterPath, QLinearGradient, QRadialGradient,
)
from PyQt5.QtWidgets import QWidget, QApplication

try:
    from ALIRA_ui import svg_pixmap, ASSETS
except Exception:                                       # standalone fallback
    ASSETS = Path(__file__).resolve().parent / "TABBU_modules" / "assets"

    def svg_pixmap(*a, **k):
        return QPixmap()

BASE_W, BASE_H = 1672.0, 941.0                          # reference image ka size — saare coordinates isi mein
RED = QColor(255, 46, 67)

TILES = [("brain", "THINKS", "Understands You"), ("mic", "LISTENS", "Natural Voice"),
         ("bolt", "AUTOMATES", "Gets Things Done"), ("monitor", "CONTROLS", "Your PC"),
         ("shield", "PROTECTS", "Your Privacy")]
TILE_X = [1055.0, 1170.0, 1285.0, 1399.0, 1513.0]
TILE_Y, TILE_W, TILE_H = 694.0, 101.5, 109.0
TILE_AT = [8.0, 22.0, 38.0, 54.0, 70.0]                # progress % jab tile "on" hota hai

BAR_X, BAR_Y, BAR_W, BAR_H = 1056.0, 604.0, 444.0, 20.0
PANEL = (1047.0, 667.0, 568.0, 232.0)
PANEL_BAR = (1040.0, 556.0, 582.0, 86.0)


def _font(px, weight=QFont.Normal, spacing=0.0):
    f = QFont("Poppins")
    f.setPixelSize(int(round(px)))
    f.setWeight(weight)
    if spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f


class ALIRASplash(QWidget):
    def __init__(self, width: int = 0):
        super().__init__(None, Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        scr = QApplication.primaryScreen().availableGeometry()
        w = width or int(min(1280, scr.width() * 0.72))
        w = max(720, w)
        h = int(w * BASE_H / BASE_W)
        self.resize(w, h)
        self.move(scr.center().x() - w // 2, scr.center().y() - h // 2)
        self._s = w / BASE_W

        bg = ASSETS / "splash_bg.jpg"
        pm = QPixmap(str(bg))
        self._bg = pm.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation) if not pm.isNull() else QPixmap()

        self._frost = self._make_frost(bg, PANEL)
        self._frost_bar = self._make_frost(bg, PANEL_BAR)
        self._target = 0.0
        self._shown = 0.0
        self._glow = [0.0] * len(TILES)
        self._t0 = time.monotonic()
        self._finishing = False
        self._done_cb = None
        self._full_cb = None
        self._icons = {}
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(_ALIRA_slot(self._tick))
        self._timer.start()

    @staticmethod
    def _make_frost(path, rect):
        """Panel ke neeche ka hissa blur + dark (ek baar) — frosted glass."""
        try:
            from PIL import Image, ImageFilter
            from PyQt5.QtGui import QImage
            im = Image.open(str(path)).convert("RGB")
            x, y, w, h = rect
            box = (int(x - 30), int(y - 30), int(x + w + 30), int(y + h + 30))
            crop = im.crop(box).filter(ImageFilter.GaussianBlur(16))
            crop = crop.crop((30, 30, 30 + int(w), 30 + int(h)))
            crop = Image.blend(crop, Image.new("RGB", crop.size, (6, 4, 7)), 0.55)
            data = crop.tobytes("raw", "RGB")
            qi = QImage(data, crop.width, crop.height, 3 * crop.width, QImage.Format_RGB888).copy()
            return QPixmap.fromImage(qi)
        except Exception as e:
            print(f"[Splash] frost: {e}")
            return None

    # ── public ───────────────────────────────────────────────────
    def set_progress(self, pct: float):
        self._target = max(self._target, min(100.0, float(pct)))

    @property
    def progress(self) -> float:
        return self._shown

    def jump(self, pct: float):
        """Bhaari kaam (jo event-loop block karta hai) ke beech progress dikhao: seedha set + turant repaint.
        (Timer tick nahi chal sakta jab GUI thread busy ho — isliye yahan synchronous paint.)"""
        pct = min(99.0, float(pct))
        self._target = max(self._target, pct)
        self._shown = max(self._shown, pct)
        for i, th in enumerate(TILE_AT):
            if self._shown >= th:
                self._glow[i] = 1.0
        self.repaint()

    def finish(self, on_done=None, on_full=None):
        """100% tak le jao -> on_full() (yahan main window dikhao) -> thoda ruko -> fade-out -> close."""
        self._target = 100.0
        self._finishing = True
        self._done_cb = on_done
        self._full_cb = on_full

    # ── animation ────────────────────────────────────────────────
    def _tick(self):
        gap = self._target - self._shown
        if gap > 0:
            self._shown += max(0.18, gap * (0.2 if self._finishing else 0.085))   # ease-out; finish par tez
            self._shown = min(self._shown, self._target)
        elif not self._finishing and self._shown < 92.0:
            self._shown += 0.025                           # target ke baad bhi halka creep (atka hua na lage)
        for i, th in enumerate(TILE_AT):
            on = self._shown >= th
            self._glow[i] += ((1.0 if on else 0.0) - self._glow[i]) * 0.14
        if self._finishing and self._shown >= 99.5:
            self._shown = 100.0                            # bar exact 100% par snap — "99%" dikhte hue window na khule
        if self._finishing and self._shown >= 99.9 and all(g > 0.95 for g in self._glow):
            self._finishing = False
            print(f"[Splash] bar {self._shown:.1f}% — ab main window dikhegi")
            if self._full_cb:                              # bar poora 100% — AB main window dikhao (pehle nahi)
                try:
                    self._full_cb()
                except Exception as e:
                    print(f"[Splash] on_full: {e}")
            QTimer.singleShot(380, self._fade_out)
        self.update()

    def _fade_out(self):
        self._timer.stop()
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setDuration(320)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.InOutQuad)
        self._anim.finished.connect(_ALIRA_slot(self._closed))
        self._anim.start()

    def _closed(self):
        self.hide()
        self.close()
        if self._done_cb:
            try:
                self._done_cb()
            except Exception as e:
                print(f"[Splash] done cb: {e}")

    # ── painting ─────────────────────────────────────────────────
    def _icon(self, name):
        key = (name, int(44 * self._s * 2))
        if key not in self._icons:
            self._icons[key] = svg_pixmap(name, "#FF4054", key[1], 1.5)
        return self._icons[key]

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        W, H = self.width(), self.height()
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(0, 0, W, H), 20, 20)
        p.setClipPath(clip)
        if not self._bg.isNull():
            p.drawPixmap(0, 0, self._bg)
        else:
            p.fillRect(self.rect(), QColor("#0E0C11"))

        p.scale(self._s, self._s)                                  # ab sab kuch reference-image ke coordinates mein

        # bottom-right ko halka dark karo taaki overlay saaf padhe
        g = QRadialGradient(QPointF(1330, 745), 470)
        g.setColorAt(0, QColor(0, 0, 0, 150)); g.setColorAt(0.65, QColor(0, 0, 0, 90)); g.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen); p.fillRect(QRectF(760, 470, BASE_W - 760, BASE_H - 470), QBrush(g))

        # glass panel (tiles + footer ke peeche)
        for rect, frost, rad in ((PANEL_BAR, self._frost_bar, 18), (PANEL, self._frost, 16)):
            panel = QRectF(*rect)
            pc = QPainterPath(); pc.addRoundedRect(panel, rad, rad)
            if frost is not None:                            # blur + dark = frosted glass (peeche ka text/mug nahi dikhta)
                p.save(); p.setClipPath(pc, Qt.IntersectClip)
                p.drawPixmap(panel, frost, QRectF(frost.rect()))
                p.restore()
            p.setPen(QPen(QColor(255, 255, 255, 30), 1.2)); p.setBrush(QColor(8, 6, 9, 70 if frost is not None else 170))
            p.drawRoundedRect(panel, rad, rad)

        self._draw_label(p)
        self._draw_bar(p)
        for i in range(len(TILES)):
            self._draw_tile(p, i)
        self._draw_footer(p)

    def _draw_label(self, p):
        p.setFont(_font(21, QFont.Normal))
        x, y = 1058.0, 590.0
        for txt, col in (("Starting ", QColor("#FFFFFF")), ("ALIRA ", QColor("#F5A3A8")), ("OS…", QColor(255, 59, 78))):
            p.setPen(col)
            p.drawText(QPointF(x, y), txt)
            x += p.fontMetrics().horizontalAdvance(txt)

    def _draw_bar(self, p):
        pct = max(0.0, min(100.0, self._shown))
        track = QRectF(BAR_X, BAR_Y, BAR_W, BAR_H)
        p.setPen(QPen(QColor(255, 255, 255, 85), 1.4)); p.setBrush(QColor(0, 0, 0, 95))
        p.drawRoundedRect(track, BAR_H / 2, BAR_H / 2)
        fw = (BAR_W - 4) * pct / 100.0
        if fw > 1:
            fr = QRectF(BAR_X + 2, BAR_Y + 2, max(fw, BAR_H - 4), BAR_H - 4)
            lg = QLinearGradient(fr.left(), 0, fr.right(), 0)
            lg.setColorAt(0, QColor(255, 36, 60)); lg.setColorAt(0.85, QColor(255, 60, 80)); lg.setColorAt(1, QColor(255, 98, 112))
            p.setPen(Qt.NoPen); p.setBrush(QBrush(lg))
            p.drawRoundedRect(fr, fr.height() / 2, fr.height() / 2)
            # fine vertical texture (reference jaisa)
            p.setPen(QPen(QColor(255, 255, 255, 22), 1))
            x = fr.left() + 6
            while x < fr.right() - 4:
                p.drawLine(QPointF(x, fr.top() + 2), QPointF(x, fr.bottom() - 2)); x += 5
            # leading-edge glow
            eg = QRadialGradient(QPointF(fr.right(), fr.center().y()), 22)
            eg.setColorAt(0, QColor(255, 90, 105, 190)); eg.setColorAt(1, QColor(255, 60, 80, 0))
            p.setPen(Qt.NoPen); p.setBrush(QBrush(eg)); p.drawEllipse(QPointF(fr.right(), fr.center().y()), 22, 15)
        p.setPen(QColor("#FFFFFF"))
        p.setFont(_font(20, QFont.Normal))
        p.drawText(QRectF(1514, BAR_Y - 3, 70, 28), Qt.AlignLeft | Qt.AlignVCenter, f"{int(pct)}%")

    def _draw_tile(self, p, i):
        icon, title, sub = TILES[i]
        glow = self._glow[i]
        r = QRectF(TILE_X[i], TILE_Y, TILE_W, TILE_H)
        # card
        fill = QColor(26, 16, 19, int(150 + 40 * glow))
        p.setBrush(fill)
        border = QColor(255, 255, 255, int(30 + 25 * glow))
        if glow > 0.05:
            border = QColor(255, 70, 90, int(40 + 150 * glow))
        p.setPen(QPen(border, 1.3))
        p.drawRoundedRect(r, 12, 12)
        if glow > 0.05:                                        # activate hone par halki red glow
            gg = QRadialGradient(r.center(), 85)
            gg.setColorAt(0, QColor(255, 46, 67, int(46 * glow))); gg.setColorAt(1, QColor(255, 46, 67, 0))
            p.setPen(Qt.NoPen); p.setBrush(QBrush(gg)); p.drawRoundedRect(r, 12, 12)
        # icon
        pm = self._icon(icon)
        if not pm.isNull():
            sz = 44.0
            ir = QRectF(r.center().x() - sz / 2, r.top() + 14, sz, sz)
            p.setOpacity(0.38 + 0.62 * glow)
            if glow > 0.05:                                    # neon halo
                p.setOpacity(0.30 * glow)
                p.drawPixmap(QRectF(ir.adjusted(-5, -5, 5, 5)), pm, QRectF(pm.rect()))
                p.setOpacity(0.38 + 0.62 * glow)
            p.drawPixmap(ir, pm, QRectF(pm.rect()))
            p.setOpacity(1.0)
        # texts
        a = int(150 + 105 * glow)
        p.setPen(QColor(255, 255, 255, a)); p.setFont(_font(12.5, QFont.DemiBold, 0.3))
        p.drawText(QRectF(r.left(), r.top() + 64, r.width(), 20), Qt.AlignHCenter | Qt.AlignVCenter, title)
        p.setPen(QColor(236, 232, 238, int(150 + 90 * glow))); p.setFont(_font(10.5, QFont.Normal))
        p.drawText(QRectF(r.left() - 6, r.top() + 82, r.width() + 12, 20), Qt.AlignHCenter | Qt.AlignVCenter, sub)

    def _draw_footer(self, p):
        y = 845.0
        f1, f2 = _font(12.5, QFont.Normal, 1.7), _font(12.5, QFont.DemiBold, 1.7)
        p.setFont(f1); w1 = p.fontMetrics().horizontalAdvance("BUILDING ")
        p.setFont(f2); w2 = p.fontMetrics().horizontalAdvance("YOUR INTELLIGENT WORLD")
        total = w1 + w2
        x0 = 1330 - total / 2
        p.setFont(f1); p.setPen(QColor(215, 210, 218)); p.drawText(QPointF(x0, y + 5), "BUILDING ")
        p.setFont(f2); p.setPen(QColor("#FFFFFF")); p.drawText(QPointF(x0 + w1, y + 5), "YOUR INTELLIGENT WORLD")
        p.setPen(QPen(QColor(255, 59, 78, 220), 2))
        p.drawLine(QPointF(x0 - 62, y), QPointF(x0 - 14, y))
        p.drawLine(QPointF(x0 + total + 14, y), QPointF(x0 + total + 62, y))
