# -*- coding: utf-8 -*-
"""
ALIRA Screen Share Module
========================
Real-time screen capture + Gemini AI vision integration.

Features:
  ✅ Screen capture via mss (fast, cross-platform)
  ✅ Fallback: PIL ImageGrab
  ✅ Realtime frame send to Gemini via WebSocket (base64 JPEG)
  ✅ PyQt5 signals for UI integration
  ✅ Overlay window showing capture region
  ✅ Auto-notify AI when screen share starts
  ✅ FPS throttle — 1 frame/sec default (API rate limit safe)
"""

import base64
import io
import json
import threading
import time
from typing import Optional, Callable

import numpy as np
from PyQt5.QtCore import QObject, QThread, pyqtSignal, QRect, Qt, QTimer
from PyQt5.QtGui import QColor, QPainter, QPen, QFont
from PyQt5.QtWidgets import QWidget, QApplication

# ── Try fast capture lib first ─────────────────────────────────
try:
    import mss
    _HAS_MSS = True
except ImportError:
    _HAS_MSS = False
    print("[ScreenShare] mss not found — pip install mss  (fallback: PIL)")

try:
    from PIL import ImageGrab, Image
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False
    print("[ScreenShare] PIL not found — pip install Pillow")

# ══════════════════════════════════════════════════════════════
# SCREEN SHARE OVERLAY — compat shim
# Purana pulsing-cyan overlay hata diya: wo khud screen frames mein capture ho jata tha aur
# poori screen ka translucent window 16 fps repaint karta tha. Ab border/badge
# ALIRA_edge_glow.EdgeGlow se aata hai (patli strips, capture se bahar, rang-birangi).
# ══════════════════════════════════════════════════════════════
class ScreenShareOverlay:
    def __init__(self):
        self._glow = None

    def show_on_screen(self):
        try:
            from ALIRA_edge_glow import EdgeGlow
            self._glow = EdgeGlow()
            self._glow.set_mode("screenshare")
        except Exception as e:
            print(f"[ScreenShare] overlay: {e}")

    def close(self):
        if self._glow:
            self._glow.set_mode(None)
            self._glow = None


