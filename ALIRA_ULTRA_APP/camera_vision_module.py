# -*- coding: utf-8 -*-
"""
ALIRA Camera Vision Module  (v2 — smooth + reconnect + new UI)
==============================================================
  - Live camera feed — ALIRA real-time mein dekh sakti hai
  - Frame capture -> base64 JPEG -> Gemini vision (auto-vision ya manual Describe)
  - Smooth: capture thread -> "latest frame" slot, GUI timer se pull (queue/lag nahi banta)
  - Camera atak jaye to khud reconnect (watchdog)
  - Photo lo (snapshot), mirror, camera badlo, frame speed

PERFORMANCE NOTES (kyun lag/freeze hota tha):
  * Pehle har frame 1280x720 QImage copy hokar 30fps se GUI thread par aata tha aur do jagah
    smooth-scale hota tha -> GUI peeche reh jata tha, signal queue bharti thi.
    Ab thread sirf 640px preview "latest slot" mein rakhta hai, GUI usse timer par kheenchta hai.
  * "Describe" ek DUSRA VideoCapture khol deta tha jab camera pehle se chal raha tha -> lock/freeze.
    Ab live thread ka latest frame hi use hota hai.
  * Camera open (MSMF) GUI thread ko rokta tha; ab DirectShow + MJPG, thread ke andar.
  * Frame aana band ho jaye to pehle hamesha ke liye atak jata tha; ab watchdog reopen karta hai.
"""

from alira_slot import slot as _ALIRA_slot
import asyncio
import base64
import json
import os
import threading
import time
from typing import Callable, Optional

# MSMF ka hardware-transform path kai PCs par camera open ko 10-30 sec tak rok deta hai
os.environ.setdefault("OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS", "0")
import cv2
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QSizePolicy,
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QObject, QTimer, QRectF, QPointF, QSize, QVariantAnimation,
)
from PyQt5.QtGui import (
    QImage, QPainter, QColor, QPen, QFont, QPainterPath, QLinearGradient, QPixmap, QIcon,
)

# ── ALIRA UI tokens/widgets (agar available hon) ───────────────────
try:
    from ALIRA_ui import T, F, pill, Segmented, svg_pixmap, svg_icon
    _HAS_ALIRA_UI = True
except Exception:                                   # standalone / test mode
    _HAS_ALIRA_UI = False
    T = dict(bg="#07060A", panel="#0E0C11", panel2="#131016", red="#FF2E43", text="#F4F3F6",
             muted="#9C99A4", dim="#6C6975", green="#2BD66B")

    def F(weight, size):
        return f"font-size:{size}px;font-weight:{int(weight)};"

    def svg_pixmap(name, color="#FFFFFF", size=22, stroke=1.7):
        return QPixmap()

    def svg_icon(name, color="#FFFFFF", size=22, stroke=1.7):
        return QIcon()

    def pill(text, icon=None, kind="ghost", h=40):
        b = QPushButton(text)
        b.setFixedHeight(h)
        return b

    class Segmented(QWidget):
        changed = pyqtSignal(str)

        def __init__(self, options, current=None):
            super().__init__()
            hl = QHBoxLayout(self)
            hl.setContentsMargins(0, 0, 0, 0)
            self._b = {}
            for key, label in options:
                b = QPushButton(label)
                b.clicked.connect(lambda _=False, k=key: self.changed.emit(k))
                self._b[key] = b
                hl.addWidget(b)

        def set_current(self, cur):
            for k, b in self._b.items():
                b.setEnabled(k != cur)

_GREEN = "#2BD66B"
_AMBER = "#F5A524"
_INK = "#050407"


def _font(px: int, weight=QFont.DemiBold) -> QFont:
    f = QFont("Poppins")
    f.setPixelSize(px)
    f.setWeight(weight)
    return f


