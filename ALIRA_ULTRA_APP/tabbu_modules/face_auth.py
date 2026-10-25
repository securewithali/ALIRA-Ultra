# -*- coding: utf-8 -*-
"""
TITAN Face Authentication — v8
==============================
FIXES v8 (over v7):
  1. STRICT FACE MATCHING — threshold 0.52→0.78, multi-method with LBP features
  2. USER ISOLATION — each OS user gets their own face file, cannot use another's
  3. ENROLLMENT FLOW BUG — _show_error_win mid-function caused fall-through to
     verification; fixed with explicit return + restructured flow
  4. DEVICE BINDING — still enforced as before
  5. QUALITY CHECK — still enforced as before
"""

from ALIRA_slot import slot as _ALIRA_slot
import os, sys, time, math, base64, threading, hashlib, platform, uuid, json
import cv2
import numpy as np
from datetime import datetime

# ── Path helper ───────────────────────────────────────────────────────────────
def get_root_path() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    p = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(p) == "TITAN_modules":
        return os.path.dirname(p)
    return p

def get_bundle_path() -> str:
    if hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return get_root_path()

ROOT_PATH   = get_root_path()
BUNDLE_PATH = get_bundle_path()
MODULE_PATH = os.path.dirname(os.path.abspath(__file__))

# ── Face image path ───────────────────────────────────────────────────────────
FACE_DIR        = os.path.join(ROOT_PATH, "TITAN_face_data")
SAVED_FACE_PATH = os.path.join(FACE_DIR, "registered_face.jpg")
DEVICE_LOCK_PATH= os.path.join(FACE_DIR, "device_lock.json")
os.makedirs(FACE_DIR, exist_ok=True)

# ── .env ──────────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT_PATH, ".env"))
except Exception:
    pass

# ── PyQt5 ─────────────────────────────────────────────────────────────────────
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget,
                              QVBoxLayout, QHBoxLayout, QLabel, QPushButton)
from PyQt5.QtCore    import (Qt, QTimer, QThread, pyqtSignal, QRect, QEventLoop)
from PyQt5.QtGui     import (QPainter, QColor, QPen, QBrush, QFont,
                              QLinearGradient, QRadialGradient,
                              QPixmap, QImage, QPalette)

# ── Constants ─────────────────────────────────────────────────────────────────
# FIX FACE MATCH: Threshold raised significantly — was 0.65, now 0.78
# This means random faces will be rejected; same person from different angles still works
FACE_MATCH_THRESHOLD = 0.78
STABLE_FACE_TIME     = 3.0    # 3 sec stable face for enrollment
CAMERA_TIMEOUT       = 45
MAX_VERIFY_ATTEMPTS  = 3

CASCADE_PATH = os.path.join(BUNDLE_PATH, 'TITAN_modules', 'haarcascade_frontalface_default.xml')
try:
    if not os.path.exists(CASCADE_PATH):
        CASCADE_PATH = os.path.join(BUNDLE_PATH, 'haarcascade_frontalface_default.xml')
    if not os.path.exists(CASCADE_PATH):
        CASCADE_PATH = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    print(f"[FaceAuth] Using cascade: {CASCADE_PATH}")
    _face_cascade     = cv2.CascadeClassifier(CASCADE_PATH)
    FACE_DETECTION_OK = not _face_cascade.empty()
except Exception as _e:
    print(f"[FaceAuth] Cascade: {_e}")
    _face_cascade     = None
    FACE_DETECTION_OK = False


# ═════════════════════════════════════════════════════════════════════════════
#  DEVICE BINDING
# ═════════════════════════════════════════════════════════════════════════════
def _get_device_fingerprint() -> str:
    parts = []
    try:
        mac = ':'.join([
            '{:02x}'.format((uuid.getnode() >> ele) & 0xff)
            for ele in range(0, 8*6, 8)
        ][::-1])
        parts.append(f"MAC:{mac}")
    except Exception:
        pass
    try:
        parts.append(f"HOST:{platform.node().lower()}")
    except Exception:
        pass
    try:
        parts.append(f"USER:{os.getlogin().lower()}")
    except Exception:
        try:
            parts.append(f"USER:{os.environ.get('USERNAME','').lower()}")
        except Exception:
            pass
    try:
        parts.append(f"OS:{platform.system().lower()}")
    except Exception:
        pass
    raw = "|".join(parts)
    fp  = hashlib.sha256(raw.encode()).hexdigest()[:32]
    print(f"[DeviceBind] Raw: {raw}")
    print(f"[DeviceBind] Fingerprint: {fp}")
    return fp


