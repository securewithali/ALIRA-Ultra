# -*- coding: utf-8 -*-
"""
ALIRA Screen Guardian — ALIRA screen dekhti rehti hai aur kuch GALAT dikhe to bolti hai.

    g = ScreenGuardian(busy_fn=lambda: False)
    g.sig_alert.connect(lambda text: ...)      # "Sir, ..." — bolne/dikhane ke liye
    g.start()  /  g.stop()

Kaise kaam karta hai:
  * Har ~45 sec mein (sirf tab jab screen badli ho) primary screen ka frame Gemini ko bheja jaata hai.
  * Gemini ko bola gaya hai: sirf CLEAR galti par 1-2 vakya mein batao (error message, typo wala command,
    failed build/test, phishing/scam page, galat form field, risky dialog) — warna sirf "OK".
  * Same chetawani dobara nahi; do chetawaniyon ke beech cooldown.

Privacy (zaroori):
  * Opt-in — Settings / orb menu / pehli baar ke setup dialog se ON hota hai. Default OFF.
  * Password manager, banking, private/incognito window ya "password"/"OTP" title wali window par
    frame bheja hi nahi jaata.
  * ALIRA ki apni window dikh rahi ho ya screen share ON ho to skip.
  * Prompt mein bola gaya hai ki password/card/OTP kabhi repeat na karo.
"""

import ctypes
import re
import threading
import time
from typing import Callable, Optional

from PyQt5.QtCore import QObject, pyqtSignal

import ALIRA_prefs as prefs

try:
    import mss
    _HAS_MSS = True
except Exception:
    _HAS_MSS = False

SENSITIVE_TITLE = re.compile(
    r"(password|passcode|bitwarden|1password|keepass|lastpass|dashlane|\botp\b|verification code|"
    r"netbanking|net banking|bank|paypal|upi|credit card|debit card|wallet|incognito|inprivate|private browsing)",
    re.I)

PROMPT = (
    "Tum ALIRA ho — user ki screen dekhkar madad karne wali assistant. Screenshot dekho.\n"
    "Agar screen par koi CLEAR galti ya problem dikh rahi hai — jaise error/exception message, galat spelling "
    "wala command ya code (typo), failed build/test, 'not found'/'permission denied', phishing ya scam jaisa page, "
    "form mein galat/khaali zaroori field, risky ya shaky dialog (jaise anjaan file install) — to SIRF tab 1-2 chhote "
    "vakyon mein Hinglish mein batao: kya galat hai aur kaise theek karein. 'Sir,' se shuru karo.\n"
    "Agar sab theek hai, ya kuch clear nahi dikh raha, ya sirf normal kaam ho raha hai — sirf ek shabd likho: OK\n"
    "Kabhi andaza mat lagao, sirf wahi jo screen par saaf dikh raha ho. Password, OTP, card number ya private "
    "baat kabhi repeat mat karo. Jawab 40 shabdon se chhota rakho."
)


def _foreground_title() -> str:
    try:
        buf = ctypes.create_unicode_buffer(512)
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
        return buf.value.strip()
    except Exception:
        return ""


class ScreenGuardian(QObject):
    sig_alert = pyqtSignal(str)       # chetawani ka text
    sig_state = pyqtSignal(str)       # off / watching / analyzing / paused

    MAX_W = 1280

    def __init__(self, busy_fn: Optional[Callable[[], bool]] = None, api_key_fn: Optional[Callable[[], str]] = None):
        super().__init__()
        self._busy = busy_fn or (lambda: False)
        self._key = api_key_fn
        self._run = False
        self._thread: Optional[threading.Thread] = None
        self._wake = threading.Event()
        self._prev_fp = None
        self._last_alert = 0.0
        self._recent = []              # pichli chetawaniyon ki chhoti-si list (dedupe)
        self.checks = 0
        self.alerts = 0

    @property
    def is_running(self) -> bool:
        return self._run

    def interval(self) -> int:
        return prefs.clamp(prefs.get("guardian_interval", 45), 15, 300)

    def start(self):
        if self._run:
            return
        self._run = True
        self._wake.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="ALIRA-guardian")
        self._thread.start()
        self.sig_state.emit("watching")

    def stop(self):
        self._run = False
        self._wake.set()
        self.sig_state.emit("off")

    # ── capture ──────────────────────────────────────────────────
    def _grab_jpeg(self):
        import cv2
        import numpy as np
        with mss.mss() as sct:
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            bgr = np.asarray(sct.grab(mon))[:, :, :3]
        small = cv2.cvtColor(cv2.resize(bgr, (64, 36), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY).astype("int16")
        h, w = bgr.shape[:2]
        if w > self.MAX_W:
            bgr = cv2.resize(bgr, (self.MAX_W, int(h * self.MAX_W / w)), interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", bgr, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return (buf.tobytes() if ok else b""), small

    # ── analysis ─────────────────────────────────────────────────
    def analyze_jpeg(self, jpeg: bytes) -> Optional[str]:
        """Gemini se pucho. Chetawani ka text return karta hai, ya None (sab theek)."""
        import base64
        from TABBU_modules import gemini_rest as gr
        who = prefs.user_name() or "Sir"
        payload = {
            "contents": [{"role": "user", "parts": [
                {"text": PROMPT.replace("'Sir,'", f"'{who},'")},
                {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(jpeg).decode()}},
            ]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 160},
        }
        key = self._key() if self._key else None
        data, _model = gr.generate(payload, api_key=key or None, timeout=30)
        text = gr.text_of(data).strip()
        if not text or text.upper().startswith("OK") or len(text) < 8:
            return None
        return text

    def _is_duplicate(self, text: str) -> bool:
        k = re.sub(r"[^a-z0-9 ]", "", text.lower())[:70]
        for r in self._recent:
            if r == k or (len(k) > 20 and (k[:35] in r or r[:35] in k)):
                return True
        return False

    def _loop(self):
        while self._run:
            self._wake.wait(self.interval())
            self._wake.clear()
            if not self._run:
                break
            try:
                self._tick()
            except Exception as e:
                print(f"[Guardian] {type(e).__name__}: {e}")

    def _tick(self):
        if not _HAS_MSS:
            return
        title = _foreground_title()
        if (self._busy() or SENSITIVE_TITLE.search(title) or title.startswith("ALIRA")
                or time.time() - self._last_alert < 120):
            self.sig_state.emit("paused")
            return
        jpeg, fp = self._grab_jpeg()
        if not jpeg:
            return
        if self._prev_fp is not None and float(abs(fp - self._prev_fp).mean()) < 2.0:
            self.sig_state.emit("watching")
            return                                  # screen badli hi nahi — API call bachao
        self._prev_fp = fp
        self.sig_state.emit("analyzing")
        self.checks += 1
        msg = self.analyze_jpeg(jpeg)
        self.sig_state.emit("watching")
        if msg and not self._is_duplicate(msg):
            self._recent = (self._recent + [re.sub(r"[^a-z0-9 ]", "", msg.lower())[:70]])[-8:]
            self._last_alert = time.time()
            self.alerts += 1
            self.sig_alert.emit(msg)