# ══════════════════════════════════════════════════════════════════
# CAPTURE THREAD
# ══════════════════════════════════════════════════════════════════
class CameraVisionThread(QThread):
    """
    Camera se frames capture karo.
      - preview: 640px QImage "latest slot" mein (GUI timer isse kheenchta hai, signal nahi)
      - vision : base64 JPEG, sirf vision_fps par (Gemini ke liye), signal se
      - watchdog: frames band ho jayein to camera dobara kholta hai
    """
    state_changed      = pyqtSignal(str)   # connecting / live / reconnecting
    vision_frame_ready = pyqtSignal(str)   # base64 JPEG for Gemini
    error              = pyqtSignal(str)

    PREVIEW_W  = 640
    VISION_W   = 1024
    TARGET_FPS = 30

    def __init__(self, vision_fps: float = 0.5, cam_index: Optional[int] = None, mirror: bool = True):
        super().__init__()
        self._running         = False
        self._vision_fps      = vision_fps
        self._vision_interval = 1.0 / vision_fps
        self._auto_vision     = False
        self._quality         = 72
        self._cam_index       = cam_index
        self._mirror          = mirror
        self._lock            = threading.Lock()
        self._preview         = None
        self._seq             = 0
        self._raw             = None
        self.fps              = 0.0
        self.resolution       = (0, 0)
        self.cam_index_open   = None

    # ── controls (GUI thread se) ─────────────────────────────────
    def set_auto_vision(self, on: bool):
        self._auto_vision = on

    def set_vision_fps(self, fps: float):
        self._vision_fps      = fps
        self._vision_interval = 1.0 / fps

    def set_mirror(self, on: bool):
        self._mirror = on

    def start_capture(self):
        self._running = True
        self.start()

    def request_stop(self):
        self._running = False

    def stop_capture(self, timeout_ms: int = 1500) -> bool:
        self._running = False
        return self.wait(timeout_ms)

    # ── shared state (GUI thread kheenchta hai) ──────────────────
    def take_preview(self, last_seq: int):
        with self._lock:
            if self._seq == last_seq or self._preview is None:
                return None, last_seq
            return self._preview, self._seq

    def latest_raw(self):
        with self._lock:
            return None if self._raw is None else self._raw.copy()

    def _frame_to_b64(self, frame) -> str:
        h, w = frame.shape[:2]
        if w > self.VISION_W:
            frame = cv2.resize(frame, (self.VISION_W, int(h * self.VISION_W / w)), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self._quality])
        return base64.b64encode(buf.tobytes()).decode("utf-8") if ok else ""

    def encode_latest(self) -> str:
        fr = self.latest_raw()
        return self._frame_to_b64(fr) if fr is not None else ""

    # ── camera open ──────────────────────────────────────────────
    def _sleep(self, sec: float):
        end = time.monotonic() + sec
        while self._running and time.monotonic() < end:
            time.sleep(0.05)

    def _open(self):
        order = [self._cam_index] if self._cam_index is not None else []
        order += [i for i in range(4) if i not in order]
        # Benchmark (is PC par): MSMF 30fps/1.2s open, DSHOW sirf 9-15fps -> MSMF pehle, DSHOW fallback
        backends = [(getattr(cv2, "CAP_MSMF", cv2.CAP_ANY), False),
                    (getattr(cv2, "CAP_DSHOW", cv2.CAP_ANY), True),
                    (cv2.CAP_ANY, False)]
        for idx in order:
            for be, mjpg in backends:
                if not self._running:
                    return None
                cap = cv2.VideoCapture(idx, be)
                if cap.isOpened():
                    if mjpg:                                # DSHOW par MJPG se fps behtar milta hai
                        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                    cap.set(cv2.CAP_PROP_FPS, self.TARGET_FPS)
                    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    for _ in range(12):                     # warm-up: pehle kuch frames fail ho sakte hain
                        ok, fr = cap.read()
                        if ok and fr is not None:
                            self.cam_index_open = idx
                            print(f"[CameraVision] Camera opened: index {idx}")
                            return cap
                        time.sleep(0.05)
                cap.release()
        return None

    # ── main loop ────────────────────────────────────────────────
    def run(self):
        self.state_changed.emit("connecting")
        failures = 0
        while self._running:
            cap = self._open()
            if cap is None:
                failures += 1
                if not self._running:
                    break
                if failures >= 3:
                    self.error.emit("Koi camera nahi mila — connection check karo ya koi aur app camera use kar rahi hai")
                    return
                self.state_changed.emit("reconnecting")
                self._sleep(1.0 * failures)
                continue
            failures = 0
            self.state_changed.emit("live")
            self._pump(cap)
            cap.release()
            if self._running:                               # stall -> reconnect
                print("[CameraVision] Frames ruk gaye — camera dobara khol rahi hoon")
                self.state_changed.emit("reconnecting")
                self._sleep(0.6)
        print("[CameraVision] Camera released")

    def _pump(self, cap):
        interval   = 1.0 / self.TARGET_FPS
        last_vis   = 0.0
        read_fails = 0
        last_ok    = time.monotonic()
        n, t_fps   = 0, time.monotonic()
        while self._running:
            t0 = time.perf_counter()
            ok, frame = cap.read()
            if not ok or frame is None:
                read_fails += 1
                if read_fails >= 20 or time.monotonic() - last_ok > 3.0:
                    return
                time.sleep(0.03)
                continue
            read_fails, last_ok = 0, time.monotonic()

            h, w = frame.shape[:2]
            pw = min(self.PREVIEW_W, w)
            ph = int(h * pw / w)
            small = cv2.resize(frame, (pw, ph), interpolation=cv2.INTER_LINEAR)
            if self._mirror:
                small = cv2.flip(small, 1)                  # sirf preview mirror — ALIRA ko asli (text seedha) jaata hai
            rgb = cv2.cvtColor(small, cv2.COLOR_BGR2RGB)
            img = QImage(rgb.data, pw, ph, 3 * pw, QImage.Format_RGB888).copy()
            with self._lock:
                self._preview, self._raw, self.resolution = img, frame, (w, h)
                self._seq += 1

            now = time.monotonic()
            if self._auto_vision and (now - last_vis) >= self._vision_interval:
                last_vis = now
                b64 = self._frame_to_b64(frame)
                if b64:
                    self.vision_frame_ready.emit(b64)

            n += 1
            if now - t_fps >= 1.0:
                self.fps, n, t_fps = n / (now - t_fps), 0, now

            spare = interval - (time.perf_counter() - t0)
            if spare > 0.002:
                time.sleep(spare)

    def capture_single(self) -> str:
        """Standalone use ke liye: ek frame (live thread chal raha ho to encode_latest() use karo)."""
        cap = self._open_once()
        if cap is None:
            return ""
        ok, frame = cap.read()
        cap.release()
        return self._frame_to_b64(frame) if ok and frame is not None else ""

    def _open_once(self):
        was, self._running = self._running, True
        try:
            return self._open()
        finally:
            self._running = was


