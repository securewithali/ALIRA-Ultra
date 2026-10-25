# -*- coding: utf-8 -*-
"""
ALIRA Admin — tabbu_activation.py  [SECURE v4]
=============================================
Admin tool: Key creation / management
Client activation: tabbu_modules/tabbu_activation.py use karo

NOTE: Yeh file admin_and_build_tools mein hai — developer use only.
      PyPI package mein ship NAHI hoti.
      Firebase Admin SDK sirf is file mein hai (server/developer machine pe only).
"""
import sys, os, json, hashlib, uuid, platform, socket, subprocess, base64
import urllib.request, urllib.error, urllib.parse, time, re
from pathlib import Path
from datetime import datetime, timezone

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFrame, QStackedWidget,
    QGraphicsDropShadowEffect, QMessageBox
)
from PyQt5.QtCore  import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui   import QColor, QPainter, QPen, QBrush, QLinearGradient, QPalette, QFont
import math, random as rnd

# ══ CONFIG ═══════════════════════════════════════════════════════════════════
PROJECT_ID = "speen-to-earn"
ACTIVE_DB  = "(default)"
CONFIG_FILE = Path.home() / ".ALIRA_config.enc"

TELEGRAM_SUPPORT  = "https://t.me/SecureWithAli"
TELEGRAM_USERNAME = "@SecureWithAli"

KEY_PREFIX  = "TITAN"
KEY_PATTERN = re.compile(r'^(TITAN|ALIRA)-[A-Z0-9]{4}-[A-Z0-9]{4,6}$')

# SA JSON — admin_and_build_tools/ mein rakho (sirf developer ke paas)
_SA_NAMES = ["speen-to-earn-firebase-adminsdk-fbsvc-5b5054d17e.json"]

# ── Colors ────────────────────────────────────────────────────────────────────
BG=("#07091a"); BG2=("#0c1124"); BG3=("#111830"); ACCENT=("#7c5cfc"); ACC2=("#a080ff")
CYAN=("#00e5ff"); TEAL=("#00c9a7"); GOLD=("#ffc947"); TEXT=("#e2e8f8")
MUTED=("#5a6485"); MUTED2=("#8892b0"); GREEN=("#00d68f"); RED=("#ff4757")

# ══ DEVICE ═══════════════════════════════════════════════════════════════════
def get_device_id() -> str:
    try:
        mac = uuid.getnode()
        raw = f"{mac}-{platform.node()}-{platform.machine()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]
    except Exception:
        return hashlib.sha256(platform.node().encode()).hexdigest()[:32]

def get_device_info() -> dict:
    try:
        hn = socket.gethostname()
        try: un = os.getlogin()
        except: un = os.environ.get("USERNAME","")
        return {
            "device_id":    get_device_id(),
            "device_label": f"{hn} ({un})",
            "pc_username":  un, "pc_hostname": hn,
            "pc_os":        f"{platform.system()} {platform.release()}",
            "pc_model":     platform.node(),
            "pc_processor": platform.processor()[:80] if platform.processor() else "",
        }
    except Exception:
        return {"device_id": get_device_id(), "device_label": "Unknown"}

# ══ SA PATH — admin machine / server pe ══════════════════════════════════════
def _find_sa_path() -> str:
    search = [
        Path(__file__).parent,
        Path(__file__).parent.parent / "TABBU_modules",
        Path.home() / ".ALIRA",
    ]
    # EXE mein bhi check karo
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
        search += [base / "admin_and_build_tools", base / "TABBU_modules", base]

    for base in search:
        if not base.exists(): continue
        for n in _SA_NAMES:
            p = base / n
            if p.exists():
                return str(p)
    return ""

