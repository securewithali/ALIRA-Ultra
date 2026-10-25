# -*- coding: utf-8 -*-
"""
ALIRA UI v9 — red/black "ALIRA AI" dashboard (mockup: assets/ui_reference.png)
=============================================================================
Sirf nayi widgets: Sidebar, HeroPanel (girl + greeting), StatsCard, QuickToolsCard,
RecentActivityCard, HeaderBar, InputBar, ChipsRow, StatusBar. Logic TABBU.py mein hai.
Icons inline SVG (QtSvg) se render hote hain — koi extra icon file nahi chahiye.
"""

from ALIRA_slot import slot as _ALIRA_slot
import os, sys, math, random, time
from pathlib import Path

from PyQt5.QtWidgets import (
    QDialog, QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QLineEdit,
    QToolButton, QMenu, QAction, QSizePolicy, QGraphicsDropShadowEffect, QSizeGrip,
)
from PyQt5.QtCore import Qt, QTimer, QRectF, QPointF, QSize, pyqtSignal, QByteArray
from PyQt5.QtGui import (
    QColor, QPainter, QPen, QBrush, QPixmap, QIcon, QFont, QLinearGradient,
    QRadialGradient, QPainterPath, QFontMetrics,
)
from PyQt5.QtSvg import QSvgRenderer

try:
    import psutil
except ImportError:
    psutil = None

# ── Design tokens ─────────────────────────────────────────────────
T = dict(
    bg="#07060A", bg_side="#0A090D", panel="#0E0C11", panel2="#131016",
    line="rgba(255,255,255,0.08)", line_red="rgba(255,46,67,0.55)",
    red="#FF2E43", red_deep="#B3122A", red_soft="rgba(255,46,67,0.16)",
    text="#F4F3F6", muted="#9C99A4", dim="#6C6975",
    green="#2BD66B", cyan="#27B5E6", blue="#2A8BE8",
)
ASSETS = Path(__file__).resolve().parent / "TABBU_modules" / "assets"
FONT = "'Poppins','Segoe UI VTABBUble','Segoe UI',TABBUl,sans-serif"
def F(weight, size):
    """Poppins (assets/fonts) — numeric font-weight (Qt stylesheet 100-900 support karta hai)."""
    px = max(9, int(round(size * 0.94)))          # Poppins thoda chauda hai
    return f"font-family:'Poppins','Segoe UI',TABBUl,sans-serif;font-size:{px}px;font-weight:{int(weight)};"

_FONTS_LOADED = False

def load_fonts():
    """QApplication ke baad bulao — bundled Poppins register karta hai (ek hi baar, dobara bulane par kuch nahi)."""
    global _FONTS_LOADED
    if _FONTS_LOADED: return []
    from PyQt5.QtGui import QFontDatabase
    d = ASSETS / "fonts"
    _FONTS_LOADED = True
    return [QFontDatabase.addApplicationFont(str(f)) for f in sorted(d.glob("*.ttf"))] if d.exists() else []


def css3d(sel="QPushButton", kind="ghost", r=10, font="", color=None, extra=""):
    """3D 'keycap' button: upar chamak, gradient face, neeche mota dark kinara, press par dab jaata hai."""
    g = lambda a, b, c=None: ("qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 %s," % a) + (("stop:0.5 %s," % c) if c else "") + ("stop:1 %s)" % b)
    if kind == "primary":
        face, hov = g("#FF6E80", "#C7132E", "#F2334C"), g("#FF8392", "#D91A36", "#FF4560")
        bd = "border:1px solid rgba(255,255,255,0.30);border-top:1px solid rgba(255,255,255,0.60);border-bottom:3px solid #6E0A1A;"
        col = color or "#FFFFFF"
    elif kind == "active":
        face, hov = g("rgba(255,70,92,0.60)", "rgba(150,14,34,0.50)"), g("rgba(255,90,110,0.72)", "rgba(170,18,40,0.58)")
        bd = "border:1px solid rgba(255,90,110,0.75);border-top:1px solid rgba(255,175,185,0.80);border-bottom:3px solid #4A0714;"
        col = color or "#FFFFFF"
    elif kind == "danger":
        face, hov = g("rgba(255,46,67,0.24)", "rgba(110,10,24,0.40)"), g("rgba(255,60,80,0.40)", "rgba(130,12,28,0.50)")
        bd = "border:1px solid rgba(255,70,90,0.55);border-top:1px solid rgba(255,140,150,0.60);border-bottom:3px solid #35060F;"
        col = color or "#FF8A98"
    else:
        face, hov = g("rgba(255,255,255,0.14)", "rgba(255,255,255,0.04)"), g("rgba(255,70,92,0.32)", "rgba(255,255,255,0.07)")
        bd = "border:1px solid rgba(255,255,255,0.13);border-top:1px solid rgba(255,255,255,0.32);border-bottom:3px solid rgba(0,0,0,0.78);"
        col = color or "#EDEBF0"
    return (f"{sel}{{{font}color:{col};background:{face};{bd}border-radius:{r}px;{extra}}}"
            f"{sel}:hover{{background:{hov};}}"
            f"{sel}:pressed{{margin-top:2px;border-bottom:1px solid rgba(0,0,0,0.55);}}"
            f"{sel}:focus{{border:1px solid #FFFFFF;border-bottom:3px solid rgba(0,0,0,0.78);}}")


def lift(w, blur=14, dy=5, alpha=170, color="#000000"):
    """Button ke neeche soft shadow (ground shadow) — 3D depth."""
    eff = QGraphicsDropShadowEffect(w)
    c = QColor(color); c.setAlpha(alpha)
    eff.setColor(c); eff.setBlurRadius(blur); eff.setOffset(0, dy)
    w.setGraphicsEffect(eff)


# ══════════════════════════════════════════════════════════════════
# SVG ICONS (24x24, stroke style)
# ══════════════════════════════════════════════════════════════════
_P = {
    "home": '<path d="M3 11l9-8 9 8"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>',
    "chat": '<path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M8 10h.01M12 10h.01M16 10h.01"/>',
    "mic": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
    "monitor": '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
    "grid": '<rect x="4" y="4" width="6" height="6" rx="1.5"/><rect x="14" y="4" width="6" height="6" rx="1.5"/><rect x="4" y="14" width="6" height="6" rx="1.5"/><rect x="14" y="14" width="6" height="6" rx="1.5"/>',
    "automation": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="2.6"/><path d="M12 3.5v3M12 17.5v3M3.5 12h3M17.5 12h3"/>',
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="M21 16l-5-5-9 9"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.2 3 14.8 0 18M12 3c-3 3.2-3 14.8 0 18"/>',
    "activity": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "user": '<circle cx="12" cy="8" r="3.2"/><path d="M5 20a7 7 0 0 1 14 0"/><circle cx="12" cy="12" r="10"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>',
    "screenshot": '<path d="M4 8V6a2 2 0 0 1 2-2h2M16 4h2a2 2 0 0 1 2 2v2M20 16v2a2 2 0 0 1-2 2h-2M8 20H6a2 2 0 0 1-2-2v-2"/><rect x="8" y="9" width="8" height="6" rx="1"/>',
    "volume": '<path d="M11 5L6 9H3v6h3l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 6a9 9 0 0 1 0 12"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3M12 15v2"/>',
    "power": '<path d="M12 3v8"/><path d="M6.4 6.4a8 8 0 1 0 11.2 0"/>',
    "whatsapp": '<path d="M3 21l1.6-4.6A9 9 0 1 1 8 19.6z"/><path d="M9 8.5c0 3.5 3 6.5 6.5 6.5l1-1.5-2-1-1 .8c-1-.4-2-1.4-2.4-2.4l.8-1-1-2z"/>',
    "paperclip": '<path d="M21 11l-8.5 8.5a5 5 0 0 1-7-7L14 4a3.3 3.3 0 0 1 4.7 4.7l-8.6 8.6a1.7 1.7 0 0 1-2.4-2.4L15 7"/>',
    "send": '<path d="M3 11.5L21 3l-6 18-3.2-7.3z" fill="currentColor"/>',
    "keyboard": '<rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10"/>',
    "maximize": '<path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/>',
    "minus": '<path d="M5 12h14"/>',
    "square": '<rect x="5" y="5" width="14" height="14" rx="1.5"/>',
    "x": '<path d="M6 6l12 12M18 6L6 18"/>',
    "chevron_down": '<path d="M6 9l6 6 6-6"/>',
    "chevron_right": '<path d="M9 6l6 6-6 6"/>',
    "crown": '<path d="M3 8l4.5 4L12 5l4.5 7L21 8l-2 11H5z"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "bolt": '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "play": '<path d="M7 4l13 8-13 8z" fill="currentColor"/>',
    "pause": '<rect x="6" y="4" width="4" height="16" rx="1" fill="currentColor"/><rect x="14" y="4" width="4" height="16" rx="1" fill="currentColor"/>',
    "next": '<path d="M5 4l10 8-10 8z" fill="currentColor"/><path d="M19 5v14"/>',
    "prev": '<path d="M19 4L9 12l10 8z" fill="currentColor"/><path d="M5 5v14"/>',
    "brain": '<path d="M9.5 4a3 3 0 0 0-3 3 3 3 0 0 0-2.3 2.9A3 3 0 0 0 5.4 14.3 3 3 0 0 0 9 18.5a3 3 0 0 0 3-1V5.2A3 3 0 0 0 9.5 4z"/><path d="M14.5 4a3 3 0 0 1 3 3 3 3 0 0 1 2.3 2.9 3 3 0 0 1-1.2 4.4 3 3 0 0 1-3.6 4.2 3 3 0 0 1-3-1"/><path d="M8.6 9.2h1.2M14.2 9.2h1.2M8.6 13.4h1.2M14.2 13.4h1.2"/>',
    "instagram": '<rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4"/><path d="M17.4 6.6h.01"/>',
    "camera": '<path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/><circle cx="12" cy="13" r="3.5"/>',
    "trash": '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "check": '<path d="M5 13l4 4L19 7"/>',
    "refresh": '<path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7"/>',
    "sliders": '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
    "sparkle": '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>',
    "code": '<path d="M8 8l-4 4 4 4M16 8l4 4-4 4M14 5l-4 14"/>',
    "translate": '<path d="M4 6h9M8.5 4v2M6 6c1 4 3 6 6 7M12 6c-1 4-3 6-7 8M14 20l4-9 4 9M15.5 17h5"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "external": '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    "cpu": '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
    "youtube": '<rect x="2" y="5" width="20" height="14" rx="4"/><path d="M10 9l5 3-5 3z" fill="currentColor"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
    "pin": '<path d="M12 21s7-6 7-11a7 7 0 0 0-14 0c0 5 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/>',
    "news": '<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 9h8M8 13h8M8 17h5"/>',
    "wifi": '<path d="M2 9a15 15 0 0 1 20 0M5 12.5a10 10 0 0 1 14 0M8.5 16a5 5 0 0 1 7 0"/><circle cx="12" cy="19" r="1" fill="currentColor"/>',
    "download": '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>',
    "infinity": '<path d="M18.2 8c-2.2 0-3.7 1.6-5 4-1.3 2.4-2.8 4-5 4a4 4 0 0 1 0-8c2.2 0 3.7 1.6 5 4 1.3 2.4 2.8 4 5 4a4 4 0 0 0 0-8z"/>',
    "stopcircle": '<circle cx="12" cy="12" r="9"/><rect x="9" y="9" width="6" height="6" rx="1" fill="currentColor"/>',
    "dot": '<circle cx="12" cy="12" r="5" fill="currentColor"/>',
    "shield": '<path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z"/><path d="M9 12l2 2 4-4"/>',

}
_PIX_CACHE = {}