# ══════════════════════════════════════════════════════════════════
# MANAGER
# ══════════════════════════════════════════════════════════════════
class CameraVisionManager(QObject):
    """
    Complete camera vision controller (API purane jaisa; naye signals extra).

    sig_vision_frame(str)   — base64 JPEG for Gemini
    sig_ui_frame(QImage)    — ~10fps (sidebar mini-preview)
    sig_preview_frame(QImage) — full rate (panel viewfinder)
    sig_state(str)          — off / connecting / live / reconnecting / error
    sig_stats(fps, sent, secs_since_sent, w, h)
    """
    sig_vision_frame  = pyqtSignal(str)
    sig_ui_frame      = pyqtSignal(QImage)
    sig_preview_frame = pyqtSignal(QImage)
    sig_started       = pyqtSignal()
    sig_stopped       = pyqtSignal()
    sig_error         = pyqtSignal(str)
    sig_status        = pyqtSignal(str)
    sig_describe_now  = pyqtSignal(str)
    sig_state         = pyqtSignal(str)
    sig_stats         = pyqtSignal(float, int, float, int, int)
    sig_frame_sent    = pyqtSignal()
    sig_snapshot      = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._thread      = None
        self._active      = False
        self._auto_mode   = True
        self._vision_fps  = 0.5
        self._mirror      = True
        self._cam_index   = None
        self._sent        = 0
        self._last_sent   = 0.0
        self._last_seq    = 0
        self._tick        = 0
        self._dying       = []
        self._pull = QTimer(self)
        self._pull.setInterval(33)
        self._pull.timeout.connect(_ALIRA_slot(self._pull_frame))
        self._stats = QTimer(self)
        self._stats.setInterval(1000)
        self._stats.timeout.connect(_ALIRA_slot(self._emit_stats))

    # ── properties ───────────────────────────────────────────────
    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def camera_index(self) -> Optional[int]:
        if self._thread and self._thread.cam_index_open is not None:
            return self._thread.cam_index_open
        return self._cam_index

    # ── lifecycle ────────────────────────────────────────────────
    def start(self):
        if self._active:
            return
        for t in list(self._dying):                         # purana thread camera chhod de, tab naya khule
            t.wait(1500)
        th = CameraVisionThread(self._vision_fps, self._cam_index, self._mirror)
        th.set_auto_vision(self._auto_mode)                 # auto-vision default ON — ALIRA ko frames jaate rahein
        th.state_changed.connect(lambda s, t=th: self._on_state(t, s))
        th.vision_frame_ready.connect(lambda b, t=th: self._on_vision(t, b))
        th.error.connect(lambda e, t=th: self._on_error(t, e))
        self._thread, self._active = th, True
        self._last_seq, self._tick = 0, 0
        th.start_capture()
        self._pull.start()
        self._stats.start()
        self.sig_state.emit("connecting")
        self.sig_started.emit()
        self.sig_status.emit("📷  Camera Vision ACTIVE")

    def stop(self):
        """Non-blocking: GUI ko rokta nahi. Thread khud camera release karke khatam hota hai."""
        if not self._active:
            return
        self._active = False
        self._pull.stop()
        self._stats.stop()
        th, self._thread = self._thread, None
        if th:
            th.request_stop()
            self._dying.append(th)
            th.finished.connect(lambda t=th: self._dying.remove(t) if t in self._dying else None)
        self.sig_state.emit("off")
        self.sig_stopped.emit()
        self.sig_status.emit("📷  Camera Vision stopped")

    def shutdown(self):
        """App band hote waqt: stop + saare threads ke khatam hone ka intezaar (QThread crash se bachne ke liye)."""
        self.stop()
        for t in list(self._dying):
            t.wait(1500)

    def toggle(self):
        self.stop() if self._active else self.start()

    # ── settings ─────────────────────────────────────────────────
    def set_auto_vision(self, on: bool):
        self._auto_mode = on
        if self._thread:
            self._thread.set_auto_vision(on)

    def set_vision_fps(self, fps: float):
        self._vision_fps = fps
        if self._thread:
            self._thread.set_vision_fps(fps)

    def set_mirror(self, on: bool):
        self._mirror = on
        if self._thread:
            self._thread.set_mirror(on)

    def set_camera_index(self, idx: Optional[int]):
        self._cam_index = idx
        if self._active:                                    # chalte camera ko naye index par restart
            self.stop()
            QTimer.singleShot(150, self.start)

    # ── internals ────────────────────────────────────────────────
    def _pull_frame(self):
        th = self._thread
        if not th:
            return
        img, seq = th.take_preview(self._last_seq)
        if img is None:
            return
        self._last_seq = seq
        self.sig_preview_frame.emit(img)
        self._tick += 1
        if self._tick % 3 == 0:
            self.sig_ui_frame.emit(img)

    def _emit_stats(self):
        th = self._thread
        if not th:
            return
        ago = (time.monotonic() - self._last_sent) if self._last_sent else -1.0
        self.sig_stats.emit(th.fps, self._sent, ago, th.resolution[0], th.resolution[1])

    def _on_state(self, thread, state: str):
        if thread is self._thread:
            self.sig_state.emit(state)

    def _on_vision(self, thread, b64: str):
        if thread is not self._thread:
            return
        self._sent += 1
        self._last_sent = time.monotonic()
        self.sig_frame_sent.emit()
        self.sig_vision_frame.emit(b64)

    def _on_error(self, thread, err: str):
        if thread is not self._thread:
            return
        print(f"[CameraVision] Error: {err}")
        self._active = False
        self._pull.stop()
        self._stats.stop()
        self._thread = None
        self.sig_state.emit("error")
        self.sig_error.emit(err)
        # camera open fail hone par bhi Start/Stop button sahi state mein aaye
        self.sig_stopped.emit()

    # ── actions ──────────────────────────────────────────────────
    def grab_b64(self) -> str:
        """Live thread ka latest frame (doosra VideoCapture NAHI kholta)."""
        if self._thread:
            return self._thread.encode_latest()
        return ""

    def describe_now(self, get_ws_func, get_loop_func):
        """Abhi ka frame ALIRA ko bhejo aur describe karne ko kaho."""
        b64 = self.grab_b64()
        if not b64:
            self.sig_status.emit("📷  Abhi frame nahi mila — camera start karke 1-2 sec ruko")
            return
        self.sig_describe_now.emit(b64)
        self._sent += 1
        self._last_sent = time.monotonic()
        self.sig_frame_sent.emit()
        ws, loop = get_ws_func(), get_loop_func()
        if not (ws and loop):
            return
        msg = {"realtimeInput": {"video": {"mimeType": "image/jpeg", "data": b64}}}
        txt = {"clientContent": {"turns": [{"role": "user", "parts": [{"text":
                "Yeh camera se liya hua REAL frame hai. "
                "Sirf wahi describe karo jo is image mein sach mein dikh raha hai — "
                "objects, text, log, environment. Andaza ya kalpana bilkul mat karo; "
                "jo clear na dikhe wo bolo 'clear nahi dikh raha'."}]}],
               "turnComplete": True}}
        asyncio.run_coroutine_threadsafe(
            self._send_both(ws, json.dumps(msg).encode(), json.dumps(txt).encode()), loop)

    async def _send_both(self, ws, data1: bytes, data2: bytes):
        try:
            await ws.send(data1)
            await asyncio.sleep(0.05)
            await ws.send(data2)
        except Exception as e:
            print(f"[CameraVision] send error: {e}")

    def snapshot(self) -> str:
        """Latest frame ko Pictures/ALIRA Camera mein JPEG save karo."""
        fr = self._thread.latest_raw() if self._thread else None
        if fr is None:
            return ""
        folder = os.path.join(os.path.expanduser("~"), "Pictures", "ALIRA Camera")
        try:
            os.makedirs(folder, exist_ok=True)
            path = os.path.join(folder, "cam_" + time.strftime("%Y%m%d_%H%M%S") + ".jpg")
            ok, buf = cv2.imencode(".jpg", fr, [cv2.IMWRITE_JPEG_QUALITY, 92])
            if not ok:
                return ""
            with open(path, "wb") as f:                     # imwrite non-ascii path par fail hota hai
                f.write(buf.tobytes())
        except Exception as e:
            print(f"[CameraVision] snapshot error: {e}")
            return ""
        self.sig_snapshot.emit(path)
        return path


