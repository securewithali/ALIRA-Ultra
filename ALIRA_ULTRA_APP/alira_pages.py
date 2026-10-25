# -*- coding: utf-8 -*-
"""
ALIRA pages — sidebar ke har feature ka alag, kaam karne wala page.
Har page PageBase (ALIRA_ui) se banta hai => left mein girl, right mein content.
Pages ek `Bus` ke through window (TABBU.py) se baat karte hain.
"""

from alira_slot import slot as _ALIRA_slot
import os, time, hashlib, collections, threading
from datetime import datetime
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, QLineEdit, QSlider,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem, QFileDialog, QInputDialog, QMessageBox,
    QCheckBox, QSizePolicy, QHeaderView, QBoxLayout, QComboBox, QCompleter,
)
from PyQt5.QtCore import Qt, QObject, QTimer, QSize, QRectF, QPointF, pyqtSignal
from PyQt5.QtGui import QIcon, QColor, QPainter, QPen, QBrush, QPixmap, QLinearGradient, QPainterPath, QFont

from alira_ui import (
    T, F, svg_pixmap, svg_icon, make_card, pill, Segmented, SLIDER_CSS, PageBase, Orb, ModeBar, css3d, lift, ASSETS,
)
import alira_actions as act
from tabbu_ui import _tm_tasks_load, _tm_tasks_save, _tm_parse_due, _tm_set_reminder, _HAS_TASK_MANAGER

INPUT_CSS = (f"QLineEdit{{background:rgba(255,255,255,0.05);color:#fff;border:1px solid rgba(255,255,255,0.14);"
             f"border-radius:10px;padding:8px 12px;{F(400,14)}selection-background-color:{T['red']};}}"
             f"QLineEdit:focus{{border:1px solid {T['red']};}}")
LIST_CSS = (f"QListWidget,QTreeWidget{{background:rgba(255,255,255,0.03);color:#EDEBF0;border:1px solid rgba(255,255,255,0.08);"
            f"border-radius:10px;{F(400,14)}outline:0;}}"
            f"QListWidget::item,QTreeWidget::item{{padding:6px 8px;border-radius:6px;}}"
            f"QListWidget::item:selected,QTreeWidget::item:selected{{background:rgba(255,46,67,0.28);color:#fff;}}"
            f"QListWidget::item:hover,QTreeWidget::item:hover{{background:rgba(255,255,255,0.06);}}"
            f"QHeaderView::section{{background:rgba(255,255,255,0.05);color:{T['muted']};border:none;padding:6px 8px;{F(600,12)}}}"
            f"QScrollBar:vertical{{background:transparent;width:8px;}}QScrollBar::handle:vertical{{background:rgba(255,255,255,0.18);border-radius:4px;}}"
            f"QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{{height:0;}}")


class _Bridge(QObject):
    done = pyqtSignal(object)

from concurrent.futures import ThreadPoolExecutor
_FAST_EXEC = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ALIRA-fast")   # disk listing jaise halke kaam (COM wale slow thread se alag)

def run_async(fn, cb, owner, fast=False):
    """fn background worker thread par chalao, cb(result) GUI thread par bulao. UI kabhi block nahi hota.
    fast=True: alag halka pool (volume/brightness wale slow thread ki queue me intezaar nahi)."""
    br = _Bridge(owner); br.done.connect(cb)
    def job():
        try: res = fn()
        except Exception as e: res = e
        br.done.emit(res)
    (_FAST_EXEC if fast else act._EXEC).submit(job)


class Bus(QObject):
    """Pages <-> window (TABBU.py) ka sandesh-vahak."""
    prompt = pyqtSignal(str); goto = pyqtSignal(str); listen_mode = pyqtSignal(str)
    voice_toggle = pyqtSignal(); model_pick = pyqtSignal(str); mic_select = pyqtSignal(); api_change = pyqtSignal()
    persona_toggle = pyqtSignal(); camera_toggle = pyqtSignal(); screenshare_toggle = pyqtSignal()
    coder = pyqtSignal(); webforge = pyqtSignal(); fullscreen = pyqtSignal(); always_on_top = pyqtSignal(bool)
    toast = pyqtSignal(str); sens_changed = pyqtSignal(int, float); state_changed = pyqtSignal()
    deploy_site = pyqtSignal(str)
    edge_glow = pyqtSignal(bool)
    user_name = pyqtSignal(str)
    language = pyqtSignal(str)
    orb_on_minimize = pyqtSignal(bool); orb_float_size = pyqtSignal(int); orb_ui_scale = pyqtSignal(int)
    autostart = pyqtSignal(bool); guardian = pyqtSignal(bool); guardian_interval = pyqtSignal(int); orb_preview = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.state = {"mic_on": True, "listen_mode": "continuous", "voice": "female", "model_key": "3.1",
                      "models": [], "persona": "ALIRA", "cam_on": False, "screen_on": False,
                      "session": {}, "rms": 35, "gain": 2.5}


def _label(text, color=None, size=14, bold=False):
    l = QLabel(text); l.setStyleSheet(f"color:{color or T['muted']};{F(700 if bold else 400, size)}"); l.setWordWrap(True); return l


class RadioList(QWidget):
    changed = pyqtSignal(str)
    def __init__(self, options, current=None):
        super().__init__(); self._b = {}
        vl = QVBoxLayout(self); vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(6)
        for key, label in options:
            b = QPushButton(label); b.setCursor(Qt.PointingHandCursor); b.setFixedHeight(38)
            b.clicked.connect(lambda _=False, k=key: self.changed.emit(k)); self._b[key] = b; vl.addWidget(b)
        self.set_current(current)
    def set_current(self, cur):
        for k, b in self._b.items():
            on = k == cur; b.setText(("●  " if on else "○  ") + b.text().lstrip("●○ "))
            b.setStyleSheet(css3d("QPushButton", "active" if on else "ghost", 10, F(500, 12), "#FFFFFF", "text-align:left;padding:0 14px;"))
            if b.graphicsEffect() is None: lift(b, 10, 3, 150)


class LevelBar(QWidget):
    def __init__(self):
        super().__init__(); self.setFixedHeight(12); self._v = 0.0
    def set_level(self, rms):
        self._v = min(1.0, float(rms) / 100.0); self.update()
    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(0, 2, self.width(), 8); p.setPen(Qt.NoPen); p.setBrush(QColor(255, 255, 255, 25)); p.drawRoundedRect(r, 4, 4)
        g = QLinearGradient(0, 0, self.width(), 0); g.setColorAt(0, QColor("#2BD66B")); g.setColorAt(0.65, QColor("#F5C542")); g.setColorAt(1, QColor(T["red"]))
        p.setBrush(QBrush(g)); p.drawRoundedRect(QRectF(0, 2, self.width() * self._v, 8), 4, 4)


# ══════════════════════════════════════════════════════════════════
# CHAT
# ══════════════════════════════════════════════════════════════════
class ChatPage(PageBase):
    def __init__(self, bus, chat_widget):
        super().__init__("Chat", "ALIRA se baat karo — voice ya text, history yahan dikhti hai", "chat")
        self.scroll.hide()
        self.layout().addWidget(chat_widget, 1)


# ══════════════════════════════════════════════════════════════════
# VOICE MODE
# ══════════════════════════════════════════════════════════════════
class VoicePage(PageBase):
    def set_orb_size(self, px):
        self.orb.setFixedSize(int(px), int(px))

    def __init__(self, bus):
        super().__init__("Voice Mode", "Listening mode, awaaz, model aur mic sensitivity", "mic")
        self.bus = bus
        # — assistant card
        card, vl = make_card("Voice Assistant", "mic")
        self.orb = Orb(230); self.orb.setFixedSize(230, 230); self.orb.clicked.connect(lambda: bus.listen_mode.emit("tap"))
        row = QHBoxLayout(); row.addStretch(); row.addWidget(self.orb); row.addStretch(); vl.addLayout(row)
        self.modes = ModeBar(columns=4); self.modes.sig_mode.connect(bus.listen_mode); vl.addWidget(self.modes)
        self.mode_hint = _label("", size=12); vl.addWidget(self.mode_hint)
        self.live_user = _label("", "#EDEBF0", 14); self.live_TABBU = _label("", T["red"], 14)
        vl.addWidget(self.live_user); vl.addWidget(self.live_TABBU); self.body.addWidget(card)
        # — voice & persona
        card, vl = make_card("Voice & Persona", "user")
        vl.addWidget(_label("Awaaz", size=12)); self.seg_voice = Segmented([("female", "Female (Aoede)"), ("male", "Male (Charon)")], "female")
        self.seg_voice.changed.connect(lambda k: bus.voice_toggle.emit() if k != bus.state["voice"] else None); vl.addWidget(self.seg_voice)
        vl.addWidget(_label("Persona", size=12)); self.seg_persona = Segmented([("ALIRA", "ALIRA 🌸 (friendly)"), ("normal", "Normal 👔 (professional)")], "ALIRA")
        self.seg_persona.changed.connect(lambda k: bus.persona_toggle.emit() if k != bus.state["persona"] else None); vl.addWidget(self.seg_persona)
        self.body.addWidget(card)
        # — model
        card, vl = make_card("Gemini Live model", "bolt")
        self.models = RadioList([], None); self._model_box = vl; vl.addWidget(self.models); self.body.addWidget(card)
        # — mic
        card, vl = make_card("Microphone", "sliders")
        self.level = LevelBar(); vl.addWidget(_label("Live mic level", size=12)); vl.addWidget(self.level)
        self.lbl_rms = _label("", "#EDEBF0", 13); vl.addWidget(self.lbl_rms)
        self.s_rms = QSlider(Qt.Horizontal); self.s_rms.setRange(5, 120); self.s_rms.setStyleSheet(SLIDER_CSS)
        vl.addWidget(_label("Sensitivity threshold (kam = zyada sensitive)", size=12)); vl.addWidget(self.s_rms)
        self.lbl_gain = _label("", "#EDEBF0", 13); self.s_gain = QSlider(Qt.Horizontal); self.s_gain.setRange(10, 50); self.s_gain.setStyleSheet(SLIDER_CSS)
        vl.addWidget(_label("Mic gain", size=12)); vl.addWidget(self.s_gain); vl.addWidget(self.lbl_gain)
        for s in (self.s_rms, self.s_gain): s.valueChanged.connect(_ALIRA_slot(self._sens))
        b = pill("Mic / Speaker device chuno…", "mic"); b.clicked.connect(_ALIRA_slot(bus.mic_select)); vl.addWidget(b)
        self.body.addWidget(card); self.body.addStretch(1)
        bus.state_changed.connect(self.refresh)

    def _sens(self, _=None):
        rms, gain = self.s_rms.value(), self.s_gain.value() / 10.0
        self.lbl_rms.setText(f"Threshold: {rms}"); self.lbl_gain.setText(f"Gain: {gain:.1f}x")
        self.bus.sens_changed.emit(rms, gain)

    HINTS = {"wake": "Wake Word: ALIRA sirf tab bolegi jab aap 'ALIRA' bolo (phir 30 sec tak baat-cheet chalti rahegi).",
             "tap": "Tap to Talk: mic band rehta hai — orb ya mic button dabao, bolo; jawab ke baad mic khud band.",
             "continuous": "Continuous: mic hamesha on, ALIRA har baat ka jawab degi.",
             "stop": "Stop Listening: mic band. Koi mode dabao ya mic button dabao to dobara chalu."}

    def refresh(self):
        st = self.bus.state
        self.modes.set_mode(st["listen_mode"]); self.mode_hint.setText(self.HINTS.get(st["listen_mode"], ""))
        self.seg_voice.set_current(st["voice"]); self.seg_persona.set_current(st["persona"])
        if [k for k, _ in st["models"]] != list(self.models._b):
            self.models.setParent(None); self.models = RadioList(st["models"], st["model_key"])
            self.models.changed.connect(self.bus.model_pick); self._model_box.addWidget(self.models)
        self.models.set_current(st["model_key"])
        for s, v in ((self.s_rms, int(st["rms"])), (self.s_gain, int(st["gain"] * 10))):
            if s.isSliderDown(): continue          # user drag kar raha hai
            s.blockSignals(True); s.setValue(v); s.blockSignals(False)
        self.lbl_rms.setText(f"Threshold: {int(st['rms'])}"); self.lbl_gain.setText(f"Gain: {st['gain']:.1f}x")

    def on_show(self): self.refresh()
    def set_live(self, user, TABBU):
        self.live_user.setText(f"🎤 {user}" if user else ""); self.live_TABBU.setText(f"ALIRA: {TABBU}" if TABBU else "")