# ══ FIRESTORE REST (JWT-based — no firebase_admin) ═══════════════════════════
def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _get_sa_token(sa_path: str = "") -> str:
    path = sa_path or _find_sa_path()
    if not path:
        print("[Token] SA JSON not found — place in admin_and_build_tools/")
        return ""
    try:
        sa  = json.loads(Path(path).read_text())
        now = int(time.time())
        header  = _b64url(json.dumps({"alg":"RS256","typ":"JWT"},separators=(',',':')).encode())
        payload = _b64url(json.dumps({
            "iss": sa["client_email"], "sub": sa["client_email"],
            "aud": "https://oauth2.googleapis.com/token",
            "iat": now, "exp": now + 3600,
            "scope": "https://www.googleapis.com/auth/cloud-platform",
        }, separators=(',',':')).encode())
        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.backends import default_backend
            pk  = serialization.load_pem_private_key(sa["private_key"].encode(), password=None, backend=default_backend())
            sig = pk.sign(f"{header}.{payload}".encode(), padding.PKCS1v15(), hashes.SHA256())
            jwt = f"{header}.{payload}.{_b64url(sig)}"
        except ImportError:
            import jwt as pyjwt
            jwt = pyjwt.encode(
                {"iss":sa["client_email"],"sub":sa["client_email"],
                 "aud":"https://oauth2.googleapis.com/token",
                 "iat":now,"exp":now+3600,
                 "scope":"https://www.googleapis.com/auth/cloud-platform"},
                sa["private_key"], algorithm="RS256"
            )
            if isinstance(jwt, bytes): jwt = jwt.decode()

        data = urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion":  jwt,
        }).encode()
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token", data=data,
            headers={"Content-Type":"application/x-www-form-urlencoded"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()).get("access_token","")
    except Exception as e:
        print(f"[Token] Error: {e}"); return ""

def _db_enc(): return urllib.parse.quote(ACTIVE_DB, safe="()")
def _fs_base(): return f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}/databases/{_db_enc()}/documents"
def _auth_h(t): return {"Accept":"application/json","Authorization":f"Bearer {t}"}
def _read_err(e):
    try: return e.read().decode()[:400]
    except: return ""

def fs_get_key(key: str) -> dict | None:
    token = _get_sa_token()
    if not token: return None
    url = f"{_fs_base()}/keys/{urllib.parse.quote(key, safe='')}"
    try:
        req = urllib.request.Request(url, headers=_auth_h(token))
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404: return None
        print(f"[FS GET] {e.code}: {_read_err(e)}"); return None