# ══════════════════════════════════════════════════════════════
# SCREEN CAPTURE THREAD
# ══════════════════════════════════════════════════════════════
class ScreenCaptureThread(QThread):
    """
    Background thread: primary screen capture -> 1280px JPEG -> base64.

    FIX (lag): pehle har frame naya mss.mss() banta tha, full-resolution (bina resize) JPEG ban-ta tha,
    aur stop par GUI 3 sec rukta tha. Ab: ek mss instance, cv2 se downscale, bina badlav wali
    screen skip (har 5 sec mein ek baar fir bhi bhejta hai), stop non-blocking.
    """
    frame_ready   = pyqtSignal(str)    # base64 JPEG string
    capture_error = pyqtSignal(str)

    MAX_W        = 1280
    KEEPALIVE_S  = 5.0     # screen na badle tab bhi itne sec mein ek frame

    def __init__(self, fps: float = 1.0):
        super().__init__()
        self._fps      = fps
        self._running  = False
        self._interval = 1.0 / fps
        self._quality  = 70   # JPEG quality — lower = smaller = faster API
        self.sent      = 0
        self.skipped   = 0

    def set_fps(self, fps: float):
        self._fps      = fps
        self._interval = 1.0 / fps

    def set_quality(self, q: int):
        self._quality = q

    def start_capture(self):
        self._running = True
        self.start()

    def request_stop(self):
        self._running = False

    def stop_capture(self, timeout_ms: int = 1500) -> bool:
        self._running = False
        return self.wait(timeout_ms)

    def _encode(self, rgb_or_bgr, is_bgr: bool) -> bytes:
        import cv2
        h, w = rgb_or_bgr.shape[:2]
        if w > self.MAX_W:
            rgb_or_bgr = cv2.resize(rgb_or_bgr, (self.MAX_W, int(h * self.MAX_W / w)), interpolation=cv2.INTER_AREA)
        if not is_bgr:
            rgb_or_bgr = cv2.cvtColor(rgb_or_bgr, cv2.COLOR_RGB2BGR)
        ok, buf = cv2.imencode(".jpg", rgb_or_bgr, [cv2.IMWRITE_JPEG_QUALITY, self._quality])
        return buf.tobytes() if ok else b""

    @staticmethod
    def _fingerprint(bgr):
        import cv2
        return cv2.cvtColor(cv2.resize(bgr, (64, 36), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype("int16")

    def run(self):
        print("[ScreenShare] Capture thread started")
        sct = None
        prev_fp, last_sent = None, 0.0
        try:
            if _HAS_MSS:
                sct = mss.mss()                     # mss instance usi thread mein banana zaroori hai
            while self._running:
                t_start = time.monotonic()
                try:
                    if sct is not None:
                        mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]   # primary screen
                        bgr = np.asarray(sct.grab(mon))[:, :, :3]
                        is_bgr = True
                    elif _HAS_PIL:
                        bgr = np.asarray(ImageGrab.grab().convert("RGB"))
                        is_bgr = False
                    else:
                        self.capture_error.emit("Screen capture lib missing — pip install mss pillow")
                        time.sleep(2)
                        continue

                    # bina badlav wali screen mat bhejo (API/bandwidth/lag bachta hai)
                    probe = bgr if is_bgr else np.ascontiguousarray(bgr[:, :, ::-1])
                    fp = self._fingerprint(probe)
                    now = time.monotonic()
                    changed = prev_fp is None or float(abs(fp - prev_fp).mean()) > 0.8
                    if changed or (now - last_sent) >= self.KEEPALIVE_S:
                        prev_fp, last_sent = fp, now
                        data = self._encode(bgr, is_bgr)
                        if data:
                            self.sent += 1
                            self.frame_ready.emit(base64.b64encode(data).decode("utf-8"))
                    else:
                        self.skipped += 1
                except Exception as e:
                    print(f"[ScreenShare] Capture error: {e}")
                    self.capture_error.emit(str(e)[:80])
                    time.sleep(1)

                # sleep chhote tukdon mein — stop turant sune
                end = t_start + self._interval
                while self._running and time.monotonic() < end:
                    time.sleep(0.05)
        finally:
            if sct is not None:
                try:
                    sct.close()
                except Exception:
                    pass
        print(f"[ScreenShare] Capture thread stopped (sent {self.sent}, skipped {self.skipped} unchanged)")


# ══════════════════════════════════════════════════════════════
# SCREEN SHARE MANAGER — Main controller
# ══════════════════════════════════════════════════════════════
class ScreenShareManager(QObject):
    """
    Screen sharing ka complete manager.

    Signals:
        sig_frame_ready(str)    — base64 JPEG frame (send to Gemini)
        sig_started()           — screen share shuru hua
        sig_stopped()           — screen share band hua
        sig_error(str)          — koi error aayi
        sig_status(str)         — status message for UI

    Border/badge ab TABBU.py mein EdgeGlow se control hota hai (mode "screenshare").
    """
    sig_frame_ready = pyqtSignal(str)   # base64 JPEG
    sig_started     = pyqtSignal()
    sig_stopped     = pyqtSignal()
    sig_error       = pyqtSignal(str)
    sig_status      = pyqtSignal(str)

    def __init__(self, fps: float = 1.0):
        super().__init__()
        self._fps         = fps
        self._active      = False
        self._overlay     = None
        self._capture_thr = None
        self._dying       = []
        self._frame_count = 0
        self._start_time  = 0.0

    @property
    def is_active(self) -> bool:
        return self._active

    def start(self):
        if self._active:
            return
        if not _HAS_MSS and not _HAS_PIL:
            self.sig_error.emit("Screen capture not available.\nRun: pip install mss pillow")
            return
        for t in list(self._dying):                 # purana thread khatam ho le
            t.wait(1500)

        self._active      = True
        self._frame_count = 0
        self._start_time  = time.monotonic()

        th = ScreenCaptureThread(fps=self._fps)
        th.frame_ready.connect(lambda b, t=th: self._on_frame(t, b))
        th.capture_error.connect(self._on_error)
        self._capture_thr = th
        th.start_capture()

        self.sig_started.emit()
        self.sig_status.emit("🖥️  Screen sharing ACTIVE")
        print(f"[ScreenShare] Started at {self._fps} fps")

    def stop(self):
        """Non-blocking — GUI nahi rukta."""
        if not self._active:
            return
        self._active = False

        th, self._capture_thr = self._capture_thr, None
        if th:
            th.request_stop()
            self._dying.append(th)
            th.finished.connect(lambda t=th: self._dying.remove(t) if t in self._dying else None)

        elapsed = time.monotonic() - self._start_time
        self.sig_stopped.emit()
        self.sig_status.emit(f"🖥️  Screen sharing stopped ({self._frame_count} frames, {elapsed:.0f}s)")
        print(f"[ScreenShare] Stopped — {self._frame_count} frames in {elapsed:.1f}s")

    def shutdown(self):
        """App band hote waqt: stop + thread khatam hone ka intezaar."""
        self.stop()
        for t in list(self._dying):
            t.wait(1500)

    def toggle(self):
        if self._active:
            self.stop()
        else:
            self.start()

    def set_fps(self, fps: float):
        self._fps = fps
        if self._capture_thr:
            self._capture_thr.set_fps(fps)

    def _on_frame(self, thread, b64: str):
        if thread is not self._capture_thr:
            return
        self._frame_count += 1
        self.sig_frame_ready.emit(b64)

    def _on_error(self, err: str):
        print(f"[ScreenShare] Error: {err}")
        self.sig_error.emit(err)


# ══════════════════════════════════════════════════════════════
# SCREEN SHARE BUTTON WIDGET
# ══════════════════════════════════════════════════════════════
from PyQt5.QtWidgets import QPushButton

class ScreenShareButton(QPushButton):
    """
    Ready-made styled button — ALIRA ke dark UI ke liye.
    States: Off (cyan outline) / On (glowing red border — recording)
    """
    def __init__(self, parent=None):
        super().__init__("🖥️  Share Screen", parent)
        self.setFixedSize(112, 36)
        self.setCursor(Qt.PointingHandCursor)
        self._sharing = False
        self._apply_style_off()

    def set_sharing(self, on: bool):
        self._sharing = on
        if on:
            self._apply_style_on()
        else:
            self._apply_style_off()

    def _apply_style_off(self):
        self.setText("🖥️  Share Screen")
        self.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #041820, stop:0.5 #062838, stop:1 #041820);
                border: 1px solid rgba(0,200,255,0.45);
                border-radius: 18px;
                color: #00CCFF;
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 0.3px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #083050, stop:0.5 #0A4060, stop:1 #083050);
                border: 1px solid rgba(0,220,255,0.80);
                color: #00EEFF;
            }
            QPushButton:pressed {
                background: #041820;
                border: 1px solid rgba(0,180,220,0.30);
            }
        """)

    def _apply_style_on(self):
        self.setText("⏹️  Stop Sharing")
        self.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #200408, stop:0.5 #380A10, stop:1 #200408);
                border: 1px solid rgba(255,60,80,0.75);
                border-radius: 18px;
                color: #FF4455;
                font-size: 10px;
                font-weight: bold;
                letter-spacing: 0.3px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #400810, stop:0.5 #601020, stop:1 #400810);
                border: 1px solid rgba(255,80,100,0.95);
                color: #FF6677;
            }
            QPushButton:pressed {
                background: #200408;
            }
        """)