# ══════════════════════════════════════════════════════════════════
# UI — VIEWFINDER
# ══════════════════════════════════════════════════════════════════
class CameraView(QWidget):
    """
    16:9 viewfinder. Painter se draw hota hai (QLabel+pixmap scale nahi) — sasta aur smooth.
    HUD: status chip, fps, corner brackets. Jab ALIRA ko frame jaata hai to brackets red flash
    karte hain + "ALIRA ne frame dekha" (asli feedback — pata chalta hai wo sach mein dekh rahi hai).
    """
    _STATES = {
        "off":          ("OFF",          "#6C6975"),
        "connecting":   ("Connecting",   _AMBER),
        "live":         ("Live",         _GREEN),
        "reconnecting": ("Reconnecting", _AMBER),
        "error":        ("Error",        "#FF2E43"),
    }

    def __init__(self):
        super().__init__()
        self.setMinimumHeight(190)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._img, self._state, self._msg = None, "off", ""
        self._fps, self._res = 0.0, (0, 0)
        self._flash, self._toast = 0.0, ""
        self._ft = QTimer(self)
        self._ft.setInterval(16)
        self._ft.timeout.connect(_ALIRA_slot(self._tick_flash))
        self._toast_t = QTimer(self)
        self._toast_t.setSingleShot(True)
        self._toast_t.timeout.connect(_ALIRA_slot(self._clear_toast))
        self.setAccessibleName("Camera preview")

    def hasHeightForWidth(self):
        return True

    def heightForWidth(self, w):
        return int(w * 9 / 16)

    def sizeHint(self):
        return QSize(480, 270)

    def set_image(self, img: QImage):
        self._img = img
        self.update()

    def set_state(self, state: str, msg: str = ""):
        self._state, self._msg = state, msg
        if state in ("off", "error"):
            self._img = None
        self.update()

    def set_stats(self, fps: float, res):
        self._fps, self._res = fps, res
        self.update()

    def pulse(self):
        self._flash = 1.0
        if not self._ft.isActive():
            self._ft.start()

    def toast(self, text: str, ms: int = 2200):
        self._toast = text
        self._toast_t.start(ms)
        self.update()

    def _clear_toast(self):
        self._toast = ""
        self.update()

    def _tick_flash(self):
        self._flash = max(0.0, self._flash - 0.04)
        self.update()
        if self._flash <= 0.0:
            self._ft.stop()

    # ── drawing ──────────────────────────────────────────────────
    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect())
        clip = QPainterPath()
        clip.addRoundedRect(r, 16, 16)
        p.setClipPath(clip)
        p.fillRect(r, QColor(_INK))

        showing = self._img is not None and self._state in ("live", "reconnecting")
        if showing:
            iw, ih = self._img.width(), self._img.height()
            sc = max(r.width() / iw, r.height() / ih)
            sw, sh = r.width() / sc, r.height() / sc
            p.setRenderHint(QPainter.SmoothPixmapTransform, True)
            p.drawImage(r, self._img, QRectF((iw - sw) / 2, (ih - sh) / 2, sw, sh))
            for y0, y1, a0, a1 in ((0, 64, 150, 0), (r.height() - 64, r.height(), 0, 160)):
                g = QLinearGradient(0, y0, 0, y1)
                g.setColorAt(0, QColor(0, 0, 0, a0))
                g.setColorAt(1, QColor(0, 0, 0, a1))
                p.fillRect(QRectF(0, y0, r.width(), y1 - y0), g)
            if self._state == "reconnecting":
                p.fillRect(r, QColor(5, 4, 7, 150))
                self._center_text(p, r, "Camera dobara connect ho raha hai…", "Ek second…")
        else:
            self._placeholder(p, r)

        self._hud(p, r, showing)
        p.end()

    def _placeholder(self, p, r):
        title, sub = {
            "off":        ("Camera band hai", "Start dabao — phir ALIRA tumhe real mein dekh sakegi"),
            "connecting": ("Camera shuru ho raha hai…", "Pehli baar 2-3 second lag sakte hain"),
            "error":      ("Camera nahi chala", self._msg or "Dobara try karo"),
        }.get(self._state, ("Camera band hai", ""))
        col = "#FF8A98" if self._state == "error" else "#6C6975"
        pm = svg_pixmap("camera", col, 54, 1.4)
        if not pm.isNull():
            p.drawPixmap(int(r.center().x() - 27), int(r.center().y() - 66), pm)
        self._center_text(p, r, title, sub, dy=8)

    def _center_text(self, p, r, title, sub, dy=-6):
        p.setPen(QColor(T["text"]))
        p.setFont(_font(15))
        p.drawText(QRectF(r.left() + 20, r.center().y() + dy, r.width() - 40, 26), Qt.AlignHCenter | Qt.AlignVCenter, title)
        p.setPen(QColor(T["muted"]))
        p.setFont(_font(12, QFont.Normal))
        p.drawText(QRectF(r.left() + 28, r.center().y() + dy + 28, r.width() - 56, 44),
                   Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, sub)

    def _chip(self, p, x, y, text, dot=None, align_right=False):
        p.setFont(_font(11))
        fm = p.fontMetrics()
        w = fm.horizontalAdvance(text) + (34 if dot else 22)
        if align_right:
            x = x - w
        box = QRectF(x, y, w, 26)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 150))
        p.drawRoundedRect(box, 13, 13)
        tx = x + 11
        if dot:
            p.setBrush(QColor(dot))
            p.drawEllipse(QPointF(x + 14, y + 13), 4.2, 4.2)
            tx = x + 25
        p.setPen(QColor(T["text"]))
        p.drawText(QRectF(tx, y, w, 26), Qt.AlignLeft | Qt.AlignVCenter, text)

    def _hud(self, p, r, showing):
        label, col = self._STATES.get(self._state, self._STATES["off"])
        self._chip(p, 14, 14, label, col)
        if showing and self._fps > 0:
            res = f"{self._res[0]}×{self._res[1]} · " if self._res[0] else ""
            self._chip(p, r.width() - 14, 14, f"{res}{self._fps:.0f} fps", None, True)

        # corner brackets — flash = ALIRA ko frame gaya
        if showing:
            a = int(95 + 160 * self._flash)
            pen = QPen(QColor(255, 46, 67, a), 2.6 + 1.2 * self._flash)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            m, L = 16.0, 24.0
            x0, y0, x1, y1 = m, m + 34, r.width() - m, r.height() - m
            for (cx, cy, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
                path = QPainterPath(QPointF(cx + dx * L, cy))
                path.lineTo(cx, cy)
                path.lineTo(cx, cy + dy * L)
                p.drawPath(path)
            if self._flash > 0.05:
                self._chip_center(p, r, "ALIRA ne frame dekha", int(255 * min(1.0, self._flash * 1.6)))

        if self._toast:
            self._chip_center(p, r, self._toast, 255)

    def _chip_center(self, p, r, text, alpha):
        p.save()
        p.setOpacity(alpha / 255.0)
        p.setFont(_font(12))
        w = p.fontMetrics().horizontalAdvance(text) + 28
        box = QRectF(r.center().x() - w / 2, r.height() - 52, w, 30)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 46, 67, 215))
        p.drawRoundedRect(box, 15, 15)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(box, Qt.AlignCenter, text)
        p.restore()