def fs_patch_key(key: str, fields: dict, masks: list = None) -> bool:
    token = _get_sa_token()
    if not token: return False
    mask_qs = "&".join(f"updateMask.fieldPaths={m}" for m in (masks or list(fields.keys())))
    url = f"{_fs_base()}/keys/{urllib.parse.quote(key, safe='')}?{mask_qs}"
    body = {"fields": {k: {"stringValue": str(v)} for k, v in fields.items()}}
    data = json.dumps(body).encode()
    req  = urllib.request.Request(url, data=data, method="PATCH",
                                  headers={**_auth_h(token),"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return r.status < 300
    except Exception as e:
        print(f"[FS PATCH] {e}"); return False

# ══ CONFIG ════════════════════════════════════════════════════════════════════
def save_config(data: dict):
    try:
        try:
            from cryptography.fernet import Fernet
            key = hashlib.sha256(get_device_id().encode()).digest()
            import base64 as b64
            f   = Fernet(b64.urlsafe_b64encode(key))
            CONFIG_FILE.write_bytes(f.encrypt(json.dumps(data).encode()))
        except Exception:
            CONFIG_FILE.write_text(json.dumps(data))
        print(f"[Config] Saved → {CONFIG_FILE}")
    except Exception as e:
        print(f"[Config] Save error: {e}")

def load_config() -> dict | None:
    # First try AppData/Roaming/ALIRA/license.json (new location)
    try:
        from tabbu_modules.license_client import load_license
        lic = load_license()
        if lic: return lic
    except Exception:
        pass
    # Fallback old .ALIRA_config.enc
    if not CONFIG_FILE.exists(): return None
    try:
        from cryptography.fernet import Fernet
        key = hashlib.sha256(get_device_id().encode()).digest()
        import base64 as b64
        f   = Fernet(b64.urlsafe_b64encode(key))
        return json.loads(f.decrypt(CONFIG_FILE.read_bytes()))
    except Exception:
        try: return json.loads(CONFIG_FILE.read_text())
        except: return None

# ══ UI (same as before — minimal) ════════════════════════════════════════════
class AnimBg(QWidget):
    def __init__(self, p=None):
        super().__init__(p)
        self._pts = [{"x":rnd.random(),"y":rnd.random(),"vx":rnd.uniform(-3e-4,3e-4),"vy":rnd.uniform(-3e-4,3e-4),"r":rnd.uniform(1,3),"a":rnd.uniform(.2,.7)} for _ in range(45)]
        self._t = 0
        t = QTimer(self); t.timeout.connect(self._tick); t.start(33)
    def _tick(self):
        self._t += 1
        for p in self._pts: p["x"]=(p["x"]+p["vx"])%1; p["y"]=(p["y"]+p["vy"])%1
        self.update()
    def paintEvent(self,_):
        W,H=self.width(),self.height(); p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        g=QLinearGradient(0,0,0,H); g.setColorAt(0,QColor(BG)); g.setColorAt(1,QColor(BG2)); p.fillRect(0,0,W,H,g)
        pen=QPen()
        for pt in self._pts:
            x,y=int(pt["x"]*W),int(pt["y"]*H); c=QColor(ACCENT); c.setAlphaF(pt["a"]*(0.5+0.5*math.sin(self._t*.04)))
            pen.setColor(c); p.setPen(pen); p.setBrush(QBrush(c)); r=pt["r"]; p.drawEllipse(x-r,y-r,r*2,r*2)
        p.end()

def _L(t,c=TEXT,s=14,b=False,a=Qt.AlignLeft):
    l=QLabel(t); l.setStyleSheet(f"color:{c};font-size:{s}px;font-weight:{'700'if b else'400'};background:transparent;"); l.setAlignment(a); return l

def _I(ph="",pw=False):
    e=QLineEdit(); e.setPlaceholderText(ph)
    if pw: e.setEchoMode(QLineEdit.Password)
    e.setStyleSheet(f"QLineEdit{{background:{BG3};border:1.5px solid rgba(124,92,252,.35);border-radius:10px;color:{TEXT};font-size:14px;padding:10px 14px;}}QLineEdit:focus{{border:1.5px solid {ACCENT};}}"); e.setMinimumHeight(44); return e

def _B(t,pri=True):
    b=QPushButton(t)
    if pri: b.setStyleSheet(f"QPushButton{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {ACCENT},stop:1 {ACC2});color:#fff;font-size:14px;font-weight:700;border:none;border-radius:10px;padding:12px 32px;}}QPushButton:hover{{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {ACC2},stop:1 {ACCENT});}}QPushButton:disabled{{background:{MUTED};color:#333;}}")
    else: b.setStyleSheet(f"QPushButton{{background:transparent;color:{MUTED2};font-size:12px;border:none;padding:6px;}}QPushButton:hover{{color:{ACC2};}}")
    b.setCursor(Qt.PointingHandCursor); return b

class _Worker(QObject):
    sig_ok  = pyqtSignal(dict)
    sig_err = pyqtSignal(str)
    def run(self, key, gkey, name, dev):
        import threading
        threading.Thread(target=self._run, args=(key,gkey,name,dev), daemon=True).start()
    def _run(self, key, gkey, name, dev):
        # This is the ADMIN activation — uses SA token directly
        token = _get_sa_token()
        if not token:
            self.sig_err.emit("❌ Firebase credentials not found.\n\nPlace SA JSON in admin_and_build_tools/"); return
        doc = fs_get_key(key)
        if doc is None:
            self.sig_err.emit(f"❌ Key not found: {key}"); return
        fields = doc.get("fields",{})
        if fields.get("active",{}).get("booleanValue") == False or \
           fields.get("active",{}).get("stringValue","").lower() == "false":
            self.sig_err.emit("❌ Key deactivated."); return
        exp = fields.get("expiresAt",{}).get("stringValue","")
        if exp:
            try:
                from datetime import datetime,timezone
                exp_dt = datetime.fromisoformat(exp.replace("Z","+00:00"))
                if datetime.now(timezone.utc) > exp_dt:
                    self.sig_err.emit("❌ License expired."); return
            except Exception: pass
        bound = fields.get("device_id",{}).get("stringValue","").strip()
        if bound and bound != dev["device_id"]:
            bound_lbl = fields.get("device_label",{}).get("stringValue","?")
            self.sig_err.emit(f"❌ Key locked to: {bound_lbl}\nAsk admin to UNBIND."); return
        patch = {
            "device_id":    dev["device_id"],
            "device_label": dev["device_label"],
            "pc_username":  dev.get("pc_username",""),
            "pc_hostname":  dev.get("pc_hostname",""),
            "pc_os":        dev.get("pc_os",""),
            "display_name": name,
            "gemini_api_key": gkey,
            "last_seen":    datetime.now(timezone.utc).isoformat(),
        }
        if not bound: patch["bound_at"] = datetime.now(timezone.utc).isoformat()
        fs_patch_key(key, patch)
        cfg = {
            "access_key": key, "device_id": dev["device_id"],
            "display_name": name, "gemini_api_key": gkey,
            "plan": fields.get("plan",{}).get("stringValue","PRO"),
            "expires_at": exp,
        }
        save_config(cfg)
        self.sig_ok.emit(cfg)

class _PKey(QWidget):
    sig_back = pyqtSignal(); sig_ok = pyqtSignal(str)
    def __init__(self):
        super().__init__(); self.setAttribute(Qt.WA_TranslucentBackground)
        v = QVBoxLayout(self); v.setContentsMargins(40,40,40,40); v.setSpacing(14)
        v.addStretch(1)
        v.addWidget(_L("🔑",GOLD,36,a=Qt.AlignCenter))
        v.addWidget(_L("Access Key",TEXT,20,b=True,a=Qt.AlignCenter))
        v.addWidget(_L("Format: TITAN-XXXX-XXXXX",MUTED2,12,a=Qt.AlignCenter))
        v.addSpacing(10)
        self._i=_I("TITAN-XXXX-XXXXX"); self._i.setAlignment(Qt.AlignCenter); self._i.textChanged.connect(lambda t: self._b.setEnabled(len(t.strip())>=5)); v.addWidget(self._i)
        self._e=_L("",RED,12,a=Qt.AlignCenter); self._e.setWordWrap(True); v.addWidget(self._e)
        self._b=_B("Next →"); self._b.setFixedWidth(200); self._b.setEnabled(False); self._b.clicked.connect(self._next)
        bh=QHBoxLayout(); bh.addStretch(); bh.addWidget(self._b); bh.addStretch(); v.addLayout(bh)
        v.addStretch(1)
    def _next(self):
        k=self._i.text().strip().upper()
        if not KEY_PATTERN.match(k): self._e.setText("❌ Invalid format"); return
        self.sig_ok.emit(k)

class _PProfile(QWidget):
    sig_back = pyqtSignal(); sig_activated = pyqtSignal(dict); sig_err = pyqtSignal(str)
    def __init__(self):
        super().__init__(); self.setAttribute(Qt.WA_TranslucentBackground)
        self._key=""; self._w=_Worker(); self._w.sig_ok.connect(self.sig_activated); self._w.sig_err.connect(self._on_err)
        v = QVBoxLayout(self); v.setContentsMargins(40,40,40,40); v.setSpacing(12)
        v.addStretch(1)
        v.addWidget(_L("👤",CYAN,36,a=Qt.AlignCenter))
        v.addWidget(_L("Complete Profile",TEXT,20,b=True,a=Qt.AlignCenter))
        v.addWidget(_L("Display Name",MUTED2,12)); self._n=_I("Your Name"); v.addWidget(self._n)
        v.addWidget(_L("Gemini API Key",MUTED2,12)); self._a=_I("AIzaSy..."); v.addWidget(self._a)
        lk=_B("🔗 Get API key",False); lk.clicked.connect(lambda:__import__("webbrowser").open("https://aistudio.google.com/app/apikey")); v.addWidget(lk)
        self._e=_L("",RED,12,a=Qt.AlignCenter); self._e.setWordWrap(True); v.addWidget(self._e)
        self._b=_B("🚀 Activate"); self._b.setFixedWidth(200); self._b.clicked.connect(self._act)
        bh=QHBoxLayout(); bh.addStretch(); bh.addWidget(self._b); bh.addStretch(); v.addLayout(bh)
        bk=_B("← Back",False); bk.clicked.connect(self.sig_back)
        bh2=QHBoxLayout(); bh2.addStretch(); bh2.addWidget(bk); bh2.addStretch(); v.addLayout(bh2)
        v.addStretch(1)
    def set_key(self,k): self._key=k
    def _act(self):
        n=self._n.text().strip(); a=self._a.text().strip()
        if not n: self._e.setText("⚠️ Enter display name"); return
        if not a: self._e.setText("⚠️ Enter Gemini API key"); return
        self._b.setEnabled(False); self._b.setText("Activating…"); self._e.setText("")
        self._w.run(self._key, a, n, get_device_info())
    def _on_err(self,m): self._e.setText(m); self._b.setText("🚀 Activate"); self._b.setEnabled(True)

class _PSuccess(QWidget):
    sig_launch = pyqtSignal()
    def __init__(self):
        super().__init__(); self.setAttribute(Qt.WA_TranslucentBackground)
        v=QVBoxLayout(self); v.setContentsMargins(40,40,40,40); v.setSpacing(16)
        v.addStretch(1)
        v.addWidget(_L("✅",GREEN,52,a=Qt.AlignCenter))
        v.addWidget(_L("Activation Successful!",GREEN,22,b=True,a=Qt.AlignCenter))
        self._wl=_L("Welcome!",CYAN,16,a=Qt.AlignCenter); v.addWidget(self._wl)
        b=_B("🚀 Launch ALIRA"); b.setFixedWidth(200); b.clicked.connect(self.sig_launch)
        bh=QHBoxLayout(); bh.addStretch(); bh.addWidget(b); bh.addStretch(); v.addLayout(bh)
        v.addStretch(1)
    def set_user(self,n): self._wl.setText(f"Welcome, {n}! 🎉")

class ActivationWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ALIRA — Activation"); self.setFixedSize(480,580)
        self.setWindowFlag(Qt.FramelessWindowHint); self.setAttribute(Qt.WA_TranslucentBackground)
        self._drag=None
        self._bg=AnimBg(self); self._bg.setGeometry(0,0,480,580)
        card=QFrame(self); card.setGeometry(24,24,432,532)
        card.setStyleSheet(f"QFrame{{background:rgba(12,17,36,.92);border:1.5px solid rgba(124,92,252,.35);border-radius:20px;}}")
        self._stack=QStackedWidget(card); self._stack.setGeometry(0,0,432,532); self._stack.setStyleSheet("background:transparent;")
        self._pk=_PKey(); self._pp=_PProfile(); self._ps=_PSuccess()
        for p in [self._pk,self._pp,self._ps]: self._stack.addWidget(p)
        self._pk.sig_ok.connect(self._on_key); self._pp.sig_back.connect(lambda:self._stack.setCurrentIndex(0))
        self._pp.sig_activated.connect(self._on_act); self._ps.sig_launch.connect(self.close)
        cb=QPushButton("✕",self); cb.setGeometry(440,8,32,32)
        cb.setStyleSheet(f"QPushButton{{background:rgba(255,71,87,.15);color:{RED};border:1px solid rgba(255,71,87,.3);border-radius:16px;font-size:14px;}}QPushButton:hover{{background:{RED};color:white;}}")
        cb.clicked.connect(self.close)
    def _on_key(self,k): self._pp.set_key(k); self._stack.setCurrentIndex(1)
    def _on_act(self,cfg): self._ps.set_user(cfg.get("display_name","User")); self._stack.setCurrentIndex(2)
    def mousePressEvent(self,e):
        if e.button()==Qt.LeftButton: self._drag=e.globalPos()-self.frameGeometry().topLeft()
    def mouseMoveEvent(self,e):
        if self._drag and e.buttons()==Qt.LeftButton: self.move(e.globalPos()-self._drag)
    def mouseReleaseEvent(self,e): self._drag=None

if __name__ == "__main__":
    app=QApplication(sys.argv); app.setStyle("Fusion")
    win=ActivationWindow(); win.show(); sys.exit(app.exec_())