# ══════════════════════════════════════════════════════════════════
# PC CONTROL
# ══════════════════════════════════════════════════════════════════
class PCControlPage(PageBase):
    def __init__(self, bus):
        super().__init__("PC Control", "Volume, brightness, power, screenshot aur system shortcuts", "monitor")
        self.bus = bus
        # sound & display
        card, vl = make_card("Sound & Display", "volume")
        r1 = QHBoxLayout(); self.lbl_vol = _label("Volume", "#EDEBF0", 14); self.s_vol = QSlider(Qt.Horizontal); self.s_vol.setRange(0, 100); self.s_vol.setStyleSheet(SLIDER_CSS)
        self.btn_mute = pill("Mute", "volume", h=34); self.btn_mute.clicked.connect(_ALIRA_slot(self._mute))
        r1.addWidget(self.lbl_vol, 1); r1.addWidget(self.btn_mute); vl.addLayout(r1); vl.addWidget(self.s_vol)
        self.s_vol.sliderReleased.connect(lambda: self._async(lambda v=self.s_vol.value(): act.set_volume(v)))
        self.s_vol.valueChanged.connect(lambda v: self.lbl_vol.setText(f"Volume — {v}%"))
        self.lbl_br = _label("Brightness", "#EDEBF0", 14); self.s_br = QSlider(Qt.Horizontal); self.s_br.setRange(0, 100); self.s_br.setStyleSheet(SLIDER_CSS)
        vl.addWidget(self.lbl_br); vl.addWidget(self.s_br)
        self.s_br.sliderReleased.connect(lambda: self._async(lambda v=self.s_br.value(): act.set_brightness(v)))
        self.s_br.valueChanged.connect(lambda v: self.lbl_br.setText(f"Brightness — {v}%"))
        self.body.addWidget(card)
        # media
        card, vl = make_card("Media controls", "play")
        row = QHBoxLayout()
        for icon, key, tip in (("prev", "prevtrack", "Previous"), ("play", "playpause", "Play / Pause"), ("next", "nexttrack", "Next"),
                               ("volume", "volumeup", "Volume +"), ("minus", "volumedown", "Volume -")):
            b = pill("", icon, h=40); b.setToolTip(tip); b.setFixedWidth(60); b.clicked.connect(lambda _=False, k=key: self._toast(act.media_key(k)))
            row.addWidget(b)
        row.addStretch(); vl.addLayout(row); self.body.addWidget(card)
        # quick actions
        card, vl = make_card("Quick actions", "bolt"); g = QGridLayout(); g.setSpacing(8)
        items = [("Screenshot", "screenshot", self._shot), ("Task Manager", "activity", lambda: act.open_app("task manager")),
                 ("Settings", "gear", lambda: act.open_app("settings")), ("Calculator", "grid", lambda: act.open_app("calculator")),
                 ("Notepad", "file", lambda: act.open_app("notepad")), ("File Explorer", "folder", lambda: act.open_app("explorer")),
                 ("Control Panel", "sliders", lambda: act.open_app("control panel")), ("Terminal", "code", lambda: act.open_app("terminal"))]
        for i, (t, ic, fn) in enumerate(items):
            b = pill(t, ic); b.clicked.connect(lambda _=False, f=fn: self._toast(f())); g.addWidget(b, i // 2, i % 2)
        vl.addLayout(g); self.body.addWidget(card)
        # power
        card, vl = make_card("Power", "power"); g = QGridLayout(); g.setSpacing(8)
        for i, (t, ic, fn, kind) in enumerate([("Lock PC", "lock", act.lock_pc, "ghost"), ("Sleep", "clock", act.sleep_pc, "ghost"),
                                               ("Sign out", "user", act.sign_out, "ghost"), ("Restart", "refresh", act.restart_pc, "danger"),
                                               ("Shutdown", "power", act.shutdown_pc, "danger"), ("Cancel shutdown", "x", act.cancel_shutdown, "ghost")]):
            b = pill(t, ic, kind); b.clicked.connect(lambda _=False, n=t, f=fn: self._power(n, f)); g.addWidget(b, i // 3, i % 3)
        vl.addLayout(g); vl.addWidget(_label("Restart/Shutdown 15 second ke countdown ke saath hota hai — 'Cancel shutdown' se roko.", size=12))
        self.body.addWidget(card); self.body.addStretch(1)

    def _toast(self, res):
        ok, msg = res if isinstance(res, tuple) else (True, str(res)); self.bus.toast.emit(("✓ " if ok else "✗ ") + msg)

    def _async(self, fn, then=None):
        run_async(fn, lambda r: (self._toast(r) if isinstance(r, tuple) else None, then() if then else None), self)

    def _shot(self):
        def done(res):
            ok, msg = res if isinstance(res, tuple) else (False, str(res))
            if ok: self.bus.toast.emit(f"✓ Screenshot saved: {msg}"); act.reveal_in_explorer(msg)
            else:  self.bus.toast.emit(f"✗ {msg}")
        run_async(act.screenshot, done, self)

    def _mute(self):
        self._async(act.toggle_mute, self.on_show)

    def _power(self, name, fn):
        if name in ("Restart", "Shutdown", "Sign out", "Sleep"):
            if QMessageBox.question(self, name, f"PC ko {name} karna hai?") != QMessageBox.Yes: return
        self._async(fn)

    def on_show(self):
        # slow reads (brightness WMI ~4s) background me — page turant khulta hai
        self.lbl_vol.setText("Volume — …"); self.lbl_br.setText("Brightness — …")
        run_async(lambda: (act.get_volume(), act.get_brightness(), act.is_muted()), self._apply_state, self)

    def _apply_state(self, res):
        if not isinstance(res, tuple): return
        v, b, m = res
        for s, val in ((self.s_vol, v), (self.s_br, b)):
            s.blockSignals(True); s.setEnabled(val is not None); s.setValue(val or 0); s.blockSignals(False)
        self.lbl_vol.setText(f"Volume — {v}%" if v is not None else "Volume (support nahi)")
        self.lbl_br.setText(f"Brightness — {b}%" if b is not None else "Brightness (is display par support nahi)")
        self.btn_mute.setText("  Unmute" if m else "  Mute")


# ══════════════════════════════════════════════════════════════════
# APPS & TOOLS
# ══════════════════════════════════════════════════════════════════
class AppsToolsPage(PageBase):
    AI_TOOLS = [
        ("Generate Image", "image", "Is description par ek image banao:", "Generate an image: {x}"),
        ("Summarize Text", "file", "Jis text ko summarize karna hai wo paste karo:", "Summarize this text briefly:\n{x}"),
        ("Translate", "translate", "Kya translate karna hai? (language bhi likho, jaise 'Hindi to English: ...')", "Translate: {x}"),
        ("Write Code", "code", "Kaunsa code chahiye? (language + kya karna hai)", "Write code for: {x}"),
        ("Create PDF", "file", "PDF mein kya likhna hai / topic?", "Create a PDF document about: {x}"),
        ("Analyze File", "folder", None, "Analyze this file and give key insights: {x}"),
        ("Plan My Day", "calendar", "Aaj ke kaam / priorities likho:", "Plan my day with these tasks, time-blocked: {x}"),
    ]

    def __init__(self, bus):
        super().__init__("Apps & Tools", "AI tools, ALIRA Coder, WebForge aur app launcher", "grid")
        self.bus = bus
        card, vl = make_card("AI Tools", "sparkle"); g = QGridLayout(); g.setSpacing(8)
        for i, (name, ic, ask, tpl) in enumerate(self.AI_TOOLS):
            b = pill(name, ic); b.clicked.connect(lambda _=False, a=ask, t=tpl, n=name: self._ai(n, a, t)); g.addWidget(b, i // 2, i % 2)
        vl.addLayout(g); self.body.addWidget(card)
        card, vl = make_card("Builders", "code"); row = QHBoxLayout()
        b1 = pill("ALIRA Coder — AI se code/website", "code", "primary"); b1.clicked.connect(_ALIRA_slot(bus.coder))
        b2 = pill("WebForge — website + deploy", "globe", "primary"); b2.clicked.connect(_ALIRA_slot(bus.webforge))
        row.addWidget(b1); row.addWidget(b2); vl.addLayout(row); self.body.addWidget(card)
        card, vl = make_card("App launcher", "grid")
        self.search = QLineEdit(); self.search.setPlaceholderText("App ka naam likho… (Enter se kholo)"); self.search.setStyleSheet(INPUT_CSS)
        self.list = QListWidget(); self.list.setStyleSheet(LIST_CSS); self.list.setMinimumHeight(260)
        self.count = _label("", size=12)
        vl.addWidget(self.search); vl.addWidget(self.list); vl.addWidget(self.count)
        self.search.textChanged.connect(_ALIRA_slot(self._filter)); self.search.returnPressed.connect(_ALIRA_slot(self._launch_first))
        self.list.itemActivated.connect(lambda it: self._launch(it.data(Qt.UserRole)))
        self._apps = []; self.body.addWidget(card); self.body.addStretch(1)

    def _ai(self, name, ask, tpl):
        if ask is None:
            path, _ = QFileDialog.getOpenFileName(self, name)
            if not path: return
            x = path
        else:
            x, ok = QInputDialog.getMultiLineText(self, name, ask)
            if not ok or not x.strip(): return
        self.bus.prompt.emit(tpl.format(x=x.strip()))

    def on_show(self):
        if not self._apps:
            self._apps = act.start_menu_apps(); self._filter()

    def _filter(self, _=None):
        q = self.search.text().strip().lower(); self.list.clear(); n = 0
        for name, path in self._apps:
            if q in name.lower():
                it = QListWidgetItem(name); it.setData(Qt.UserRole, path); self.list.addItem(it); n += 1
        self.count.setText(f"{n} apps")

    def _launch_first(self):
        if self.list.count(): self._launch(self.list.item(0).data(Qt.UserRole))

    def _launch(self, path):
        ok, msg = act.open_path(path); self.bus.toast.emit(("✓ Opened: " if ok else "✗ ") + os.path.basename(path).replace(".lnk", ""))


# ══════════════════════════════════════════════════════════════════
# AUTOMATION
# ══════════════════════════════════════════════════════════════════
class AutomationPage(PageBase):
    def __init__(self, bus):
        super().__init__("Automation", "Tasks, reminders aur one-click routines", "automation")
        self.bus = bus
        card, vl = make_card("Tasks & Reminders", "calendar")
        row = QHBoxLayout()
        self.t_title = QLineEdit(); self.t_title.setPlaceholderText("Task / reminder…"); self.t_title.setStyleSheet(INPUT_CSS)
        self.t_due = QLineEdit(); self.t_due.setPlaceholderText("Kab? (kal 5pm, friday 10:00…)"); self.t_due.setStyleSheet(INPUT_CSS); self.t_due.setMaximumWidth(220)
        add = pill("Add", "plus", "primary"); add.clicked.connect(_ALIRA_slot(self._add)); self.t_title.returnPressed.connect(_ALIRA_slot(self._add))
        row.addWidget(self.t_title, 1); row.addWidget(self.t_due); row.addWidget(add); vl.addLayout(row)
        self.list = QListWidget(); self.list.setStyleSheet(LIST_CSS); self.list.setMinimumHeight(230); vl.addWidget(self.list)
        row = QHBoxLayout()
        for t, ic, fn, kind in (("Done", "check", self._done, "ghost"), ("Delete", "trash", self._del, "danger"), ("Refresh", "refresh", self.reload, "ghost")):
            b = pill(t, ic, kind, 36); b.clicked.connect(_ALIRA_slot(fn)); row.addWidget(b)
        row.addStretch(); vl.addLayout(row)
        if not _HAS_TASK_MANAGER: vl.addWidget(_label("⚠ TABBU_modules.TABBU_advanced_tools nahi mila — reminders persist nahi honge.", "#FFAA55", 12))
        self.body.addWidget(card)
        card, vl = make_card("Routines (one-click)", "bolt"); g = QGridLayout(); g.setSpacing(8)
        routines = [("Good Morning", "sun", "Aaj ki date, mausam aur mere pending tasks batao. Warm good-morning ke saath.", None),
                    ("Focus Mode", "shield", "Focus mode on — mujhe disturb mat karna, short replies.", lambda: (act.set_volume(20), act.set_brightness(70))),
                    ("Meeting Mode", "mic", "Meeting mode on — main meeting mein hoon.", lambda: (act.set_volume(0), act.set_brightness(50))),
                    ("Night Mode", "clock", "Night mode on — dheere, shaant awaaz mein baat karo.", lambda: (act.set_volume(15), act.set_brightness(20))),
                    ("Daily Summary", "news", "Aaj mene kya kya kiya uska short summary do aur kal ke liye suggestions.", None),
                    ("Clean Up", "trash", "Mere Downloads folder ko organize karne ke tips do.", None)]
        for i, (name, ic, prompt, local) in enumerate(routines):
            b = pill(name, ic); b.clicked.connect(lambda _=False, p=prompt, l=local, n=name: self._routine(n, p, l)); g.addWidget(b, i // 2, i % 2)
        vl.addLayout(g); vl.addWidget(_label("Focus/Meeting/Night routines volume + brightness bhi badalte hain.", size=12))
        self.body.addWidget(card); self.body.addStretch(1)

    def _routine(self, name, prompt, local):
        if local: run_async(local, lambda r: None, self)      # volume/brightness background me
        self.bus.toast.emit(f"✓ Routine: {name}"); self.bus.prompt.emit(prompt)

    def on_show(self): self.reload()

    def reload(self):
        self.list.clear()
        for t in _tm_tasks_load():
            done = t.get("status") == "done"; due = t.get("due", "")
            it = QListWidgetItem(f"{'✅' if done else '⏳'}  {t.get('title', '')}" + (f"    ·  {due[:16].replace('T', ' ')}" if due else ""))
            it.setData(Qt.UserRole, t.get("id")); self.list.addItem(it)

    def _add(self):
        title = self.t_title.text().strip()
        if not title: return
        due_text = self.t_due.text().strip(); due = _tm_parse_due(due_text) if due_text else ""
        task = {"id": hashlib.md5(f"{title}{time.time()}".encode()).hexdigest()[:8], "title": title, "description": "", "due": due,
                "priority": "normal", "status": "pending", "platform": "local", "created_at": datetime.now().isoformat()}
        tasks = _tm_tasks_load(); tasks.append(task); _tm_tasks_save(tasks)
        if due: _tm_set_reminder(title, due)
        self.t_title.clear(); self.t_due.clear(); self.reload(); self.bus.toast.emit("✓ Task add hua" + (" + reminder set" if due else ""))

    def _sel(self):
        it = self.list.currentItem(); return it.data(Qt.UserRole) if it else None

    def _done(self):
        tid = self._sel()
        if not tid: return
        tasks = _tm_tasks_load()
        for t in tasks:
            if t.get("id") == tid: t["status"] = "done"
        _tm_tasks_save(tasks); self.reload()

    def _del(self):
        tid = self._sel()
        if not tid: return
        _tm_tasks_save([t for t in _tm_tasks_load() if t.get("id") != tid]); self.reload()


# ══════════════════════════════════════════════════════════════════
# FILES & DOCUMENTS
# ══════════════════════════════════════════════════════════════════
class FilesPage(PageBase):
    def __init__(self, bus):
        super().__init__("Files & Documents", "Folders browse karo, kholo ya ALIRA se summarize karwao", "file")
        self.bus = bus; self.cwd = None
        card, vl = make_card("Browser", "folder")
        row = QHBoxLayout(); row.setSpacing(6)
        locs = dict(act.user_dirs()); locs["Screenshots"] = act.SHOT_DIR
        for name, path in locs.items():
            b = pill(name, None, "ghost", 32); b.clicked.connect(lambda _=False, p=path: self.go(p)); row.addWidget(b)
        row.addStretch(); vl.addLayout(row)
        r2 = QHBoxLayout(); self.path_lbl = _label("", "#EDEBF0", 12)
        up = pill("Up", None, "ghost", 32); up.clicked.connect(_ALIRA_slot(self.up))
        self.filter = QLineEdit(); self.filter.setPlaceholderText("Filter / search…"); self.filter.setStyleSheet(INPUT_CSS); self.filter.setMaximumWidth(220)
        self.filter.textChanged.connect(_ALIRA_slot(self._render))
        r2.addWidget(up); r2.addWidget(self.path_lbl, 1); r2.addWidget(self.filter); vl.addLayout(r2)
        self.tree = QTreeWidget(); self.tree.setHeaderLabels(["Name", "Size", "Modified"]); self.tree.setRootIsDecorated(False)
        self.tree.setStyleSheet(LIST_CSS); self.tree.setMinimumHeight(400)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch); self.tree.setColumnWidth(1, 90); self.tree.setColumnWidth(2, 140)
        self.tree.itemDoubleClicked.connect(lambda it, _c: self.open_item(it)); vl.addWidget(self.tree)
        r3 = QHBoxLayout()
        for t, ic, fn, kind in (("Open", "external", self.open_sel, "primary"), ("Show in Explorer", "folder", self.reveal, "ghost"),
                                ("Ask ALIRA to summarize", "sparkle", self.summarize, "ghost"), ("WhatsApp par bhejo", "whatsapp", self.whatsapp, "ghost"),
                                ("Refresh", "refresh", lambda: self.go(self.cwd), "ghost")):
            b = pill(t, ic, kind, 36); b.clicked.connect(_ALIRA_slot(fn)); r3.addWidget(b)
        r3.addStretch(); vl.addLayout(r3); self.count = _label("", size=12); vl.addWidget(self.count)
        self.body.addWidget(card); self._entries = []

    def on_show(self):
        if self.cwd is None:
            d = act.user_dirs(); self.go(d.get("Documents") or d.get("Desktop") or Path.home())

    def go(self, path):
        self.cwd = Path(path); self.path_lbl.setText(str(self.cwd))
        want = self.cwd
        def done(rows):
            if want != self.cwd or isinstance(rows, Exception): return      # tab tak user aage badh gaya
            self._entries = rows; self._render()
        run_async(lambda: act.list_dir(want), done, self, fast=True)

    def up(self):
        if self.cwd and self.cwd.parent != self.cwd: self.go(self.cwd.parent)

    def _render(self, _=None):
        q = self.filter.text().strip().lower(); self.tree.clear(); n = 0
        for name, full, is_dir, size, mt in self._entries:
            if q and q not in name.lower(): continue
            it = QTreeWidgetItem([("📁 " if is_dir else "📄 ") + name, "" if is_dir else act.human_size(size), datetime.fromtimestamp(mt).strftime("%d %b %Y %H:%M")])
            it.setData(0, Qt.UserRole, (full, is_dir)); self.tree.addTopLevelItem(it); n += 1
        self.count.setText(f"{n} items")

    def _cur(self):
        it = self.tree.currentItem(); return it.data(0, Qt.UserRole) if it else (None, False)

    def open_item(self, it):
        full, is_dir = it.data(0, Qt.UserRole)
        self.go(full) if is_dir else self._toast(act.open_path(full))

    def open_sel(self):
        full, is_dir = self._cur()
        if full: self.go(full) if is_dir else self._toast(act.open_path(full))

    def reveal(self):
        full, _ = self._cur(); self._toast(act.reveal_in_explorer(full or self.cwd))

    def summarize(self):
        full, is_dir = self._cur()
        if full and not is_dir: self.bus.prompt.emit(f"Is file ko padho aur summarize karo: {full}")
        else: self.bus.toast.emit("✗ Pehle koi file select karo")

    def whatsapp(self):
        full, is_dir = self._cur()
        if full and not is_dir: self.bus.prompt.emit(f"Ye file WhatsApp par bhejni hai: {full}")
        else: self.bus.toast.emit("✗ Pehle koi file select karo")

    def _toast(self, res):
        ok, msg = res
        self.bus.toast.emit(("✓ " + os.path.basename(str(msg))) if ok else ("✗ " + str(msg)))


# ══════════════════════════════════════════════════════════════════
# MEDIA
# ══════════════════════════════════════════════════════════════════
class MediaPage(PageBase):
    def __init__(self, bus):
        super().__init__("Media", "Camera vision, screen share, media keys aur screenshots", "image")
        self.bus = bus
        card, vl = make_card("Camera Vision", "camera")
        r = QHBoxLayout(); self.cam_btn = pill("Camera ON/OFF", "camera", "primary"); self.cam_btn.clicked.connect(_ALIRA_slot(bus.camera_toggle))
        self.cam_lbl = _label("Camera band hai", size=13); r.addWidget(self.cam_btn); r.addWidget(self.cam_lbl, 1); vl.addLayout(r)
        self.cam_holder = QWidget(); self.cam_holder.setMinimumHeight(300); self.cam_holder.setStyleSheet("background:transparent;")
        QVBoxLayout(self.cam_holder).setContentsMargins(0, 0, 0, 0); vl.addWidget(self.cam_holder); self.body.addWidget(card)
        card, vl = make_card("Screen share", "monitor")
        r = QHBoxLayout(); self.ss_btn = pill("Screen share ON/OFF", "monitor", "primary"); self.ss_btn.clicked.connect(_ALIRA_slot(bus.screenshare_toggle))
        self.ss_lbl = _label("Band hai — ON karne par ALIRA aapki screen dekh sakti hai", size=13); r.addWidget(self.ss_btn); r.addWidget(self.ss_lbl, 1); vl.addLayout(r)
        self.body.addWidget(card)
        card, vl = make_card("Media keys", "play"); row = QHBoxLayout()
        for icon, key in (("prev", "prevtrack"), ("play", "playpause"), ("next", "nexttrack"), ("volume", "volumemute")):
            b = pill("", icon, h=40); b.setFixedWidth(60); b.clicked.connect(lambda _=False, k=key: act.media_key(k)); row.addWidget(b)
        row.addStretch(); vl.addLayout(row); self.body.addWidget(card)
        card, vl = make_card("Screenshots", "image")
        r = QHBoxLayout(); b = pill("Screenshot lo", "screenshot", "primary"); b.clicked.connect(_ALIRA_slot(self._shot))
        o = pill("Folder kholo", "folder"); o.clicked.connect(lambda: (act.SHOT_DIR.mkdir(parents=True, exist_ok=True), act.open_path(act.SHOT_DIR)))
        r.addWidget(b); r.addWidget(o); r.addStretch(); vl.addLayout(r)
        self.grid = QGridLayout(); self.grid.setSpacing(8); vl.addLayout(self.grid); self.body.addWidget(card); self.body.addStretch(1)
        bus.state_changed.connect(self.refresh)

    def _shot(self):
        ok, msg = act.screenshot(); self.bus.toast.emit(("✓ Saved: " if ok else "✗ ") + os.path.basename(msg)); self.reload()

    def refresh(self):
        st = self.bus.state
        self.cam_lbl.setText("● Camera LIVE — ALIRA dekh rahi hai" if st["cam_on"] else "Camera band hai")
        self.ss_lbl.setText("● Screen LIVE — ALIRA aapki screen dekh rahi hai" if st["screen_on"] else "Band hai — ON karne par ALIRA aapki screen dekh sakti hai")

    def on_show(self): self.refresh(); self.reload()

    def reload(self):
        while self.grid.count():
            w = self.grid.takeAt(0).widget()
            if w: w.deleteLater()
        for i, path in enumerate(act.list_screenshots(8)):
            pm = QPixmap(path)
            if pm.isNull(): continue
            thumb = pm.scaled(190, 110, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation).copy(0, 0, 190, 110)
            b = QPushButton(); b.setIcon(QIcon(thumb))
            b.setIconSize(QSize(190, 110)); b.setFixedSize(198, 118); b.setCursor(Qt.PointingHandCursor); b.setToolTip(os.path.basename(path))
            b.setStyleSheet("QPushButton{border:1px solid rgba(255,255,255,0.12);border-radius:8px;background:rgba(255,255,255,0.03);}"
                            f"QPushButton:hover{{border:1px solid {T['red']};}}")
            b.clicked.connect(lambda _=False, p=path: act.open_path(p)); self.grid.addWidget(b, i // 3, i % 3)


# ══════════════════════════════════════════════════════════════════
# WEB & SEARCH
# ══════════════════════════════════════════════════════════════════
class WebSearchPage(PageBase):
    ENGINES = {"google": ("Google", "https://www.google.com/search?q={q}"), "youtube": ("YouTube", "https://www.youtube.com/results?search_query={q}"),
               "bing": ("Bing", "https://www.bing.com/search?q={q}"), "ddg": ("DuckDuckGo", "https://duckduckgo.com/?q={q}"),
               "wiki": ("Wikipedia", "https://en.wikipedia.org/w/index.php?search={q}")}
    SITES = [("YouTube", "youtube", "https://youtube.com"), ("Gmail", "mail", "https://mail.google.com"), ("Drive", "folder", "https://drive.google.com"),
             ("Maps", "pin", "https://maps.google.com"), ("News", "news", "https://news.google.com"), ("GitHub", "code", "https://github.com"),
             ("WhatsApp Web", "whatsapp", "https://web.whatsapp.com"), ("Translate", "translate", "https://translate.google.com")]

    def __init__(self, bus):
        super().__init__("Web & Search", "Browser search, quick sites aur website builder", "globe")
        self.bus = bus; self.engine = "google"
        card, vl = make_card("Search", "search")
        self.seg = Segmented([(k, v[0]) for k, v in self.ENGINES.items()], "google"); self.seg.changed.connect(self._eng); vl.addWidget(self.seg)
        r = QHBoxLayout(); self.q = QLineEdit(); self.q.setPlaceholderText("Kya search karna hai?"); self.q.setStyleSheet(INPUT_CSS); self.q.returnPressed.connect(_ALIRA_slot(self._search))
        go = pill("Search", "search", "primary"); go.clicked.connect(_ALIRA_slot(self._search))
        ask = pill("ALIRA se poocho", "sparkle"); ask.clicked.connect(_ALIRA_slot(self._ask))
        r.addWidget(self.q, 1); r.addWidget(go); r.addWidget(ask); vl.addLayout(r); self.body.addWidget(card)
        card, vl = make_card("Quick sites", "globe"); g = QGridLayout(); g.setSpacing(8)
        for i, (name, ic, url) in enumerate(self.SITES):
            b = pill(name, ic); b.clicked.connect(lambda _=False, u=url: self.bus.toast.emit("✓ " + act.open_url(u)[1])); g.addWidget(b, i // 4, i % 4)
        vl.addLayout(g); self.body.addWidget(card)
        card, vl = make_card("Website Builder", "code")
        self.site = QLineEdit(); self.site.setPlaceholderText("Kaisi website? (jaise: dark portfolio website for a photographer)"); self.site.setStyleSheet(INPUT_CSS)
        r = QHBoxLayout(); b1 = pill("Website banao", "sparkle", "primary"); b1.clicked.connect(_ALIRA_slot(self._build))
        b2 = pill("WebForge kholo", "globe"); b2.clicked.connect(_ALIRA_slot(bus.webforge)); b3 = pill("ALIRA Coder", "code"); b3.clicked.connect(_ALIRA_slot(bus.coder))
        r.addWidget(b1); r.addWidget(b2); r.addWidget(b3); r.addStretch(); vl.addWidget(self.site); vl.addLayout(r); self.body.addWidget(card); self.body.addStretch(1)

    def _eng(self, k): self.engine = k; self.seg.set_current(k)

    def _search(self):
        q = self.q.text().strip()
        if not q: return
        from urllib.parse import quote_plus
        ok, url = act.open_url(self.ENGINES[self.engine][1].format(q=quote_plus(q))); self.bus.toast.emit(f"✓ {self.ENGINES[self.engine][0]} search: {q}")

    def _ask(self):
        q = self.q.text().strip()
        if q: self.bus.prompt.emit(f"Web par search karke batao: {q}")

    def _build(self):
        d = self.site.text().strip()
        if d: self.bus.prompt.emit(f"Ek website banao: {d}")


# ══════════════════════════════════════════════════════════════════
# SYSTEM MONITOR  (v2 — ring gauges, smooth live charts, process bars)
# ══════════════════════════════════════════════════════════════════
def _pfont(px, weight=QFont.DemiBold):
    f = QFont("Poppins")
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


def _load_color(v):
    """Green < 60 < Amber < 85 < Red — semantic, sirf rang par bharosa nahi: number bhi dikhta hai."""
    return QColor(T["green"]) if v < 60 else (QColor("#F5A524") if v < 85 else QColor(T["red"]))


class RingGauge(QWidget):
    """Gol gauge: bada number + chhota caption. Value badalne par arc smoothly animate hota hai."""

    def __init__(self, title, icon):
        super().__init__()
        from PyQt5.QtCore import QVariantAnimation
        self._title, self._icon = title, icon
        self._v = self._shown = 0.0
        self._main, self._sub, self._color = "—", "", QColor(T["dim"])
        self.setMinimumSize(150, 176)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(450)
        self._anim.valueChanged.connect(_ALIRA_slot(self._on_anim))
        self.setAccessibleName(title)

    def _on_anim(self, v):
        self._shown = float(v)
        self.update()

    def set_value(self, v, main, sub, color=None):
        self._v = max(0.0, min(100.0, float(v)))
        self._main, self._sub = main, sub
        self._color = QColor(color) if color else _load_color(self._v)
        self._anim.stop()
        self._anim.setStartValue(self._shown)
        self._anim.setEndValue(self._v)
        self._anim.start()
        self.setAccessibleDescription(f"{self._title} {main}. {sub}")

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        # title row
        pm = svg_pixmap(self._icon, T["red"], 18, 1.7)
        p.drawPixmap(14, 12, pm)
        p.setPen(QColor("#EDEBF0"))
        p.setFont(_pfont(13))
        p.drawText(QRectF(38, 8, w - 50, 26), Qt.AlignVCenter | Qt.AlignLeft, self._title)
        # ring
        d = max(60, min(w - 36, h - 82))
        cx, top = w / 2.0, 42
        rect = QRectF(cx - d / 2, top, d, d)
        lw = max(9.0, d * 0.095)
        rect = rect.adjusted(lw / 2, lw / 2, -lw / 2, -lw / 2)
        pen = QPen(QColor(255, 255, 255, 22), lw)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(rect, 0, 360 * 16)
        span = int(-360 * 16 * (self._shown / 100.0))
        if abs(span) > 4:
            glow = QColor(self._color); glow.setAlpha(55)
            gp = QPen(glow, lw + 7); gp.setCapStyle(Qt.RoundCap)
            p.setPen(gp); p.drawArc(rect, 90 * 16, span)
            pp = QPen(self._color, lw); pp.setCapStyle(Qt.RoundCap)
            p.setPen(pp); p.drawArc(rect, 90 * 16, span)
        # centre number
        p.setPen(QColor("#FFFFFF"))
        p.setFont(_pfont(max(16, int(d * 0.25)), QFont.Bold))
        p.drawText(QRectF(rect), Qt.AlignCenter, self._main)
        # caption
        p.setPen(QColor(T["muted"]))
        p.setFont(_pfont(12, QFont.Normal))
        p.drawText(QRectF(8, top + d + 8, w - 16, 22), Qt.AlignHCenter | Qt.AlignTop, self._sub)


class LiveChart(QWidget):
    """Smooth area chart (multi-series) — grid, y-labels, legend with current values."""

    def __init__(self, title, series, unit="%", fixed_max=100, n=60):
        super().__init__()
        self.title, self.unit, self.fmax = title, unit, fixed_max
        self.series = [(name, QColor(col)) for name, col in series]
        self.data = {name: collections.deque([None] * n, maxlen=n) for name, _ in self.series}
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setAccessibleName(title)

    def push(self, **vals):
        for k, v in vals.items():
            if k in self.data:
                self.data[k].append(float(v))
        self.update()

    def _fmt(self, v):
        if self.unit == "%":
            return f"{v:.0f}%"
        return f"{v / 1024:.1f} MB/s" if v >= 1024 else f"{v:.0f} KB/s"

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        w, h = self.width(), self.height()
        L, Tp, R, B = (46 if self.unit == "%" else 76), 62, 14, 14
        pw, ph = max(10, w - L - R), max(10, h - Tp - B)
        # title
        p.setPen(QColor("#EDEBF0")); p.setFont(_pfont(13))
        p.drawText(QRectF(14, 8, w - 28, 24), Qt.AlignVCenter | Qt.AlignLeft, self.title)
        # legend with live values
        x = 14
        for name, col in self.series:
            p.setPen(Qt.NoPen); p.setBrush(col)
            p.drawEllipse(QPointF(x + 5, 46), 4.5, 4.5)
            last = self.data[name][-1]
            txt = f"{name}  {self._fmt(last) if last is not None else '—'}"
            p.setPen(QColor(T["muted"])); p.setFont(_pfont(12, QFont.Normal))
            fw = p.fontMetrics().horizontalAdvance(txt)
            p.drawText(QRectF(x + 14, 34, fw + 8, 24), Qt.AlignVCenter | Qt.AlignLeft, txt)
            x += fw + 40
        # y scale
        if self.fmax:
            mx = float(self.fmax)
        else:
            peak = max([v for d in self.data.values() for v in d if v is not None] or [0.0])
            mx = 64.0
            while mx < peak * 1.15:
                mx *= 2
        p.setFont(_pfont(10, QFont.Normal))
        for i in range(5):
            y = Tp + ph * i / 4.0
            p.setPen(QPen(QColor(255, 255, 255, 18), 1))
            p.drawLine(QPointF(L, y), QPointF(L + pw, y))
            p.setPen(QColor(T["dim"]))
            p.drawText(QRectF(0, y - 9, L - 6, 18), Qt.AlignRight | Qt.AlignVCenter, self._fmt(mx * (1 - i / 4.0)).replace(".0", ""))
        # series
        for name, col in self.series:
            vals = list(self.data[name])
            n = len(vals)
            pts = [QPointF(L + pw * i / (n - 1), Tp + ph - (min(v, mx) / mx) * ph) for i, v in enumerate(vals) if v is not None]
            if len(pts) < 2:
                continue
            path = QPainterPath(pts[0])
            for a, b in zip(pts, pts[1:]):                       # smooth: mid-point cubic
                mid = (a.x() + b.x()) / 2.0
                path.cubicTo(QPointF(mid, a.y()), QPointF(mid, b.y()), b)
            fill = QPainterPath(path)
            fill.lineTo(pts[-1].x(), Tp + ph); fill.lineTo(pts[0].x(), Tp + ph); fill.closeSubpath()
            g = QLinearGradient(0, Tp, 0, Tp + ph)
            c1 = QColor(col); c1.setAlpha(95); c2 = QColor(col); c2.setAlpha(0)
            g.setColorAt(0, c1); g.setColorAt(1, c2)
            p.fillPath(fill, QBrush(g))
            pen = QPen(col, 2.2); pen.setJoinStyle(Qt.RoundJoin); pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen); p.setBrush(Qt.NoBrush); p.drawPath(path)
            p.setPen(Qt.NoPen); p.setBrush(col); p.drawEllipse(pts[-1], 3.6, 3.6)      # latest point


from PyQt5.QtWidgets import QStyledItemDelegate, QStyle


class _BarDelegate(QStyledItemDelegate):
    """Process list: CPU/Memory cell ke andar bar (fraction Qt.UserRole+1 mein)."""

    def paint(self, painter, option, index):
        frac = index.data(Qt.UserRole + 1)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, QColor(255, 46, 67, 60))
        elif option.state & QStyle.State_MouseOver:
            painter.fillRect(option.rect, QColor(255, 255, 255, 12))
        if frac is None:
            painter.setPen(QColor("#EDEBF0")); painter.setFont(_pfont(13, QFont.Normal))
            painter.drawText(option.rect.adjusted(10, 0, -6, 0), Qt.AlignVCenter | Qt.AlignLeft, str(index.data(Qt.DisplayRole)))
        else:
            r = QRectF(option.rect.adjusted(6, 7, -6, -7))
            painter.setPen(Qt.NoPen); painter.setBrush(QColor(255, 255, 255, 14))
            painter.drawRoundedRect(r, 7, 7)
            col = QColor(index.data(Qt.UserRole + 2) or T["red"]); col.setAlpha(150)
            painter.setBrush(col)
            painter.drawRoundedRect(QRectF(r.x(), r.y(), max(8.0, r.width() * float(frac)), r.height()), 7, 7)
            painter.setPen(QColor("#FFFFFF")); painter.setFont(_pfont(12))
            painter.drawText(r, Qt.AlignCenter, str(index.data(Qt.DisplayRole)))
        painter.restore()

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        s.setHeight(max(s.height(), 34))
        return s


class _SysSampler(QObject):
    """CPU/RAM/net/disk/processes ek background thread me naapta hai (psutil process scan 100s ms leta hai)."""
    data = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent); self._run = False; self.net = act.NetSampler(); self.procs = act.ProcSampler(); self._info = None

    def start(self):
        if self._run: return
        self._run = True; threading.Thread(target=self._loop, daemon=True, name="ALIRA-sysmon").start()

    def stop(self): self._run = False

    def _loop(self):
        import psutil
        tick = 0
        while self._run:
            d = {}
            try:
                d["cpu"] = psutil.cpu_percent(); vm = psutil.virtual_memory(); d["ram"] = vm.percent
                d["ram_used"], d["ram_total"] = vm.used / 1024 ** 3, vm.total / 1024 ** 3
                d["net"] = self.net.sample(); b = psutil.sensors_battery()
                d["bat"] = ((b.percent, bool(b.power_plugged)) if b else None)
                if tick % 4 == 0:
                    du = psutil.disk_usage(os.path.abspath(os.sep))
                    d["disk"] = (du.percent, du.used / 1024 ** 3, du.total / 1024 ** 3)
                    d["uptime"] = time.time() - psutil.boot_time()
                    d["nproc"] = len(psutil.pids())
                if tick % 3 == 0:                      # process scan is machine par ~3s — har 3 second me ek baar
                    d["procs"] = self.procs.top(60)
                tick += 1
                if self._info is None: self._info = act.sys_info()
                d["info"] = self._info
            except Exception:
                pass
            if self._run:
                try: self.data.emit(d)
                except RuntimeError:                 # page/QObject destroy ho chuka (app band hote waqt) — thread chupchap khatam
                    self._run = False; return
            for _ in range(10):
                if not self._run: break
                time.sleep(0.1)


def _fmt_uptime(sec):
    sec = int(sec); dd, r = divmod(sec, 86400); hh, r = divmod(r, 3600); mm = r // 60
    return (f"{dd}d " if dd else "") + f"{hh}h {mm}m"


class SystemMonitorPage(PageBase):
    def __init__(self, bus):
        super().__init__("System Monitor", "Live CPU, RAM, disk, network aur top processes", "activity")
        self.bus = bus; self._info_shown = False; self._procs = []; self._sort = "cpu"; self._cols = 4
        # header: uptime chip
        self.chip = QLabel("")
        self.chip.setStyleSheet(f"color:#EDEBF0;background:rgba(255,255,255,0.06);border:1px solid {T['line']};border-radius:14px;padding:5px 14px;{F(500, 12)}")
        self.header_right.addWidget(self.chip)

        # ── gauges (CPU / Memory / Disk / Battery) ──
        self.g_cpu = RingGauge("CPU", "cpu"); self.g_ram = RingGauge("Memory", "grid")
        self.g_disk = RingGauge("Disk", "folder"); self.g_bat = RingGauge("Battery", "bolt")
        self._gauges = (self.g_cpu, self.g_ram, self.g_disk, self.g_bat)
        self.tiles = QGridLayout(); self.tiles.setSpacing(12)
        for g in self._gauges:
            card, v = make_card(); v.setContentsMargins(0, 0, 0, 0); v.addWidget(g); g._card = card
        self._place_tiles(4)
        self.body.addLayout(self.tiles)

        # ── charts ──
        self.c_perf = LiveChart("CPU & Memory — last 60 sec", [("CPU", "#2A8BE8"), ("Memory", "#B65CFF")], "%", 100)
        self.c_net = LiveChart("Network", [("Download", "#2BD66B"), ("Upload", "#F5C542")], "KB/s", None)
        self.charts = QBoxLayout(QBoxLayout.LeftToRight); self.charts.setSpacing(12)
        for c, ic in ((self.c_perf, "activity"), (self.c_net, "wifi")):
            card, v = make_card(); v.setContentsMargins(0, 0, 0, 0); v.addWidget(c); self.charts.addWidget(card, 1)
        self.body.addLayout(self.charts)

        # ── processes ──
        seg = Segmented([("cpu", "CPU"), ("mem", "Memory")], "cpu"); seg.changed.connect(self._set_sort); self.seg = seg
        card, vl = make_card("Top processes", "cpu", seg)
        self.tree = QTreeWidget(); self.tree.setHeaderLabels(["Process", "CPU", "Memory"]); self.tree.setRootIsDecorated(False)
        self.tree.setStyleSheet(LIST_CSS); self.tree.setMinimumHeight(330); self.tree.setUniformRowHeights(True)
        self.tree.setItemDelegate(_BarDelegate(self.tree)); self.tree.setMouseTracking(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Fixed); self.tree.header().setSectionResizeMode(2, QHeaderView.Fixed)
        self.tree.setColumnWidth(1, 130); self.tree.setColumnWidth(2, 150)
        vl.addWidget(self.tree)
        k = pill("Selected process band karo", "x", "danger", 38); k.clicked.connect(_ALIRA_slot(self._kill)); vl.addWidget(k, 0, Qt.AlignLeft)
        self.body.addWidget(card)

        # ── system info ──
        card, vl = make_card("System info", "monitor"); self.info = QGridLayout(); self.info.setHorizontalSpacing(18); self.info.setVerticalSpacing(8)
        vl.addLayout(self.info); self.body.addWidget(card); self.body.addStretch(1)
        self.sampler = _SysSampler(self); self.sampler.data.connect(self._apply)

    # ── responsive ──
    def _place_tiles(self, cols):
        self._cols = cols
        while self.tiles.count():
            self.tiles.takeAt(0)
        for i, g in enumerate(self._gauges):
            self.tiles.addWidget(g._card, i // cols, i % cols)
        for c in range(4):
            self.tiles.setColumnStretch(c, 1 if c < cols else 0)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        wide = self.width() >= 1000
        want_cols = 4 if self.width() >= 880 else 2
        if want_cols != self._cols: self._place_tiles(want_cols)
        want = QBoxLayout.LeftToRight if wide else QBoxLayout.TopToBottom
        if self.charts.direction() != want: self.charts.setDirection(want)

    def on_show(self): self.sampler.start()          # page turant dikhta hai, data thread se aata hai
    def hideEvent(self, e): self.sampler.stop(); super().hideEvent(e)

    def _set_sort(self, k):
        self._sort = k; self.seg.set_current(k); self._fill_procs()

    def _apply(self, d):
        if not self.isVisible(): return
        if "cpu" in d:
            info = d.get("info") or {}
            self.g_cpu.set_value(d["cpu"], f"{d['cpu']:.0f}%", (info.get("Cores", "").split(" /")[0] + " cores") if info.get("Cores") else "")
            self.g_ram.set_value(d["ram"], f"{d['ram']:.0f}%", f"{d['ram_used']:.1f} / {d['ram_total']:.1f} GB")
            self.c_perf.push(CPU=d["cpu"], Memory=d["ram"])
        if "net" in d: self.c_net.push(Download=d["net"][0], Upload=d["net"][1])
        if "disk" in d: self.g_disk.set_value(d["disk"][0], f"{d['disk'][0]:.0f}%", f"{d['disk'][1]:.0f} / {d['disk'][2]:.0f} GB")
        if "bat" in d:
            b = d["bat"]
            if b: self.g_bat.set_value(b[0], f"{b[0]:.0f}%", "Charging ⚡" if b[1] else "On battery",
                                       T["green"] if (b[1] or b[0] > 30) else T["red"])
            else: self.g_bat.set_value(0, "n/a", "Desktop PC", T["dim"])
        if "uptime" in d: self.chip.setText(f"Uptime {_fmt_uptime(d['uptime'])}  ·  {d.get('nproc', '?')} processes")
        if d.get("info") and not self._info_shown:
            self._info_shown = True
            items = [(k, v) for k, v in d["info"].items() if k != "Uptime"]
            for i, (k, v) in enumerate(items):
                r, c = i % ((len(items) + 1) // 2), (i // ((len(items) + 1) // 2)) * 2
                self.info.addWidget(_label(k, size=13), r, c); self.info.addWidget(_label(str(v), "#EDEBF0", 13), r, c + 1)
            self.info.setColumnStretch(1, 1); self.info.setColumnStretch(3, 1)
        if "procs" in d:
            self._procs = d["procs"]; self._fill_procs()

    def _fill_procs(self):
        if not self._procs: return
        key = (lambda r: r[2]) if self._sort == "cpu" else (lambda r: r[3])
        rows = sorted(self._procs, key=key, reverse=True)[:10]
        mx_cpu = max(10.0, max(r[2] for r in rows)); mx_mem = max(r[3] for r in rows) or 1.0
        sel = self.tree.currentItem().data(0, Qt.UserRole) if self.tree.currentItem() else None
        self.tree.setUpdatesEnabled(False); self.tree.clear()
        for pid, name, cpu, mem in rows:
            it = QTreeWidgetItem([name, f"{cpu:.1f}%", f"{mem:.0f} MB"]); it.setData(0, Qt.UserRole, pid)
            it.setData(1, Qt.UserRole + 1, min(1.0, cpu / mx_cpu)); it.setData(1, Qt.UserRole + 2, "#2A8BE8")
            it.setData(2, Qt.UserRole + 1, min(1.0, mem / mx_mem)); it.setData(2, Qt.UserRole + 2, "#B65CFF")
            self.tree.addTopLevelItem(it)
            if pid == sel: self.tree.setCurrentItem(it)
        self.tree.setUpdatesEnabled(True)

    def _kill(self):
        it = self.tree.currentItem()
        if not it: return
        pid = it.data(0, Qt.UserRole)
        if QMessageBox.question(self, "Process band karo", f"{it.text(0)} (PID {pid}) band kar dun?") == QMessageBox.Yes:
            run_async(lambda: act.kill_process(pid), lambda r: self.bus.toast.emit(("✓ " if isinstance(r, tuple) and r[0] else "✗ ") + it.text(0)), self)


# ══════════════════════════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════════════════════════
class SettingsPage(PageBase):
    def __init__(self, bus):
        super().__init__("Settings", "API key, voice model, session aur window options", "gear")
        self.bus = bus
        card, vl = make_card("Profile", "user")
        vl.addWidget(_label("ALIRA tumhe isi naam se bulayegi aur Home par greeting mein dikhega.", size=12))
        r = QHBoxLayout(); r.setSpacing(10)
        self.name_edit = QLineEdit(); self.name_edit.setMaxLength(30); self.name_edit.setStyleSheet(INPUT_CSS)
        self.name_edit.setPlaceholderText("Apna naam likho (jaise: Alih)"); self.name_edit.setText(str(bus.state.get("user_name", "") or ""))
        self.name_edit.setAccessibleName("Aapka naam"); self.name_edit.setMinimumHeight(40)
        self.name_save = pill("Save", "check", "primary", 40); self.name_msg = _label("", T["green"], 12)
        self.name_save.clicked.connect(lambda *_: self._save_name()); self.name_edit.returnPressed.connect(lambda: self._save_name())
        r.addWidget(self.name_edit, 1); r.addWidget(self.name_save); vl.addLayout(r); vl.addWidget(self.name_msg); self.body.addWidget(card)
        import alira_lang
        card, vl = make_card("Language / भाषा", "globe")
        vl.addWidget(_label(f"Duniya ki {len(alira_lang.LANGUAGES)}+ languages — jo chuno, ALIRA usi mein sunegi aur bolegi. Naam type karke dhundo.", size=12))
        r = QHBoxLayout(); r.setSpacing(10)
        self.lang_box = QComboBox(); self.lang_box.setEditable(True); self.lang_box.setMinimumHeight(40); self.lang_box.setMaxVisibleItems(14)
        self.lang_box.setAccessibleName("ALIRA ki language"); self.lang_box.setInsertPolicy(QComboBox.NoInsert)
        self.lang_box.setStyleSheet(
            f"QComboBox{{background:rgba(255,255,255,0.05);color:#fff;border:1px solid rgba(255,255,255,0.14);border-radius:10px;padding:0 12px;{F(400,14)}}}"
            f"QComboBox:focus{{border:1px solid {T['red']};}}"
            "QComboBox::drop-down{border:none;width:30px;}"
            "QComboBox::down-arrow{image:none;border-left:5px solid transparent;border-right:5px solid transparent;border-top:6px solid #EDEBF0;margin-right:10px;}"
            f"QComboBox QAbstractItemView{{background:#14101C;color:#EDEBF0;border:1px solid rgba(255,255,255,0.14);outline:0;selection-background-color:{T['red']};selection-color:#fff;}}")
        self.lang_box.lineEdit().setStyleSheet("background:transparent;color:#fff;border:none;")
        self.lang_box.addItem("Auto — Hinglish (default)", "auto")
        for it in alira_lang.LANGUAGES:
            self.lang_box.addItem(alira_lang.display(it), it[0])
        cp = QCompleter([self.lang_box.itemText(i) for i in range(self.lang_box.count())], self.lang_box)
        cp.setFilterMode(Qt.MatchContains); cp.setCaseSensitivity(Qt.CaseInsensitive); self.lang_box.setCompleter(cp)
        self.lang_save = pill("Apply", "check", "primary", 40); self.lang_msg = _label("", T["green"], 12)
        self.lang_save.clicked.connect(lambda *_: self._save_lang()); self.lang_box.lineEdit().returnPressed.connect(lambda: self._save_lang())
        self._set_lang_box(str(bus.state.get("language", "auto") or "auto"))
        r.addWidget(self.lang_box, 1); r.addWidget(self.lang_save); vl.addLayout(r); vl.addWidget(self.lang_msg); self.body.addWidget(card)
        card, vl = make_card("Gemini API", "shield")
        self.key_lbl = _label("", "#EDEBF0", 13); b = pill("API key badlo…", "gear", "primary"); b.clicked.connect(_ALIRA_slot(bus.api_change))
        vl.addWidget(self.key_lbl); vl.addWidget(b, 0, Qt.AlignLeft); self.body.addWidget(card)
        card, vl = make_card("Voice & model", "mic")
        vl.addWidget(_label("Awaaz", size=12)); self.seg_voice = Segmented([("female", "Female"), ("male", "Male")], "female")
        self.seg_voice.changed.connect(lambda k: bus.voice_toggle.emit() if k != bus.state["voice"] else None); vl.addWidget(self.seg_voice)
        vl.addWidget(_label("Persona", size=12)); self.seg_persona = Segmented([("ALIRA", "ALIRA 🌸"), ("normal", "Normal 👔")], "ALIRA")
        self.seg_persona.changed.connect(lambda k: bus.persona_toggle.emit() if k != bus.state["persona"] else None); vl.addWidget(self.seg_persona)
        vl.addWidget(_label("Live model", size=12)); self.models = RadioList([], None); self._mbox = vl; vl.addWidget(self.models)
        r = QHBoxLayout(); m = pill("Mic / Speaker…", "mic"); m.clicked.connect(_ALIRA_slot(bus.mic_select)); v = pill("Voice Mode settings", "sliders"); v.clicked.connect(lambda: bus.goto.emit("voice"))
        r.addWidget(m); r.addWidget(v); r.addStretch(); vl.addLayout(r); self.body.addWidget(card)
        card, vl = make_card("Session (live)", "activity"); self.sess = QGridLayout(); self.sess.setSpacing(6); vl.addLayout(self.sess)
        vl.addWidget(_label("Session resumption ON hai — reconnect ho bhi to baat-cheet ka context bana rehta hai.", size=12)); self.body.addWidget(card)
        card, vl = make_card("Window", "monitor")
        r = QHBoxLayout(); fs = pill("Fullscreen", "maximize"); fs.clicked.connect(_ALIRA_slot(bus.fullscreen)); r.addWidget(fs)
        self.top = QCheckBox("Always on top"); self.top.setStyleSheet(f"QCheckBox{{color:#EDEBF0;{F(500,14)}spacing:8px;}}"); self.top.toggled.connect(_ALIRA_slot(bus.always_on_top)); r.addWidget(self.top)
        self.edge = QCheckBox("Screen edge glow"); self.edge.setChecked(bool(bus.state.get("edge_glow", True)))
        self.edge.setToolTip("Listening / speaking / screen share par screen ke kinaron par rang-birangi animation")
        self.edge.setStyleSheet(f"QCheckBox{{color:#EDEBF0;{F(500,14)}spacing:8px;}}"); self.edge.toggled.connect(_ALIRA_slot(bus.edge_glow)); r.addWidget(self.edge)
        cf = pill("Config folder", "folder"); cf.clicked.connect(lambda: act.open_path(Path.home() / ".TABBU")); r.addWidget(cf); r.addStretch(); vl.addLayout(r); self.body.addWidget(card)
        card, vl = make_card("Orb, startup & Screen Guardian", "sparkle")
        _cb = lambda t: QCheckBox(t)
        _cbcss = f"QCheckBox{{color:#EDEBF0;{F(500,14)}spacing:8px;}}"
        st0 = bus.state
        self.chk_orbmin = _cb("ALIRA minimize karne par floating orb dikhao"); self.chk_orbmin.setStyleSheet(_cbcss)
        self.chk_orbmin.setChecked(bool(st0.get("orb_on_minimize", True))); self.chk_orbmin.toggled.connect(_ALIRA_slot(bus.orb_on_minimize)); vl.addWidget(self.chk_orbmin)
        vl.addWidget(_label("Minimize wale orb ka size (screen par jo orb aata hai)", size=12))
        r = QHBoxLayout(); r.setSpacing(12)
        self.sl_float = QSlider(Qt.Horizontal); self.sl_float.setRange(56, 200); self.sl_float.setValue(int(st0.get("orb_float_size", 96))); self.sl_float.setStyleSheet(SLIDER_CSS)
        self.lbl_float = _label(f"{self.sl_float.value()} px", "#EDEBF0", 13); self.lbl_float.setFixedWidth(64)
        self.sl_float.valueChanged.connect(lambda v: (self.lbl_float.setText(f"{v} px"), bus.orb_float_size.emit(int(v))))
        r.addWidget(self.sl_float, 1); r.addWidget(self.lbl_float); vl.addLayout(r)
        vl.addWidget(_label("ALIRA ki UI par orb ka size (Home aur Voice page)", size=12))
        r = QHBoxLayout(); r.setSpacing(12)
        self.sl_ui = QSlider(Qt.Horizontal); self.sl_ui.setRange(60, 140); self.sl_ui.setValue(int(st0.get("orb_ui_scale", 100))); self.sl_ui.setStyleSheet(SLIDER_CSS)
        self.lbl_ui = _label(f"{self.sl_ui.value()}%", "#EDEBF0", 13); self.lbl_ui.setFixedWidth(64)
        self.sl_ui.valueChanged.connect(lambda v: (self.lbl_ui.setText(f"{v}%"), bus.orb_ui_scale.emit(int(v))))
        r.addWidget(self.sl_ui, 1); r.addWidget(self.lbl_ui); vl.addLayout(r)
        pv = pill("Orb abhi dikhao — jagah / size set karo", "sparkle", "ghost", 38); pv.clicked.connect(_ALIRA_slot(bus.orb_preview)); vl.addWidget(pv, 0, Qt.AlignLeft)
        self.chk_auto = _cb("Windows start / restart par ALIRA khud chalu ho (background mein orb)"); self.chk_auto.setStyleSheet(_cbcss)
        self.chk_auto.setChecked(bool(st0.get("autostart", False))); self.chk_auto.toggled.connect(_ALIRA_slot(bus.autostart)); vl.addWidget(self.chk_auto)
        self.chk_guard = _cb("Screen Guardian — ALIRA screen dekhe aur kuch galat lage to bataye"); self.chk_guard.setStyleSheet(_cbcss)
        self.chk_guard.setChecked(bool(st0.get("guardian", False))); self.chk_guard.toggled.connect(_ALIRA_slot(bus.guardian)); vl.addWidget(self.chk_guard)
        vl.addWidget(_label("Guardian ke liye screenshot Gemini ko jaata hai — sirf jab screen badli ho. Password/banking/incognito window par kabhi nahi bheja jaata.", size=11))
        self.seg_gint = Segmented([("30", "Har 30 sec"), ("45", "Har 45 sec"), ("90", "Har 90 sec")], str(int(st0.get("guardian_interval", 45))))
        self.seg_gint.changed.connect(lambda k: (self.seg_gint.set_current(k), bus.guardian_interval.emit(int(k)))); vl.addWidget(self.seg_gint)
        self.body.addWidget(card)
        card, vl = make_card("About", "sparkle"); vl.addWidget(_label("ALIRA AI v9 — Personal AI Assistant\nGemini Live voice · ALIRA Coder · WebForge · PC control", "#EDEBF0", 13)); self.body.addWidget(card); self.body.addStretch(1)
        bus.state_changed.connect(self.refresh)
        self.timer = QTimer(self, interval=1000, timeout=self.refresh)

    def _set_lang_box(self, code):
        i = self.lang_box.findData(code)
        self.lang_box.setCurrentIndex(i if i >= 0 else 0)

    def _save_lang(self):
        import alira_lang
        txt = self.lang_box.currentText().strip()
        code = "auto" if txt.lower().startswith("auto") else None
        if code is None:
            it = alira_lang.find(txt.split(" — ")[0]) or alira_lang.find(txt)
            if not it:
                self.lang_msg.setStyleSheet(f"color:{T['red']};{F(400, 12)}"); self.lang_msg.setText("Ye language list mein nahi mili — naam sahi se likho"); return
            code = it[0]; txt = alira_lang.display(it)
        self._set_lang_box(code)
        self.bus.language.emit(code)
        self.lang_msg.setStyleSheet(f"color:{T['green']};{F(400, 12)}"); self.lang_msg.setText(f"✓ Language: {txt} — ALIRA ab isi mein baat karegi")

    def _save_name(self):
        n = self.name_edit.text().strip()
        if not n:
            self.name_msg.setStyleSheet(f"color:{T['red']};{F(400, 12)}"); self.name_msg.setText("Naam khali nahi ho sakta"); return
        self.bus.user_name.emit(n)
        self.name_msg.setStyleSheet(f"color:{T['green']};{F(400, 12)}"); self.name_msg.setText(f"✓ Naam save ho gaya: {n}")

    def on_show(self): self.refresh(); self.timer.start()
    def hideEvent(self, e): self.timer.stop(); super().hideEvent(e)

    def refresh(self):
        st = self.bus.state; s = st["session"]
        lg = str(st.get("language", "auto") or "auto")
        if not self.lang_box.hasFocus() and self.lang_box.currentData() != lg:
            self._set_lang_box(lg)
        if not self.name_edit.hasFocus() and self.name_edit.text() != str(st.get("user_name", "") or ""):
            self.name_edit.setText(str(st.get("user_name", "") or ""))      # voice se naam badla ho to yahan bhi
        for chk, key in ((self.chk_orbmin, "orb_on_minimize"), (self.chk_auto, "autostart"), (self.chk_guard, "guardian"), (self.edge, "edge_glow")):
            if key in st and chk.isChecked() != bool(st[key]):
                chk.blockSignals(True); chk.setChecked(bool(st[key])); chk.blockSignals(False)
        self.key_lbl.setText("API key: " + ("✓ set" if s.get("has_key") else "✗ set nahi hai"))
        self.seg_voice.set_current(st["voice"]); self.seg_persona.set_current(st["persona"])
        if [k for k, _ in st["models"]] != list(self.models._b):
            self.models.setParent(None); self.models = RadioList(st["models"], st["model_key"]); self.models.changed.connect(self.bus.model_pick)
            self._mbox.insertWidget(self._mbox.count() - 1, self.models)
        self.models.set_current(st["model_key"])
        rows = [("Model", s.get("model", "-")), ("Endpoint", s.get("endpoint", "-")), ("Session #", s.get("num", 0)), ("Uptime", s.get("uptime", "-")),
                ("Resumption", "ready ✓" if s.get("resumable") else "waiting…"), ("Listening mode", st["listen_mode"])]
        while self.sess.count():
            w = self.sess.takeAt(0).widget()
            if w: w.deleteLater()
        for i, (k, v) in enumerate(rows):
            self.sess.addWidget(_label(k, size=13), i, 0); self.sess.addWidget(_label(str(v), "#EDEBF0", 13), i, 1)


# ══════════════════════════════════════════════════════════════════
# ABOUT — developer, co-founder, social links
# (NOVA_Assistant ke About screen se: Alih "SecureWithAli" + Krishna "Nextdeveloper")
# ══════════════════════════════════════════════════════════════════
ABOUT_INSTAGRAM = "https://instagram.com/SecureWithAli"
ABOUT_YOUTUBE   = "https://youtube.com/@SecureWithAli"
APP_VERSION     = "8.0"


def _open_url(url: str):
    from PyQt5.QtGui import QDesktopServices
    from PyQt5.QtCore import QUrl
    QDesktopServices.openUrl(QUrl(url))


class PortraitView(QWidget):
    """Cut-out photo accent glow par khada — kinare card mein fade (hard cut-off line nahi dikhti)."""

    def __init__(self, photo_path, accent, height=290):
        super().__init__()
        self._src = QPixmap(str(photo_path))
        self._accent = QColor(accent)
        self._cache = None
        self._cache_w = 0
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def _build(self, w, h):
        from PyQt5.QtGui import QImage, QRadialGradient
        img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        g = QRadialGradient(QPointF(w / 2, h * 0.5), min(w, h) * 0.5)
        c = QColor(self._accent); c.setAlpha(120)
        g.setColorAt(0, c); c.setAlpha(0); g.setColorAt(1, c)
        p.fillRect(0, 0, w, h, QBrush(g))
        if not self._src.isNull():
            ph = int(h * 0.97)
            sc = self._src.scaledToHeight(ph, Qt.SmoothTransformation)
            layer = QImage(sc.size(), QImage.Format_ARGB32_Premultiplied)
            layer.fill(0)
            lp = QPainter(layer)
            lp.drawPixmap(0, 0, sc)
            lp.setCompositionMode(QPainter.CompositionMode_DestinationIn)
            vg = QLinearGradient(0, 0, 0, sc.height())
            vg.setColorAt(0.0, QColor(0, 0, 0, 255)); vg.setColorAt(0.78, QColor(0, 0, 0, 255)); vg.setColorAt(1.0, QColor(0, 0, 0, 0))
            lp.fillRect(layer.rect(), QBrush(vg))
            hg = QLinearGradient(0, 0, sc.width(), 0)
            hg.setColorAt(0.0, QColor(0, 0, 0, 0)); hg.setColorAt(0.14, QColor(0, 0, 0, 255))
            hg.setColorAt(0.86, QColor(0, 0, 0, 255)); hg.setColorAt(1.0, QColor(0, 0, 0, 0))
            lp.fillRect(layer.rect(), QBrush(hg))
            lp.end()
            p.drawImage((w - layer.width()) // 2, h - layer.height(), layer)
        p.end()
        return img

    def paintEvent(self, _e):
        w, h = self.width(), self.height()
        if self._cache is None or self._cache_w != w:
            self._cache, self._cache_w = self._build(w, h), w
        p = QPainter(self)
        p.drawImage(0, 0, self._cache)


class PersonCard(QFrame):
    def __init__(self, role, name, handle, bio, photo, accent, socials=()):
        super().__init__()
        card, vl = make_card()
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0); outer.addWidget(card)
        vl.setSpacing(6)
        chip = QLabel(role)
        chip.setStyleSheet(f"color:{accent};background:rgba(255,255,255,0.05);border:1px solid {accent};"
                           f"border-radius:11px;padding:3px 12px;{F(600, 12)}")
        chip.setFixedHeight(24)
        chip.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        vl.addWidget(chip, 0, Qt.AlignHCenter)
        vl.addWidget(PortraitView(photo, accent))
        n = QLabel(name); n.setAlignment(Qt.AlignHCenter); n.setStyleSheet(f"color:#fff;{F(800, 26)}background:transparent;")
        h = QLabel(handle); h.setAlignment(Qt.AlignHCenter); h.setStyleSheet(f"color:{accent};{F(500, 14)}background:transparent;")
        b = _label(bio, "#C9C6CF", 13); b.setAlignment(Qt.AlignHCenter)
        vl.addWidget(n); vl.addWidget(h); vl.addSpacing(4); vl.addWidget(b)
        vl.addStretch(1)
        if socials:
            r = QHBoxLayout(); r.setSpacing(10); r.addStretch()
            for text, icon, url in socials:
                btn = pill(text, icon, "ghost", 38)
                btn.setAccessibleName(f"{text} kholo")
                btn.clicked.connect(lambda _=False, u=url: _open_url(u))
                r.addWidget(btn)
            r.addStretch(); vl.addSpacing(6); vl.addLayout(r)


class AboutPage(PageBase):
    def __init__(self, bus):
        super().__init__("About", "ALIRA ko kisne banaya — Developer, Team aur Social Links", "sparkle")
        self.bus = bus

        # hero
        hero, hv = make_card()
        row = QHBoxLayout(); row.setSpacing(18)
        logo = QLabel(); lp = QPixmap(str(ASSETS / "alira_logo.png"))
        if not lp.isNull():
            logo.setPixmap(lp.scaledToHeight(76, Qt.SmoothTransformation))
        row.addWidget(logo)
        col = QVBoxLayout(); col.setSpacing(2)
        t = QLabel(f'<span style="color:#FFFFFF">ALIRA</span> <span style="color:{T["red"]}">ULTRA</span>')
        t.setStyleSheet(f"{F(800, 30)}background:transparent;")
        tag = _label("Tumhara personal AI assistant — sunti hai, dekhti hai aur kaam khud kar deti hai.", "#EDEBF0", 14)
        ver = QLabel(f"Version {APP_VERSION}"); ver.setStyleSheet(f"color:{T['green']};{F(600, 12)}background:transparent;")
        col.addWidget(t); col.addWidget(tag); col.addWidget(ver)
        row.addLayout(col, 1)
        hv.addLayout(row)
        self.body.addWidget(hero)

        # portraits
        self._people = QBoxLayout(QBoxLayout.LeftToRight); self._people.setSpacing(14)
        dev = PersonCard(
            "CEO & Developer", "Md Ali", "@SecureWithAli",
            "Main ALIRA banata hoon — ek voice-first AI assistant jo tumhara PC samajhta hai, tumhari baat sunta hai "
            "aur kaam khud kar deta hai. ALIRA use karne ke liye shukriya — tumhara feedback hi agla feature banata hai.",
            ASSETS / "about" / "developer.png", T["red"],
            socials=(("Instagram", "instagram", ABOUT_INSTAGRAM), ("YouTube", "youtube", ABOUT_YOUTUBE)))
        co = PersonCard(
            "Co-Founder", "Ali", "@Cyber Security Expert",
            "ALIRA ke Co-founder ke roop mein main ideas, product aur experience shape karta hoon — taaki ALIRA har din "
            "smarter, simpler aur zyada kaam ki bane. Is safar ka hissa banne ke liye shukriya.",
            ASSETS / "about" / "cofounder.png", "#6EA8FF")
        self._people.addWidget(dev, 1); self._people.addWidget(co, 1)
        self.body.addLayout(self._people)

        # social links
        card, vl = make_card("Follow SecureWithAli", "globe")
        vl.addWidget(_label("Naye updates, tutorials aur ALIRA ke behind-the-scenes yahan milte hain.", size=13))
        r = QHBoxLayout(); r.setSpacing(10)
        for text, icon, url in (("Instagram", "instagram", ABOUT_INSTAGRAM), ("YouTube", "youtube", ABOUT_YOUTUBE)):
            b = pill(text, icon, "primary" if icon == "instagram" else "ghost", 42)
            b.clicked.connect(lambda _=False, u=url: _open_url(u)); r.addWidget(b)
        r.addStretch(); vl.addLayout(r)
        self.body.addWidget(card)

        # details
        card, vl = make_card("App info", "shield")
        g = QGridLayout(); g.setSpacing(8)
        rows = [("Version", APP_VERSION), ("Developer", "Md Ali (SecureWithAli)"), ("Co-founder", "Ali (Cyber Security Expert)"),
                ("Built with", "PyQt5 · Gemini Live · ALIRA Coder · WebForge")]
        for i, (k, v) in enumerate(rows):
            g.addWidget(_label(k, size=13), i, 0); g.addWidget(_label(v, "#EDEBF0", 13), i, 1)
        g.setColumnStretch(1, 1); vl.addLayout(g)
        self.body.addWidget(card)
        self.body.addStretch(1)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        # chhoti window par portraits upar-neeche, badi par side-by-side
        want = QBoxLayout.TopToBottom if self.width() < 980 else QBoxLayout.LeftToRight
        if self._people.direction() != want:
            self._people.setDirection(want)
