"""
ALIRA v2 — Green Cyberpunk AI Voice Assistant
=============================================
Fixes v2:
  1. Proper font rendering — Courier New bold, crisp text
  2. ALIRA orb perfectly centered in middle panel
  3. Chat bubbles working — user + ALIRA messages visible
  4. Clean border-box style for stat bars (red/green border)
  5. Better layout proportions
"""
import os, sys, asyncio, threading, base64, json, math, random, time
import numpy as np
import sounddevice as sd
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QSizePolicy,
    QGraphicsDropShadowEffect, QSpacerItem
)
from PyQt5.QtCore  import Qt, pyqtSignal, QTimer, QObject, QRect, QPoint
from PyQt5.QtGui   import (
    QColor, QPainter, QPen, QBrush, QLinearGradient,
    QRadialGradient, QPalette, QFont, QPolygon, QFontMetrics
)python.exe -m pip install --upgrade pip
import websockets

# ── Prompt ──────────────────────────────────────────────────
try:
    from prompt import TITAN_PROMPT as _PROMPT
    ALIRA_PROMPT = _PROMPT.replace("TITAN","ALIRA").replace("TITAN","ALIRA")
except ImportError:
    ALIRA_PROMPT = (
        "You are ALIRA, a warm caring AI voice assistant. "
        "Greet user immediately when connected. "
        "Keep replies to 1-3 short sentences. "
        "Detect Hindi/English/Hinglish and reply in same language. "
        "Never say 'As an AI'. Be natural like a close friend. "
        "Your name is ALIRA."
    )

# ── Tools ───────────────────────────────────────────────────
try:
    from tools import TOOL_DECLARATIONS, dispatch as _base_dispatch, TOOL_MAP as _TOOL_MAP
    _HAS_BASE = True
except ImportError:
    TOOL_DECLARATIONS=[]; _HAS_BASE=False; _TOOL_MAP={}
    async def _base_dispatch(n,a): return "ok"

try:
    from whatsapp_file_sender import WA_FILE_TOOL_DECLARATIONS, wa_file_dispatch, WA_FILE_TOOL_MAP
except ImportError:
    WA_FILE_TOOL_DECLARATIONS=[]; WA_FILE_TOOL_MAP={}
    async def wa_file_dispatch(n,a): return "ok"

try:
    from TITAN_advanced_tools import (
        ADVANCED_TOOL_DECLARATIONS, advanced_dispatch,
        init_advanced, memory_save,
    )
    _HAS_ADV   = True
    _ALL_TOOLS = TOOL_DECLARATIONS + ADVANCED_TOOL_DECLARATIONS + WA_FILE_TOOL_DECLARATIONS
except ImportError:
    _HAS_ADV   = False
    _ALL_TOOLS = TOOL_DECLARATIONS + WA_FILE_TOOL_DECLARATIONS
    async def advanced_dispatch(n,a): return "not loaded"
    async def memory_save(r,c): pass
    def init_advanced(**kw): pass

async def dispatch(name:str, args:dict)->str:
    if name in _TOOL_MAP:        return await _base_dispatch(name,args)
    if name in WA_FILE_TOOL_MAP: return await wa_file_dispatch(name,args)
    return await advanced_dispatch(name,args)

# ── Config ───────────────────────────────────────────────────
_API_KEY = os.getenv("GEMINI_API_KEY", "")
_WS_URL  = ("wss://generativelanguage.googleapis.com/ws/"
            "google.ai.generativelanguage.v1beta."
            "GenerativeService.BidiGenerateContent")
_SETUP = {
    "setup":{
        "model":"models/gemini-3.1-flash-live-preview",
        "generation_config":{
            "temperature":0.8,
            "response_modalities":["AUDIO"],
            "speech_config":{"voice_config":{
                "prebuilt_voice_config":{"voice_name":"Aoede"}
            }}
        },
        "system_instruction":{"parts":[{"text":ALIRA_PROMPT}]},
        "tools":[{"functionDeclarations":_ALL_TOOLS}]
    }
}

# ── Audio ────────────────────────────────────────────────────
MIC_RATE=16000; SPK_RATE=24000
FRAMES=int(MIC_RATE*20/1000)
SILENCE_RMS=150; SILENCE_FRAMES=25; MAX_QUEUE=80

def _enc(o): return json.dumps(o).encode()
def _now():  return datetime.now().strftime("%H:%M")

# ── Colors ───────────────────────────────────────────────────
BG        = "#020b04"
GREEN_MID = "#00ff41"
GREEN_LO  = "#00c832"
GREEN_DIM = "#006420"
AMBER     = "#ffb300"
ORANGE    = "#ff6600"
CYAN_G    = "#00ffcc"
TEXT_G    = "#b0ffcc"
MUTED_G   = "#3a7a4a"
DARK_P    = "#050f07"

LETTER_COLORS = ["#ffff00","#00ff88","#00aaff","#cc44ff"]