# ══════════════════════════════════════════════════════════════════
# UI — TOGGLE SWITCH (keyboard accessible)
# ══════════════════════════════════════════════════════════════════
class ToggleSwitch(QWidget):
    toggled = pyqtSignal(bool)

    def __init__(self, checked=False, name="toggle"):
        super().__init__()
        self.setFixedSize(48, 28)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAccessibleName(name)
        self._on  = checked
        self._pos = 1.0 if checked else 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(140)
        self._anim.valueChanged.connect(_ALIRA_slot(self._set_pos))

    def _set_pos(self, v):
        self._pos = float(v)
        self.update()

    def isChecked(self):
        return self._on

    def setChecked(self, on: bool, emit=False):
        if on == self._on:
            return
        self._on = on
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()
        if emit:
            self.toggled.emit(on)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.pos()):
            self.setChecked(not self._on, True)

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            self.setChecked(not self._on, True)
        else:
            super().keyPressEvent(e)

    def paintEvent(self, _e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        off, on = QColor(255, 255, 255, 36), QColor(T["red"])
        t = self._pos
        c = QColor(int(off.red() + (on.red() - off.red()) * t), int(off.green() + (on.green() - off.green()) * t),
                   int(off.blue() + (on.blue() - off.blue()) * t), int(off.alpha() + (255 - off.alpha()) * t))
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawRoundedRect(QRectF(1, 3, 46, 22), 11, 11)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QPointF(13 + 22 * t, 14), 8.5, 8.5)
        if self.hasFocus():
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(QColor("#FFFFFF"), 1.6))
            p.drawRoundedRect(QRectF(0.8, 2.2, 46.4, 23.6), 12, 12)


