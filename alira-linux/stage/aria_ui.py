# -*- coding: utf-8 -*-
"""
ALIRA UI widgets — TABBU.py se alag kiya gaya (sirf UI: orb, sidebar, chat,
top/bottom bars, dialogs). Logic/worker/main window TABBU.py mein hai.
"""

from ALIRA_slot import slot as _ALIRA_slot
import sys, os, json, math, random, time
from datetime import datetime
from pathlib import Path

import numpy as np
import sounddevice as sd

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QSizePolicy, QFileDialog,
    QDialog, QComboBox, QDialogButtonBox, QLineEdit, QStackedWidget,
    QListWidget, QListWidgetItem, QInputDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QObject, QRect, QSize, QThread, QEvent
from PyQt5.QtGui import (
    QColor, QPainter, QPen, QBrush, QLinearGradient,
    QRadialGradient, QPalette, QFont, QPixmap, QImage
)

try:
    from screen_share_module import ScreenShareButton
except ImportError:
    class ScreenShareButton(QPushButton):
        def __init__(self, p=None):
            super().__init__("🖥️  N/A", p)
            self.setFixedSize(112, 36)
        def set_sharing(self, on): pass

try:
    from TABBU_modules.TABBU_advanced_tools import (
        _tasks_load as _tm_tasks_load, _tasks_save as _tm_tasks_save,
        _parse_due as _tm_parse_due, _set_reminder as _tm_set_reminder,
    )
    _HAS_TASK_MANAGER = True
except ImportError:
    _HAS_TASK_MANAGER = False
    def _tm_tasks_load(): return []
    def _tm_tasks_save(tasks): pass
    def _tm_parse_due(text): return ""
    def _tm_set_reminder(title, due_iso): pass