# ════════════════════════════════════════════════════════════
#  ALIRA ORB
# ════════════════════════════════════════════════════════════
class ALIRAOrb(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(360, 360)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.state   = "standby"
        self._t      = 0.0
        self._energy = 0.0
        self._noise  = [random.uniform(0, 2*math.pi) for _ in range(72)]
        self._gp     = 0.0; self._gd = 1
        self._dots   = [0.0, 1.0, 2.0]
        t = QTimer(self); t.timeout.connect(self._tick); t.start(18)

    def set_state(self, s): self.state = s
    def set_energy(self, e): self._energy = min(1.0, e/3000.0)

    def _tick(self):
        self._t += 0.05
        self._gp += 0.025*self._gd
        if self._gp>=1: self._gd=-1
        if self._gp<=0: self._gd= 1
        spd = 0.05 if self.state=="speaking" else 0.012
        for i in range(len(self._noise)):
            self._noise[i] += spd + random.uniform(-0.004,0.004)
        for i in range(3):
            self._dots[i] = (self._dots[i]+0.06)%(2*math.pi)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx = cy = 180

        for r,a in [(168,6),(155,12),(140,20),(128,30)]:
            c = QColor(0,255,65); c.setAlpha(a)
            p.setPen(QPen(c,1.2)); p.setBrush(Qt.NoBrush)
            p.drawEllipse(cx-r, cy-r, r*2, r*2)

        active = self.state in ("speaking","listening")
        amp    = (18 if self.state=="speaking" else 10) + self._energy*22 if active else 2.5
        base_r = 128
        pts    = []
        for i in range(72):
            ang = (i/72)*2*math.pi
            nr  = base_r + math.sin(self._noise[i])*amp + math.cos(self._t*1.8+i*0.25)*(amp*0.35)
            pts.append(QPoint(int(cx+math.cos(ang)*nr), int(cy+math.sin(ang)*nr)))

        ring_col = QColor(0,255,200) if self.state=="speaking" else \
                   QColor(0,255,65)  if self.state=="listening" else \
                   QColor(0,140,40)
        ring_col.setAlpha(200 if active else 55)
        p.setPen(QPen(ring_col, 2.2 if active else 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawPolygon(QPolygon(pts))

        gi = int(45 + self._gp*75)
        gr = QRadialGradient(cx, cy, 125)
        gc = QColor(0,190,55); gc.setAlpha(gi)
        gr.setColorAt(0, QColor(0,255,80,25))
        gr.setColorAt(0.45, gc)
        gr.setColorAt(1, QColor(0,0,0,0))
        p.setBrush(QBrush(gr)); p.setPen(Qt.NoPen)
        p.drawEllipse(cx-125, cy-125, 250, 250)

        bgr = QRadialGradient(cx,cy,115)
        bgr.setColorAt(0, QColor(10,35,15))
        bgr.setColorAt(0.7, QColor(5,18,8))
        bgr.setColorAt(1, QColor(2,10,4))
        p.setBrush(QBrush(bgr))
        ec = QColor(0,200,55); ec.setAlpha(140)
        p.setPen(QPen(ec,2.5))
        p.drawEllipse(cx-115, cy-115, 230, 230)

        font = QFont("Courier New", 42, QFont.Black)
        p.setFont(font)
        fm   = QFontMetrics(font)
        letters = ["M","A","Y","A"]
        lw = [fm.horizontalAdvance(l) for l in letters]
        gap   = 14
        total = sum(lw)+gap*3
        sx    = cx - total//2
        ty    = cy + fm.ascent()//2 - 4

        for i,(ltr,col) in enumerate(zip(letters, LETTER_COLORS)):
            sc = QColor(col); sc.setAlpha(70)
            p.setPen(sc)
            p.drawText(sx+2, ty+2, ltr)
            p.setPen(QColor(col))
            p.drawText(sx, ty, ltr)
            sx += lw[i]+gap

        for i,ph in enumerate(self._dots):
            dx = cx - 16 + i*16
            dy = cy + 52
            bri = int(80 + math.sin(ph)*80)
            dc = QColor(0, max(50,bri), 30)
            p.setBrush(QBrush(dc)); p.setPen(Qt.NoPen)
            p.drawEllipse(dx-5, dy-5, 10, 10)
        p.end()


# ════════════════════════════════════════════════════════════
#  STAT BAR
# ════════════════════════════════════════════════════════════
class StatBar(QWidget):
    def __init__(self, label, pct, bar_color=GREEN_MID, val_text=None):
        super().__init__()
        self._pct   = pct
        vl = QVBoxLayout(self)
        vl.setContentsMargins(0,1,0,1); vl.setSpacing(2)

        box = QFrame()
        box.setStyleSheet(
            f"background:rgba(0,0,0,0.4);"
            f"border:1px solid {bar_color};"
            f"border-radius:2px;"
        )
        bl = QHBoxLayout(box); bl.setContentsMargins(6,3,6,3)
        lk = QLabel(label)
        lk.setStyleSheet(
            f"color:{bar_color};font-size:10px;font-weight:bold;"
            f"font-family:'Courier New';letter-spacing:1px;border:none;background:transparent;")
        self._val_lbl = QLabel(val_text or f"{pct}%")
        self._val_lbl.setStyleSheet(
            f"color:{bar_color};font-size:10px;font-weight:bold;"
            f"font-family:'Courier New';border:none;background:transparent;")
        bl.addWidget(lk); bl.addStretch(); bl.addWidget(self._val_lbl)
        vl.addWidget(box)

        track = QWidget(); track.setFixedHeight(4)
        track.setStyleSheet("background:rgba(0,255,65,0.07);border-radius:2px;")
        self._fill = QWidget(track)
        self._fill.setFixedHeight(4)
        self._fill.setStyleSheet(f"background:{bar_color};border-radius:2px;")
        self._fill.move(0,0)
        vl.addWidget(track)
        self._track = track

        t = QTimer(self); t.timeout.connect(self._flicker)
        t.start(1800+random.randint(0,1200))

    def resizeEvent(self,e):
        super().resizeEvent(e)
        self._update_fill()

    def _update_fill(self):
        w = max(4, int(self._track.width()*self._pct/100))
        self._fill.setFixedWidth(w)

    def set_value(self,pct,txt=None):
        self._pct=pct
        if txt: self._val_lbl.setText(txt)
        else:   self._val_lbl.setText(f"{pct}%")
        self._update_fill()

    def _flicker(self):
        d   = random.randint(-4,4)
        new = max(5,min(95, self._pct+d))
        self._fill.setFixedWidth(max(4,int(self._track.width()*new/100)))
        QTimer.singleShot(180, self._update_fill)


# ════════════════════════════════════════════════════════════
#  EPHEMERAL LOG
# ════════════════════════════════════════════════════════════
class EphLog(QWidget):
    def __init__(self, main_txt, sub_txt):
        super().__init__()
        vl = QVBoxLayout(self)
        vl.setContentsMargins(0,1,0,1); vl.setSpacing(0)
        mt = QLabel(main_txt)
        mt.setStyleSheet(
            f"color:{GREEN_MID};font-family:'Courier New';font-size:11px;"
            f"font-weight:bold;background:transparent;")
        st = QLabel(sub_txt)
        st.setStyleSheet(
            f"color:{MUTED_G};font-family:'Courier New';font-size:8px;"
            f"letter-spacing:1px;background:transparent;")
        vl.addWidget(mt); vl.addWidget(st)


# ════════════════════════════════════════════════════════════
#  CHAT BUBBLE
# ════════════════════════════════════════════════════════════
class ChatBubble(QFrame):
    def __init__(self, who:str, text:str):
        super().__init__()
        self.setStyleSheet("background:transparent;border:none;")
        vl = QVBoxLayout(self)
        vl.setContentsMargins(0,0,0,0); vl.setSpacing(2)

        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lbl.setMaximumWidth(240)
        lbl.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)

        ts = QLabel(_now())
        ts.setStyleSheet(
            f"color:{MUTED_G};font-size:8px;font-family:'Courier New';"
            f"background:transparent;padding:0;border:none;")

        if who == "user":
            lbl.setStyleSheet(
                "background: rgba(0,255,65,0.09);"
                "border: 1px solid rgba(0,255,65,0.32);"
                "border-radius: 10px;"
                "border-bottom-right-radius: 2px;"
                "padding: 8px 12px;"
                "color: #d4ffd8;"
                "font-size: 12px;"
                "font-family: 'Segoe UI', sans-serif;"
            )
            vl.addWidget(lbl, 0, Qt.AlignRight)
            vl.addWidget(ts,  0, Qt.AlignRight)

        elif who == "ALIRA":
            nm = QLabel("⚡ ALIRA")
            nm.setStyleSheet(
                f"color:{GREEN_MID};font-size:9px;font-weight:bold;"
                f"font-family:'Courier New';background:transparent;"
                f"letter-spacing:1px;border:none;")
            lbl.setStyleSheet(
                "background: rgba(0,180,50,0.08);"
                "border: 1px solid rgba(0,255,65,0.25);"
                "border-radius: 10px;"
                "border-bottom-left-radius: 2px;"
                "padding: 8px 12px;"
                "color: #a0ffb8;"
                "font-size: 12px;"
                "font-family: 'Segoe UI', sans-serif;"
            )
            vl.addWidget(nm,  0, Qt.AlignLeft)
            vl.addWidget(lbl, 0, Qt.AlignLeft)
            vl.addWidget(ts,  0, Qt.AlignLeft)

        elif who == "sys":
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setMaximumWidth(258)
            lbl.setStyleSheet(
                "background: rgba(0,255,200,0.04);"
                "border: 1px solid rgba(0,255,200,0.20);"
                "border-radius: 4px;"
                "padding: 4px 10px;"
                "color: rgba(0,255,200,0.70);"
                "font-size: 9px;"
                "font-family: 'Courier New';"
                "letter-spacing: 0.5px;"
            )
            vl.addWidget(lbl, 0, Qt.AlignHCenter)

        elif who == "tool":
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setMaximumWidth(258)
            lbl.setStyleSheet(
                "background: rgba(255,179,0,0.04);"
                "border: 1px solid rgba(255,179,0,0.25);"
                "border-radius: 4px;"
                "padding: 4px 10px;"
                "color: rgba(255,200,60,0.85);"
                "font-size: 9px;"
                "font-family: 'Courier New';"
            )
            vl.addWidget(lbl, 0, Qt.AlignHCenter)


# ════════════════════════════════════════════════════════════
#  TYPING DOTS
# ════════════════════════════════════════════════════════════
class TypingDots(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("background:transparent;border:none;")
        self._idx = 0
        hl = QHBoxLayout(self); hl.setContentsMargins(0,0,0,0); hl.setSpacing(0)
        frame = QFrame()
        frame.setStyleSheet(
            "background: rgba(0,180,50,0.06);"
            "border: 1px solid rgba(0,255,65,0.20);"
            "border-radius: 10px;")
        fl = QHBoxLayout(frame); fl.setContentsMargins(12,8,12,8); fl.setSpacing(5)
        self._dots=[]
        for _ in range(3):
            d=QLabel("●")
            d.setStyleSheet("color:rgba(0,255,65,0.18);font-size:10px;background:transparent;border:none;")
            fl.addWidget(d); self._dots.append(d)
        hl.addWidget(frame); hl.addStretch()
        t=QTimer(self); t.timeout.connect(self._tick); t.start(320)
        self._t=t

    def _tick(self):
        for i,d in enumerate(self._dots):
            d.setStyleSheet(
                f"color:{'#00ff41' if i==self._idx%3 else 'rgba(0,255,65,0.15)'};"
                f"font-size:10px;background:transparent;border:none;")
        self._idx+=1

    def stop(self): self._t.stop()


# ════════════════════════════════════════════════════════════
#  MAIN WINDOW
# ════════════════════════════════════════════════════════════
class ALIRAWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ALIRA — AI Voice System")
        self.setMinimumSize(1100, 660)
        self.resize(1280, 780)
        self._msg_count = 0
        self._typing_w  = None
        self._mic_on    = True
        self._muted     = False
        self._apply_global_style()
        self._build_ui()
        self._start_worker()

    def _apply_global_style(self):
        self.setStyleSheet("""
            QMainWindow { background: #020b04; }
            QWidget     { background: transparent; color: #b0ffcc;
                          font-family: 'Courier New'; }
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical {
                background: transparent; width: 5px; margin: 0; }
            QScrollBar::handle:vertical {
                background: rgba(0,255,65,0.22); border-radius: 2px; min-height: 20px; }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical { height: 0; }
            QLabel { background: transparent; border: none; }
        """)

    def _build_ui(self):
        root = QWidget()
        root.setStyleSheet(
            "background: qradialgradient("
            "  cx:0.5, cy:0.5, radius:1.0,"
            "  stop:0 #071610, stop:0.6 #040d07, stop:1 #020804);"
        )
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)

        border = QFrame()
        border.setStyleSheet(
            "border: 2px solid rgba(200,30,30,0.65);"
            "border-radius: 3px;"
            "background: transparent;"
        )
        bvl = QVBoxLayout(border)
        bvl.setContentsMargins(1,1,1,1); bvl.setSpacing(0)
        outer.addWidget(border, 1)

        body = QWidget(); body.setStyleSheet("border:none;background:transparent;")
        hl = QHBoxLayout(body)
        hl.setContentsMargins(0,0,0,0); hl.setSpacing(0)
        hl.addWidget(self._mk_left())
        hl.addWidget(self._mk_center(), 1)
        hl.addWidget(self._mk_right())
        bvl.addWidget(body)

    # ════════════════════════════════════════════════════════
    #  LEFT SIDEBAR
    # ════════════════════════════════════════════════════════
    def _mk_left(self):
        sb = QFrame()
        sb.setFixedWidth(228)
        sb.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "  stop:0 rgba(2,10,4,0.99), stop:1 rgba(4,16,7,0.90));"
            "border-right: 1px solid rgba(0,255,65,0.13);"
        )
        vl = QVBoxLayout(sb)
        vl.setContentsMargins(12,12,12,12); vl.setSpacing(7)
        vl.setAlignment(Qt.AlignTop)

        # SYSTEM UPDATE boxed header
        hdr_box = QFrame()
        hdr_box.setStyleSheet(
            f"background:rgba(0,0,0,0.45);"
            f"border:1px solid {GREEN_MID};"
            f"border-radius:2px;"
        )
        hbl = QHBoxLayout(hdr_box); hbl.setContentsMargins(8,4,8,4)
        h1 = QLabel("SYSTEM UPDATE")
        h1.setStyleSheet(
            f"color:{GREEN_MID};font-size:11px;font-weight:bold;"
            f"letter-spacing:2px;font-family:'Courier New';border:none;background:transparent;")
        hbl.addWidget(h1); hbl.addStretch()
        v2 = QLabel("v2")
        v2.setStyleSheet(f"color:{MUTED_G};font-size:8px;font-family:'Courier New';border:none;background:transparent;")
        hbl.addWidget(v2)
        vl.addWidget(hdr_box)

        self._neural_bar = StatBar("NEURAL LOAD",   24, GREEN_MID, "24%")
        vl.addWidget(self._neural_bar)
        self._mem_bar    = StatBar("MEMORY BUFFER", 42, AMBER,     "42%")
        vl.addWidget(self._mem_bar)
        self._core_bar   = StatBar("CORE TEMP",     45, ORANGE,    "45°C")
        vl.addWidget(self._core_bar)

        sr = QHBoxLayout(); sr.setSpacing(6)
        for k,v in [("STORAGE","68%"),("LIFETIME","2d")]:
            cell = QFrame()
            cell.setStyleSheet(
                f"background:rgba(0,0,0,0.4);"
                f"border:1px solid {GREEN_DIM};"
                f"border-radius:2px;")
            cl2 = QVBoxLayout(cell); cl2.setContentsMargins(7,3,7,3); cl2.setSpacing(1)
            lk2 = QLabel(k)
            lk2.setStyleSheet(f"color:{MUTED_G};font-size:8px;letter-spacing:1px;"
                              f"font-family:'Courier New';border:none;background:transparent;")
            lv2 = QLabel(v)
            lv2.setStyleSheet(f"color:{GREEN_MID};font-size:13px;font-weight:bold;"
                              f"font-family:'Courier New';border:none;background:transparent;")
            cl2.addWidget(lk2); cl2.addWidget(lv2)
            sr.addWidget(cell)
        vl.addLayout(sr)

        vl.addWidget(self._divider())

        elh = QHBoxLayout(); elh.setContentsMargins(0,0,0,0)
        el_lbl = QLabel("EPHEMERAL_LOGS")
        el_lbl.setStyleSheet(
            f"color:{GREEN_MID};font-size:10px;font-weight:bold;"
            f"letter-spacing:1px;font-family:'Courier New';")
        elh.addWidget(el_lbl); elh.addStretch()
        self._log_cnt = QLabel("5/12")
        self._log_cnt.setStyleSheet(f"color:{MUTED_G};font-size:8px;font-family:'Courier New';")
        elh.addWidget(self._log_cnt)
        vl.addLayout(elh)

        ls = QScrollArea(); ls.setWidgetResizable(True)
        ls.setStyleSheet("background:transparent;border:none;")
        lc = QWidget(); lc.setStyleSheet("background:transparent;")
        self._log_vl = QVBoxLayout(lc)
        self._log_vl.setContentsMargins(0,0,0,0)
        self._log_vl.setSpacing(5)
        self._log_vl.setAlignment(Qt.AlignTop)
        ls.setWidget(lc)
        vl.addWidget(ls, 1)

        for t,s in [
            ("k==<$_#~*$P(_|#.#M$","LOAD IT NEURAL"),
            ("*k?_f$____","PROC LOADED"),
            ("ff&#1_INIT","INIT COMPLETE"),
            ("We_Ji-G","LINK STABLE"),
            ("#_HfP","SYS ACTIVE"),
        ]:
            self._log_vl.addWidget(EphLog(t,s))

        ft = QLabel("ALIRA v2.0  •  Gemini 2.5")
        ft.setStyleSheet(
            f"color:rgba(0,100,30,0.45);font-size:8px;"
            f"font-family:'Courier New';"
            f"qproperty-alignment:AlignCenter;")
        vl.addWidget(ft)
        return sb

    # ════════════════════════════════════════════════════════
    #  CENTER
    # ════════════════════════════════════════════════════════
    def _mk_center(self):
        cw = QWidget()
        cw.setStyleSheet("background:transparent;border:none;")
        vl = QVBoxLayout(cw)
        vl.setContentsMargins(0,0,0,0); vl.setSpacing(0)

        vl.addStretch(2)

        self._orb = ALIRAOrb()
        vl.addWidget(self._orb, 0, Qt.AlignHCenter)

        vl.addSpacing(10)

        # ALIRA boxed label
        ALIRA_box = QFrame()
        ALIRA_box.setFixedWidth(200)
        ALIRA_box.setStyleSheet(
            f"background:rgba(0,0,0,0.55);"
            f"border:1px solid {GREEN_MID};"
            f"border-radius:3px;"
        )
        mbl = QHBoxLayout(ALIRA_box); mbl.setContentsMargins(0,5,0,5)
        ml = QLabel("M  A  Y  A")
        ml.setAlignment(Qt.AlignCenter)
        ml.setStyleSheet(
            f"color:{GREEN_MID};font-size:14px;font-weight:bold;"
            f"letter-spacing:8px;font-family:'Courier New';border:none;background:transparent;")
        mbl.addWidget(ml)
        vl.addWidget(ALIRA_box, 0, Qt.AlignHCenter)

        vl.addSpacing(8)

        # Status boxed
        self._status_box = QFrame()
        self._status_box.setStyleSheet(
            f"background:rgba(0,0,0,0.5);"
            f"border:1px solid {GREEN_DIM};"
            f"border-radius:3px;")
        sbl = QHBoxLayout(self._status_box); sbl.setContentsMargins(16,5,16,5)
        self._status_lbl = QLabel("● STANDBY")
        self._status_lbl.setAlignment(Qt.AlignCenter)
        self._status_lbl.setStyleSheet(
            f"color:{GREEN_MID};font-size:10px;font-weight:bold;"
            f"letter-spacing:3px;font-family:'Courier New';border:none;background:transparent;")
        sbl.addWidget(self._status_lbl)
        vl.addWidget(self._status_box, 0, Qt.AlignHCenter)

        vl.addStretch(2)

        # Bottom buttons
        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(20,0,20,18); btn_row.setSpacing(20)
        btn_row.addStretch()

        self._mute_btn = QPushButton()
        self._mute_btn.setFixedSize(128,58)
        self._mute_btn.clicked.connect(self._on_mute)
        self._set_mute_style(False)
        btn_row.addWidget(self._mute_btn)

        self._fix_btn = QPushButton()
        self._fix_btn.setFixedSize(128,58)
        self._fix_btn.clicked.connect(self._on_fix)
        self._set_fix_style(False)
        btn_row.addWidget(self._fix_btn)

        btn_row.addStretch()
        vl.addLayout(btn_row)
        return cw

    # ════════════════════════════════════════════════════════
    #  RIGHT PANEL
    # ════════════════════════════════════════════════════════
    def _mk_right(self):
        rp = QFrame()
        rp.setFixedWidth(278)
        rp.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "  stop:0 rgba(4,16,7,0.90), stop:1 rgba(2,10,4,0.99));"
            "border-left: 1px solid rgba(0,255,65,0.13);"
        )
        vl = QVBoxLayout(rp)
        vl.setContentsMargins(12,12,12,12); vl.setSpacing(8)
        vl.setAlignment(Qt.AlignTop)

        self._conn_frame = QFrame()
        self._conn_frame.setStyleSheet(
            "background:rgba(0,0,0,0.4);"
            "border:1px solid rgba(255,50,50,0.45);"
            "border-radius:3px;")
        cf = QVBoxLayout(self._conn_frame)
        cf.setContentsMargins(10,8,10,8); cf.setSpacing(4)
        lock_row = QHBoxLayout()
        self._lock_lbl = QLabel("🔒")
        self._lock_lbl.setStyleSheet("font-size:18px;border:none;background:transparent;")
        lock_row.addStretch(); lock_row.addWidget(self._lock_lbl); lock_row.addStretch()
        cf.addLayout(lock_row)
        self._conn_lbl = QLabel("NOT SECURE — DISCONNECTED")
        self._conn_lbl.setAlignment(Qt.AlignCenter)
        self._conn_lbl.setWordWrap(True)
        self._conn_lbl.setStyleSheet(
            "color:rgba(255,80,80,0.85);font-size:9px;"
            "letter-spacing:1px;font-family:'Courier New';border:none;background:transparent;")
        cf.addWidget(self._conn_lbl)
        self._conn_bar = QFrame(); self._conn_bar.setFixedHeight(2)
        self._conn_bar.setStyleSheet(
            "background:rgba(255,60,60,0.35);border-radius:1px;border:none;")
        cf.addWidget(self._conn_bar)
        vl.addWidget(self._conn_frame)

        fs_hdr = QLabel("FOCUS SUBJECT")
        fs_hdr.setStyleSheet(
            f"color:{GREEN_MID};font-size:10px;font-weight:bold;"
            f"letter-spacing:2px;font-family:'Courier New';")
        vl.addWidget(fs_hdr)

        self._focus_box = QFrame()
        self._focus_box.setStyleSheet(
            f"background:rgba(0,0,0,0.35);"
            f"border:1px solid {GREEN_DIM};"
            f"border-radius:3px;")
        fbl = QVBoxLayout(self._focus_box); fbl.setContentsMargins(8,8,8,8)
        self._focus_lbl = QLabel("IDLE — WAITING FOR INPUT")
        self._focus_lbl.setAlignment(Qt.AlignCenter)
        self._focus_lbl.setWordWrap(True)
        self._focus_lbl.setStyleSheet(
            f"color:{MUTED_G};font-size:9px;font-family:'Courier New';"
            f"letter-spacing:0.5px;border:none;background:transparent;")
        fbl.addWidget(self._focus_lbl)
        vl.addWidget(self._focus_box)

        self._proc_lbl = QLabel("PROCESSING CORE 03")
        self._proc_lbl.setAlignment(Qt.AlignRight)
        self._proc_lbl.setStyleSheet(
            "color:rgba(0,255,65,0.25);font-size:8px;"
            "font-family:'Courier New';letter-spacing:1px;")
        vl.addWidget(self._proc_lbl)

        vl.addWidget(self._divider())

        conv_hdr = QLabel("// CONVERSATION LOG")
        conv_hdr.setStyleSheet(
            "color:rgba(0,255,65,0.45);font-size:9px;"
            "letter-spacing:2px;font-family:'Courier New';")
        vl.addWidget(conv_hdr)

        # ── CHAT SCROLL AREA ──
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("background:transparent;border:none;")

        self._msg_cont = QWidget()
        self._msg_cont.setStyleSheet("background:transparent;border:none;")
        self._msg_vl = QVBoxLayout(self._msg_cont)
        self._msg_vl.setContentsMargins(2,4,2,4)
        self._msg_vl.setSpacing(8)
        self._msg_vl.setAlignment(Qt.AlignTop)
        self._scroll.setWidget(self._msg_cont)
        vl.addWidget(self._scroll, 1)

        # Live bar
        lt = QFrame(); lt.setFixedHeight(34)
        lt.setStyleSheet(
            "background:rgba(2,10,4,0.85);"
            "border-top:1px solid rgba(0,255,65,0.10);"
            "border-radius:0;")
        ll = QHBoxLayout(lt); ll.setContentsMargins(8,0,8,0); ll.setSpacing(6)
        self._live_lbl = QLabel("LIVE")
        self._live_lbl.setFixedWidth(34)
        self._live_lbl.setStyleSheet(
            "color:rgba(0,255,65,0.25);font-size:8px;letter-spacing:2px;"
            "font-family:'Courier New';background:transparent;border:none;")
        self._live_txt = QLabel("Initializing...")
        self._live_txt.setStyleSheet(
            "color:rgba(0,255,65,0.55);font-size:11px;font-style:italic;"
            "font-family:'Segoe UI';background:transparent;border:none;")
        ll.addWidget(self._live_lbl); ll.addWidget(self._live_txt, 1)
        vl.addWidget(lt)
        return rp

    # ── Helpers ──────────────────────────────────────────────
    def _divider(self):
        d = QFrame(); d.setFixedHeight(1)
        d.setStyleSheet("background:rgba(0,255,65,0.10);border:none;")
        return d

    def _add_log(self, text):
        labels = ["RUNTIME","NET.SIGNAL","CORE.MSG","PROC","SYS EVENT"]
        self._log_vl.insertWidget(0, EphLog(text[:18], random.choice(labels)))
        while self._log_vl.count() > 12:
            item = self._log_vl.takeAt(self._log_vl.count()-1)
            if item.widget(): item.widget().deleteLater()
        self._log_cnt.setText(f"{self._log_vl.count()}/12")

    # ── Chat ─────────────────────────────────────────────────
    def _add_bubble(self, who, text):
        if not text.strip(): return
        self._rm_typing()
        b = ChatBubble(who, text)
        self._msg_vl.addWidget(b)
        QTimer.singleShot(30, self._scroll_bot)
        if who in ("user","ALIRA"):
            self._msg_count += 1

    def _add_sys(self, t):  self._add_bubble("sys",  t)
    def _add_tool(self, t): self._add_bubble("tool", t)

    def _show_typing(self):
        if self._typing_w: return
        self._typing_w = TypingDots()
        self._msg_vl.addWidget(self._typing_w)
        QTimer.singleShot(30, self._scroll_bot)

    def _rm_typing(self):
        if self._typing_w:
            self._typing_w.stop()
            try: self._typing_w.setParent(None)
            except: pass
            self._typing_w = None

    def _scroll_bot(self):
        self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum())

    def _set_live(self, who, text):
        if who is None:
            self._live_lbl.setText("LIVE")
            self._live_lbl.setStyleSheet(
                "color:rgba(0,255,65,0.25);font-size:8px;letter-spacing:2px;"
                "font-family:'Courier New';background:transparent;border:none;")
            self._live_txt.setText("")
            return
        nm  = {"user":"YOU","ALIRA":"ALIRA"}.get(who,"LIVE")
        col = {"user":"rgba(0,255,65,0.60)","ALIRA":"rgba(0,255,100,0.85)"}.get(who,"rgba(0,255,65,0.3)")
        tc  = {"user":"#c8ffd4","ALIRA":"#80ffaa"}.get(who,"rgba(0,255,65,0.5)")
        self._live_lbl.setStyleSheet(
            f"color:{col};font-size:8px;letter-spacing:2px;"
            f"font-family:'Courier New';background:transparent;border:none;")
        self._live_lbl.setText(nm)
        self._live_txt.setStyleSheet(
            f"color:{tc};font-size:11px;font-style:italic;"
            f"font-family:'Segoe UI';background:transparent;border:none;")
        self._live_txt.setText((text+" ▌") if text else "")

    # ── Button styles ─────────────────────────────────────────
    def _set_mute_style(self, muted:bool):
        icon = "🔇" if muted else "🎤"
        txt  = f"{icon}\nMUTE {'OFF' if muted else 'ON'}"
        col  = "#ff4444" if muted else GREEN_MID
        self._mute_btn.setText(txt)
        self._mute_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,0,0,0.65);
                border: 2px solid {col};
                border-radius: 5px;
                color: {col};
                font-family: 'Courier New';
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
            QPushButton:hover   {{ background: rgba(0,255,65,0.10); }}
            QPushButton:pressed {{ background: rgba(0,255,65,0.18); }}
        """)

    def _set_fix_style(self, active:bool):
        col = AMBER if active else GREEN_MID
        self._fix_btn.setText("🔧\nFIX ERROR")
        self._fix_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(0,0,0,0.65);
                border: 2px solid {col};
                border-radius: 5px;
                color: {col};
                font-family: 'Courier New';
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 1px;
            }}
            QPushButton:hover   {{ background: rgba(0,255,65,0.10); }}
            QPushButton:pressed {{ background: rgba(0,255,65,0.18); }}
        """)

    # ── Button handlers ───────────────────────────────────────
    def _on_mute(self):
        self._muted  = not self._muted
        self._mic_on = not self._muted
        self._set_mute_style(self._muted)
        self._worker.set_mic(self._mic_on)
        self._add_sys("🎤 MIC " + ("MUTED" if self._muted else "ACTIVE"))
        self._add_log("MIC_TOGGLE")

    def _on_fix(self):
        self._set_fix_style(True)
        self._add_sys("⚡ RUNNING DIAGNOSTICS...")
        self._add_log("DIAG_STARTED")
        QTimer.singleShot(1500, self._fix_done)

    def _fix_done(self):
        self._set_fix_style(False)
        self._add_sys("✓  SYSTEM OK — No errors")
        self._add_log("DIAG_COMPLETE")

    # ── Signal handlers ───────────────────────────────────────
    def _on_status(self, state, label):
        col = {
            "standby":  GREEN_MID,
            "listening":"#ffff44",
            "thinking": AMBER,
            "speaking": CYAN_G,
        }.get(state, GREEN_MID)
        self._status_lbl.setText(f"● {label}")
        self._status_lbl.setStyleSheet(
            f"color:{col};font-size:10px;font-weight:bold;"
            f"letter-spacing:3px;font-family:'Courier New';border:none;background:transparent;")
        self._status_box.setStyleSheet(
            f"background:rgba(0,0,0,0.5);"
            f"border:1px solid {col};"
            f"border-radius:3px;")
        self._orb.set_state(state)
        focus = {
            "standby":  "IDLE — WAITING FOR INPUT",
            "listening":"AUDIO CAPTURE — ACTIVE",
            "thinking": "NEURAL PROCESSING...",
            "speaking": "AUDIO OUTPUT — ACTIVE",
        }.get(state,"")
        self._focus_lbl.setText(focus)
        self._focus_lbl.setStyleSheet(
            f"color:{col};font-size:9px;font-family:'Courier New';"
            f"letter-spacing:0.5px;border:none;background:transparent;")
        self._focus_box.setStyleSheet(
            f"background:rgba(0,0,0,0.35);"
            f"border:1px solid {col};"
            f"border-radius:3px;")
        if state == "thinking":     self._show_typing()
        elif state != "thinking":   self._rm_typing()

    def _on_energy(self, e:float):
        if self._mic_on:
            self._orb.set_energy(e)
            pct = min(95, int(24+e/80))
            self._neural_bar.set_value(pct, f"{pct}%")

    def _on_user_live(self, t):  self._set_live("user", t)
    def _on_ALIRA_live(self, t):  self._set_live("ALIRA", t)

    def _on_user_msg(self, t):
        self._add_bubble("user", t)
        self._set_live(None, "")
        self._add_log(t[:16])

    def _on_ALIRA_msg(self, t):
        self._add_bubble("ALIRA", t)
        self._set_live(None, "")

    def _on_sys_msg(self, t):     self._add_sys(t)
    def _on_tool_call(self, t):   self._add_tool(t); self._add_log(t[:16])
    def _on_tool_result(self, t): self._add_tool(t)

    def _on_connected(self, ok:bool):
        if ok:
            self._conn_frame.setStyleSheet(
                "background:rgba(0,0,0,0.4);"
                "border:1px solid rgba(0,255,65,0.45);"
                "border-radius:3px;")
            self._conn_lbl.setText("SECURE — CONNECTED")
            self._conn_lbl.setStyleSheet(
                "color:rgba(0,255,65,0.90);font-size:9px;"
                "letter-spacing:1px;font-family:'Courier New';"
                "border:none;background:transparent;")
            self._conn_bar.setStyleSheet(
                "background:rgba(0,255,65,0.50);border-radius:1px;border:none;")
            self._lock_lbl.setText("🔓")
            self._live_txt.setText("Connected! Ab bolo...")
        else:
            self._conn_frame.setStyleSheet(
                "background:rgba(0,0,0,0.4);"
                "border:1px solid rgba(255,50,50,0.45);"
                "border-radius:3px;")
            self._conn_lbl.setText("NOT SECURE — DISCONNECTED")
            self._conn_lbl.setStyleSheet(
                "color:rgba(255,80,80,0.85);font-size:9px;"
                "letter-spacing:1px;font-family:'Courier New';"
                "border:none;background:transparent;")
            self._conn_bar.setStyleSheet(
                "background:rgba(255,60,60,0.35);border-radius:1px;border:none;")
            self._lock_lbl.setText("🔒")
            self._live_txt.setText("Reconnecting...")

    def _on_suggestion(self, s:str):
        self._add_bubble("ALIRA", f"💡 {s}")

    # ── Worker ────────────────────────────────────────────────
    def _start_worker(self):
        init_advanced(api_key=_API_KEY, suggestion_cb=self._on_suggestion)
        self._worker = GeminiWorker()
        self._worker.sig_status.connect(self._on_status)
        self._worker.sig_user_live.connect(self._on_user_live)
        self._worker.sig_TITAN_live.connect(self._on_ALIRA_live)
        self._worker.sig_user_msg.connect(self._on_user_msg)
        self._worker.sig_TITAN_msg.connect(self._on_ALIRA_msg)
        self._worker.sig_sys_msg.connect(self._on_sys_msg)
        self._worker.sig_tool_call.connect(self._on_tool_call)
        self._worker.sig_tool_result.connect(self._on_tool_result)
        self._worker.sig_connected.connect(self._on_connected)
        self._worker.sig_energy.connect(self._on_energy)
        self._worker.start_thread()
        # Initial messages
        self._add_sys("⚡  ALIRA SYSTEM BOOT  //  CONNECTING...")
        self._add_bubble("ALIRA", "Namaste! Main ALIRA hoon. Bolo, main sun rahi hoon! 💚")

    def closeEvent(self, e):
        self._worker.stop()
        super().closeEvent(e)