# ══════════════════════════════════════════════════════════════════
# UI — PANEL
# ══════════════════════════════════════════════════════════════════
class CameraVisionPanel(QWidget):
    """
    ┌──────────────────────────────────────┐
    │ ● Live                    28 fps     │  viewfinder (16:9, HUD)
    │            (live preview)            │
    └──────────────────────────────────────┘
    [  Start camera  ] [ Describe ] [ Photo ]
    Auto-vision ........................ (o)
    Frame speed ........ [Slow|Normal|Fast]
    Mirror preview ..................... (o)
    Camera #0 ............................ [Badlo]
    28 fps | 1280×720 | ALIRA ko 12 frame bheje
    """

    sig_describe_now = pyqtSignal()
    sig_auto_toggle  = pyqtSignal(bool)

    _SPEEDS = {"slow": 0.2, "normal": 0.5, "fast": 1.0}

    def __init__(self, camera_manager: CameraVisionManager, parent=None):
        super().__init__(parent)
        self._mgr    = camera_manager
        self._active = False
        self._build_ui()
        self._connect_signals()
        self._set_active(False)

    # ── build ────────────────────────────────────────────────────
    def _build_ui(self):
        self.setStyleSheet("background:transparent;")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        self._view = CameraView()
        root.addWidget(self._view)

        # actions
        row = QHBoxLayout()
        row.setSpacing(10)
        self._start_btn    = pill("Start camera", "play", "primary", 42)
        self._describe_btn = pill("Describe", "sparkle", "ghost", 42)
        self._snap_btn     = pill("Photo lo", "image", "ghost", 42)
        self._start_btn.setAccessibleName("Camera start ya stop")
        self._describe_btn.setAccessibleName("ALIRA ko abhi ka frame dikhao")
        self._snap_btn.setAccessibleName("Photo save karo")
        for b in (self._describe_btn, self._snap_btn):
            b.setStyleSheet(b.styleSheet() + "QPushButton:disabled{color:rgba(255,255,255,0.28);}")
        row.addWidget(self._start_btn, 2)
        row.addWidget(self._describe_btn, 1)
        row.addWidget(self._snap_btn, 1)
        root.addLayout(row)

        # settings
        box = QFrame()
        box.setObjectName("camset")
        box.setStyleSheet(f"QFrame#camset{{background:rgba(255,255,255,0.035);"
                          f"border:1px solid rgba(255,255,255,0.08);border-radius:14px;}}")
        bl = QVBoxLayout(box)
        bl.setContentsMargins(16, 6, 16, 6)
        bl.setSpacing(0)

        self._auto_sw = ToggleSwitch(True, "Auto-vision")
        self._mirror_sw = ToggleSwitch(True, "Mirror preview")
        self._speed = Segmented([("slow", "Slow"), ("normal", "Normal"), ("fast", "Fast")], "normal")
        self._cam_lbl_sub = QLabel("Auto")
        self._cam_btn = pill("Badlo", "refresh", "ghost", 34)
        self._cam_btn.setAccessibleName("Dusra camera chuno")

        bl.addLayout(self._setting("Auto-vision", "ALIRA ko frames khud bhejte raho", self._auto_sw))
        bl.addLayout(self._setting("Frame speed", "Slow 5s · Normal 2s · Fast 1s", self._speed))
        bl.addLayout(self._setting("Mirror preview", "Sirf tumhe ulta dikhega — ALIRA ko asli frame jaata hai", self._mirror_sw))
        bl.addLayout(self._setting("Camera", None, self._cam_btn, sub_label=self._cam_lbl_sub))
        root.addWidget(box)

        # stats
        sr = QHBoxLayout()
        sr.setSpacing(10)
        self._st_fps  = self._stat("—", "fps")
        self._st_res  = self._stat("—", "resolution")
        self._st_sent = self._stat("0", "ALIRA ko bheje")
        for w in (self._st_fps, self._st_res, self._st_sent):
            sr.addWidget(w["frame"], 1)
        root.addLayout(sr)
        root.addStretch(1)

    def _setting(self, title, sub, widget, sub_label=None):
        h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(12)
        col = QVBoxLayout()
        col.setSpacing(1)
        t = QLabel(title)
        t.setStyleSheet(f"color:{T['text']};{F(500, 13)}background:transparent;")
        s = sub_label or QLabel(sub or "")
        s.setStyleSheet(f"color:{T['dim']};{F(400, 11)}background:transparent;")
        s.setWordWrap(True)
        for lb in (t, s):
            lb.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        col.addStretch(1)
        col.addWidget(t)
        col.addWidget(s)
        col.addStretch(1)
        h.addLayout(col, 1)
        h.addWidget(widget, 0, Qt.AlignRight | Qt.AlignVCenter)
        wrap = QWidget()
        wrap.setMinimumHeight(52)
        wrap.setLayout(h)
        wrap.setStyleSheet("background:transparent;")
        out = QVBoxLayout()
        out.setContentsMargins(0, 0, 0, 0)
        out.setSpacing(0)
        out.addWidget(wrap)
        return out

    def _stat(self, value, caption):
        f = QFrame()
        f.setStyleSheet("QFrame{background:rgba(255,255,255,0.035);border:1px solid rgba(255,255,255,0.08);border-radius:12px;}")
        v = QVBoxLayout(f)
        v.setContentsMargins(12, 8, 12, 8)
        v.setSpacing(0)
        val = QLabel(value)
        val.setStyleSheet(f"color:{T['text']};{F(600, 15)}background:transparent;border:none;")
        cap = QLabel(caption)
        cap.setStyleSheet(f"color:{T['dim']};{F(400, 11)}background:transparent;border:none;")
        v.addWidget(val)
        v.addWidget(cap)
        return {"frame": f, "val": val, "cap": cap}

    # ── signals ──────────────────────────────────────────────────
    def _connect_signals(self):
        m = self._mgr
        self._start_btn.clicked.connect(_ALIRA_slot(self._on_toggle))
        self._describe_btn.clicked.connect(_ALIRA_slot(self.sig_describe_now))
        self._snap_btn.clicked.connect(_ALIRA_slot(self._on_snapshot))
        self._auto_sw.toggled.connect(_ALIRA_slot(self._on_auto))
        self._mirror_sw.toggled.connect(_ALIRA_slot(m.set_mirror))
        self._speed.changed.connect(self._on_speed)
        self._cam_btn.clicked.connect(_ALIRA_slot(self._on_cam_next))

        m.sig_preview_frame.connect(self._view.set_image)
        m.sig_state.connect(self._on_state)
        m.sig_started.connect(lambda: self._set_active(True))
        m.sig_stopped.connect(lambda: self._set_active(False))
        m.sig_error.connect(lambda e: self._view.set_state("error", e))
        m.sig_stats.connect(self._on_stats)
        m.sig_frame_sent.connect(self._view.pulse)
        m.sig_snapshot.connect(lambda path: self._view.toast("Photo save hui — Pictures/ALIRA Camera"))

    # ── handlers ─────────────────────────────────────────────────
    def _on_toggle(self):
        self._mgr.stop() if self._mgr.is_active else self._mgr.start()

    def _on_auto(self, on: bool):
        self._mgr.set_auto_vision(on)
        self.sig_auto_toggle.emit(on)

    def _on_speed(self, key: str):
        self._speed.set_current(key)
        self._mgr.set_vision_fps(self._SPEEDS[key])

    def _on_snapshot(self):
        if not self._mgr.snapshot():
            self._view.toast("Abhi frame nahi mila")

    def _on_cam_next(self):
        cur = self._mgr.camera_index
        nxt = 0 if cur is None else (cur + 1) % 4
        self._cam_lbl_sub.setText(f"Camera #{nxt}")
        self._mgr.set_camera_index(nxt)

    def _on_state(self, state: str):
        self._view.set_state(state, self._view._msg if state == "error" else "")
        if state == "live" and self._mgr.camera_index is not None:
            self._cam_lbl_sub.setText(f"Camera #{self._mgr.camera_index}")

    def _on_stats(self, fps, sent, ago, w, h):
        self._view.set_stats(fps, (w, h))
        self._st_fps["val"].setText(f"{fps:.0f}" if fps else "—")
        self._st_res["val"].setText(f"{w}×{h}" if w else "—")
        self._st_sent["val"].setText(str(sent))
        self._st_sent["cap"].setText("ALIRA ko bheje" if ago < 0 else f"ALIRA ko bheje · {int(ago)}s pehle")

    def _set_active(self, on: bool):
        self._active = on
        self._describe_btn.setEnabled(on)
        self._snap_btn.setEnabled(on)
        self._start_btn.setText("  Stop camera" if on else "  Start camera")
        self._start_btn.setIcon(svg_icon("square" if on else "play", "#FFFFFF", 18, 1.6))
        if not on:
            for k in (self._st_fps, self._st_res):
                k["val"].setText("—")