# ══════════════════════════════════════════════════════════════
# GEMINI SCREEN FRAME SENDER — WS mein inject karta hai
# ══════════════════════════════════════════════════════════════
import asyncio

class ScreenFrameSender:
    """
    ScreenShareManager ke frames ko Gemini WebSocket mein
    bhejna — existing GeminiWorker ke loop ke saath compatible.
    """
    def __init__(self, get_ws_func: Callable, get_loop_func: Callable):
        """
        get_ws_func   — callable jo current websocket return kare
        get_loop_func — callable jo asyncio loop return kare
        """
        self._get_ws   = get_ws_func
        self._get_loop = get_loop_func
        self._frame_q  = []
        self._lock     = threading.Lock()

    def push_frame(self, b64_jpeg: str):
        """Screen frame queue mein daalo"""
        ws   = self._get_ws()
        loop = self._get_loop()
        if ws is None or loop is None:
            return
        msg = {
            "realtimeInput": {
                "video": {
                    "mimeType": "image/jpeg",
                    "data": b64_jpeg
                }
            }
        }
        asyncio.run_coroutine_threadsafe(
            self._safe_send(ws, json.dumps(msg).encode()),
            loop
        )

    async def _safe_send(self, ws, data: bytes):
        try:
            await ws.send(data)
        except Exception as e:
            print(f"[ScreenSender] Send failed: {e}")

    def send_screen_start_notify(self, text_prompt: str = None):
        """
        AI ko inform karo ki screen sharing shuru ho gayi —
        ek text message bhejo taaki AI context samjhe.
        """
        ws   = self._get_ws()
        loop = self._get_loop()
        if ws is None or loop is None:
            return
        msg_text = text_prompt or (
            "User ne screen sharing ON kar di hai. "
            "Ab tum user ki screen real-time mein dekh sakti ho. "
            "Jo bhi screen pe chal raha hai uske baare mein helpful commentary do. "
            "User ke questions ka jawab screen context ke saath do. "
            "Pehle ek baar bolo ki 'Main ab tumhari screen dekh sakti hoon!'"
        )
        msg = {
            "clientContent": {
                "turns": [{"role": "user", "parts": [{"text": msg_text}]}],
                "turnComplete": True
            }
        }
        asyncio.run_coroutine_threadsafe(
            self._safe_send(ws, json.dumps(msg).encode()),
            loop
        )

    def send_screen_stop_notify(self):
        """AI ko batao ki screen sharing band ho gayi"""
        ws   = self._get_ws()
        loop = self._get_loop()
        if ws is None or loop is None:
            return
        msg = {
            "clientContent": {
                "turns": [{"role": "user", "parts": [{"text":
                    "Screen sharing band ho gayi. Ab normal conversation mode mein aao."
                }]}],
                "turnComplete": True
            }
        }
        asyncio.run_coroutine_threadsafe(
            self._safe_send(ws, json.dumps(msg).encode()),
            loop
        )