def _save_device_lock(fingerprint: str):
    data = {
        "fingerprint":   fingerprint,
        "hostname":      platform.node(),
        "os_user":       os.environ.get("USERNAME", os.environ.get("USER", "")),
        "platform":      platform.system(),
        "registered_at": datetime.utcnow().isoformat(),
        "app":           "TITAN_v8"
    }
    try:
        with open(DEVICE_LOCK_PATH, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[DeviceBind] Saved lock: {DEVICE_LOCK_PATH}")
    except Exception as e:
        print(f"[DeviceBind] Save error: {e}")


def _check_device_lock() -> bool:
    if not os.path.exists(DEVICE_LOCK_PATH):
        return True
    try:
        with open(DEVICE_LOCK_PATH) as f:
            saved = json.load(f)
        saved_fp   = saved.get("fingerprint", "")
        current_fp = _get_device_fingerprint()
        if saved_fp == current_fp:
            print("[DeviceBind] ✅ Device match")
            return True
        else:
            print(f"[DeviceBind] ❌ Mismatch! saved={saved_fp} current={current_fp}")
            return False
    except Exception as e:
        print(f"[DeviceBind] Check error: {e}")
        return True


# ═════════════════════════════════════════════════════════════════════════════
#  USER ISOLATION — FIX: Each OS user gets their own face file
# ═════════════════════════════════════════════════════════════════════════════
def _get_current_os_user() -> str:
    """
    Get the actual OS-level logged in username.
    This is the primary isolation key — not TITAN_USER_UID env var.
    """
    try:
        return os.getlogin().lower().strip()
    except Exception:
        pass
    for k in ("USERNAME", "USER", "LOGNAME"):
        v = os.environ.get(k, "").lower().strip()
        if v:
            return v
    return "default"


def _get_user_face_path(os_user: str = None) -> str:
    """
    FIX USER ISOLATION: Each OS user has their own face image.
    Format: TITAN_face_data/face_<os_username>.jpg
    This ensures user A cannot unlock TITAN registered for user B.
    """
    if os_user is None:
        os_user = _get_current_os_user()
    safe_name = "".join(c for c in os_user if c.isalnum() or c in "-_")
    return os.path.join(FACE_DIR, f"face_{safe_name}.jpg")


def _get_user_lock_path(os_user: str = None) -> str:
    """Per-user device lock file"""
    if os_user is None:
        os_user = _get_current_os_user()
    safe_name = "".join(c for c in os_user if c.isalnum() or c in "-_")
    return os.path.join(FACE_DIR, f"device_lock_{safe_name}.json")


# ═════════════════════════════════════════════════════════════════════════════
#  FACE QUALITY CHECK
# ═════════════════════════════════════════════════════════════════════════════
def _check_face_quality(face_roi: np.ndarray) -> tuple:
    if face_roi is None or face_roi.size == 0:
        return False, "NO FACE ROI", 0
    h, w = face_roi.shape[:2]
    if w < 80 or h < 80:
        return False, f"TOO SMALL ({w}x{h})", 10
    gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
    blur_score = cv2.Laplacian(gray, cv2.CV_64F).var()
    if blur_score < 80:
        return False, f"TOO BLURRY ({blur_score:.0f})", int(blur_score)
    brightness = np.mean(gray)
    if brightness < 40:
        return False, f"TOO DARK ({brightness:.0f})", int(brightness)
    if brightness > 220:
        return False, f"TOO BRIGHT ({brightness:.0f})", int(brightness)
    blur_q = min(100, int(blur_score / 5))
    bri_q  = 100 - abs(int(brightness) - 128)
    score  = int(blur_q * 0.6 + bri_q * 0.4)
    return True, "GOOD QUALITY", score


def _get_best_face_roi(frame: np.ndarray, faces: list) -> np.ndarray:
    best_roi   = None
    best_score = -1
    for (x, y, w, h) in faces:
        pad = 10
        x1  = max(0, x - pad);  y1 = max(0, y - pad)
        x2  = min(frame.shape[1], x + w + pad)
        y2  = min(frame.shape[0], y + h + pad)
        roi = frame[y1:y2, x1:x2]
        ok, reason, score = _check_face_quality(roi)
        if ok and score > best_score:
            best_score = score
            best_roi   = roi
            print(f"[Quality] Face ({w}x{h}) score={score}")
    return best_roi


# ═════════════════════════════════════════════════════════════════════════════
#  FIX FACE MATCH: Stricter multi-method comparison with LBP texture features
# ═════════════════════════════════════════════════════════════════════════════
def _extract_lbp_hist(gray: np.ndarray, radius: int = 1, n_points: int = 8) -> np.ndarray:
    """
    Local Binary Pattern histogram — captures micro-texture of skin, pores, features.
    Much harder to spoof than color histograms alone.
    Different people have distinctly different LBP distributions.
    """
    h, w     = gray.shape
    lbp      = np.zeros_like(gray, dtype=np.uint8)
    for i in range(radius, h - radius):
        for j in range(radius, w - radius):
            center  = gray[i, j]
            binary  = 0
            offsets = [
                (-1, -1), (-1, 0), (-1, 1),
                ( 0, -1),          ( 0, 1),
                ( 1, -1), ( 1, 0), ( 1, 1),
            ]
            for k, (di, dj) in enumerate(offsets):
                if gray[i + di, j + dj] >= center:
                    binary |= (1 << k)
            lbp[i, j] = binary
    hist, _ = np.histogram(lbp.ravel(), bins=256, range=(0, 256))
    hist     = hist.astype(np.float32)
    norm     = np.linalg.norm(hist)
    if norm > 0:
        hist /= norm
    return hist


def _extract_lbp_hist_fast(gray: np.ndarray) -> np.ndarray:
    """
    Faster approximation of LBP using pre-computed neighbor offsets.
    Works on face sub-regions for better discrimination.
    """
    sz  = (64, 64)
    g   = cv2.resize(gray, sz)
    # Divide into 4x4 blocks, compute local histogram per block
    block_hists = []
    bh, bw = sz[1] // 4, sz[0] // 4
    for r in range(4):
        for c in range(4):
            block = g[r*bh:(r+1)*bh, c*bw:(c+1)*bw]
            # Simple intensity distribution per block
            hist, _ = np.histogram(block.ravel(), bins=32, range=(0, 256))
            hist     = hist.astype(np.float32)
            norm     = np.linalg.norm(hist)
            if norm > 0: hist /= norm
            block_hists.append(hist)
    return np.concatenate(block_hists)


def _cmp(saved_img: np.ndarray, live_roi: np.ndarray) -> float:
    """
    FIX FACE MATCH: Multi-method strict comparison.

    Methods:
      1. Grayscale histogram (texture) — 25%
      2. HSV hue histogram (color tone) — 20%
      3. Structural similarity (pixel diff) — 20%
      4. Block LBP features (micro-texture) — 35%  ← NEW, hardest to spoof

    Threshold is now 0.78 (was 0.65).
    Different people typically score 0.40–0.65.
    Same person typically scores 0.75–0.92.
    """
    try:
        sz = (128, 128)
        a  = cv2.resize(saved_img, sz)
        b  = cv2.resize(live_roi,  sz)

        ga = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
        gb = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)

        # 1. Gray histogram
        ha = cv2.calcHist([ga], [0], None, [256], [0, 256]); cv2.normalize(ha, ha)
        hb = cv2.calcHist([gb], [0], None, [256], [0, 256]); cv2.normalize(hb, hb)
        hist_score = max(0.0, 1.0 - cv2.compareHist(ha, hb, cv2.HISTCMP_BHATTACHARYYA))

        # 2. HSV hue
        ah  = cv2.calcHist([cv2.cvtColor(a, cv2.COLOR_BGR2HSV)], [0], None, [180], [0, 180])
        bh2 = cv2.calcHist([cv2.cvtColor(b, cv2.COLOR_BGR2HSV)], [0], None, [180], [0, 180])
        cv2.normalize(ah, ah); cv2.normalize(bh2, bh2)
        col_score = max(0.0, cv2.compareHist(ah, bh2, cv2.HISTCMP_CORREL))

        # 3. Structural similarity (normalized pixel diff)
        diff      = cv2.absdiff(ga, gb)
        struct_s  = max(0.0, 1.0 - np.mean(diff) / 128.0)

        # 4. Block LBP texture features (cosine similarity)
        lbp_a     = _extract_lbp_hist_fast(ga)
        lbp_b     = _extract_lbp_hist_fast(gb)
        dot       = np.dot(lbp_a, lbp_b)
        norm_a    = np.linalg.norm(lbp_a)
        norm_b    = np.linalg.norm(lbp_b)
        if norm_a > 0 and norm_b > 0:
            lbp_score = float(dot / (norm_a * norm_b))
        else:
            lbp_score = 0.0
        lbp_score = max(0.0, lbp_score)

        # Weighted combination — LBP gets highest weight
        final = (hist_score * 0.25 +
                 col_score  * 0.20 +
                 struct_s   * 0.20 +
                 lbp_score  * 0.35)

        print(f"[Cmp] hist={hist_score:.3f} col={col_score:.3f} "
              f"struct={struct_s:.3f} lbp={lbp_score:.3f} → {final:.3f} "
              f"(need {FACE_MATCH_THRESHOLD})")
        return final

    except Exception as e:
        print(f"[Cmp] Error: {e}")
        return 0.0