# ══════════════════════════════════════════════════════════════════
# GEMINI FRAME INJECTOR — vision frames bhejo WS mein
# ══════════════════════════════════════════════════════════════════
class VisionFrameInjector:
    """Camera vision frames ko Gemini WebSocket mein inject karta hai"""

    def __init__(self, get_ws_func: Callable, get_loop_func: Callable):
        self._get_ws   = get_ws_func
        self._get_loop = get_loop_func

    def push_frame(self, b64_jpeg: str):
        ws   = self._get_ws()
        loop = self._get_loop()
        if not ws or not loop:
            return
        msg = {
            "realtimeInput": {
                "video": {"mimeType": "image/jpeg", "data": b64_jpeg}
            }
        }
        asyncio.run_coroutine_threadsafe(
            self._send(ws, json.dumps(msg).encode()), loop
        )

    def send_camera_start_notify(self):
        ws   = self._get_ws()
        loop = self._get_loop()
        if not ws or not loop:
            return
        txt = {
            "clientContent": {
                "turns": [{"role": "user", "parts": [{"text":
                    "User ne camera vision ON kar di hai. "
                    "Ab tum camera se real-time frames dekh sakti ho. "
                    "Khushi se respond karo: 'Main ab tumhari camera se dekh sakti hoon!' "
                    "Har frame mein jo bhi dikh raha ho usse describe karo — "
                    "objects, text, logo, chehra, environment, colors sab batao."
                }]}],
                "turnComplete": True
            }
        }
        asyncio.run_coroutine_threadsafe(
            self._send(ws, json.dumps(txt).encode()), loop
        )

    def send_camera_stop_notify(self):
        ws   = self._get_ws()
        loop = self._get_loop()
        if not ws or not loop:
            return
        txt = {
            "clientContent": {
                "turns": [{"role": "user", "parts": [{"text":
                    "Camera band ho gayi. Normal conversation mode mein aao."
                }]}],
                "turnComplete": True
            }
        }
        asyncio.run_coroutine_threadsafe(
            self._send(ws, json.dumps(txt).encode()), loop
        )

    async def _send(self, ws, data: bytes):
        try:
            await ws.send(data)
        except Exception as e:
            print(f"[VisionInjector] Error: {e}")