# ════════════════════════════════════════════════════════════
#  GEMINI WORKER
# ════════════════════════════════════════════════════════════
class GeminiWorker(QObject):
    sig_status      = pyqtSignal(str, str)
    sig_user_live   = pyqtSignal(str)
    sig_TITAN_live   = pyqtSignal(str)
    sig_user_msg    = pyqtSignal(str)
    sig_TITAN_msg    = pyqtSignal(str)
    sig_sys_msg     = pyqtSignal(str)
    sig_tool_call   = pyqtSignal(str)
    sig_tool_result = pyqtSignal(str)
    sig_connected   = pyqtSignal(bool)
    sig_energy      = pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.mic_on  = True
        self.running = True
        self._q      = None
        self._retry  = 0

    def set_mic(self, on:bool): self.mic_on = on
    def stop(self):             self.running = False

    def start_thread(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._q = asyncio.Queue(maxsize=MAX_QUEUE)
        try:    loop.run_until_complete(self._main())
        finally: loop.close()

    async def _main(self):
        while self.running:
            try:
                await self._session()
                self._retry = 0
            except Exception as e:
                print(f"[ALIRA] {e}")
                self.sig_connected.emit(False)
                wait = min(2**self._retry, 30)
                self._retry += 1
                self.sig_status.emit("standby", f"RETRY {wait}s...")
                await asyncio.sleep(wait)

    async def _session(self):
        async with websockets.connect(
            f"{_WS_URL}?key={_API_KEY}",
            max_size=None, ping_interval=20,
            ping_timeout=30, close_timeout=10, compression=None,
        ) as ws:
            self.sig_connected.emit(True); self._retry=0
            await ws.send(_enc(_SETUP)); await ws.recv()
            self.sig_status.emit("standby","STANDBY")
            self.sig_sys_msg.emit("⚡  ALIRA ONLINE  //  READY")

            import queue as _queue
            _audio_q   = _queue.Queue()
            _play_stop = threading.Event()

            def _play_thread():
                BUF = int(SPK_RATE*0.20)
                buf = np.array([], dtype=np.float32)
                st  = sd.OutputStream(samplerate=SPK_RATE, channels=1,
                                      dtype="float32", blocksize=BUF, latency="high")
                st.start()
                while not _play_stop.is_set():
                    try:
                        chunk = _audio_q.get(timeout=0.15)
                        if chunk is None:
                            if len(buf)>0:
                                pad=BUF-(len(buf)%BUF)
                                if pad<BUF:
                                    buf=np.concatenate([buf,np.zeros(pad,dtype=np.float32)])
                                st.write(buf); buf=np.array([],dtype=np.float32)
                            continue
                        buf=np.concatenate([buf,chunk])
                        while len(buf)>=BUF:
                            st.write(buf[:BUF]); buf=buf[BUF:]
                    except _queue.Empty:
                        if len(buf)>0:
                            pad=BUF-len(buf)
                            st.write(np.concatenate([buf,np.zeros(pad,dtype=np.float32)]))
                            buf=np.array([],dtype=np.float32)
                st.stop(); st.close()

            pt = threading.Thread(target=_play_thread, daemon=True); pt.start()

            async def play():
                while self.running: await asyncio.sleep(0.5)

            async def send():
                with sd.InputStream(samplerate=MIC_RATE, channels=1,
                                    dtype="int16", blocksize=FRAMES, latency="low") as mic:
                    was_live=False; silent_frames=0; stream_ended=False
                    while self.running:
                        pcm,_=mic.read(FRAMES)
                        if not self.mic_on:
                            if was_live: was_live=False; silent_frames=0; stream_ended=False
                            await asyncio.sleep(0.02); continue
                        rms=float(np.sqrt(np.mean(pcm.astype(np.float32)**2)))
                        if was_live or rms>=SILENCE_RMS: self.sig_energy.emit(rms)
                        if rms<SILENCE_RMS:
                            silent_frames+=1
                            if was_live and silent_frames==SILENCE_FRAMES and not stream_ended:
                                was_live=False; stream_ended=True
                                self.sig_status.emit("thinking","THINKING")
                                try:
                                    await ws.send(_enc({"realtimeInput":{"audioStreamEnd":True}}))
                                except: break
                            await asyncio.sleep(0.001); continue
                        silent_frames=0; stream_ended=False
                        if not was_live:
                            was_live=True
                            self.sig_status.emit("listening","LISTENING")
                        try:
                            await ws.send(_enc({"realtimeInput":{"audio":{
                                "mimeType":"audio/pcm;rate=16000",
                                "data":base64.b64encode(pcm.tobytes()).decode()
                            }}}))
                        except: break
                        await asyncio.sleep(0.001)

            async def recv():
                abuf=""; ubuf=""; speaking=False
                while self.running:
                    try: raw=await ws.recv(); msg=json.loads(raw)
                    except websockets.exceptions.ConnectionClosed: break
                    except Exception as e: print(f"[Recv]{e}"); continue

                    for call in msg.get("toolCall",{}).get("functionCalls",[]):
                        name=call["name"]; args=call.get("args",{})
                        self.sig_tool_call.emit(f"⚙  {name}")
                        self.sig_status.emit("thinking","TOOL: "+name.upper()[:18])
                        try:    result=await dispatch(name,args)
                        except Exception as e: result=f"❌ {e}"
                        self.sig_tool_result.emit(f"✓  {name}: {str(result)[:100]}")
                        try:
                            await ws.send(_enc({"toolResponse":{"functionResponses":[{
                                "id":call["id"],"name":name,
                                "response":{"result":str(result)}
                            }]}}))
                        except: break

                    sc=msg.get("serverContent",{})
                    if not sc: continue

                    if sc.get("interrupted"):
                        self.sig_status.emit("listening","LISTENING")
                        abuf=""; speaking=False
                        while not _audio_q.empty():
                            try: _audio_q.get_nowait()
                            except: break

                    for part in sc.get("modelTurn",{}).get("parts",[]):
                        d=part.get("inlineData")
                        if d and d.get("mimeType","").startswith("audio/pcm"):
                            if not speaking:
                                speaking=True
                                self.sig_status.emit("speaking","SPEAKING")
                            raw2=base64.b64decode(d["data"])
                            chunk=np.frombuffer(raw2,dtype=np.int16).astype(np.float32)/32768.0
                            try: _audio_q.put_nowait(chunk)
                            except: pass

                    ot=sc.get("outputTranscript","")
                    if ot: abuf+=ot; self.sig_TITAN_live.emit(abuf)
                    it=sc.get("inputTranscript","")
                    if it: ubuf+=it; self.sig_user_live.emit(ubuf)

                    if sc.get("turnComplete") or sc.get("generationComplete"):
                        _audio_q.put(None)
                        if abuf.strip():
                            self.sig_TITAN_msg.emit(abuf.strip())
                            asyncio.create_task(memory_save("ALIRA",abuf.strip()))
                        abuf=""
                        if ubuf.strip():
                            self.sig_user_msg.emit(ubuf.strip())
                            asyncio.create_task(memory_save("user",ubuf.strip()))
                        ubuf=""; speaking=False
                        self.sig_status.emit("standby","STANDBY")
                        self.sig_TITAN_live.emit(""); self.sig_user_live.emit("")

            try:    await asyncio.gather(send(),recv(),play())
            finally: _play_stop.set(); _audio_q.put(None); pt.join(timeout=2.0)


# ════════════════════════════════════════════════════════════
#  ENTRY
# ════════════════════════════════════════════════════════════
if __name__=="__main__":
    import subprocess
    subprocess.Popen(['python', 'ALIRA_mini.py'])
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor(BG))
    pal.setColor(QPalette.WindowText,      QColor(TEXT_G))
    pal.setColor(QPalette.Base,            QColor(DARK_P))
    pal.setColor(QPalette.Text,            QColor(TEXT_G))
    pal.setColor(QPalette.Button,          QColor(DARK_P))
    pal.setColor(QPalette.ButtonText,      QColor(TEXT_G))
    pal.setColor(QPalette.Highlight,       QColor(GREEN_MID))
    pal.setColor(QPalette.HighlightedText, QColor("#000000"))
    app.setPalette(pal)
    win = ALIRAWindow()
    win.show()
    sys.exit(app.exec_())