def svg_pixmap(name, color="#FFFFFF", size=22, stroke=1.7):
    key = (name, color, size, stroke)
    if key in _PIX_CACHE:
        return _PIX_CACHE[key]
    body = _P[name].replace("currentColor", color)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
           f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">{body}</svg>')
    r = QSvgRenderer(QByteArray(svg.encode()))
    scale = 2
    pm = QPixmap(size * scale, size * scale); pm.fill(Qt.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing); r.render(p); p.end()
    pm.setDevicePixelRatio(scale)
    _PIX_CACHE[key] = pm
    return pm

def svg_icon(name, color="#FFFFFF", size=22, stroke=1.7):
    return QIcon(svg_pixmap(name, color, size, stroke))

def _glow(widget, color=T["red"], blur=28, alpha=150):
    eff = QGraphicsDropShadowEffect(widget)
    c = QColor(color); c.setAlpha(alpha)
    eff.setColor(c); eff.setBlurRadius(blur); eff.setOffset(0, 0)
    widget.setGraphicsEffect(eff)


# ══════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════
NAV_ITEMS = [
    ("home", "home", "Home"), ("chat", "chat", "Chat"), ("voice", "mic", "Voice Mode"),
    ("pc", "monitor", "PC Control"), ("apps", "grid", "Apps & Tools"),
    ("automation", "automation", "Automation"), ("files", "file", "Files & Documents"),
    ("media", "image", "Media"), ("web", "globe", "Web & Search"), ("studio", "code", "Website Studio"),
    ("monitor", "user", "System Monitor"), ("settings", "gear", "Settings"), ("about", "sparkle", "About"),
]

class NavButton(QPushButton):
    def __init__(self, key, icon_name, text):
        super().__init__("  " + text.replace("&", "&&"))
        self.key, self._icon = key, icon_name
        self.setCheckable(False); self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(46); self.setIconSize(QSize(22, 22))
        self.setFocusPolicy(Qt.TabFocus)   # mouse click pe focus ring nahi, keyboard Tab pe aayega
        self.set_active(False)

    def set_active(self, on):
        self.setIcon(svg_icon(self._icon, "#FFFFFF" if on else "#C9C6CF", 22))
        self.setStyleSheet(css3d("QPushButton", "active" if on else "ghost", 12, F(600 if on else 500, 15),
                                 "#FFFFFF" if on else "#E6E4EA", "text-align:left;padding-left:16px;"))
        if self.graphicsEffect() is None:
            lift(self, 12, 4, 160)


class Sidebar(QFrame):
    sig_nav = pyqtSignal(str)
    sig_tool_clicked = pyqtSignal(str)       # purane TABBU.py API ke liye

    def __init__(self, has_webforge=False):
        super().__init__()
        self.setObjectName("sidebar"); self.setFixedWidth(300)
        self.setStyleSheet(f"#sidebar{{background:{T['bg_side']};border-right:1px solid {T['line']};}}")
        vl = QVBoxLayout(self); vl.setContentsMargins(14, 14, 14, 16); vl.setSpacing(6)

        brand = QHBoxLayout(); brand.setContentsMargins(6, 0, 0, 10); brand.setSpacing(12)
        logo = QLabel(); lp = QPixmap(str(ASSETS / "ALIRA_logo.png"))
        if not lp.isNull():
            logo.setPixmap(lp.scaledToHeight(54, Qt.SmoothTransformation))
        brand.addWidget(logo)
        tb = QVBoxLayout(); tb.setSpacing(0)
        name = QLabel(f'<span style="color:#FFFFFF">ALIRA</span> <span style="color:{T["red"]}">AI</span>')
        name.setStyleSheet(f"{F(800,34)};letter-spacing:1px;")
        sub = QLabel("Your Personal AI Assistant"); sub.setStyleSheet(f"color:{T['muted']};{F(400,13)};")
        tb.addWidget(name); tb.addWidget(sub); brand.addLayout(tb); brand.addStretch()
        vl.addLayout(brand)

        self._btns = {}
        # nav ek scroll area me — chhoti window par 12 items bhi fit (scroll), bade par seedhe dikhte hain
        from PyQt5.QtWidgets import QScrollArea
        nav = QWidget(); nav.setStyleSheet("background:transparent;")
        nv = QVBoxLayout(nav); nv.setContentsMargins(0, 2, 0, 12); nv.setSpacing(14)     # neeche jagah: shadow kat na jaye
        for key, icon, text in NAV_ITEMS:
            b = NavButton(key, icon, text); b.clicked.connect(lambda _=False, k=key: self.sig_nav.emit(k))
            self._btns[key] = b; nv.addWidget(b)
        nv.addStretch(1)
        sc = QScrollArea(); sc.setWidgetResizable(True); sc.setFrameShape(QFrame.NoFrame); sc.setWidget(nav)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setStyleSheet("QScrollArea{background:transparent;border:none;}QScrollBar:vertical{width:5px;background:transparent;}"
                         "QScrollBar::handle:vertical{background:rgba(255,255,255,0.18);border-radius:2px;}"
                         "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")
        sc.viewport().setAutoFillBackground(False)
        vl.addWidget(sc, 1)

        card = QFrame(); card.setObjectName("prem"); card.setCursor(Qt.PointingHandCursor); card.setFixedHeight(84)
        card.setStyleSheet(f"""#prem{{border:1px solid {T['line_red']};border-radius:12px;
            background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgba(255,46,67,0.22),stop:1 rgba(255,46,67,0.05));}}""")
        hl = QHBoxLayout(card); hl.setContentsMargins(16, 0, 14, 0); hl.setSpacing(12)
        crown = QLabel(); crown.setPixmap(svg_pixmap("crown", T["red"], 30, 1.6))
        col = QVBoxLayout(); col.setSpacing(2); col.setAlignment(Qt.AlignVCenter)
        t = QLabel("ALIRA Premium"); t.setStyleSheet(f"color:#fff;{F(700,17)};")
        self._prem_sub = QLabel(f'<span style="color:{T["green"]}">●</span>  <span style="color:{T["green"]}">Active</span>')
        self._prem_sub.setStyleSheet(f"{F(500,14)};")
        col.addWidget(t); col.addWidget(self._prem_sub)
        chev = QLabel(); chev.setPixmap(svg_pixmap("chevron_right", "#C9C6CF", 20))
        hl.addWidget(crown); hl.addLayout(col, 1); hl.addWidget(chev)
        vl.addWidget(card)
        self.set_active("home")

    def set_active(self, key):
        cur = getattr(self, "_active_key", None)
        if cur == key: return
        self._active_key = key
        for k in (cur, key):                     # sirf purana + naya button — baaki 10 ko chhedna nahi
            b = self._btns.get(k)
            if b is not None: b.set_active(k == key)

    # ── purane LeftSidebar API (TABBU.py inhe call karta hai) ──
    def update_webforge_status(self, building: bool, msg: str = ""):
        txt, col = (f"Building… {msg[:12]}", T["red"]) if building else ("Active", T["green"])
        self._prem_sub.setText(f'<span style="color:{col}">●</span>  <span style="color:{col}">{txt}</span>')
    def update_screenshare_status(self, active: bool): pass
    def update_camera_status(self, active: bool): pass
    def update_mic_level(self, rms): pass
    def update_camera_frame(self, img): pass