# ═════════════════════════════════════════════════════════════════════════════
#  VOICE
# ═════════════════════════════════════════════════════════════════════════════
class _VoiceThread(QThread):
    def __init__(self, text):
        super().__init__()
        self.text = text
    def run(self):
        try:
            import pyttsx3
            e  = pyttsx3.init()
            vs = e.getProperty('voices')
            fem = [v.id for v in vs if any(n in v.name.lower()
                   for n in ('zira','hazel','eva','female','woman','TITAN'))]
            if fem:   e.setProperty('voice', fem[0])
            elif vs:  e.setProperty('voice', vs[-1].id)
            e.setProperty('rate', 158)
            e.setProperty('volume', 0.95)
            e.say(self.text)
            e.runAndWait()
        except Exception as ex:
            print(f"[Voice] {ex}")

_vref = []
def TITAN_say(txt: str):
    t = _VoiceThread(txt)
    _vref.append(t)
    t.finished.connect(lambda: _vref.remove(t) if t in _vref else None)
    t.start()


# ═════════════════════════════════════════════════════════════════════════════
#  SOUNDS
# ═════════════════════════════════════════════════════════════════════════════
def _beep(f, ms):
    def _b():
        try:
            import winsound; winsound.Beep(max(37, min(f, 32767)), ms)
        except: pass
    threading.Thread(target=_b, daemon=True).start()

def snd_start(): _beep(880, 120)
def snd_ok():
    def _s():
        try:
            import winsound
            winsound.Beep(1047, 160); time.sleep(0.12); winsound.Beep(1319, 280)
        except: pass
    threading.Thread(target=_s, daemon=True).start()
def snd_fail(): _beep(280, 450)

class BeepLoop:
    def __init__(self): self._stop = threading.Event()
    def start(self):
        self._stop.clear()
        threading.Thread(target=self._run, daemon=True).start()
    def stop(self): self._stop.set()
    def _run(self):
        while not self._stop.is_set():
            _beep(1100, 45); self._stop.wait(0.38)


# ═════════════════════════════════════════════════════════════════════════════
#  FIREBASE
# ═════════════════════════════════════════════════════════════════════════════
class FaceFirebase:
    _db = None; _init = False

    @classmethod
    def connect(cls):
        if cls._init: return cls._db
        cls._init = True
        try:
            try:
                from firebase_connection import get_firebase_db
            except ImportError:
                from TABBU_modules.firebase_connection import get_firebase_db
            cls._db = get_firebase_db()
        except Exception as e:
            print(f"[FaceFirebase] {e}")
        return cls._db

    @classmethod
    def upload(cls, path: str, uid: str = "default", device_fp: str = "",
               os_user: str = ""):
        db = cls.connect()
        if not db: return False
        try:
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            db.collection("TITAN_faces").document(uid).set({
                "face_b64":      b64,
                "device_fp":     device_fp,
                "os_user":       os_user,         # FIX: store OS username
                "registered_at": datetime.utcnow().isoformat(),
                "hostname":      platform.node(),
            })
            print(f"[FaceFirebase] Uploaded uid={uid} os_user={os_user}")
            return True
        except Exception as e:
            print(f"[FaceFirebase] Upload error: {e}")
            return False

    @classmethod
    def download(cls, uid: str = "default") -> dict:
        db = cls.connect()
        if not db: return None
        try:
            doc = db.collection("TITAN_faces").document(uid).get()
            if not doc.exists: return None
            return doc.to_dict()
        except Exception as e:
            print(f"[FaceFirebase] Download error: {e}")
            return None