# ══════════════════════════════════════════════════════════════════
# CENTER ORB ANIMATION
# ══════════════════════════════════════════════════════════════════
class GoalOrb(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = "idle"; self._t = 0.0; self._sparks = []; self._sc = 0
        self._energy = 0.0; self._rphase = [0.0, 1.0, 2.0]
        for _ in range(15): self._new_spark()
        QTimer(self, interval=20, timeout=self._tick).start()

    def set_state(self, s):
        if self.state != s:
            self.state = s
            for _ in range({"listening":35,"speaking":40,"thinking":20,"idle":8,
                            "error":12,"screenshare":25,"webforge":30}.get(s, 8)):
                self._new_spark()

    def set_energy(self, e): self._energy = min(1.0, e / 1400.0)

    @property
    def _colors(self):
        return {
            "idle":        (["#BB9900","#DDAA00","#997700"],               "#CC9900"),
            "listening":   (["#00D4FF","#0099FF","#40E0FF","#00BBFF"],     "#0099FF"),
            "speaking":    (["#FFD060","#FF9500","#FFA500","#FF6600"],     "#FF9500"),
            "thinking":    (["#AA55FF","#CC77FF","#8833CC","#BB44FF"],     "#9933CC"),
            "error":       (["#FF3333","#FF6666","#CC0000","#FF4444"],     "#CC0000"),
            "screenshare": (["#00FFCC","#00DDBB","#00EEDD","#00CCAA"],     "#00DDBB"),
            # ✅ NEW: WebForge state — green-gold (building)
            "webforge":    (["#44FF88","#00FF66","#AAFF44","#00DD55"],     "#22FF66"),
        }.get(self.state, (["#BB9900","#DDAA00","#997700"], "#CC9900"))

    def _new_spark(self):
        if len(self._sparks) >= 400: return
        cx = self.width()/2 or 400; cy = self.height()/2 or 300
        ang = random.uniform(0, 2*math.pi); orig = random.uniform(70, 140)
        spd = random.uniform(0.8, 5.0)
        vx = math.cos(ang)*spd + random.uniform(-0.8, 0.8)
        vy = math.sin(ang)*spd + random.uniform(-0.8, 0.8)
        cols, _ = self._colors
        self._sparks.append([cx + math.cos(ang)*orig, cy + math.sin(ang)*orig,
                              vx, vy, random.uniform(0.55, 1.0), random.uniform(1.5, 4.5),
                              random.choice(cols)])

    def _tick(self):
        self._t += 0.032
        self._rphase = [p + 0.048 + i*0.013 for i, p in enumerate(self._rphase)]
        self._sc += 1
        emit_every = {"speaking":1,"listening":2,"thinking":5,"idle":25,
                      "error":10,"screenshare":3,"webforge":2}.get(self.state, 25)
        count = {"speaking":6,"listening":5,"thinking":2,"idle":1,
                 "error":3,"screenshare":4,"webforge":5}.get(self.state, 1)
        if self._sc % emit_every == 0:
            for _ in range(count): self._new_spark()
            if self.state == "listening" and self._energy > 0.1:
                for _ in range(int(self._energy*6)): self._new_spark()
        self._sparks = [
            (lambda s: s if (s.__setitem__(4, s[4]-0.014) or True) and s[4] > 0 else None)(s)
            for s in [[s[0]+s[2],s[1]+s[3],s[2]*0.965,s[3]*0.965,s[4],s[5],s[6]] for s in self._sparks]
        ]
        self._sparks = [s for s in self._sparks if s is not None]
        self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        W = self.width(); H = self.height(); cx = W/2; cy = H/2
        ring_cols, core_col = self._colors
        p.fillRect(0, 0, W, H, QColor("#040810"))
        rng = random.Random(73)
        for _ in range(140):
            sx = rng.randint(0,W); sy = rng.randint(0,H)
            a  = rng.randint(15,110); sz = rng.choice([1,1,1,2])
            c  = QColor(255,255,255,a)
            p.setBrush(QBrush(c)); p.setPen(Qt.NoPen); p.drawEllipse(sx,sy,sz,sz)
        gr = QRadialGradient(cx,cy,200)
        c0 = QColor(core_col); c0.setAlpha(30)
        c1 = QColor(core_col); c1.setAlpha(0)
        gr.setColorAt(0,c0); gr.setColorAt(1,c1)
        p.setBrush(QBrush(gr)); p.setPen(Qt.NoPen)
        p.drawEllipse(int(cx-200),int(cy-200),400,400)
        for s in self._sparks:
            sx,sy,_,_,life,sz,col = s
            if life <= 0: continue
            alpha = min(1.0, life)
            gr2 = QRadialGradient(sx, sy, sz*4)
            cg = QColor(col); cg.setAlphaF(alpha*0.5)
            cg2 = QColor(col); cg2.setAlpha(0)
            gr2.setColorAt(0,cg); gr2.setColorAt(1,cg2)
            p.setBrush(QBrush(gr2)); p.setPen(Qt.NoPen)
            r4 = sz*4
            p.drawEllipse(int(sx-r4),int(sy-r4),int(r4*2),int(r4*2))
            cs = QColor(col); cs.setAlphaF(min(1.0,alpha*1.3))
            p.setBrush(QBrush(cs))
            p.drawEllipse(int(sx-sz/2),int(sy-sz/2),int(sz),int(sz))
        ring_radii = [98, 122, 144]
        for i, (base_r, phase) in enumerate(zip(ring_radii, self._rphase)):
            if self.state in ("speaking","listening","screenshare","webforge"):
                pulse = math.sin(phase)*(13 + self._energy*10)
            elif self.state == "thinking": pulse = math.sin(phase*0.5)*8
            else: pulse = math.sin(phase*0.25)*4
            r   = base_r + pulse
            col = ring_cols[i % len(ring_cols)]
            base_alpha = [230,170,110][i]
            if self.state == "idle": base_alpha = [60,40,25][i]
            for w_fac, a_fac in [(5.0,0.10),(3.0,0.22),(1.6,0.50),(0.7,1.0)]:
                c = QColor(col); c.setAlpha(int(base_alpha*a_fac))
                p.setPen(QPen(c, w_fac*2.2)); p.setBrush(Qt.NoBrush)
                p.drawEllipse(int(cx-r),int(cy-r),int(r*2),int(r*2))
        cr  = 65 + math.sin(self._t*0.9)*6
        cg3 = QRadialGradient(cx,cy,cr)
        ca  = QColor(core_col); ca.setAlpha(100)
        cb  = QColor(core_col); cb.setAlpha(35)
        cc  = QColor(core_col); cc.setAlpha(0)
        cg3.setColorAt(0,ca); cg3.setColorAt(0.55,cb); cg3.setColorAt(1,cc)
        p.setBrush(QBrush(cg3)); p.setPen(Qt.NoPen)
        p.drawEllipse(int(cx-cr),int(cy-cr),int(cr*2),int(cr*2))
        text_col = QColor(ring_cols[0])
        for sz_add, a in [(6,8),(4,14),(2,25)]:
            gf = QFont("TABBUl Black", 46+sz_add, QFont.Bold)
            p.setFont(gf)
            gc = QColor(ring_cols[0]); gc.setAlpha(a)
            p.setPen(gc)
            p.drawText(QRect(int(cx-160),int(cy-55),320,110), Qt.AlignCenter, "ALIRA")
        p.setFont(QFont("TABBUl Black", 50, QFont.Bold))
        p.setPen(text_col)
        p.drawText(QRect(int(cx-160),int(cy-55),320,110), Qt.AlignCenter, "ALIRA")
        p.end()


# ══════════════════════════════════════════════════════════════════
# LEFT SIDEBAR
# ══════════════════════════════════════════════════════════════════
class _ToolRow(QFrame):
    """Clickable sidebar row — plain QFrame+QLabel had no click handling at all."""
    clicked = pyqtSignal()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class LeftSidebar(QFrame):
    sig_tool_clicked = pyqtSignal(str)

    def __init__(self, has_webforge=False):
        super().__init__()
        self._has_webforge = has_webforge
        self.setFixedWidth(215)
        self.setStyleSheet("QFrame{background:#06101E;border-right:1px solid rgba(0,80,160,0.25);}")
        vl = QVBoxLayout(self); vl.setContentsMargins(0,0,0,0); vl.setSpacing(0)

        hdr = QWidget(); hdr.setFixedHeight(50)
        hdr.setStyleSheet("background:#07111F;border-bottom:1px solid rgba(0,80,160,0.20);")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(14,0,14,0); hl.setSpacing(10)
        gear = QLabel("⚙"); gear.setStyleSheet("color:#4477AA;font-size:20px;background:transparent;")
        t = QLabel("All Tools"); t.setStyleSheet("color:#99BBCC;font-size:15px;font-weight:bold;background:transparent;")
        hl.addWidget(gear); hl.addWidget(t); hl.addStretch()
        vl.addWidget(hdr)

        tools = [
            ("image_generator", "🔷","Image Generator","#2244BB","#4466FF"),
            ("text_generator",  "🔵","Text Generator", "#1155AA","#2277DD"),
            ("ALIRA_coder",      "⬡","ALIRA Coder",    "#004422","#00AA55"),
            ("translator",      "🟠","Translator",     "#AA4411","#FF6622"),
            ("data_analysis",   "🔴","Data Analysis",  "#AA1133","#DD2244"),
            ("task_manager",    "🔧","Task Manager",   "#442299","#6633CC"),
            ("webforge",        "🌐","WebForge AI",    "#004422","#00AA55"),   # ✅ NEW WebForge entry
            ("settings",        "⚙","Settings",       "#553311","#886622"),
        ]
        for key, icon, name, dark, light in tools:
            vl.addWidget(self._tool_row(key, icon, name, dark, light))
        vl.addStretch(1)

        # Mic level
        mic_hdr = QWidget(); mic_hdr.setFixedHeight(38)
        mic_hdr.setStyleSheet("background:#07111F;border-top:1px solid rgba(0,80,160,0.20);")
        mh = QHBoxLayout(mic_hdr); mh.setContentsMargins(12,0,12,0); mh.setSpacing(8)
        mh.addWidget(QLabel("🎤")); self._mic_level_lbl = QLabel("MIC: —")
        self._mic_level_lbl.setStyleSheet("color:#44FF88;font-size:10px;background:transparent;")
        mh.addWidget(self._mic_level_lbl); mh.addStretch()
        vl.addWidget(mic_hdr)

        # WebForge status  ✅ NEW
        wf_hdr = QWidget(); wf_hdr.setFixedHeight(38)
        wf_hdr.setStyleSheet("background:#07111F;border-top:1px solid rgba(0,80,160,0.15);")
        wh = QHBoxLayout(wf_hdr); wh.setContentsMargins(12,0,12,0); wh.setSpacing(8)
        wh.addWidget(QLabel("🌐"))
        self._wf_status_lbl = QLabel("WebForge: Ready" if self._has_webforge else "WebForge: N/A")
        _wf_color = "#00AA55" if self._has_webforge else "#553322"
        self._wf_status_lbl.setStyleSheet(f"color:{_wf_color};font-size:10px;background:transparent;")
        wh.addWidget(self._wf_status_lbl); wh.addStretch()
        vl.addWidget(wf_hdr)

        # Screen share status
        ss_hdr = QWidget(); ss_hdr.setFixedHeight(38)
        ss_hdr.setStyleSheet("background:#07111F;border-top:1px solid rgba(0,80,160,0.15);")
        sh = QHBoxLayout(ss_hdr); sh.setContentsMargins(12,0,12,0); sh.setSpacing(8)
        sh.addWidget(QLabel("🖥️"))
        self._ss_status_lbl = QLabel("Screen: OFF")
        self._ss_status_lbl.setStyleSheet("color:#334455;font-size:10px;background:transparent;")
        sh.addWidget(self._ss_status_lbl); sh.addStretch()
        vl.addWidget(ss_hdr)

        # Camera
        cam_hdr = QWidget(); cam_hdr.setFixedHeight(38)
        cam_hdr.setStyleSheet("background:#07111F;border-top:1px solid rgba(0,80,160,0.20);")
        ch = QHBoxLayout(cam_hdr); ch.setContentsMargins(12,0,12,0); ch.setSpacing(8)
        ch.addWidget(QLabel("🎥")); ch.addWidget(QLabel("Live Camera"))
        self._cam_status = QLabel("● ●")
        self._cam_status.setStyleSheet("color:#1C3344;font-size:13px;background:transparent;letter-spacing:3px;")
        ch.addStretch(); ch.addWidget(self._cam_status)
        vl.addWidget(cam_hdr)

        self._cam_lbl = QLabel(); self._cam_lbl.setFixedHeight(140)
        self._cam_lbl.setAlignment(Qt.AlignCenter)
        self._cam_lbl.setStyleSheet("background:#020810;color:#1C3344;font-size:22px;border-top:1px solid rgba(0,60,120,0.15);")
        self._cam_lbl.setText("📷")
        vl.addWidget(self._cam_lbl)

    def update_mic_level(self, rms):
        bars    = int(min(rms / 5, 10))
        bar_str = "█" * bars + "░" * (10 - bars)
        color   = "#FF4444" if rms > 60 else "#44FF88" if rms > 10 else "#555555"
        self._mic_level_lbl.setStyleSheet(f"color:{color};font-size:9px;background:transparent;font-family:monospace;")
        self._mic_level_lbl.setText(f"{bar_str} {int(rms)}")

    def update_screenshare_status(self, active: bool):
        if active:
            self._ss_status_lbl.setStyleSheet("color:#00DDBB;font-size:10px;background:transparent;font-weight:bold;")
            self._ss_status_lbl.setText("Screen: LIVE ●")
        else:
            self._ss_status_lbl.setStyleSheet("color:#334455;font-size:10px;background:transparent;")
            self._ss_status_lbl.setText("Screen: OFF")

    def update_webforge_status(self, building: bool, msg: str = ""):
        """✅ NEW: WebForge building status"""
        if building:
            self._wf_status_lbl.setStyleSheet("color:#44FF88;font-size:10px;background:transparent;font-weight:bold;")
            self._wf_status_lbl.setText(f"WebForge: {msg[:16] or 'Building...'}")
        else:
            self._wf_status_lbl.setStyleSheet("color:#00AA55;font-size:10px;background:transparent;")
            self._wf_status_lbl.setText("WebForge: Ready")

    def _tool_row(self, key, icon, name, dark, light):
        f = _ToolRow(); f.setFixedHeight(44); f.setCursor(Qt.PointingHandCursor)
        f.setStyleSheet(f"""QFrame{{background:transparent;border:none;border-left:3px solid transparent;}}
            QFrame:hover{{background:rgba(30,80,180,0.10);border-left:3px solid {light};}}""")
        hl = QHBoxLayout(f); hl.setContentsMargins(10,0,12,0); hl.setSpacing(10)
        ic = QLabel(icon); ic.setFixedSize(30,30); ic.setAlignment(Qt.AlignCenter)
        ic.setStyleSheet(f"background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 {dark},stop:1 {light});border-radius:7px;font-size:15px;")
        nm = QLabel(name); nm.setStyleSheet("color:#7799BB;font-size:12px;background:transparent;")
        hl.addWidget(ic); hl.addWidget(nm); hl.addStretch()
        f.clicked.connect(lambda k=key: self.sig_tool_clicked.emit(k))
        return f

    # ✅ FIX: sidebar ab apna alag camera capture nahi karta — CameraVisionManager
    # (Vision tab wala asli AI vision engine) ke signals se driven hai, taaki
    # sirf EK hi cv2.VideoCapture handle khule aur camera lock-conflict na ho.
    def update_camera_status(self, active: bool):
        if active:
            self._cam_status.setStyleSheet("color:#00BBFF;font-size:13px;background:transparent;letter-spacing:3px;")
        else:
            self._cam_status.setStyleSheet("color:#1C3344;font-size:13px;background:transparent;letter-spacing:3px;")
            self._cam_lbl.setText("📷")
            self._cam_lbl.setPixmap(QPixmap())
            self._cam_lbl.setStyleSheet("background:#020810;color:#1C3344;font-size:22px;border-top:1px solid rgba(0,60,120,0.15);")

    def update_camera_frame(self, img):
        self._cam_lbl.setText("")
        pix = QPixmap.fromImage(img)
        w = self._cam_lbl.width(); h = self._cam_lbl.height()
        pix = pix.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x = (pix.width()-w)//2; y = (pix.height()-h)//2
        self._cam_lbl.setPixmap(pix.copy(x,y,w,h))


# ══════════════════════════════════════════════════════════════════
# STATS WIDGET
# ══════════════════════════════════════════════════════════════════
class StatsWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("QFrame{background:rgba(7,14,30,0.98);border:1px solid rgba(20,70,150,0.30);border-radius:10px;}")
        layout = QVBoxLayout(self); layout.setContentsMargins(16,13,16,13); layout.setSpacing(10)
        wr = QHBoxLayout()
        wr.addWidget(self._lbl("Weather","#5577AA",13,True)); wr.addStretch()
        self._weather = self._lbl("26°C  Sunny ☀","#FFFFFF",13,True)
        wr.addWidget(self._weather); layout.addLayout(wr)
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background:rgba(255,255,255,0.07);max-height:1px;border:none;")
        layout.addWidget(sep)
        self._stat_lbls = {}
        for key, name, icon, col in [
            ("battery","Battery","🔋","#44FF88"),
            ("cpu",    "CPU",    "⬤","#4499FF"),
            ("ram",    "RAM",    "≡","#FFAA33"),
            ("time",   "Time",   "⏱","#DDDDDD"),
        ]:
            row = QHBoxLayout()
            row.addWidget(self._lbl(f"{icon}  {name}", col, 13, True, 95)); row.addStretch()
            v = self._lbl("—","#FFFFFF",15,True); v.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
            self._stat_lbls[key] = v; row.addWidget(v); layout.addLayout(row)
        QTimer(self, timeout=self._refresh, interval=2000).start()
        self._refresh()

    def _lbl(self, text, color, size, bold, w=None):
        l = QLabel(text); fw = "bold" if bold else "normal"
        l.setStyleSheet(f"color:{color};font-size:{size}px;font-weight:{fw};background:transparent;")
        if w: l.setFixedWidth(w)
        return l

    def _refresh(self):
        self._stat_lbls["time"].setText(datetime.now().strftime("%I:%M %p"))
        try:
            import psutil
            bat = psutil.sensors_battery()
            self._stat_lbls["battery"].setText(f"{int(bat.percent)}%" if bat else "78%")
            self._stat_lbls["cpu"].setText(f"{int(psutil.cpu_percent())}%")
            self._stat_lbls["ram"].setText(f"{int(psutil.virtual_memory().percent)}%")
        except:
            self._stat_lbls["battery"].setText("78%")
            self._stat_lbls["cpu"].setText("45%")
            self._stat_lbls["ram"].setText("62%")


# ══════════════════════════════════════════════════════════════════
# CHAT WIDGET
# ══════════════════════════════════════════════════════════════════
class ChatWidget(QFrame):
    def __init__(self):
        super().__init__()
        self.setObjectName("chatw")
        self.setStyleSheet("#chatw{background:rgba(14,12,18,0.92);border:1px solid rgba(255,255,255,0.08);border-radius:14px;}QLabel{border:none;}")
        vl = QVBoxLayout(self); vl.setContentsMargins(0,0,0,0); vl.setSpacing(0)
        hdr = QWidget(); hdr.setFixedHeight(48)
        hdr.setStyleSheet("background:rgba(20,16,24,0.99);border-radius:10px;border-bottom-left-radius:0;border-bottom-right-radius:0;border-bottom:1px solid rgba(255,255,255,0.08);")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(12,0,14,0); hl.setSpacing(10)
        ai_box = QWidget(); ai_box.setFixedSize(30,30)
        ai_box.setStyleSheet("background:qradialgradient(cx:0.4,cy:0.4,radius:0.8,stop:0 #FF2E43,stop:1 #8A1020);border-radius:15px;")
        ail = QHBoxLayout(ai_box); ail.setContentsMargins(0,0,0,0)
        ai_txt = QLabel("AI"); ai_txt.setAlignment(Qt.AlignCenter)
        ai_txt.setStyleSheet("color:white;font-size:9px;font-weight:bold;background:transparent;")
        ail.addWidget(ai_txt)
        hl.addWidget(ai_box); hl.addWidget(QLabel("ALIRA Assistant")); hl.addStretch(); hl.addWidget(QLabel("• • •"))
        vl.addWidget(hdr)
        usr_hdr = QWidget(); usr_hdr.setFixedHeight(34)
        usr_hdr.setStyleSheet("background:rgba(16,13,20,0.99);border-bottom:1px solid rgba(255,255,255,0.05);")
        ul = QHBoxLayout(usr_hdr); ul.setContentsMargins(14,0,14,0); ul.setSpacing(8)
        ul.addWidget(QLabel("●")); ul.addSpacing(4); ul.addWidget(QLabel("User")); ul.addStretch()
        vl.addWidget(usr_hdr)
        self._scroll = QScrollArea(); self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("background:transparent;border:none;")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.verticalScrollBar().setStyleSheet(
            "QScrollBar:vertical{background:transparent;width:4px;}"
            "QScrollBar::handle:vertical{background:rgba(255,255,255,0.12);border-radius:2px;min-height:20px;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")
        self._mw = QWidget(); self._mw.setStyleSheet("background:transparent;")
        self._ml = QVBoxLayout(self._mw); self._ml.setContentsMargins(10,10,10,10)
        self._ml.setSpacing(10); self._ml.setAlignment(Qt.AlignTop)
        self._scroll.setWidget(self._mw); vl.addWidget(self._scroll, 1)
        self._live_u = None; self._live_a = None

    def _user_lbl(self, txt):
        l = QLabel(txt); l.setWordWrap(True); l.setMaximumWidth(520)
        l.setTextInteractionFlags(Qt.TextSelectableByMouse)
        l.setStyleSheet("background:rgba(60,22,30,0.92);border:1px solid rgba(255,46,67,0.40);border-radius:10px;border-bottom-right-radius:3px;padding:8px 12px;color:#F4E8EA;font-size:14px;")
        row = QHBoxLayout(); row.setContentsMargins(0,0,0,0)
        row.addStretch(); row.addWidget(l)
        c = QWidget(); c.setStyleSheet("background:transparent;"); c.setLayout(row)
        self._ml.addWidget(c); QTimer.singleShot(20, self._bot); return l

    def _TABBU_row(self, txt):
        hrow = QHBoxLayout(); hrow.setContentsMargins(0,0,0,2); hrow.setSpacing(6)
        ic = QLabel("AI"); ic.setFixedSize(22,22); ic.setAlignment(Qt.AlignCenter)
        ic.setStyleSheet("background:qradialgradient(cx:0.4,cy:0.4,radius:0.8,stop:0 #FF2E43,stop:1 #8A1020);border-radius:11px;color:white;font-size:8px;font-weight:bold;")
        nm = QLabel("ALIRA"); nm.setStyleSheet("color:#9C99A4;font-size:10px;background:transparent;")
        hrow.addWidget(ic); hrow.addWidget(nm); hrow.addStretch()
        l = QLabel(txt); l.setWordWrap(True); l.setMaximumWidth(560)
        l.setTextInteractionFlags(Qt.TextSelectableByMouse)
        l.setStyleSheet("background:transparent;border:none;padding:3px 2px;color:#F4F3F6;font-size:14px;line-height:160%;")
        cw = QWidget(); cw.setStyleSheet("background:transparent;")
        cv = QVBoxLayout(cw); cv.setContentsMargins(0,0,0,0); cv.setSpacing(2)
        cv.addLayout(hrow); cv.addWidget(l)
        self._ml.addWidget(cw); QTimer.singleShot(20, self._bot); return l

    def _sys_lbl(self, txt, color="#FFFFFF22"):
        l = QLabel(txt); l.setAlignment(Qt.AlignCenter)
        l.setStyleSheet(f"color:{color};font-size:10px;background:transparent;padding:2px;")
        self._ml.addWidget(l); QTimer.singleShot(20, self._bot)

    def add_error(self, txt):          self._sys_lbl(f"⚠️  {txt}", "#FF4444CC")
    def add_warning(self, txt):        self._sys_lbl(f"⚡ {txt}", "#FFAA33CC")
    def add_sys(self, t):              self._sys_lbl(t)

    def add_screen_share_badge(self, active: bool):
        if active:
            self._sys_lbl("🖥️  Screen sharing STARTED — ALIRA ab tumhari screen dekh sakti hai", "#00DDBBCC")
        else:
            self._sys_lbl("🖥️  Screen sharing STOPPED", "#336655CC")

    def add_webforge_badge(self, msg: str, success: bool = True):
        """✅ NEW: WebForge status badge in chat"""
        color = "#44FF88CC" if success else "#FF4444CC"
        self._sys_lbl(f"🌐 {msg}", color)

    def update_live_user(self, t):
        if not t.strip(): self._live_u = None; return
        if not self._live_u: self._live_u = self._user_lbl(t)
        else: self._live_u.setText(t); QTimer.singleShot(10, self._bot)

    def update_live_TABBU(self, t):
        if not t.strip(): self._live_a = None; return
        if not self._live_a: self._live_a = self._TABBU_row(t)
        else: self._live_a.setText(t); QTimer.singleShot(10, self._bot)

    def finalize_user(self, t):
        if self._live_u: self._live_u.setText(t); self._live_u = None
        else: self._user_lbl(t)

    def finalize_TABBU(self, t):
        if self._live_a: self._live_a.setText(t); self._live_a = None
        else: self._TABBU_row(t)

    def _bot(self):
        sb = self._scroll.verticalScrollBar(); sb.setValue(sb.maximum())


# ══════════════════════════════════════════════════════════════════
# BOTTOM CONTROLS
# ══════════════════════════════════════════════════════════════════
class BottomControls(QWidget):
    sig_mute        = pyqtSignal()
    sig_speak       = pyqtSignal()
    sig_camera      = pyqtSignal()
    sig_voice       = pyqtSignal()
    sig_screenshare = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setFixedHeight(82); self.setStyleSheet("background:transparent;")
        vl = QVBoxLayout(self); vl.setContentsMargins(0,6,0,5); vl.setSpacing(6)

        r1 = QHBoxLayout(); r1.setAlignment(Qt.AlignCenter); r1.setSpacing(0)
        self.mute_btn   = self._btn("🔇  Mute",  "#9A0E1E","#CC1128","#EE2233",100,36)
        self.speak_btn  = self._btn("🎤  Speak", "#0E2299","#1133AA","#2255CC",100,36)
        self.screen_btn = ScreenShareButton()

        r1.addWidget(QLabel("——→")); r1.addSpacing(6)
        r1.addWidget(self.mute_btn); r1.addSpacing(10)
        r1.addWidget(self.screen_btn); r1.addSpacing(10)
        r1.addWidget(self.speak_btn)
        r1.addSpacing(6); r1.addWidget(QLabel("←——"))
        vl.addLayout(r1)

        r2 = QHBoxLayout(); r2.setAlignment(Qt.AlignCenter); r2.setSpacing(15)
        self.cam_btn   = self._btn("🎥  Camera On/Off","#131320","#1C1C35","#252545",130,28)
        self.voice_btn = self._btn("Voice: Female",    "#4A0E4A","#6A116A","#8A138A",110,28)
        r2.addWidget(self.cam_btn); r2.addWidget(self.voice_btn)
        vl.addLayout(r2)

        self.mute_btn.clicked.connect(_ALIRA_slot(self.sig_mute))
        self.speak_btn.clicked.connect(_ALIRA_slot(self.sig_speak))
        self.cam_btn.clicked.connect(_ALIRA_slot(self.sig_camera))
        self.voice_btn.clicked.connect(_ALIRA_slot(self.sig_voice))
        self.screen_btn.clicked.connect(_ALIRA_slot(self.sig_screenshare))

    @staticmethod
    def _btn(text, s1, s2, s3, w, h):
        b = QPushButton(text); b.setFixedSize(w,h); b.setCursor(Qt.PointingHandCursor)
        r = h//2
        b.setStyleSheet(f"""
            QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {s1},stop:0.5 {s2},stop:1 {s3});
            border:1px solid rgba(255,255,255,0.18);border-radius:{r}px;
            color:#FFFFFF;font-size:{'11' if h>32 else '9'}px;font-weight:bold;letter-spacing:0.5px;}}
            QPushButton:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {s3},stop:0.5 {s2},stop:1 {s1});
            border:1px solid rgba(255,255,255,0.35);}}
            QPushButton:pressed{{background:{s1};border:1px solid rgba(255,255,255,0.10);}}""")
        return b


# ══════════════════════════════════════════════════════════════════
# TOP STATUS BAR
# ══════════════════════════════════════════════════════════════════
class TopBar(QWidget):
    sig_mode       = pyqtSignal()
    sig_mic_select = pyqtSignal()
    sig_api_change = pyqtSignal()
    sig_model      = pyqtSignal()

    def __init__(self, live_model_key="3.1"):
        super().__init__()
        self.setFixedHeight(40)
        self.setStyleSheet("background:rgba(4,8,18,0.98);border-bottom:1px solid rgba(0,70,140,0.22);")
        hl = QHBoxLayout(self); hl.setContentsMargins(18,0,18,0); hl.setSpacing(10)
        self._status = QLabel("● STANDBY")
        self._status.setStyleSheet("color:#2A6644;font-family:'Courier New';font-size:11px;font-weight:bold;background:transparent;letter-spacing:1.5px;")
        self._mode_btn = QPushButton("🌸 ALIRA MODE")
        self._mode_btn.setFixedSize(128,26); self._mode_btn.setCursor(Qt.PointingHandCursor)
        self._mode_btn.setStyleSheet("""QPushButton{background:rgba(160,40,70,0.16);border:1px solid rgba(200,60,90,0.40);
            border-radius:13px;color:#FF7799;font-size:9px;font-weight:bold;letter-spacing:1px;}
            QPushButton:hover{background:rgba(160,40,70,0.28);}""")
        self._mode_btn.clicked.connect(_ALIRA_slot(self.sig_mode))
        self._mic_sel_btn = QPushButton("🎙 MIC")
        self._mic_sel_btn.setFixedSize(72,26); self._mic_sel_btn.setCursor(Qt.PointingHandCursor)
        self._mic_sel_btn.setStyleSheet("""QPushButton{background:rgba(0,120,80,0.15);border:1px solid rgba(0,180,100,0.35);
            border-radius:13px;color:#44FF88;font-size:9px;font-weight:bold;letter-spacing:1px;}
            QPushButton:hover{background:rgba(0,120,80,0.28);}""")
        self._mic_sel_btn.clicked.connect(_ALIRA_slot(self.sig_mic_select))
        self._api_btn = QPushButton("🔑 API")
        self._api_btn.setFixedSize(72,26); self._api_btn.setCursor(Qt.PointingHandCursor)
        self._api_btn.setStyleSheet("""QPushButton{background:rgba(180,100,0,0.15);border:1px solid rgba(220,150,20,0.35);
            border-radius:13px;color:#FFCC55;font-size:9px;font-weight:bold;letter-spacing:1px;}
            QPushButton:hover{background:rgba(180,100,0,0.28);}""")
        self._api_btn.clicked.connect(_ALIRA_slot(self.sig_api_change))
        self._model_btn = QPushButton()
        self._model_btn.setFixedSize(92,26); self._model_btn.setCursor(Qt.PointingHandCursor)
        self._model_btn.setToolTip("Voice model switch karo (Gemini Live 3.1 ↔ 3.8)")
        self._model_btn.setStyleSheet("""QPushButton{background:rgba(90,60,200,0.16);border:1px solid rgba(140,110,255,0.40);
            border-radius:13px;color:#B9A6FF;font-size:9px;font-weight:bold;letter-spacing:1px;}
            QPushButton:hover{background:rgba(90,60,200,0.30);}""")
        self._model_btn.clicked.connect(_ALIRA_slot(self.sig_model))
        self.set_model_label(live_model_key)
        hl.addWidget(self._status); hl.addStretch()
        hl.addWidget(self._model_btn); hl.addWidget(self._mic_sel_btn); hl.addWidget(self._api_btn); hl.addWidget(self._mode_btn)

    def set_model_label(self, key):
        self._model_btn.setText(f"⚡ LIVE {key}")

    def set_status(self, state, label):
        c = {"standby":"#2A6644","listening":"#0077CC","thinking":"#8833BB","speaking":"#BB7700",
             "error":"#CC2222","screenshare":"#00BBAA","webforge":"#22CC66"}.get(state,"#2A6644")
        d = {"standby":"●","listening":"◉","thinking":"◎","speaking":"◉",
             "error":"✖","screenshare":"▣","webforge":"⬡"}.get(state,"●")
        self._status.setText(f"{d} {label}")
        self._status.setStyleSheet(f"color:{c};font-family:'Courier New';font-size:11px;font-weight:bold;background:transparent;letter-spacing:1.5px;")


# ══════════════════════════════════════════════════════════════════
# MIC SELECTION DIALOG
# ══════════════════════════════════════════════════════════════════
class MicSelectDialog(QDialog):
    sig_devices_set = pyqtSignal(int, int)

    def __init__(self, parent=None, mic_device=None, spk_device=None, silence_rms=35, mic_gain=2.5):
        super().__init__(parent)
        self._mic_device = mic_device; self._spk_device = spk_device
        self._silence_rms = silence_rms; self._mic_gain = mic_gain
        self.setWindowTitle("Select Audio Devices")
        self.setFixedWidth(420)
        self.setStyleSheet("""
            QDialog{background:#040810;color:#CCDDEE;border:1px solid rgba(0,80,160,0.3);}
            QLabel{color:#88AABB;font-weight:bold;margin-top:10px;}
            QComboBox{background:#061224;border:1px solid rgba(0,100,200,0.3);color:#FFFFFF;
            padding:5px;border-radius:5px;min-height:24px;}
            QPushButton{background:#0A2440;border:1px solid #1A4470;color:#CCDDEE;
            padding:6px 15px;border-radius:4px;min-width:80px;}
            QPushButton:hover{background:#12365C;border-color:#2466AA;}""")
        vl = QVBoxLayout(self); vl.setContentsMargins(20,20,20,20); vl.setSpacing(10)
        info = QLabel(f"Mic Sensitivity: RMS threshold = {self._silence_rms}\nGain = {self._mic_gain}x amplification")
        info.setStyleSheet("color:#44FF88;font-size:10px;background:rgba(0,40,0,0.3);padding:8px;border-radius:4px;")
        info.setWordWrap(True); vl.addWidget(info)
        vl.addWidget(QLabel("🎤 Microphone Input:"))
        self.mic_combo = QComboBox(); vl.addWidget(self.mic_combo)
        vl.addWidget(QLabel("🔊 Speaker Output:"))
        self.spk_combo = QComboBox(); vl.addWidget(self.spk_combo)
        self._populate()
        vl.addSpacing(15)
        btns = QHBoxLayout()
        ok = QPushButton("Confirm"); can = QPushButton("Cancel")
        ok.clicked.connect(_ALIRA_slot(self.accept)); can.clicked.connect(_ALIRA_slot(self.reject))
        btns.addStretch(); btns.addWidget(can); btns.addWidget(ok)
        vl.addLayout(btns)

    def _populate(self):
        devices = sd.query_devices()
        def_mic = sd.default.device[0]; def_spk = sd.default.device[1]
        curr_mic = self._mic_device if self._mic_device is not None else def_mic
        curr_spk = self._spk_device if self._spk_device is not None else def_spk
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0:
                self.mic_combo.addItem(f"[{i}] {d['name']}", i)
                if i == curr_mic: self.mic_combo.setCurrentIndex(self.mic_combo.count()-1)
            if d["max_output_channels"] > 0:
                self.spk_combo.addItem(f"[{i}] {d['name']}", i)
                if i == curr_spk: self.spk_combo.setCurrentIndex(self.spk_combo.count()-1)

    def accept(self):
        self.sig_devices_set.emit(self.mic_combo.currentData(), self.spk_combo.currentData())
        super().accept()


class ApiKeySetupDialog(QDialog):
    def __init__(self, parent=None, current_api_key=""):
        super().__init__(parent)
        self.setWindowTitle("ALIRA API Key Setup")
        self.setFixedSize(450, 220)
        self.setStyleSheet("""
            QDialog { background: #050810; }
            QLabel { color: #e8eaf6; background: transparent; }
            QLineEdit {
                background: #0d1525; color: #e8eaf6;
                border: 1px solid #e8406a; border-radius: 5px; padding: 5px;
            }
            QPushButton {
                background: #e8406a; color: white; border: none;
                border-radius: 5px; padding: 8px; font-weight: bold;
            }
            QPushButton:hover { background: #ff5580; }
        """)
        self._api_key = current_api_key
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout()
        title  = QLabel("Enter Gemini API Key")
        title.setStyleSheet("color: #e8eaf6; font-size: 14px; font-weight: bold;")
        layout.addWidget(title)
        desc = QLabel("Get your API key from: https://ai.google.dev/")
        desc.setStyleSheet("color: #7799bb; font-size: 11px;")
        layout.addWidget(desc)
        status_text = "Current key loaded" if self._api_key else "No API key configured yet"
        status = QLabel(status_text)
        status.setStyleSheet("color: #99bbdd; font-size: 11px; margin-bottom: 8px;")
        layout.addWidget(status)
        self._key_input = QLineEdit()
        self._key_input.setPlaceholderText("Paste your Gemini API key here...")
        self._key_input.setEchoMode(QLineEdit.Password)
        layout.addWidget(self._key_input)
        button_layout = QHBoxLayout(); button_layout.addStretch()
        ok_btn = QPushButton("OK"); cancel_btn = QPushButton("Cancel")
        ok_btn.setFixedWidth(100); cancel_btn.setFixedWidth(100)
        ok_btn.clicked.connect(_ALIRA_slot(self.accept)); cancel_btn.clicked.connect(_ALIRA_slot(self.reject))
        button_layout.addWidget(ok_btn); button_layout.addWidget(cancel_btn)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def get_api_key(self):
        return self._key_input.text().strip()


# ══════════════════════════════════════════════════════════════════
# TASK MANAGER — sidebar "Task Manager" page
# ══════════════════════════════════════════════════════════════════
class TaskManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ALIRA — Task Manager")
        self.setMinimumSize(480, 440)
        self.setStyleSheet("""
            QDialog { background: #050810; }
            QLabel { color: #e8eaf6; background: transparent; }
            QLineEdit {
                background: #0d1525; color: #e8eaf6;
                border: 1px solid #2244BB; border-radius: 5px; padding: 6px;
            }
            QPushButton {
                background: #2244BB; color: white; border: none;
                border-radius: 5px; padding: 8px 14px; font-weight: bold;
            }
            QPushButton:hover { background: #3355DD; }
            QListWidget {
                background: #0a0f1e; color: #CCDDF0; border: 1px solid #1a2440;
                border-radius: 6px; padding: 4px;
            }
            QListWidget::item { padding: 6px; border-bottom: 1px solid #101830; }
            QListWidget::item:selected { background: #1a2c66; }
        """)
        self._setup_ui()
        self._reload()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("🔧 Task Manager")
        title.setStyleSheet("color: #e8eaf6; font-size: 16px; font-weight: bold; background: transparent;")
        layout.addWidget(title)

        row = QHBoxLayout()
        self._title_input = QLineEdit()
        self._title_input.setPlaceholderText("Task title...")
        self._due_input = QLineEdit()
        self._due_input.setPlaceholderText("Due — optional (e.g. 'kal 5 baje')")
        add_btn = QPushButton("+ Add")
        add_btn.clicked.connect(_ALIRA_slot(self._add_task))
        self._title_input.returnPressed.connect(_ALIRA_slot(self._add_task))
        row.addWidget(self._title_input, 2)
        row.addWidget(self._due_input, 1)
        row.addWidget(add_btn)
        layout.addLayout(row)

        self._list = QListWidget()
        layout.addWidget(self._list, 1)

        btn_row = QHBoxLayout()
        done_btn = QPushButton("✓ Mark Done")
        done_btn.clicked.connect(_ALIRA_slot(self._mark_done))
        del_btn = QPushButton("🗑 Delete")
        del_btn.setStyleSheet("QPushButton{background:#992222;} QPushButton:hover{background:#BB3333;}")
        del_btn.clicked.connect(_ALIRA_slot(self._delete_task))
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(_ALIRA_slot(self.accept))
        btn_row.addWidget(done_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch()
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        if not _HAS_TASK_MANAGER:
            warn = QLabel("⚠ TABBU_modules not available — tasks won't persist reminders.")
            warn.setStyleSheet("color:#FFAA55;font-size:11px;background:transparent;")
            layout.addWidget(warn)

    def _reload(self):
        self._list.clear()
        for t in _tm_tasks_load():
            status = "✅" if t.get("status") == "done" else "⏳"
            due = t.get("due", "")
            due_str = f"  (due: {due[:16].replace('T', ' ')})" if due else ""
            item = QListWidgetItem(f"{status} {t.get('title', '')}{due_str}")
            item.setData(Qt.UserRole, t.get("id"))
            self._list.addItem(item)

    def _add_task(self):
        title = self._title_input.text().strip()
        if not title:
            return
        import hashlib, time
        due_text = self._due_input.text().strip()
        due_iso = _tm_parse_due(due_text) if due_text else ""
        tid = hashlib.md5(f"{title}{time.time()}".encode()).hexdigest()[:8]
        task = {
            "id": tid, "title": title, "description": "", "due": due_iso,
            "priority": "normal", "status": "pending", "platform": "local",
            "created_at": datetime.now().isoformat(),
        }
        tasks = _tm_tasks_load()
        tasks.append(task)
        _tm_tasks_save(tasks)
        if due_iso:
            _tm_set_reminder(title, due_iso)
        self._title_input.clear()
        self._due_input.clear()
        self._reload()

    def _selected_task_id(self):
        item = self._list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _mark_done(self):
        tid = self._selected_task_id()
        if not tid:
            return
        tasks = _tm_tasks_load()
        for t in tasks:
            if t.get("id") == tid:
                t["status"] = "done"
        _tm_tasks_save(tasks)
        self._reload()

    def _delete_task(self):
        tid = self._selected_task_id()
        if not tid:
            return
        tasks = [t for t in _tm_tasks_load() if t.get("id") != tid]
        _tm_tasks_save(tasks)
        self._reload()