# ══════════════════════════════════════════════════════════════════
# HERO (girl + greeting + chips)  — set_state / set_energy = purana GoalOrb API
# ══════════════════════════════════════════════════════════════════
class Orb(QWidget):
    """Animated listening orb (mockup): dotted outer ring + glowing arcs + waveform bars."""
    clicked = pyqtSignal()
    LABELS = {"listening": "Listening…", "speaking": "Speaking…", "thinking": "Thinking…", "standby": "Standby",
              "idle": "Standby", "muted": "Mic off", "error": "Error", "screenshare": "Watching…", "webforge": "Building…"}

    def __init__(self, size=200):
        super().__init__(); self.setMinimumSize(size, size); self.setCursor(Qt.PointingHandCursor)
        # ✅ FIX: orb ke peeche black square (blink/repaint par) — widget ko poori tarah transparent karo
        self.setAttribute(Qt.WA_TranslucentBackground, True); self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False); self.setStyleSheet("background:transparent;")
        self.state, self._e, self._t = "listening", 0.0, 0.0
        self.setToolTip("Tap to talk / mute")
        QTimer(self, interval=40, timeout=self._tick).start()

    def set_state(self, s): self.state = s if s in self.LABELS else "idle"
    def set_energy(self, e): self._e = min(1.0, float(e) / 90.0)
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self.clicked.emit()

    def _tick(self):
        self._t += 0.04
        if self.isVisible(): self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height(); s = min(w, h); cx, cy = w / 2, h / 2; R = s / 2 - 4
        dim = self.state in ("muted", "idle", "standby", "error")
        base = QColor(130, 130, 140) if self.state == "muted" else QColor(255, 46, 67)
        speed = {"listening": 1.0, "speaking": 1.8, "thinking": 2.4}.get(self.state, 0.35)
        amp = {"listening": 0.35, "speaking": 0.75, "thinking": 0.5}.get(self.state, 0.12)
        t = self._t * speed
        # outer dotted ring
        p.save(); p.translate(cx, cy); p.rotate(t * 10)
        for i in range(90):
            a = 0.25 + 0.55 * ((i % 18) / 18.0)
            c = QColor(base); c.setAlphaF(a * (0.5 if dim else 1.0)); p.setPen(QPen(c, 1.6))
            p.drawLine(QPointF(R, 0), QPointF(R - (5 if i % 6 == 0 else 3), 0)); p.rotate(4)
        p.restore()
        # glowing arcs
        r2 = R * 0.80; rect = QRectF(cx - r2, cy - r2, 2 * r2, 2 * r2)
        for width, alpha in ((s * 0.075, 40), (s * 0.05, 90), (s * 0.028, 255)):
            c = QColor(base); c.setAlpha(alpha if not dim else alpha // 2)
            pen = QPen(c, width); pen.setCapStyle(Qt.RoundCap); p.setPen(pen)
            for k, (start, span) in enumerate(((20, 140), (190, 95), (310, 40))):
                p.drawArc(rect, int((start + t * 40 * (1 if k % 2 == 0 else -1)) * 16), span * 16)
        # inner disc
        r3 = R * 0.64; g = QRadialGradient(QPointF(cx, cy), r3)
        g.setColorAt(0, QColor(60, 10, 22, 175)); g.setColorAt(1, QColor(18, 5, 10, 150))
        p.setPen(QPen(QColor(base.red(), base.green(), base.blue(), 120 if not dim else 60), 1.4)); p.setBrush(QBrush(g))
        p.drawEllipse(QPointF(cx, cy), r3, r3)
        # waveform bars
        n = 15; bw = s * 0.018; gap = s * 0.016; total = n * bw + (n - 1) * gap; x0 = cx - total / 2
        p.setPen(Qt.NoPen); c = QColor(base); c.setAlpha(230 if not dim else 120); p.setBrush(c)
        for i in range(n):
            env = math.sin((i + 0.5) / n * math.pi)
            hh = (0.12 + env * (amp + 0.6 * self._e) * (0.55 + 0.45 * math.sin(self._t * 6 + i * 0.9))) * r3 * 1.2
            hh = max(s * 0.02, hh); p.drawRoundedRect(QRectF(x0 + i * (bw + gap), cy - r3 * 0.18 - hh / 2, bw, hh), bw / 2, bw / 2)
        p.setPen(QColor("#FFFFFF" if not dim else "#C9C6CF")); f = QFont("Poppins", max(9, int(s * 0.062))); f.setWeight(QFont.DemiBold); p.setFont(f)
        p.drawText(QRectF(cx - r3, cy + r3 * 0.30, 2 * r3, r3 * 0.35), Qt.AlignCenter, self.LABELS.get(self.state, ""))


class ModeBar(QWidget):
    """Wake Word / Tap to Talk / Continuous / Stop Listening."""
    sig_mode = pyqtSignal(str)
    MODES = [("wake", "dot", "Wake Word"), ("tap", "mic", "Tap to Talk"), ("continuous", "infinity", "Continuous"), ("stop", "stopcircle", "Stop Listening")]

    def __init__(self, columns=2, h=35, shadow=True, fs=12, hgap=7, vgap=7):
        super().__init__(); self._btns = {}; self._fs = fs
        from PyQt5.QtWidgets import QGridLayout
        g = QGridLayout(self); g.setContentsMargins(0, 0, 0, 0); g.setHorizontalSpacing(hgap); g.setVerticalSpacing(vgap)
        for i, (key, icon, text) in enumerate(self.MODES):
            b = QPushButton(" " + text); b.setCursor(Qt.PointingHandCursor); b.setFixedHeight(h); b.setIconSize(QSize(16, 16))
            b.clicked.connect(lambda _=False, k=key: self.sig_mode.emit(k)); b._icon = icon
            if shadow: lift(b, 10, 3, 150)
            g.addWidget(b, i // columns, i % columns); self._btns[key] = b
        self.set_mode("continuous")

    def set_mode(self, mode):
        for k, b in self._btns.items():
            on = k == mode; col = T["red"] if (b._icon in ("dot", "stopcircle") and not on) else "#FFFFFF" if on else "#C9C6CF"
            b.setIcon(svg_icon(b._icon, col, 16, 1.6))
            b.setStyleSheet(css3d("QPushButton", "active" if on else "ghost", 12, F(500, self._fs), "#FFFFFF", "padding:0 12px;text-align:left;"))


_GIRL_PM = None
def girl_pixmap():
    global _GIRL_PM
    if _GIRL_PM is None:
        _GIRL_PM = QPixmap(str(ASSETS / "ALIRA_girl.png"))
    return _GIRL_PM


class HeroPanel(QWidget):
    sig_mode = pyqtSignal(str); sig_orb = pyqtSignal(); sig_chip = pyqtSignal(str)
    CHIPS = [("Chat with me", 0), ("Control your PC", 40), ("Automate tasks", 74),
             ("Search the web", 112), ("Work with files", 122), ("And much more…", 98)]

    def __init__(self):
        super().__init__()
        self.setMinimumSize(520, 420)
        self.state, self._energy, self._t = "idle", 0.0, 0.0
        self._girl = girl_pixmap(); self._girl_scaled = None; self._girl_h = 0

        self._text = QWidget(self); self._text.setStyleSheet("background:transparent;")
        tv = QVBoxLayout(self._text); tv.setContentsMargins(0, 0, 0, 0); tv.setSpacing(0)
        self._user = QLabel(""); self._user.setStyleSheet(f"color:{T['muted']};{F(500,16)}"); self._user.hide()   # "Welcome, <naam>"
        self._hello = QLabel("Hello, I’m"); self._hello.setStyleSheet(f"color:#fff;{F(500,26)}")
        self._title = QLabel(); self._title.setTextFormat(Qt.RichText)
        sub = QHBoxLayout(); sub.setSpacing(8)
        self._sub = QLabel("Your Smart PC Assistant"); self._sub.setStyleSheet(f"color:{T['red']};{F(400,18)}")
        ecg = QLabel(); ecg.setPixmap(svg_pixmap("activity", T["red"], 28, 1.6))
        sub.addWidget(self._sub); sub.addWidget(ecg); sub.addStretch()
        tv.addWidget(self._user); tv.addWidget(self._hello); tv.addWidget(self._title); tv.addLayout(sub); tv.addSpacing(16)
        # staggered pill chips (mockup 1) — bade aur door-door
        for text, off in self.CHIPS:
            row = QHBoxLayout(); row.setContentsMargins(off, 0, 0, 0)
            b = QPushButton(text); b.setCursor(Qt.PointingHandCursor); b.setFixedHeight(42)
            b.setStyleSheet(css3d("QPushButton", "ghost", 21, F(500, 15), "#F4F3F6", "padding:0 24px;background-color:rgba(10,8,12,0.55);"))
            b.clicked.connect(lambda _=False, t=text: self.sig_chip.emit(t))
            row.addWidget(b); row.addStretch(); tv.addLayout(row); tv.addSpacing(13)
        tv.addStretch(1)
        # mode buttons — neeche-left (user ke arrow wali jagah), 2x2, bade aur alag-alag
        self.modes = ModeBar(columns=2, h=40, shadow=False, fs=13, hgap=14, vgap=14)
        self.modes.sig_mode.connect(self.sig_mode); tv.addWidget(self.modes); tv.addSpacing(6)
        # orb — title ke right mein (user ke circle wali jagah), bada
        self.orb = Orb(190); self.orb.setParent(self); self.orb.clicked.connect(_ALIRA_slot(self.sig_orb))
        self._relayout_text()
        QTimer(self, interval=90, timeout=self._tick).start()

    def set_user_name(self, name):
        name = (name or "").strip()
        self._user.setText(f"Welcome, {name}" if name else "")
        self._user.setVisible(bool(name))

    def set_orb_scale(self, f):
        self.orb_scale = max(0.5, min(1.5, float(f))); self._relayout_text()
    def set_state(self, s): self.state = s; self.orb.set_state(s)
    def set_energy(self, e): self._energy = min(1.0, float(e) / 120.0); self.orb.set_energy(e)
    def set_mode(self, m): self.modes.set_mode(m)

    def _tick(self):
        self._t += 0.05
        if self.isVisible(): self.update()

    def _relayout_text(self):
        w = max(self.width(), 520); h = max(self.height(), 420)
        px = max(38, min(60, int(w * 0.072)))
        self._title.setFixedHeight(int(px * 1.25))
        self._title.setText(f'<span style="color:#fff;{F(800, px)}">ALIRA </span>'
                            f'<span style="color:{T["red"]};{F(800, px)}">AI</span>')
        x = int(w * 0.42)
        self._text.setGeometry(x, int(h * 0.04), min(w - x - 12, 380), int(h * 0.93))
        # orb: title/subtitle ke bilkul right mein, jitni jagah mile utna bada (120..250)
        text_right = x + max(self._title.sizeHint().width(), self._sub.sizeHint().width() + 40)
        ox = text_right + 16
        size = max(120, min(250, w - ox - 10))
        size = max(90, min(340, int(size * getattr(self, 'orb_scale', 1.0))))   # Settings: UI orb size
        self.orb.setFixedSize(size, size)
        self.orb.move(min(ox, w - size - 8), int(h * 0.03)); self.orb.raise_()

    def resizeEvent(self, e):
        self._relayout_text(); super().resizeEvent(e)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height()
        p.fillRect(self.rect(), QColor(T["bg"]))
        pulse = 0.5 + 0.5 * math.sin(self._t * (3.0 if self.state in ("speaking", "listening") else 1.2))
        boost = {"speaking": 0.30, "listening": 0.22, "thinking": 0.16}.get(self.state, 0.08) + self._energy * 0.3
        g = QRadialGradient(QPointF(w * 0.25, h * 0.78), w * 0.75)
        g.setColorAt(0, QColor(255, 30, 60, int(255 * (0.18 + boost * pulse))))
        g.setColorAt(1, QColor(255, 30, 60, 0)); p.fillRect(self.rect(), QBrush(g))
        if not self._girl.isNull():
            if self._girl_scaled is None or self._girl_h != h:
                self._girl_scaled = self._girl.scaledToHeight(h, Qt.SmoothTransformation); self._girl_h = h
            p.drawPixmap(int(w * 0.27 - 0.596 * self._girl_scaled.width()), 0, self._girl_scaled)
        lf = QLinearGradient(0, 0, 40, 0); lf.setColorAt(0, QColor(T["bg"])); lf.setColorAt(1, QColor(7, 6, 10, 0))
        p.fillRect(0, 0, 40, h, QBrush(lf))
        rf = QLinearGradient(w - 60, 0, w, 0); rf.setColorAt(0, QColor(7, 6, 10, 0)); rf.setColorAt(1, QColor(T["bg"]))
        p.fillRect(w - 60, 0, 60, h, QBrush(rf))


# ══════════════════════════════════════════════════════════════════
# RIGHT PANEL CARDS
# ══════════════════════════════════════════════════════════════════
def _card_style(name):
    return f"#{name}{{background:rgba(18,15,22,0.92);border:1px solid {T['line']};border-radius:14px;}}"

class Ring(QWidget):
    def __init__(self, label, color):
        super().__init__(); self.label, self.color, self.value = label, QColor(color), 0
        self.setMinimumSize(96, 104)

    def set_value(self, v): self.value = max(0, min(100, int(v))); self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        d = min(self.width() - 8, self.height() - 30, 84); cx = self.width() / 2
        r = QRectF(cx - d / 2, 4, d, d)
        pen = QPen(QColor(30, 27, 36), 7); pen.setCapStyle(Qt.RoundCap); p.setPen(pen); p.drawArc(r, 0, 360 * 16)
        pen = QPen(self.color, 7); pen.setCapStyle(Qt.RoundCap); p.setPen(pen)
        p.drawArc(r, 90 * 16, -int(self.value * 3.6 * 16))
        p.setPen(QColor("#fff")); f = QFont("Poppins", 12); f.setWeight(QFont.DemiBold); p.setFont(f)
        p.drawText(r, Qt.AlignCenter, f"{self.value}%")
        p.setPen(QColor(T["muted"])); p.setFont(QFont("Poppins", 10))
        p.drawText(QRectF(0, d + 8, self.width(), 20), Qt.AlignCenter, self.label)


class BatteryStat(QWidget):
    def __init__(self):
        super().__init__(); self.value = 0; self.setMinimumSize(96, 104)

    def set_value(self, v): self.value = max(0, min(100, int(v))); self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        cx = self.width() / 2; body = QRectF(cx - 30, 14, 56, 28)
        p.setPen(QPen(QColor(230, 230, 235), 2)); p.setBrush(Qt.NoBrush); p.drawRoundedRect(body, 6, 6)
        p.setPen(Qt.NoPen); p.setBrush(QColor(230, 230, 235)); p.drawRoundedRect(QRectF(cx + 27, 23, 4, 10), 2, 2)
        fill = QRectF(body.x() + 3, body.y() + 3, (body.width() - 6) * self.value / 100, body.height() - 6)
        p.setBrush(QColor(T["green"])); p.drawRoundedRect(fill, 4, 4)
        p.setPen(QColor("#fff")); f = QFont("Poppins", 12); f.setWeight(QFont.DemiBold); p.setFont(f)
        p.drawText(QRectF(0, 50, self.width(), 22), Qt.AlignCenter, f"{self.value}%")
        p.setPen(QColor(T["muted"])); p.setFont(QFont("Poppins", 10))
        p.drawText(QRectF(0, 72, self.width(), 20), Qt.AlignCenter, "Battery")


class StatsCard(QFrame):
    def __init__(self):
        super().__init__(); self.setObjectName("stats"); self.setStyleSheet(_card_style("stats"))
        self.setFixedHeight(134)
        hl = QHBoxLayout(self); hl.setContentsMargins(14, 12, 14, 8); hl.setSpacing(2)
        self.cpu, self.ram, self.disk, self.bat = Ring("CPU", "#2A8BE8"), Ring("RAM", "#27B5E6"), Ring("Storage", "#F43B4E"), BatteryStat()
        for w in (self.cpu, self.ram, self.disk, self.bat): hl.addWidget(w, 1)
        QTimer(self, interval=2000, timeout=self.refresh).start(); self.refresh()

    def refresh(self):
        try:
            self.cpu.set_value(psutil.cpu_percent()); self.ram.set_value(psutil.virtual_memory().percent)
            root = os.path.abspath(os.sep); self.disk.set_value(psutil.disk_usage(root).percent)
            b = psutil.sensors_battery(); self.bat.set_value(b.percent if b else 100)
        except Exception:
            pass


class QuickToolsCard(QFrame):
    sig_tool = pyqtSignal(str)
    TOOLS = [("open_app", "grid", "Open App", "#E8E6EC"), ("screenshot", "screenshot", "Screenshot", "#E8E6EC"),
             ("clipboard", "file", "Clipboard", "#E8E6EC"), ("volume", "volume", "Volume", "#E8E6EC"),
             ("brightness", "sun", "Brightness", "#E8E6EC"), ("lock", "lock", "Lock PC", "#E8E6EC"),
             ("shutdown", "power", "Shutdown", T["red"]), ("whatsapp", "whatsapp", "WhatsApp", T["green"])]

    def __init__(self):
        super().__init__(); self.setObjectName("qt"); self.setStyleSheet(_card_style("qt"))
        vl = QVBoxLayout(self); vl.setContentsMargins(16, 14, 16, 14); vl.setSpacing(10)
        hdr = QHBoxLayout(); ic = QLabel(); ic.setPixmap(svg_pixmap("bolt", T["red"], 22, 1.6))
        t = QLabel("Quick Tools"); t.setStyleSheet(f"color:#fff;{F(600,18)};")
        va = QPushButton("View All  ›"); va.setCursor(Qt.PointingHandCursor); va.setFlat(True)
        va.setStyleSheet(f"QPushButton{{color:{T['muted']};{F(400,13)};border:none;}}QPushButton:hover{{color:#fff;}}")
        va.clicked.connect(lambda: self.sig_tool.emit("view_all"))
        hdr.addWidget(ic); hdr.addWidget(t); hdr.addStretch(); hdr.addWidget(va); vl.addLayout(hdr)
        from PyQt5.QtWidgets import QGridLayout
        grid = QGridLayout(); grid.setSpacing(8)
        for i, (key, icon, label, col) in enumerate(self.TOOLS):
            b = QToolButton(); b.setText(label); b.setIcon(svg_icon(icon, col, 28, 1.5)); b.setIconSize(QSize(28, 28))
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon); b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(70); b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            b.setStyleSheet(css3d("QToolButton", "ghost", 12, F(500, 12), "#E8E6EC", "padding-top:6px;"))
            lift(b, 12, 4, 160)
            b.clicked.connect(lambda _=False, k=key: self.sig_tool.emit(k))
            grid.addWidget(b, i // 4, i % 4)
        vl.addLayout(grid, 1)


class _ActIcon(QWidget):
    def __init__(self, kind):
        super().__init__(); self.kind = kind; self.setFixedSize(34, 34)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); r = QRectF(3, 3, 28, 28)
        k = self.kind
        if k == "vscode":
            p.setBrush(QColor("#1F9CF0")); p.setPen(Qt.NoPen)
            path = QPainterPath(); path.moveTo(24, 3); path.lineTo(31, 7); path.lineTo(31, 27); path.lineTo(24, 31)
            path.lineTo(11, 20); path.lineTo(5, 25); path.lineTo(3, 23); path.lineTo(3, 11); path.lineTo(5, 9)
            path.lineTo(11, 14); path.closeSubpath(); p.drawPath(path)
            p.setBrush(QColor(8, 8, 12)); p.drawPolygon(*[QPointF(x, y) for x, y in ((24, 10), (24, 24), (15, 17))])
        elif k == "google":
            f = QFont("Poppins", 20); f.setWeight(QFont.Bold); p.setFont(f); p.setPen(QColor("#4285F4"))
            p.drawText(self.rect(), Qt.AlignCenter, "G")
        elif k == "note":
            p.setPen(Qt.NoPen); p.setBrush(QColor("#CFCFD6")); p.drawRoundedRect(QRectF(6, 4, 22, 26), 4, 4)
            p.setPen(QPen(QColor("#3A3A44"), 2)); p.drawLine(11, 12, 23, 12); p.drawLine(11, 17, 23, 17); p.drawLine(11, 22, 18, 22)
        elif k == "pdf":
            p.setPen(Qt.NoPen); p.setBrush(QColor("#F0263C")); p.drawRoundedRect(QRectF(5, 3, 24, 28), 5, 5)
            p.setPen(QColor("#fff")); f = QFont("Poppins", 6); f.setWeight(QFont.Bold); p.setFont(f)
            p.drawText(QRectF(5, 18, 24, 12), Qt.AlignCenter, "PDF")
        else:
            p.setPen(Qt.NoPen); p.setBrush(QColor(T["red"])); p.drawEllipse(r)
            p.setPen(QColor("#fff")); p.setFont(QFont("Poppins", 10)); p.drawText(self.rect(), Qt.AlignCenter, "•")


class RecentActivityCard(QFrame):
    sig_view_all = pyqtSignal()

    def __init__(self):
        super().__init__(); self.setObjectName("ra"); self.setStyleSheet(_card_style("ra"))
        self.setFixedHeight(236)
        now = time.time()
        self._items = [("vscode", "Opened Visual Studio Code", now - 120), ("google", "Searched on Google", now - 300),
                       ("note", "Created a note", now - 720), ("pdf", "Converted image to PDF", now - 1080)]
        vl = QVBoxLayout(self); vl.setContentsMargins(16, 14, 16, 12); vl.setSpacing(6)
        hdr = QHBoxLayout(); ic = QLabel(); ic.setPixmap(svg_pixmap("clock", T["red"], 22, 1.6))
        t = QLabel("Recent Activity"); t.setStyleSheet(f"color:#fff;{F(600,18)};")
        va = QPushButton("View All  ›"); va.setFlat(True); va.setCursor(Qt.PointingHandCursor)
        va.setStyleSheet(f"QPushButton{{color:{T['muted']};{F(400,13)};border:none;}}QPushButton:hover{{color:#fff;}}")
        va.clicked.connect(_ALIRA_slot(self.sig_view_all))
        hdr.addWidget(ic); hdr.addWidget(t); hdr.addStretch(); hdr.addWidget(va); vl.addLayout(hdr)
        self._rows = []
        for _ in range(4):
            row = QHBoxLayout(); row.setSpacing(12)
            icon = _ActIcon("vscode"); txt = QLabel(); ago = QLabel()
            txt.setStyleSheet(f"color:#EDEBF0;{F(400,15)};"); ago.setStyleSheet(f"color:{T['muted']};{F(400,13)};")
            row.addWidget(icon); row.addWidget(txt, 1); row.addWidget(ago); vl.addLayout(row, 1)
            self._rows.append((icon, txt, ago))
        QTimer(self, interval=30000, timeout=self._render).start(); self._render()

    def add(self, text, kind="dot"):
        self._items.insert(0, (kind, text[:34], time.time())); self._items = self._items[:4]; self._render()

    @staticmethod
    def _ago(ts):
        m = int((time.time() - ts) // 60)
        return "just now" if m < 1 else f"{m} min ago" if m < 60 else f"{m // 60} hr ago"

    def _render(self):
        for (icon, txt, ago), (kind, text, ts) in zip(self._rows, self._items):
            icon.kind = kind; icon.update(); txt.setText(text); ago.setText(self._ago(ts))


# ══════════════════════════════════════════════════════════════════
# HEADER (Online ▾ + window controls)
# ══════════════════════════════════════════════════════════════════
class _Proxy:
    """TABBU.py ke purane BottomControls attrs (cam_btn/voice_btn/screen_btn) ka shim."""
    def __init__(self, cb): self._cb = cb
    def setText(self, t): self._cb(t)
    def set_sharing(self, on): self._cb("Screen share: ON  ●" if on else "Screen share: OFF")


class HeaderBar(QWidget):
    sig_mode = pyqtSignal(); sig_mic_select = pyqtSignal(); sig_api_change = pyqtSignal()
    sig_model = pyqtSignal(str); sig_voice = pyqtSignal(); sig_camera = pyqtSignal(); sig_screenshare = pyqtSignal()
    sig_status_text = pyqtSignal(str, str)

    def __init__(self, live_model_key="3.1", models=()):
        super().__init__(); self.setFixedHeight(56)
        hl = QHBoxLayout(self); hl.setContentsMargins(0, 8, 12, 0); hl.setSpacing(8); hl.addStretch()

        self._online = QPushButton(); self._online.setCursor(Qt.PointingHandCursor); self._online.setFixedSize(138, 40)
        self._online.setStyleSheet(css3d("QPushButton", "ghost", 12) + "QPushButton::menu-indicator{image:none;}")
        lift(self._online, 12, 4, 160)
        ol = QHBoxLayout(self._online); ol.setContentsMargins(16, 0, 12, 0); ol.setSpacing(8)
        self._dot = QLabel("●"); self._otxt = QLabel("Online"); self._chev = QLabel()
        self._chev.setPixmap(svg_pixmap("chevron_down", "#C9C6CF", 18))
        for w_ in (self._dot, self._otxt, self._chev): w_.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._otxt.setStyleSheet(f"color:#fff;{F(500,16)}")
        ol.addWidget(self._dot); ol.addWidget(self._otxt, 1); ol.addWidget(self._chev)
        self._set_online(True)
        self._menu = QMenu(self)
        self._menu.setStyleSheet(f"""QMenu{{background:#121016;color:#EDEBF0;border:1px solid {T['line_red']};border-radius:8px;padding:6px;{F(500,14)};}}
            QMenu::item{{padding:8px 22px;border-radius:6px;}}QMenu::item:selected{{background:rgba(255,46,67,0.25);}}
            QMenu::separator{{height:1px;background:{T['line']};margin:6px 4px;}}""")
        self._act = {}
        for key, text, sig in [("mode", "Mode: ALIRA 🌸", self.sig_mode), ("voice", "Voice: Female", self.sig_voice),
                               (None, None, None),
                               ("camera", "🎥  Camera On/Off", self.sig_camera), ("screen", "Screen share: OFF", self.sig_screenshare),
                               (None, None, None), ("mic", "🎙  Mic / Speaker…", self.sig_mic_select), ("api", "🔑  API key…", self.sig_api_change)]:
            if key is None: self._menu.addSeparator(); continue
            a = self._menu.addAction(text); a.triggered.connect(lambda _=False, s=sig: s.emit()); self._act[key] = a
        # Voice model submenu (checkable) — Live API models
        from PyQt5.QtWidgets import QActionGroup
        self._model_menu = self._menu.addMenu("⚡  Voice model")
        self._model_menu.setStyleSheet(self._menu.styleSheet())
        self._model_group = QActionGroup(self._model_menu); self._model_group.setExclusive(True)
        self._model_acts = {}
        for k, label in models:
            a = self._model_menu.addAction(label); a.setCheckable(True); a.setChecked(k == live_model_key)
            self._model_group.addAction(a); self._model_acts[k] = a
            a.triggered.connect(lambda _=False, key=k: self.sig_model.emit(key))
        self._online.setMenu(self._menu)
        hl.addWidget(self._online); hl.addSpacing(18)

        self.cam_btn = _Proxy(lambda t: self._act["camera"].setText(t))
        self.voice_btn = _Proxy(lambda t: self._act["voice"].setText(t))
        self.screen_btn = _Proxy(lambda t: self._act["screen"].setText(t))

        for name, slot in (("minus", lambda: self.window().showMinimized()), ("square", self._toggle_max),
                           ("x", lambda: self.window().close())):
            b = QPushButton(); b.setFixedSize(40, 40); b.setCursor(Qt.PointingHandCursor); b.setFlat(True)
            b.setIcon(svg_icon(name, "#E8E6EC", 20, 1.6)); b.setIconSize(QSize(20, 20)); b.clicked.connect(_ALIRA_slot(slot))
            b.setStyleSheet(css3d("QPushButton", "danger" if name == "x" else "ghost", 9))
            lift(b, 10, 3, 150)
            hl.addWidget(b)

    def _set_online(self, ok):
        col, txt = (T["green"], "Online") if ok else (T["red"], "Offline")
        self._dot.setStyleSheet(f"color:{col};font-size:12px;"); self._otxt.setText(txt)

    # ── purane TopBar API ──
    def set_status(self, state, label):
        self._set_online(state != "error"); self.sig_status_text.emit(state, label)
    def set_model_label(self, key):
        if key in self._model_acts: self._model_acts[key].setChecked(True)
    def set_mode_label(self, text): self._act["mode"].setText(text)

    def _toggle_max(self):
        w = self.window(); w.showNormal() if w.isMaximized() else w.showMaximized()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self.window().windowHandle():
            self.window().windowHandle().startSystemMove()
    def mouseDoubleClickEvent(self, e): self._toggle_max()


# ══════════════════════════════════════════════════════════════════
# INPUT BAR + SUGGESTION CHIPS
# ══════════════════════════════════════════════════════════════════
class InputBar(QFrame):
    sig_send = pyqtSignal(str); sig_mic = pyqtSignal(); sig_attach = pyqtSignal(); sig_image = pyqtSignal()

    def __init__(self):
        super().__init__(); self.setObjectName("inbar"); self.setFixedHeight(86)
        self.setStyleSheet(f"#inbar{{border:2px solid {T['red']};border-radius:43px;background:rgba(14,11,16,0.96);}}")
        _glow(self, T["red"], 30, 140)
        hl = QHBoxLayout(self); hl.setContentsMargins(22, 0, 18, 0); hl.setSpacing(14)
        self.mic = QPushButton(); self.mic.setFixedSize(60, 60); self.mic.setCursor(Qt.PointingHandCursor)
        self.mic.setIconSize(QSize(26, 26)); self.mic.setToolTip("Mic on/off"); self.mic.clicked.connect(_ALIRA_slot(self.sig_mic))
        self.set_mic_on(True)
        self.edit = QLineEdit(); self.edit.setPlaceholderText("Ask me anything…"); self.edit.setFrame(False)
        self.edit.setStyleSheet(f"QLineEdit{{background:transparent;color:#fff;{F(400,19)};border:none;selection-background-color:{T['red']};}}")
        self.edit.returnPressed.connect(_ALIRA_slot(self._send))
        hl.addWidget(self.mic); hl.addWidget(self.edit, 1)
        for name, sig, tip in (("paperclip", self.sig_attach, "Attach file"), ("image", self.sig_image, "Camera vision")):
            b = QPushButton(); b.setFlat(True); b.setFixedSize(40, 40); b.setCursor(Qt.PointingHandCursor); b.setToolTip(tip)
            b.setIcon(svg_icon(name, "#C9C6CF", 26, 1.5)); b.setIconSize(QSize(26, 26)); b.clicked.connect(_ALIRA_slot(sig))
            b.setStyleSheet(css3d("QPushButton", "ghost", 12)); lift(b, 10, 3, 150)
            hl.addWidget(b)
        self.send = QPushButton(); self.send.setFixedSize(88, 62); self.send.setCursor(Qt.PointingHandCursor); self.send.setToolTip("Send")
        self.send.setIcon(svg_icon("send", "#FFFFFF", 30, 1.2)); self.send.setIconSize(QSize(30, 30)); self.send.clicked.connect(_ALIRA_slot(self._send))
        self.send.setStyleSheet(css3d("QPushButton", "primary", 20))
        lift(self.send, 18, 5, 190, T["red"])
        hl.addWidget(self.send)

    def set_mic_on(self, on):
        self.mic.setIcon(svg_icon("mic", T["red"] if on else "#6C6975", 26, 1.7))
        self.mic.setStyleSheet(css3d("QPushButton", "active" if on else "ghost", 30))
        if self.mic.graphicsEffect() is None:
            lift(self.mic, 14, 4, 170, T["red"] if on else "#000000")

    def _send(self):
        t = self.edit.text().strip()
        if t: self.edit.clear(); self.sig_send.emit(t)


class ChipsRow(QWidget):
    sig_chip = pyqtSignal(str)
    CHIPS = ["Open Chrome", "Search on Google", "Summarize this file", "Create an image", "Tell me a joke"]

    def __init__(self):
        super().__init__(); self.setFixedHeight(52)
        hl = QHBoxLayout(self); hl.setContentsMargins(0, 4, 0, 4); hl.setSpacing(14); hl.addStretch()
        for i, t in enumerate(self.CHIPS):
            b = QPushButton(t); b.setCursor(Qt.PointingHandCursor); b.setFixedHeight(42)
            b.setStyleSheet(css3d("QPushButton", "ghost", 21, F(500, 13), "#EDEBF0", "padding:0 20px;"))
            lift(b, 10, 3, 150)
            b.clicked.connect(lambda _=False, x=t: self.sig_chip.emit(x)); hl.addWidget(b)
        hl.addStretch()


# ══════════════════════════════════════════════════════════════════
# STATUS BAR
# ══════════════════════════════════════════════════════════════════
class Waveform(QWidget):
    def __init__(self):
        super().__init__(); self.setFixedSize(46, 28); self._e = 0.2; self._t = 0.0; self.active = True
        QTimer(self, interval=90, timeout=self._tick).start()
    def set_energy(self, e): self._e = min(1.0, float(e) / 100.0)
    def _tick(self):
        self._t += 0.35
        if self.isVisible(): self.update()
    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.setPen(Qt.NoPen); p.setBrush(QColor(T["red"]))
        n = 9
        for i in range(n):
            amp = (0.25 + 0.75 * abs(math.sin(self._t + i * 0.9))) * (0.35 + 0.65 * max(self._e, 0.25 if self.active else 0.05))
            h = max(4, amp * 24); x = 2 + i * 5
            p.drawRoundedRect(QRectF(x, (28 - h) / 2, 3, h), 1.5, 1.5)


class StatusBar(QFrame):
    sig_globe = pyqtSignal(); sig_keyboard = pyqtSignal(); sig_settings = pyqtSignal(); sig_fullscreen = pyqtSignal()
    TEXT = {"standby": "ALIRA is on standby…", "listening": "ALIRA is listening…", "thinking": "ALIRA is thinking…",
            "speaking": "ALIRA is speaking…", "screenshare": "ALIRA is watching your screen…", "webforge": "ALIRA is building…"}

    def __init__(self):
        super().__init__(); self.setObjectName("sbar"); self.setFixedHeight(56)
        self.setStyleSheet(f"#sbar{{background:#09080C;border-top:1px solid {T['line']};}}")
        hl = QHBoxLayout(self); hl.setContentsMargins(22, 0, 14, 0); hl.setSpacing(12)
        self.wave = Waveform(); self.label = QLabel("ALIRA is listening…"); self.label.setMinimumWidth(320)
        self.label.setStyleSheet(f"color:{T['red']};{F(500,16)};")
        hl.addWidget(self.wave); hl.addWidget(self.label); hl.addStretch()
        for name, sig, tip in (("globe", self.sig_globe, "WebForge — website banao"), ("keyboard", self.sig_keyboard, "Mic / Speaker"),
                               ("gear", self.sig_settings, "API key"), ("maximize", self.sig_fullscreen, "Fullscreen")):
            b = QPushButton(); b.setFlat(True); b.setFixedSize(46, 40); b.setCursor(Qt.PointingHandCursor); b.setToolTip(tip)
            b.setIcon(svg_icon(name, "#D9D6DE", 24, 1.5)); b.setIconSize(QSize(24, 24)); b.clicked.connect(_ALIRA_slot(sig))
            b.setStyleSheet(css3d("QPushButton", "ghost", 9)); lift(b, 8, 3, 140)
            hl.addWidget(b)
        grip = QSizeGrip(self); grip.setFixedSize(16, 16); hl.addWidget(grip, 0, Qt.AlignBottom | Qt.AlignRight)

    def set_status(self, state, label):
        self._last = (state, label)
        if getattr(self, "_flashing", False): return
        self._apply(state, label)

    def _apply(self, state, label):
        self.label.setText(self.TEXT.get(state, label.title() if label else "ALIRA"))
        self.label.setStyleSheet(f"color:{T['red'] if state != 'standby' else T['muted']};{F(500,16)};")
        self.wave.active = state in ("listening", "speaking", "thinking")

    def flash(self, text, ms=4500):
        """Chhota temporary message (action result / hint) — baad mein status wapas."""
        self._flashing = True
        self.label.setText(text); self.label.setStyleSheet(f"color:#FFFFFF;{F(500,15)};")
        QTimer.singleShot(ms, self._unflash)

    def _unflash(self):
        self._flashing = False
        self._apply(*getattr(self, "_last", ("standby", "")))
    def set_energy(self, e): self.wave.set_energy(e)


# ══════════════════════════════════════════════════════════════════
# PAGE HELPERS — har page par girl + header + scrollable body
# ══════════════════════════════════════════════════════════════════
_CARD_N = [0]

def make_card(title=None, icon=None, right=None):
    """(frame, body_layout) — translucent glass card with optional title row."""
    _CARD_N[0] += 1; name = f"card{_CARD_N[0]}"
    f = QFrame(); f.setObjectName(name); f.setStyleSheet(_card_style(name))
    vl = QVBoxLayout(f); vl.setContentsMargins(18, 14, 18, 16); vl.setSpacing(10)
    if title:
        h = QHBoxLayout(); h.setSpacing(10)
        if icon:
            ic = QLabel(); ic.setPixmap(svg_pixmap(icon, T["red"], 22, 1.6)); h.addWidget(ic)
        t = QLabel(title); t.setStyleSheet(f"color:#fff;{F(600,17)}"); h.addWidget(t); h.addStretch()
        if right is not None: h.addWidget(right)
        vl.addLayout(h)
    return f, vl


def pill(text, icon=None, kind="ghost", h=40):
    b = QPushButton(("  " + text) if icon else text); b.setCursor(Qt.PointingHandCursor); b.setFixedHeight(h)
    if icon:
        b.setIcon(svg_icon(icon, "#FFFFFF" if kind == "primary" else (T["red"] if kind == "danger" else "#D9D6DE"), 18, 1.6)); b.setIconSize(QSize(18, 18))
    b.setStyleSheet(css3d("QPushButton", kind, min(h // 2, 14), F(600 if kind != "ghost" else 500, 13), None, "padding:0 16px;"))
    if kind == "primary": lift(b, 16, 4, 170, T["red"])
    else:                 lift(b, 12, 4, 160)
    return b


class Segmented(QWidget):
    """Radio-style segmented control: Segmented([(key,label),...], current)."""
    changed = pyqtSignal(str)

    def __init__(self, options, current=None):
        super().__init__(); self._btns = {}
        hl = QHBoxLayout(self); hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(8)
        for key, label in options:
            b = QPushButton(label); b.setCursor(Qt.PointingHandCursor); b.setFixedHeight(36)
            b.clicked.connect(lambda _=False, k=key: self.changed.emit(k)); self._btns[key] = b; hl.addWidget(b)
        hl.addStretch(); self.set_current(current)

    def set_current(self, cur):
        for k, b in self._btns.items():
            on = k == cur
            b.setStyleSheet(css3d("QPushButton", "active" if on else "ghost", 14, F(500, 12), "#FFFFFF", "padding:0 14px;"))
            if b.graphicsEffect() is None: lift(b, 10, 3, 150)


SLIDER_CSS = f"""QSlider::groove:horizontal{{height:6px;background:rgba(255,255,255,0.10);border-radius:3px;}}
    QSlider::sub-page:horizontal{{background:{T['red']};border-radius:3px;}}
    QSlider::handle:horizontal{{width:18px;height:18px;margin:-6px 0;border-radius:9px;background:#fff;border:2px solid {T['red']};}}"""


class PageBase(QWidget):
    """Har page ka base: left mein girl (fade), right mein title + scrollable body."""
    GIRL_FRAC, GIRL_MIN, GIRL_MAX = 0.26, 210, 340     # subclass override kar sakta hai (Studio ko zyada jagah chahiye)

    def __init__(self, title, subtitle="", icon="home"):
        super().__init__()
        from PyQt5.QtWidgets import QScrollArea
        self._girl = girl_pixmap(); self._gscaled = None; self._gh = 0; self._gw = 300
        root = QVBoxLayout(self); root.setContentsMargins(300, 18, 24, 8); root.setSpacing(12)
        head = QHBoxLayout(); head.setSpacing(14)
        ic = QLabel(); ic.setPixmap(svg_pixmap(icon, T["red"], 34, 1.6)); head.addWidget(ic)
        tb = QVBoxLayout(); tb.setSpacing(0)
        t = QLabel(title); t.setStyleSheet(f"color:#fff;{F(800,30)}")
        st = QLabel(subtitle); st.setStyleSheet(f"color:{T['muted']};{F(400,14)}")
        tb.addWidget(t); tb.addWidget(st); head.addLayout(tb); head.addStretch()
        self.header_right = QHBoxLayout(); head.addLayout(self.header_right)
        root.addLayout(head)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}"
                                  "QScrollBar:vertical{background:transparent;width:8px;}"
                                  "QScrollBar::handle:vertical{background:rgba(255,255,255,0.18);border-radius:4px;min-height:30px;}"
                                  "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")
        inner = QWidget(); inner.setStyleSheet("background:transparent;")
        self.body = QVBoxLayout(inner); self.body.setContentsMargins(0, 0, 8, 16); self.body.setSpacing(14)
        self.scroll.setWidget(inner); self.scroll.viewport().setAutoFillBackground(False)
        root.addWidget(self.scroll, 1)

    def on_show(self): pass   # subclass hook: page khulne par refresh

    def showEvent(self, e):
        self.on_show(); super().showEvent(e)

    def resizeEvent(self, e):
        self._gw = int(min(self.GIRL_MAX, max(self.GIRL_MIN, self.width() * self.GIRL_FRAC)))
        self.layout().setContentsMargins(self._gw, 18, 24, 8); super().resizeEvent(e)

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.SmoothPixmapTransform)
        w, h = self.width(), self.height(); gw = self._gw
        p.fillRect(self.rect(), QColor(T["bg"]))
        g = QRadialGradient(QPointF(gw * 0.5, h * 0.8), gw * 1.4)
        g.setColorAt(0, QColor(255, 30, 60, 60)); g.setColorAt(1, QColor(255, 30, 60, 0)); p.fillRect(self.rect(), QBrush(g))
        if not self._girl.isNull():
            if self._gscaled is None or self._gh != h:
                self._gscaled = self._girl.scaledToHeight(h, Qt.SmoothTransformation); self._gh = h
            p.setClipRect(0, 0, gw, h)
            p.drawPixmap(int(gw * 0.50 - 0.596 * self._gscaled.width()), 0, self._gscaled)
            p.setClipping(False)
        lf = QLinearGradient(gw - 110, 0, gw + 10, 0); lf.setColorAt(0, QColor(7, 6, 10, 0)); lf.setColorAt(1, QColor(T["bg"]))
        p.fillRect(gw - 110, 0, 120, h, QBrush(lf))


# ══════════════════════════════════════════════════════════════════
# API KEY DIALOG  (naya red/3D design — test key, show/hide, paste, masked current key)
# ══════════════════════════════════════════════════════════════════
class ApiKeySetupDialog(QDialog):
    _tested = pyqtSignal(bool, str)

    def __init__(self, parent=None, current_api_key=""):
        super().__init__(parent)
        load_fonts()
        self.setWindowTitle("ALIRA — Gemini API Key"); self.setModal(True); self.setFixedWidth(580)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._current = (current_api_key or "").strip(); self._busy = False
        self.setStyleSheet(f"QDialog{{background:{T['bg']};}}QLabel{{background:transparent;color:#EDEBF0;{F(400,13)}}}")
        root = QVBoxLayout(self); root.setContentsMargins(30, 28, 30, 24); root.setSpacing(16)

        head = QHBoxLayout(); head.setSpacing(14)
        ic = QLabel(); ic.setPixmap(svg_pixmap("shield", T["red"], 40, 1.5)); head.addWidget(ic, 0, Qt.AlignTop)
        tb = QVBoxLayout(); tb.setSpacing(2)
        t = QLabel("Gemini API Key"); t.setStyleSheet(f"color:#fff;{F(800,24)}")
        st = QLabel("ALIRA ki voice, vision aur Website Studio is key se chalte hain."); st.setStyleSheet(f"color:{T['muted']};{F(400,12)}"); st.setWordWrap(True)
        tb.addWidget(t); tb.addWidget(st); head.addLayout(tb, 1); root.addLayout(head)

        # steps card
        card = QFrame(); card.setObjectName("steps")
        card.setStyleSheet(f"#steps{{background:rgba(255,255,255,0.04);border:1px solid {T['line']};border-radius:14px;}}QLabel{{border:none;}}")
        cv = QVBoxLayout(card); cv.setContentsMargins(18, 14, 18, 14); cv.setSpacing(10)
        for n, txt in (("1", "Google AI Studio kholo aur  <b>Create API key</b>  dabao (free hai)."),
                       ("2", "Key copy karke neeche paste karo."),
                       ("3", "<b>Test key</b> dabake check karo, phir <b>Save</b>.")):
            r = QHBoxLayout(); r.setSpacing(12)
            num = QLabel(n); num.setFixedSize(26, 26); num.setAlignment(Qt.AlignCenter)
            num.setStyleSheet(f"background:rgba(255,46,67,0.22);border:1px solid {T['line_red']};border-radius:13px;color:#fff;{F(600,12)}")
            lb = QLabel(txt); lb.setTextFormat(Qt.RichText); lb.setWordWrap(True)
            r.addWidget(num); r.addWidget(lb, 1); cv.addLayout(r)
        getb = pill("Free key lo — aistudio.google.com", "external", "ghost", 36)
        getb.clicked.connect(lambda: __import__("webbrowser").open("https://aistudio.google.com/app/apikey")); cv.addWidget(getb, 0, Qt.AlignLeft)
        root.addWidget(card)

        # current key status
        self.cur = QLabel(); self.cur.setTextFormat(Qt.RichText); root.addWidget(self.cur)
        self._paint_current()

        # input row
        row = QHBoxLayout(); row.setSpacing(8)
        self.edit = QLineEdit(); self.edit.setEchoMode(QLineEdit.Password); self.edit.setFixedHeight(46)
        self.edit.setPlaceholderText("AIza… yahan paste karo")
        self.edit.setStyleSheet(f"QLineEdit{{background:rgba(255,255,255,0.05);color:#fff;border:1px solid rgba(255,255,255,0.16);border-radius:12px;padding:0 14px;{F(500,14)}"
                                f"selection-background-color:{T['red']};}}QLineEdit:focus{{border:1px solid {T['red']};}}")
        self.show_b = pill("Show", None, "ghost", 46); self.show_b.setFixedWidth(78); self.show_b.clicked.connect(_ALIRA_slot(self._toggle_show))
        self.paste_b = pill("Paste", "file", "ghost", 46); self.paste_b.setFixedWidth(104); self.paste_b.clicked.connect(_ALIRA_slot(self._paste))
        row.addWidget(self.edit, 1); row.addWidget(self.show_b); row.addWidget(self.paste_b); root.addLayout(row)

        self.result = QLabel(""); self.result.setWordWrap(True); self.result.setMinimumHeight(20); root.addWidget(self.result)

        btns = QHBoxLayout(); btns.setSpacing(10)
        self.test_b = pill("Test key", "check", "ghost", 44); self.test_b.clicked.connect(_ALIRA_slot(self._test))
        cancel = pill("Cancel", None, "ghost", 44); cancel.clicked.connect(_ALIRA_slot(self.reject))
        self.save_b = pill("Save key", "check", "primary", 44); self.save_b.clicked.connect(_ALIRA_slot(self.accept)); self.save_b.setDefault(True)
        btns.addWidget(self.test_b); btns.addStretch(1); btns.addWidget(cancel); btns.addWidget(self.save_b); root.addLayout(btns)

        self.edit.textChanged.connect(_ALIRA_slot(self._changed)); self._tested.connect(self._show_result); self._changed()
        QTimer.singleShot(0, self.edit.setFocus)

    # ── helpers ──
    @staticmethod
    def _mask(k):
        return (k[:4] + "•" * 10 + k[-4:]) if len(k) > 10 else "•" * len(k)

    def _paint_current(self):
        if self._current:
            self.cur.setText(f'<span style="color:{T["green"]}">●</span>&nbsp; Saved key: <b>{self._mask(self._current)}</b> '
                             f'<span style="color:{T["muted"]}">(naya paste karoge to badal jayegi)</span>')
        else:
            self.cur.setText(f'<span style="color:#F5C542">●</span>&nbsp; Abhi koi key set nahi hai.')

    def get_api_key(self):
        return self.edit.text().strip().strip("\"'").replace(" ", "")

    def _changed(self, *_):
        ok = len(self.get_api_key()) >= 20 and not self._busy
        self.save_b.setEnabled(ok); self.test_b.setEnabled(ok)
        self.result.setText("")

    def _toggle_show(self):
        hid = self.edit.echoMode() == QLineEdit.Password
        self.edit.setEchoMode(QLineEdit.Normal if hid else QLineEdit.Password); self.show_b.setText("Hide" if hid else "Show")

    def _paste(self):
        from PyQt5.QtGui import QGuiApplication
        self.edit.setText(QGuiApplication.clipboard().text().strip())

    def _test(self):
        key = self.get_api_key()
        if not key or self._busy: return
        self._busy = True; self.test_b.setText("  Testing…"); self.test_b.setEnabled(False)
        self.result.setStyleSheet(f"color:{T['muted']};{F(400,12)}"); self.result.setText("Gemini se check ho raha hai…")
        import threading

        def work():
            try:
                from TABBU_modules.gemini_rest import generate, GeminiError
                try:
                    _d, model = generate({"contents": [{"parts": [{"text": "Reply with: ok"}]}]}, key, timeout=25)
                    self._tested.emit(True, f"✓ Key sahi hai  ({model})")
                except GeminiError as e:
                    m = str(e)
                    if "429" in m or "quota" in m.lower():
                        self._tested.emit(True, "✓ Key sahi hai, par abhi free quota khatam hai (kuch ghante baad reset hoga).")
                    elif "API key not valid" in m or "API_KEY_INVALID" in m or "HTTP 400" in m or "HTTP 403" in m:
                        self._tested.emit(False, "✗ Key galat hai — dobara copy karke paste karo.")
                    else:
                        self._tested.emit(False, "✗ Check nahi ho paya: " + m[:140])
            except Exception as e:
                self._tested.emit(False, "✗ Network/internet issue: " + str(e)[:120])
        threading.Thread(target=work, daemon=True).start()

    def _show_result(self, ok, msg):
        self._busy = False; self.test_b.setText("  Test key"); self._changed_keep(ok, msg)

    def _changed_keep(self, ok, msg):
        ok_len = len(self.get_api_key()) >= 20
        self.save_b.setEnabled(ok_len); self.test_b.setEnabled(ok_len)
        self.result.setStyleSheet(f"color:{T['green'] if ok else '#FF8A98'};{F(500,12)}"); self.result.setText(msg)