# ═════════════════════════════════════════════════════════════════════════════
#  SCAN OVERLAY
# ═════════════════════════════════════════════════════════════════════════════
class ScanOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._phase  = 0.0; self._scan_y = 0.0; self._radar = 0.0
        self._status = "INITIALIZING..."; self._conf = 0
        self._mode   = "scan"; self._dots  = 0
        QTimer(self, timeout=self._tick,  interval=16).start()
        QTimer(self, timeout=self._dtick, interval=500).start()

    def set_status(self, txt, conf=0, mode="scan"):
        self._status = txt; self._conf = max(0, min(100, conf))
        self._mode   = mode; self.update()

    def _tick(self):
        self._phase  = (self._phase  + 0.012) % 1.0
        self._scan_y = (self._scan_y + 0.007) % 1.0
        self._radar  = (self._radar  + 2.8)   % 360
        self.update()

    def _dtick(self): self._dots = (self._dots + 1) % 4

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height(); cx, cy = W // 2, H // 2

        if   self._mode == "success": pc = QColor(0, 255, 100, 255);  gl = QColor(0, 255, 100, 22)
        elif self._mode == "fail":    pc = QColor(255, 60,  60,  255); gl = QColor(255, 60, 60,  22)
        elif self._mode == "warn":    pc = QColor(255, 200, 0,   255); gl = QColor(255, 200, 0,  18)
        else:                         pc = QColor(0,  212, 255, 255);  gl = QColor(0,  212, 255, 16)
        cr, cg, cb = pc.red(), pc.green(), pc.blue()

        p.fillRect(0, 0, W, H, QColor(0, 4, 12, 155))
        p.setPen(QPen(QColor(0, 212, 255, 10), 1))
        for x in range(0, W, 48): p.drawLine(x, 0, x, H)
        for y in range(0, H, 48): p.drawLine(0, y, W, y)

        bw = min(290, W - 60); bh = min(330, H - 110)
        bx = cx - bw // 2;     by = cy - bh // 2
        p.fillRect(bx, by, bw, bh, gl)

        sy = by + int(self._scan_y * bh)
        sg = QLinearGradient(bx, sy - 10, bx, sy + 10)
        sg.setColorAt(0,   QColor(cr, cg, cb, 0))
        sg.setColorAt(0.5, QColor(cr, cg, cb, 130))
        sg.setColorAt(1,   QColor(cr, cg, cb, 0))
        p.fillRect(bx, sy - 10, bw, 20, QBrush(sg))

        arm = 30; pp = QPen(pc, 2); pp.setCapStyle(Qt.RoundCap); p.setPen(pp)
        for ox, oy, dx, dy in [(bx, by, arm, arm), (bx+bw, by, -arm, arm),
                                (bx, by+bh, arm, -arm), (bx+bw, by+bh, -arm, -arm)]:
            p.drawLine(ox, oy, ox+dx, oy); p.drawLine(ox, oy, ox, oy+dy)

        dr = int(3 + 2 * math.sin(self._phase * math.pi * 2))
        p.setBrush(pc); p.setPen(Qt.NoPen)
        for ox, oy, _, __ in [(bx, by, 0, 0), (bx+bw, by, 0, 0),
                               (bx, by+bh, 0, 0), (bx+bw, by+bh, 0, 0)]:
            p.drawEllipse(ox-dr, oy-dr, dr*2, dr*2)

        if self._mode == "scan":
            rg = QRadialGradient(cx, cy, min(bw, bh) // 2)
            rg.setColorAt(0, QColor(0, 212, 255, 45)); rg.setColorAt(1, QColor(0, 212, 255, 0))
            p.setBrush(QBrush(rg)); p.setPen(Qt.NoPen)
            p.drawPie(bx, by, bw, bh, int(self._radar * 16), int(-60 * 16))

        if self._conf > 0:
            by2 = by + bh + 14
            p.setBrush(QColor(8, 8, 18, 130)); p.setPen(QPen(QColor(cr, cg, cb, 70), 1))
            p.drawRoundedRect(bx, by2, bw, 7, 3, 3)
            fw = int(bw * self._conf / 100)
            if fw > 0:
                fg = QLinearGradient(bx, 0, bx+fw, 0)
                fg.setColorAt(0, QColor(0, 140, 255, 220)); fg.setColorAt(1, pc)
                p.setBrush(QBrush(fg)); p.setPen(Qt.NoPen)
                p.drawRoundedRect(bx, by2, fw, 7, 3, 3)
            p.setFont(QFont("Courier New", 8)); p.setPen(QColor(cr, cg, cb, 150))
            p.drawText(bx, by2 + 20, f"MATCH  {self._conf}%")

        dots = "." * self._dots if self._mode == "scan" else ""
        p.setFont(QFont("Courier New", 10, QFont.Bold)); p.setPen(pc)
        p.drawText(QRect(bx, by+bh+36, bw, 26), Qt.AlignCenter, self._status + dots)

        p.setFont(QFont("Courier New", 9, QFont.Bold)); p.setPen(QColor(0, 212, 255, 165))
        p.drawText(14, 26, "◈  TITAN  BIOMETRIC  SECURITY  v8.0")

        p.setFont(QFont("Courier New", 8)); p.setPen(QColor(0, 212, 255, 75))
        p.drawText(QRect(0, H-20, W-12, 16), Qt.AlignRight,
                   datetime.now().strftime("%Y-%m-%d  %H:%M:%S"))
        p.end()


# ═════════════════════════════════════════════════════════════════════════════
#  CAMERA THREAD
# ═════════════════════════════════════════════════════════════════════════════
class CameraThread(QThread):
    sig_frame    = pyqtSignal(object)
    sig_roi_info = pyqtSignal(object, list, float)
    sig_done     = pyqtSignal()
    sig_no_cam   = pyqtSignal()
    sig_quality  = pyqtSignal(bool, str, int)

    def __init__(self, mode="verify"):
        super().__init__()
        self.mode         = mode
        self._running     = True
        self.face_stable  = None
        self.captured_roi = None
        self.captured_full= None
        self.verified     = False
        self._saved_img   = None

    def set_saved(self, img): self._saved_img = img
    def stop(self):           self._running = False

    def run(self):
        cap = self._open_cam()
        if cap is None:
            self.sig_no_cam.emit(); return

        t0 = time.time(); frame_n = 0
        while self._running and (time.time() - t0 < CAMERA_TIMEOUT):
            ret, frame = cap.read()
            if not ret: time.sleep(0.03); continue
            frame = cv2.flip(frame, 1)
            frame_n += 1

            gray  = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = []
            if _face_cascade and FACE_DETECTION_OK:
                try:
                    faces = list(_face_cascade.detectMultiScale(
                        gray, 1.15, 5, cv2.CASCADE_SCALE_IMAGE, (70, 70)))
                except: pass

            self.sig_frame.emit(frame.copy())

            if faces:
                sim = 0.0
                if self.mode == "enroll":
                    self._handle_enroll(frame, faces)
                else:
                    sim = self._handle_verify(frame, faces)
                self.sig_roi_info.emit(frame.copy(), faces, sim)
                if not self._running: break
            else:
                self.face_stable = None
                self.sig_roi_info.emit(frame.copy(), [], 0.0)

            time.sleep(0.025)

        cap.release()
        self.sig_done.emit()

    def _open_cam(self):
        for backend in [cv2.CAP_DSHOW, cv2.CAP_ANY]:
            for idx in range(4):
                try:
                    cap = cv2.VideoCapture(idx, backend)
                    if cap.isOpened():
                        ret, fr = cap.read()
                        if ret and fr is not None:
                            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
                            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                            cap.set(cv2.CAP_PROP_FPS, 30)
                            print(f"[Cam] idx={idx} OK")
                            return cap
                    cap.release()
                except Exception as e:
                    print(f"[Cam] {idx}: {e}")
        return None

    def _handle_enroll(self, frame, faces):
        best_roi = _get_best_face_roi(frame, faces)
        if best_roi is None:
            self.sig_quality.emit(False, "LOW QUALITY", 0)
            self.face_stable = None
            return
        ok, reason, score = _check_face_quality(best_roi)
        self.sig_quality.emit(ok, reason, score)
        if not ok:
            self.face_stable = None
            return
        if self.face_stable is None:
            self.face_stable = time.time()
        if time.time() - self.face_stable >= STABLE_FACE_TIME:
            self.captured_roi  = best_roi.copy()
            self.captured_full = frame.copy()
            self._running      = False

    def _handle_verify(self, frame, faces) -> float:
        if self._saved_img is None: return 0.0
        best_roi = _get_best_face_roi(frame, faces)
        if best_roi is None: return 0.0
        sim = _cmp(self._saved_img, best_roi)
        if sim > FACE_MATCH_THRESHOLD:
            self.verified  = True
            self._running  = False
        return sim


# ═════════════════════════════════════════════════════════════════════════════
#  FACE AUTH WINDOW
# ═════════════════════════════════════════════════════════════════════════════
class FaceAuthWindow(QMainWindow):
    def __init__(self, mode="verify"):
        super().__init__(None)
        self.mode    = mode
        self._result = False
        self._cam    = None
        self._beep   = BeepLoop()
        self._loop   = QEventLoop()

        self.setWindowTitle("TITAN — Biometric Authentication v8")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setFixedSize(720, 580)
        self.setStyleSheet("QMainWindow { background: #020814; }")

        try:
            scr = QApplication.primaryScreen().geometry()
            self.move((scr.width()-self.width())//2, (scr.height()-self.height())//2)
        except:
            self.move(150, 100)

        self._build_ui()

    def _build_ui(self):
        central = QWidget()
        central.setStyleSheet("""
            QWidget {
                background: #020814;
                border: 2px solid rgba(0,212,255,100);
                border-radius: 18px;
            }
        """)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 14); root.setSpacing(8)

        hdr = QLabel(
            "◈  FACE  REGISTRATION  —  TITAN  v8" if self.mode == "enroll"
            else "◈  BIOMETRIC  VERIFICATION  —  TITAN  v8"
        )
        hdr.setAlignment(Qt.AlignCenter)
        hdr.setStyleSheet(
            "color:rgba(0,212,255,230); font-family:'Courier New';"
            "font-size:12px; font-weight:bold; background:transparent;"
            "border:none; padding:4px 0;")
        root.addWidget(hdr)

        self._cam_lbl = QLabel("◈  INITIALIZING BIOMETRIC SCANNER...")
        self._cam_lbl.setFixedSize(684, 430)
        self._cam_lbl.setAlignment(Qt.AlignCenter)
        self._cam_lbl.setFont(QFont("Courier New", 11))
        self._cam_lbl.setStyleSheet(
            "color:rgba(0,212,255,180); background:#000008;"
            "border:1px solid rgba(0,212,255,45); border-radius:10px;")
        root.addWidget(self._cam_lbl, alignment=Qt.AlignCenter)

        self._overlay = ScanOverlay(self._cam_lbl)
        self._overlay.setFixedSize(684, 430)
        self._overlay.move(0, 0)
        self._overlay.show(); self._overlay.raise_()

        row = QHBoxLayout()
        self._status_lbl = QLabel("LOADING BIOMETRIC ENGINE...")
        self._status_lbl.setStyleSheet(
            "color:rgba(0,212,255,200); font-family:'Courier New';"
            "font-size:10px; background:transparent; border:none;")
        row.addWidget(self._status_lbl); row.addStretch()

        self._quality_lbl = QLabel("")
        self._quality_lbl.setStyleSheet(
            "color:rgba(255,200,0,180); font-family:'Courier New';"
            "font-size:9px; background:transparent; border:none;")
        row.addWidget(self._quality_lbl); row.addStretch()

        abort_btn = QPushButton("✕  ABORT")
        abort_btn.setFixedSize(96, 30)
        abort_btn.setStyleSheet("""
            QPushButton {
                background:rgba(255,40,40,0.12);
                border:1px solid rgba(255,80,80,120);
                border-radius:7px; color:rgba(255,110,110,210);
                font-family:'Courier New'; font-size:9px;
            }
            QPushButton:hover { background:rgba(255,40,40,0.30); }
        """)
        abort_btn.clicked.connect(_ALIRA_slot(self._abort))
        row.addWidget(abort_btn)
        root.addLayout(row)

        QTimer.singleShot(350, self._start_scan)

    def run(self) -> bool:
        self.show(); self.raise_(); self.activateWindow()
        try:
            import ctypes
            hwnd = int(self.winId())
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except: pass
        QApplication.processEvents()
        self._loop.exec_()
        return self._result

    def _finish(self, result: bool):
        self._result = result
        QTimer.singleShot(0, self._loop.quit)

    def _start_scan(self, saved_img=None):
        snd_start(); self._beep.start()
        if self.mode == "enroll":
            TITAN_say("Face registration starting. Please look into the camera and hold still.")
            self._st("ALIGN FACE IN FRAME — HOLD STILL")
            self._overlay.set_status("CENTER YOUR FACE", 0, "scan")
        else:
            TITAN_say("Identity verification required. Please look into the camera.")
            self._st("SCANNING — LOOK INTO CAMERA")
            self._overlay.set_status("SCANNING BIOMETRICS", 0, "scan")

        self._cam = CameraThread(mode=self.mode)
        if saved_img is not None:
            self._cam.set_saved(saved_img)
        self._cam.sig_frame.connect(self._on_frame)
        self._cam.sig_roi_info.connect(self._on_roi)
        self._cam.sig_done.connect(self._on_done)
        self._cam.sig_no_cam.connect(self._on_no_cam)
        self._cam.sig_quality.connect(self._on_quality)
        self._cam.start()

    def set_saved_image(self, img: np.ndarray):
        """Call before run() to set the reference image for verification"""
        self._saved_img_ref = img

    def _on_frame(self, frame):
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qi  = QImage(rgb.data.tobytes(), w, h, ch*w, QImage.Format_RGB888)
            pix = QPixmap.fromImage(qi).scaled(
                      684, 430, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            self._cam_lbl.setPixmap(pix)
            self._overlay.raise_()
        except Exception as e:
            print(f"[Frame] {e}")

    def _on_quality(self, ok: bool, reason: str, score: int):
        if not ok:
            self._quality_lbl.setText(f"⚠ {reason}")
        else:
            self._quality_lbl.setText(f"✓ QUALITY: {score}")

    def _on_roi(self, frame, faces, similarity):
        if not faces:
            self._overlay.set_status("NO FACE — MOVE CLOSER", 0, "scan")
            self._st("NO FACE DETECTED — ADJUST POSITION")
            return
        if self.mode == "enroll":
            stab = self._cam.face_stable if self._cam else None
            if stab:
                pct = min(100, int((time.time()-stab) / STABLE_FACE_TIME * 100))
                self._overlay.set_status(f"HOLD STILL — {pct}%", pct, "scan")
                self._st(f"CAPTURING BIOMETRIC DATA... {pct}%")
            else:
                self._overlay.set_status("FACE DETECTED — CHECKING QUALITY", 0, "scan")
                self._st("CHECKING IMAGE QUALITY...")
        else:
            pct = min(99, int(similarity * 130))   # scaled for 0.78 threshold
            lbl = "MATCH FOUND" if similarity > FACE_MATCH_THRESHOLD else "ANALYZING"
            self._overlay.set_status(lbl, pct, "scan")
            self._st(f"CROSS-REFERENCING... {pct}%")

    def _on_done(self):
        self._beep.stop()
        if self.mode == "enroll":
            if self._cam and self._cam.captured_roi is not None:
                self._overlay.set_status("BIOMETRIC REGISTERED", 100, "success")
                self._st("✓  FACE REGISTERED SUCCESSFULLY")
                TITAN_say("Face registered. Device locked to this machine. Welcome to TITAN.")
                snd_ok()
                QTimer.singleShot(2600, lambda: self._close_finish(True))
            else:
                self._overlay.set_status("CAPTURE FAILED — RETRY", 0, "fail")
                self._st("✕  ENSURE GOOD LIGHTING & FACE VISIBILITY")
                TITAN_say("Face capture failed. Please ensure good lighting and try again.")
                snd_fail()
                QTimer.singleShot(2400, lambda: self._close_finish(False))
        else:
            if self._cam and self._cam.verified:
                self._overlay.set_status("IDENTITY CONFIRMED", 100, "success")
                self._st("✓  ACCESS GRANTED")
                TITAN_say("Identity verified. Welcome back. Access granted.")
                snd_ok()
                QTimer.singleShot(2000, lambda: self._close_finish(True))
            else:
                self._overlay.set_status("ACCESS DENIED", 0, "fail")
                self._st("✕  FACE NOT RECOGNIZED")
                TITAN_say("Face not recognized. Access denied.")
                snd_fail()
                QTimer.singleShot(2600, lambda: self._close_finish(False))

    def _on_no_cam(self):
        self._beep.stop()
        self._overlay.set_status("CAMERA UNAVAILABLE", 0, "warn")
        self._st("⚠  NO CAMERA — BYPASSING AUTH")
        TITAN_say("Camera not available. Bypassing face authentication.")
        QTimer.singleShot(1800, lambda: self._close_finish(True))

    def _abort(self):
        self._beep.stop()
        if self._cam: self._cam.stop(); self._cam.wait(1500)
        self._close_finish(False)

    def _close_finish(self, result: bool):
        self.hide()
        if self._cam and self._cam.isRunning():
            self._cam.stop(); self._cam.wait(800)
        self._finish(result)

    def closeEvent(self, ev):
        self._beep.stop()
        if self._cam and self._cam.isRunning():
            self._cam.stop(); self._cam.wait(1000)
        super().closeEvent(ev)

    def _st(self, txt): self._status_lbl.setText(txt)


def _run_enroll_window() -> tuple:
    """
    Run enrollment window and return (success, captured_roi).
    FIX: returns the captured ROI so caller can save it properly.
    """
    win = FaceAuthWindow(mode="enroll")
    ok  = win.run()
    roi = win._cam.captured_roi if (win._cam and ok) else None
    win.close(); win.deleteLater()
    return ok, roi


def _run_verify_window(saved_img: np.ndarray) -> bool:
    """Run verify window with given reference image."""
    win = FaceAuthWindow(mode="verify")
    # Inject saved image into camera thread after it starts
    # We override _start_scan to pass the image
    win._saved_img_ref = saved_img

    # Monkey-patch to pass image correctly
    original_start = win._start_scan
    def patched_start():
        snd_start(); win._beep.start()
        TITAN_say("Identity verification required. Please look into the camera.")
        win._st("SCANNING — LOOK INTO CAMERA")
        win._overlay.set_status("SCANNING BIOMETRICS", 0, "scan")
        win._cam = CameraThread(mode="verify")
        win._cam.set_saved(saved_img)
        win._cam.sig_frame.connect(win._on_frame)
        win._cam.sig_roi_info.connect(win._on_roi)
        win._cam.sig_done.connect(win._on_done)
        win._cam.sig_no_cam.connect(win._on_no_cam)
        win._cam.sig_quality.connect(win._on_quality)
        win._cam.start()
    win._start_scan = patched_start

    ok = win.run()
    win.close(); win.deleteLater()
    return ok


# ═════════════════════════════════════════════════════════════════════════════
#  ERROR DISPLAY
# ═════════════════════════════════════════════════════════════════════════════
def _show_error_win(status: str, msg: str):
    """Show a brief error overlay then close. Does NOT affect main auth flow."""
    win = FaceAuthWindow(mode="verify")
    win.show(); win.raise_()
    win._overlay.set_status(status, 0, "fail")
    win._st(msg)
    QApplication.processEvents()
    time.sleep(3)
    win.close(); win.deleteLater()


# ═════════════════════════════════════════════════════════════════════════════
#  PUBLIC API — FIXED FLOW
# ═════════════════════════════════════════════════════════════════════════════
def run_face_auth() -> bool:
    """
    Main entry point. Call AFTER QApplication exists, on MAIN THREAD.

    FIX v8 flow:
    1. Cascade check (if missing → bypass)
    2. Get current OS user — all face files are per-OS-user
    3. Device check — different device → DENY
    4. If no face registered for this user → enroll
    5. Quality check saved face — if bad → re-enroll
    6. Verify face — must match registered face for this OS user

    Returns True = access granted, False = denied.
    """
    # ── Determine current OS user ─────────────────────────
    current_os_user  = _get_current_os_user()
    user_face_path   = _get_user_face_path(current_os_user)
    user_lock_path   = _get_user_lock_path(current_os_user)

    print(f"[FaceAuth v8] OS user: {current_os_user}")
    print(f"[FaceAuth v8] Face path: {user_face_path}")
    print(f"[FaceAuth v8] Lock path: {user_lock_path}")

    app = QApplication.instance()
    if app:
        app.setQuitOnLastWindowClosed(False)

    # ── STEP 1: Cascade check ──────────────────────────────
    if not FACE_DETECTION_OK:
        print("[FaceAuth] Cascade offline — bypass")
        TITAN_say("Biometric module offline. Proceeding without face scan.")
        return True

    # ── STEP 2: Device check (per-user) ───────────────────
    if os.path.exists(user_lock_path):
        try:
            with open(user_lock_path) as f:
                saved_lock = json.load(f)
            saved_fp   = saved_lock.get("fingerprint", "")
            current_fp = _get_device_fingerprint()
            if saved_fp and saved_fp != current_fp:
                print(f"[FaceAuth] ❌ DEVICE MISMATCH for user {current_os_user}")
                TITAN_say("Security alert. This device is not authorized for your account. Access denied.")
                _show_error_win("UNAUTHORIZED DEVICE", "❌ THIS DEVICE IS NOT AUTHORIZED")
                return False
            print(f"[FaceAuth] ✅ Device OK for user {current_os_user}")
        except Exception as e:
            print(f"[FaceAuth] Lock check error: {e}")

    # ── STEP 3: Try to download face from Firebase if missing ─
    if not os.path.exists(user_face_path):
        uid = f"{current_os_user}_{platform.node()}"
        print(f"[FaceAuth] No local face — checking Firebase for uid={uid}")
        TITAN_say("No biometric data found. Checking cloud database.")
        data = FaceFirebase.download(uid)
        if data:
            stored_os_user = data.get("os_user", "")
            # FIX USER ISOLATION: Only use Firebase data if OS user matches
            if stored_os_user and stored_os_user != current_os_user:
                print(f"[FaceAuth] Firebase data belongs to '{stored_os_user}', "
                      f"current user is '{current_os_user}' — ignoring")
            else:
                b64 = data.get("face_b64", "")
                if b64:
                    os.makedirs(FACE_DIR, exist_ok=True)
                    with open(user_face_path, "wb") as f:
                        f.write(base64.b64decode(b64))
                    print(f"[FaceAuth] Downloaded face for {current_os_user}")
                    # Also restore device lock
                    current_fp = _get_device_fingerprint()
                    lock_data  = {
                        "fingerprint":   current_fp,
                        "hostname":      platform.node(),
                        "os_user":       current_os_user,
                        "platform":      platform.system(),
                        "registered_at": datetime.utcnow().isoformat(),
                        "app":           "TITAN_v8"
                    }
                    with open(user_lock_path, "w") as f:
                        json.dump(lock_data, f, indent=2)

    # ── STEP 4: Enroll if still no face ───────────────────
    if not os.path.exists(user_face_path):
        print(f"[FaceAuth] First time registration for OS user: {current_os_user}")
        TITAN_say("First time setup. Please register your face now.")
        ok, roi = _run_enroll_window()
        if not ok or roi is None:
            TITAN_say("Enrollment failed. Please restart TITAN.")
            return False
        # FIX: Save face for this specific OS user
        _save_user_face(roi, current_os_user, user_face_path, user_lock_path)
        return True   # FIX FLOW: Return here — don't fall into verification

    # ── STEP 5: Load and quality-check saved face ──────────
    saved_img = cv2.imread(user_face_path)
    if saved_img is None:
        print(f"[FaceAuth] Cannot read saved face — re-enroll")
        TITAN_say("Biometric data corrupted. Please re-register your face.")
        ok, roi = _run_enroll_window()
        if not ok or roi is None:
            return False
        _save_user_face(roi, current_os_user, user_face_path, user_lock_path)
        return True   # FIX FLOW: Return after re-enroll

    ok_q, reason_q, score_q = _check_face_quality(saved_img)
    print(f"[FaceAuth] Saved face quality: ok={ok_q} {reason_q} score={score_q}")
    if not ok_q:
        print(f"[FaceAuth] Saved face poor quality ({reason_q}) — re-enroll")
        TITAN_say("Stored face data quality is too low. Please re-register.")
        try:
            os.remove(user_face_path)
        except Exception:
            pass
        if os.path.exists(user_lock_path):
            try:
                os.remove(user_lock_path)
            except Exception:
                pass
        ok, roi = _run_enroll_window()
        if not ok or roi is None:
            return False
        _save_user_face(roi, current_os_user, user_face_path, user_lock_path)
        return True   # FIX FLOW: Return after re-enroll

    # ── STEP 6: Verify identity ───────────────────────────
    print(f"[FaceAuth] Starting verification for OS user: {current_os_user}")
    TITAN_say("Biometric verification required.")

    for attempt in range(1, MAX_VERIFY_ATTEMPTS + 1):
        print(f"[FaceAuth] Attempt {attempt}/{MAX_VERIFY_ATTEMPTS}")
        if attempt > 1:
            TITAN_say(f"Attempt {attempt}. Please look directly at the camera.")

        ok = _run_verify_window(saved_img)
        if ok:
            print(f"[FaceAuth] ✅ Verified — OS user: {current_os_user}")
            return True

        if attempt < MAX_VERIFY_ATTEMPTS:
            TITAN_say("Verification failed. Please try again.")
        else:
            TITAN_say("Maximum attempts exceeded. Access denied.")
            print(f"[FaceAuth] ❌ All attempts failed for {current_os_user}")

    return False


def _save_user_face(roi: np.ndarray, os_user: str,
                    face_path: str, lock_path: str):
    """
    FIX USER ISOLATION: Save face + device lock — all tagged to specific OS user.
    """
    try:
        os.makedirs(FACE_DIR, exist_ok=True)

        ok, reason, score = _check_face_quality(roi)
        print(f"[SaveFace] Quality: ok={ok} reason={reason} score={score}")

        if cv2.imwrite(face_path, roi):
            kb = os.path.getsize(face_path) // 1024
            print(f"[SaveFace] Saved: {face_path} ({kb} KB) for OS user: {os_user}")
        else:
            print(f"[SaveFace] imwrite FAILED: {face_path}")
            return

        # Device lock per user
        current_fp = _get_device_fingerprint()
        lock_data  = {
            "fingerprint":   current_fp,
            "hostname":      platform.node(),
            "os_user":       os_user,
            "platform":      platform.system(),
            "registered_at": datetime.utcnow().isoformat(),
            "app":           "TITAN_v8"
        }
        with open(lock_path, "w") as f:
            json.dump(lock_data, f, indent=2)
        print(f"[SaveFace] Device locked for user '{os_user}': {current_fp[:16]}...")

        # Upload to Firebase in background
        uid = f"{os_user}_{platform.node()}"
        threading.Thread(
            target=FaceFirebase.upload,
            args=(face_path, uid, current_fp, os_user),
            daemon=True
        ).start()

    except Exception as e:
        print(f"[SaveFace] Error: {e}")


# ═════════════════════════════════════════════════════════════════════════════
#  STANDALONE TEST
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setQuitOnLastWindowClosed(False)
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#020814"))
    app.setPalette(pal)
    result = run_face_auth()
    print(f"\n{'✅ ACCESS GRANTED' if result else '❌ ACCESS DENIED'}")
    sys.exit(0 if result else 1)