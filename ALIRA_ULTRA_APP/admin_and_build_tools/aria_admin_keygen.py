# -*- coding: utf-8 -*-
"""
ALIRA v3 — Admin Key Generator
Uses Firebase REST API (service account) to create & manage access keys.

Key Format:  ALIRA-XXXX-XXXXX  (4 + 5 uppercase alphanumeric)

Install:  pip install cryptography PyQt5
Run:      python alira_admin_keygen.py
"""

import sys, os, json, random, string, threading, time, base64
import urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QFileDialog, QSizePolicy, QAbstractItemView,
)
from PyQt5.QtCore  import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui   import (
    QColor, QPainter, QPen, QBrush, QRadialGradient,
    QPalette, QFont
)
import math, random as rnd

# ══════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════
PROJECT_ID   = "speen-to-earn"
ACTIVE_DB    = "(default)"   # ← Must match tabbu_activation.py

DEFAULT_SA_PATH = Path(__file__).parent / "speen-to-earn-firebase-adminsdk-fbsvc-5b5054d17e.json"
_ALT_SA_NAMES = [
    "speen-to-earn-firebase-adminsdk-fbsvc-86926634fd.json",

]

def _find_sa() -> Path | None:
    if DEFAULT_SA_PATH.exists():
        return DEFAULT_SA_PATH
    base = Path(__file__).parent
    for name in _ALT_SA_NAMES:
        p = base / name
        if p.exists():
            return p
    return None

# ── Colors ───────────────────────────────────────────
BG     = "#07091a"
BG2    = "#0c1124"
BG3    = "#111830"
ACCENT = "#7c5cfc"
ACC2   = "#a080ff"
CYAN   = "#00e5ff"
TEAL   = "#00c9a7"
GOLD   = "#ffc947"
TEXT   = "#e2e8f8"
MUTED  = "#5a6485"
MUTED2 = "#8892b0"
GREEN  = "#00d68f"
RED    = "#ff4757"


# ════════════════════════════════════════════════════════
# KEY GENERATOR  —  ALIRA-XXXX-XXXXX
# ════════════════════════════════════════════════════════
def generate_key() -> str:
    chars = string.ascii_uppercase + string.digits
    part1 = ''.join(random.choices(chars, k=4))
    part2 = ''.join(random.choices(chars, k=5))
    return f"ALIRA-{part1}-{part2}"


# ════════════════════════════════════════════════════════
# SA TOKEN
# ════════════════════════════════════════════════════════
def _get_sa_token(sa_path: str) -> str:
    try:
        sa = json.loads(Path(sa_path).read_text())

        def b64url(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b'=').decode()

        now     = int(time.time())
        header  = b64url(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(',', ':')).encode())
        payload = b64url(json.dumps({
            "iss":   sa["client_email"],
            "sub":   sa["client_email"],
            "aud":   "https://oauth2.googleapis.com/token",
            "iat":   now, "exp": now + 3600,
            "scope": "https://www.googleapis.com/auth/cloud-platform",
        }, separators=(',', ':')).encode())

        try:
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import padding
            from cryptography.hazmat.backends import default_backend
            private_key = serialization.load_pem_private_key(
                sa["private_key"].encode(), password=None, backend=default_backend()
            )
            msg = f"{header}.{payload}".encode()
            sig = private_key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
            jwt_token = f"{header}.{payload}.{b64url(sig)}"
        except ImportError:
            try:
                import jwt as pyjwt
                jwt_token = pyjwt.encode(
                    {"iss": sa["client_email"], "sub": sa["client_email"],
                     "aud": "https://oauth2.googleapis.com/token",
                     "iat": now, "exp": now + 3600,
                     "scope": "https://www.googleapis.com/auth/cloud-platform"},
                    sa["private_key"], algorithm="RS256"
                )
                if isinstance(jwt_token, bytes):
                    jwt_token = jwt_token.decode()
            except ImportError:
                print("[Token] ERROR: pip install cryptography")
                return ""

        post_data = urllib.parse.urlencode({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion":  jwt_token,
        }).encode()
        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=post_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            resp  = json.loads(r.read())
            token = resp.get("access_token", "")
            if token:
                print(f"[Token] OAuth2 OK  ({sa.get('client_email','')})")
            return token
    except Exception as e:
        print(f"[Token] Error: {e}")
        return ""


# ════════════════════════════════════════════════════════
# FIRESTORE REST HELPERS
# ════════════════════════════════════════════════════════
def _db_enc() -> str:
    return ACTIVE_DB.replace("(", "%28").replace(")", "%29")

def _fs_base() -> str:
    return (f"https://firestore.googleapis.com/v1/projects/{PROJECT_ID}"
            f"/databases/{_db_enc()}/documents")

def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def _read_err(e) -> str:
    try: return e.read().decode()[:300]
    except: return ""


def _fs_get(path: str, token: str) -> dict | None:
    url = f"{_fs_base()}/{path}"
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=10) as r:
            doc = json.loads(r.read())
            if "fields" in doc: return doc
    except urllib.error.HTTPError as e:
        print(f"[FS] GET {path} → HTTP {e.code}: {_read_err(e)}")
    except Exception as e:
        print(f"[FS] GET error: {e}")
    return None


def _fs_create(path: str, fields: dict, token: str) -> bool:
    parts = path.rsplit("/", 1)
    if len(parts) != 2: return False
    collection, doc_id = parts
    url  = f"{_fs_base()}/{collection}?documentId={urllib.parse.quote(doc_id, safe='')}"
    body = json.dumps({"fields": fields}).encode()
    try:
        req = urllib.request.Request(
            url, data=body, headers=_auth_headers(token), method="POST"
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            resp = json.loads(r.read())
            print(f"[FS] CREATE OK → {resp.get('name','')}")
            return True
    except urllib.error.HTTPError as e:
        body2 = _read_err(e)
        print(f"[FS] CREATE HTTP {e.code}: {body2}")
        if e.code == 409:
            return _fs_patch_full(path, fields, token)
    except Exception as e:
        print(f"[FS] CREATE error: {e}")
    return False


def _fs_patch_full(path: str, fields: dict, token: str) -> bool:
    url  = f"{_fs_base()}/{path}"
    body = json.dumps({"fields": fields}).encode()
    try:
        req = urllib.request.Request(
            url, data=body, headers=_auth_headers(token), method="PATCH"
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            resp = json.loads(r.read())
            print(f"[FS] PATCH-FULL OK → {resp.get('name','')}")
            return True
    except urllib.error.HTTPError as e:
        print(f"[FS] PATCH-FULL HTTP {e.code}: {_read_err(e)}")
    except Exception as e:
        print(f"[FS] PATCH-FULL error: {e}")
    return False


def _fs_patch_fields(path: str, fields: dict, masks: list, token: str) -> bool:
    mask_qs = "&".join(f"updateMask.fieldPaths={m}" for m in masks)
    url     = f"{_fs_base()}/{path}?{mask_qs}"
    body    = json.dumps({"fields": fields}).encode()
    try:
        req = urllib.request.Request(
            url, data=body, headers=_auth_headers(token), method="PATCH"
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            r.read()
            print(f"[FS] PATCH-FIELDS OK → {path}")
            return True
    except urllib.error.HTTPError as e:
        print(f"[FS] PATCH-FIELDS HTTP {e.code}: {_read_err(e)}")
    except Exception as e:
        print(f"[FS] PATCH-FIELDS error: {e}")
    return False


def _fs_list_keys(token: str) -> list:
    url     = f"{_fs_base()}/keys?pageSize=300"
    results = []
    try:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            docs = data.get("documents", [])
            print(f"[FS] LIST → {len(docs)} keys  (DB: '{ACTIVE_DB}')")
            for doc in docs:
                name   = doc.get("name", "")
                key_id = name.split("/")[-1]
                f      = doc.get("fields", {})
                def sv(x): return f.get(x, {}).get("stringValue", "")
                def bv(x):
                    v = f.get(x, {}).get("booleanValue", False)
                    return v.lower() == "true" if isinstance(v, str) else bool(v)
                results.append({
                    "id":           key_id,
                    "key":          sv("key") or key_id,
                    "active":       bv("active"),
                    "device_id":    sv("device_id"),
                    "device_label": sv("device_label"),
                    "display_name": sv("display_name"),
                    "label":        sv("label"),
                    "pc_username":  sv("pc_username"),
                    "pc_hostname":  sv("pc_hostname"),
                    "pc_os":        sv("pc_os"),
                    "pc_model":     sv("pc_model"),
                    "pc_processor": sv("pc_processor"),
                    "created_at":   sv("created_at"),
                    "activated_at": sv("activated_at"),
                })
    except urllib.error.HTTPError as e:
        print(f"[FS] LIST HTTP {e.code}: {_read_err(e)}")
    except Exception as e:
        print(f"[FS] LIST error: {e}")
    return results


def _to_str(v):  return {"stringValue": v}
def _to_bool(v): return {"booleanValue": v}


# ════════════════════════════════════════════════════════
# ADMIN WORKER
# ════════════════════════════════════════════════════════
class AdminWorker(QObject):
    sig_ready        = pyqtSignal()
    sig_error        = pyqtSignal(str)
    sig_key_created  = pyqtSignal(str)
    sig_keys_loaded  = pyqtSignal(list)
    sig_key_revoked  = pyqtSignal(str)
    sig_key_unbound  = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._sa_path = ""; self._token = ""; self._token_exp = 0; self._ready = False

    def init(self, sa_path: str):
        threading.Thread(target=self._init, args=(sa_path,), daemon=True).start()

    def _init(self, sa_path: str):
        try:
            self._sa_path = sa_path
            token = _get_sa_token(sa_path)
            if not token:
                self.sig_error.emit("Token lena fail hua.\n\npip install cryptography\nInternet check karo.")
                return
            self._token = token
            self._token_exp = int(time.time()) + 3500
            self._ready = True
            print(f"[Admin] Ready.  DB='{ACTIVE_DB}'")
            self.sig_ready.emit()
        except FileNotFoundError:
            self.sig_error.emit(f"Service account file nahi mili:\n{sa_path}")
        except Exception as e:
            self.sig_error.emit(f"Init failed:\n{e}")

    def _tok(self) -> str:
        if int(time.time()) >= self._token_exp:
            new = _get_sa_token(self._sa_path)
            if new:
                self._token = new; self._token_exp = int(time.time()) + 3500
        return self._token

    def create_key(self, label: str = ""):
        threading.Thread(target=self._create_key, args=(label,), daemon=True).start()

    def _create_key(self, label: str):
        try:
            token = self._tok()
            key   = generate_key()
            print(f"[Admin] Creating {key}")
            fields = {
                "key":          _to_str(key),
                "active":       _to_bool(True),
                "device_id":    _to_str(""),
                "device_label": _to_str(""),
                "display_name": _to_str(""),
                "label":        _to_str(label),
                "pc_username":  _to_str(""),
                "pc_hostname":  _to_str(""),
                "pc_os":        _to_str(""),
                "pc_model":     _to_str(""),
                "pc_processor": _to_str(""),
                "created_at":   _to_str(datetime.now(timezone.utc).isoformat()),
                "activated_at": _to_str(""),
            }
            ok = _fs_create(f"keys/{key}", fields, token)
            if ok:
                saved = _fs_get(f"keys/{key}", token)
                if saved:
                    print(f"[Admin] Key verified ✓")
                    self.sig_key_created.emit(key)
                else:
                    self.sig_error.emit(f"Key likh gaya lekin verify nahi hua!\nKey: {key}")
            else:
                self.sig_error.emit(
                    f"Key save nahi hua.\n\n"
                    f"• Service account ko Firestore write permission chahiye\n"
                    f"• Console output mein HTTP error dekhen\n\n"
                    f"DB: {ACTIVE_DB}"
                )
        except Exception as e:
            self.sig_error.emit(f"Key creation failed:\n{e}")

    def load_keys(self):
        if not self._ready: return
        threading.Thread(target=self._load_keys, daemon=True).start()

    def _load_keys(self):
        try:
            keys = _fs_list_keys(self._tok())
            keys.sort(key=lambda x: x.get("created_at",""), reverse=True)
            self.sig_keys_loaded.emit(keys)
        except Exception as e:
            self.sig_error.emit(f"Load failed:\n{e}")

    def revoke_key(self, key: str):
        threading.Thread(target=self._revoke, args=(key,), daemon=True).start()

    def _revoke(self, key: str):
        try:
            fields = {"active": _to_bool(False), "revoked_at": _to_str(datetime.now(timezone.utc).isoformat())}
            ok = _fs_patch_fields(f"keys/{key}", fields, ["active","revoked_at"], self._tok())
            if ok: self.sig_key_revoked.emit(key)
            else:  self.sig_error.emit("Revoke failed.")
        except Exception as e:
            self.sig_error.emit(f"Revoke failed:\n{e}")

    def unbind_device(self, key: str):
        threading.Thread(target=self._unbind, args=(key,), daemon=True).start()

    def _unbind(self, key: str):
        try:
            masks  = ["device_id","device_label","display_name","activated_at",
                      "pc_username","pc_hostname","pc_os","pc_model","pc_processor"]
            fields = {m: _to_str("") for m in masks}
            ok = _fs_patch_fields(f"keys/{key}", fields, masks, self._tok())
            if ok: self.sig_key_unbound.emit(key)
            else:  self.sig_error.emit("Unbind failed.")
        except Exception as e:
            self.sig_error.emit(f"Unbind failed:\n{e}")


# ════════════════════════════════════════════════════════
# PARTICLE CANVAS
# ════════════════════════════════════════════════════════
class ParticleCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._pts = [
            {'x': rnd.uniform(0,1), 'y': rnd.uniform(0,1),
             'vx': rnd.uniform(-0.0003,0.0003), 'vy': rnd.uniform(-0.0002,0.0002),
             'r': rnd.uniform(1,2.5), 'a': rnd.uniform(0.1,0.5),
             'c': rnd.choice([ACCENT,CYAN,TEAL])}
            for _ in range(45)
        ]
        self._t = 0.0
        t = QTimer(self); t.timeout.connect(self._tick); t.start(33)

    def _tick(self):
        self._t += 0.01
        for p in self._pts:
            p['x']=(p['x']+p['vx'])%1.0; p['y']=(p['y']+p['vy'])%1.0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        W,H = self.width(),self.height()
        p.fillRect(0,0,W,H,QColor(BG))
        p.setPen(QPen(QColor(124,92,252,8),0.5))
        for x in range(0,W,50): p.drawLine(x,0,x,H)
        for y in range(0,H,50): p.drawLine(0,y,W,y)
        for cx,cy,cr,col,alpha in [
            (W*.1,H*.2,200,(124,92,252),22),
            (W*.9,H*.8,160,(0,229,255),16),
        ]:
            gr=QRadialGradient(cx,cy,cr)
            gr.setColorAt(0,QColor(*col,alpha)); gr.setColorAt(1,QColor(0,0,0,0))
            p.setBrush(QBrush(gr)); p.setPen(Qt.NoPen)
            p.drawEllipse(int(cx-cr),int(cy-cr),int(cr*2),int(cr*2))
        pts_abs=[(int(pt['x']*W),int(pt['y']*H)) for pt in self._pts]
        for i,(x1,y1) in enumerate(pts_abs):
            for j,(x2,y2) in enumerate(pts_abs):
                if j<=i: continue
                d=((x2-x1)**2+(y2-y1)**2)**.5
                if d<100:
                    p.setPen(QPen(QColor(124,92,252,int((1-d/100)*30)),0.5))
                    p.drawLine(x1,y1,x2,y2)
        for i,(x,y) in enumerate(pts_abs):
            pt=self._pts[i]; a=int(pt['a']*180*(0.7+0.3*math.sin(self._t*2+i)))
            col=QColor(pt['c']); col.setAlpha(a)
            p.setPen(Qt.NoPen); p.setBrush(QBrush(col))
            r=pt['r']; p.drawEllipse(int(x-r),int(y-r),int(r*2),int(r*2))
        p.end()


# ════════════════════════════════════════════════════════
# UI HELPERS
# ════════════════════════════════════════════════════════
def glow_btn(text, color=ACCENT, small=False) -> QPushButton:
    btn=QPushButton(text); btn.setFixedHeight(36 if small else 42)
    btn.setCursor(Qt.PointingHandCursor)
    c2="#5a3dd4" if color==ACCENT else color
    btn.setStyleSheet(f"""
        QPushButton {{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 {color},stop:1 {c2});
            border:none;border-radius:8px;color:white;
            font-size:{'11' if small else '12'}px;letter-spacing:2px;
            font-family:'Courier New';font-weight:700;padding:0 14px;
        }}
        QPushButton:hover {{ opacity:0.88; }}
        QPushButton:disabled {{ background:rgba(90,100,140,0.2);color:rgba(90,100,140,0.5); }}
    """)
    return btn


def outline_btn(text) -> QPushButton:
    btn=QPushButton(text); btn.setFixedHeight(36); btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(f"""
        QPushButton {{
            background:transparent;border:1px solid rgba(124,92,252,0.35);
            border-radius:8px;color:{ACC2};font-size:11px;letter-spacing:2px;
            font-family:'Courier New';padding:0 14px;
        }}
        QPushButton:hover {{ background:rgba(124,92,252,0.08); }}
    """)
    return btn


def make_cell(text:str, color:str=TEXT, mono:bool=True) -> QTableWidgetItem:
    item=QTableWidgetItem(str(text) if text else "—")
    item.setForeground(QColor(color if text else MUTED))
    if mono: item.setFont(QFont("Courier New",10))
    item.setFlags(Qt.ItemIsSelectable|Qt.ItemIsEnabled)
    return item


# ════════════════════════════════════════════════════════
# CONNECT PANEL
# ════════════════════════════════════════════════════════
class ConnectPanel(QFrame):
    sig_connected = pyqtSignal()

    def __init__(self, worker: AdminWorker, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._worker = worker
        self._build()
        self._worker.sig_ready.connect(self._on_ready)
        self._worker.sig_error.connect(self._on_error)

    def _build(self):
        self.setFixedWidth(480)
        self.setStyleSheet(f"""
            QFrame {{
                background:rgba(11,14,32,0.96);
                border:1px solid rgba(124,92,252,0.22);
                border-radius:18px;
            }}
        """)
        vl=QVBoxLayout(self); vl.setContentsMargins(36,32,36,32); vl.setSpacing(16)

        logo_row=QHBoxLayout(); logo_row.setAlignment(Qt.AlignCenter)
        ring=QLabel("⬡"); ring.setFixedSize(44,44); ring.setAlignment(Qt.AlignCenter)
        ring.setStyleSheet(f"border:2px solid {ACCENT};border-radius:22px;color:{ACCENT};font-size:18px;background:transparent;")
        title=QLabel("ALIRA  ADMIN")
        title.setStyleSheet(f"color:{TEXT};font-size:20px;font-weight:800;letter-spacing:4px;background:transparent;")
        logo_row.addWidget(ring); logo_row.addSpacing(10); logo_row.addWidget(title)
        vl.addLayout(logo_row)

        sub=QLabel("KEY MANAGEMENT CONSOLE")
        sub.setAlignment(Qt.AlignCenter)
        sub.setStyleSheet(f"color:{MUTED};font-size:9px;letter-spacing:3px;font-family:'Courier New';background:transparent;")
        vl.addWidget(sub)

        db_badge=QLabel(f"DB:  {ACTIVE_DB}   ·   Format:  ALIRA-XXXX-XXXXX")
        db_badge.setAlignment(Qt.AlignCenter)
        db_badge.setStyleSheet(f"""
            QLabel {{
                background:rgba(0,201,167,0.08);border:1px solid rgba(0,201,167,0.25);
                border-radius:6px;padding:4px 12px;color:{TEAL};
                font-size:10px;font-family:'Courier New';
            }}
        """)
        vl.addWidget(db_badge)

        sep=QFrame(); sep.setFixedHeight(1); sep.setStyleSheet(f"background:rgba(124,92,252,0.18);border:none;")
        vl.addWidget(sep)

        lbl=QLabel("SERVICE ACCOUNT JSON")
        lbl.setStyleSheet(f"color:{MUTED};font-size:10px;letter-spacing:2px;font-family:'Courier New';background:transparent;")
        vl.addWidget(lbl)

        path_row=QHBoxLayout(); path_row.setSpacing(8)
        self._path_inp=QLineEdit()
        self._path_inp.setPlaceholderText("Path to firebase-adminsdk-*.json")
        self._path_inp.setFixedHeight(42)
        self._path_inp.setStyleSheet(f"""
            QLineEdit {{
                background:rgba(5,8,16,0.85);border:1.5px solid rgba(124,92,252,0.2);
                border-radius:9px;padding:10px 14px;color:{TEXT};
                font-size:12px;font-family:'Courier New';
            }}
            QLineEdit:focus {{ border-color:{ACCENT}; }}
        """)
        browse_btn=outline_btn("BROWSE"); browse_btn.setFixedWidth(80)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(self._path_inp); path_row.addWidget(browse_btn)
        vl.addLayout(path_row)

        detected=_find_sa()
        if detected:
            self._path_inp.setText(str(detected))
            hint=QLabel(f"✓  Found:  {detected.name}")
            hint.setStyleSheet(f"color:{GREEN};font-size:11px;font-family:'Courier New';background:transparent;")
            vl.addWidget(hint)
        else:
            hint=QLabel("firebase-adminsdk JSON ko same folder mein rakho ya BROWSE karo.")
            hint.setWordWrap(True)
            hint.setStyleSheet(f"color:{GOLD};font-size:11px;background:transparent;")
            vl.addWidget(hint)

        self._err_lbl=QLabel(""); self._err_lbl.setWordWrap(True)
        self._err_lbl.setAlignment(Qt.AlignCenter)
        self._err_lbl.setStyleSheet(f"color:{RED};font-size:11px;background:transparent;min-height:18px;")
        vl.addWidget(self._err_lbl)

        self._btn=glow_btn("CONNECT TO FIREBASE")
        self._btn.clicked.connect(self._connect)
        vl.addWidget(self._btn)

    def _browse(self):
        path,_=QFileDialog.getOpenFileName(self,"Select Service Account JSON","","JSON Files (*.json)")
        if path: self._path_inp.setText(path)

    def _connect(self):
        path=self._path_inp.text().strip()
        if not path: self._err_lbl.setText("❌ JSON file select karo"); return
        if not Path(path).exists(): self._err_lbl.setText("❌ File nahi mili"); return
        try:
            with open(path) as f: sa=json.load(f)
            if sa.get("type")!="service_account":
                self._err_lbl.setText("❌ Firebase service account JSON hona chahiye"); return
        except Exception as e:
            self._err_lbl.setText(f"❌ JSON read error: {e}"); return
        self._err_lbl.setText("")
        self._btn.setEnabled(False); self._btn.setText("CONNECTING...")
        self._worker.init(path)

    def _on_ready(self):  self.sig_connected.emit()
    def _on_error(self, msg):
        self._btn.setEnabled(True); self._btn.setText("CONNECT TO FIREBASE")
        self._err_lbl.setText(f"❌ {msg}")


# ════════════════════════════════════════════════════════
# ADMIN DASHBOARD
# ════════════════════════════════════════════════════════
class AdminDashboard(QWidget):
    def __init__(self, worker: AdminWorker, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(f"background:rgba(7,9,26,0.97);")
        self._worker=worker; self._keys=[]
        self._build()
        self._worker.sig_keys_loaded.connect(self._on_keys_loaded)
        self._worker.sig_key_created.connect(self._on_key_created)
        self._worker.sig_key_revoked.connect(self._on_key_revoked)
        self._worker.sig_key_unbound.connect(self._on_key_unbound)
        self._worker.sig_error.connect(self._on_error)
        self._worker.load_keys()

    def _build(self):
        vl=QVBoxLayout(self); vl.setContentsMargins(28,20,28,20); vl.setSpacing(14)

        header_row=QHBoxLayout()
        logo=QLabel("✦  ALIRA ADMIN  —  KEY CONSOLE")
        logo.setStyleSheet(f"color:{ACCENT};font-size:15px;font-weight:800;letter-spacing:3px;font-family:'Courier New';background:transparent;")
        self._status_lbl=QLabel(f"● CONNECTED  ·  DB: {ACTIVE_DB}")
        self._status_lbl.setStyleSheet(f"color:{GREEN};font-size:10px;font-family:'Courier New';background:transparent;")
        header_row.addWidget(logo); header_row.addStretch(); header_row.addWidget(self._status_lbl)
        vl.addLayout(header_row)

        sep=QFrame(); sep.setFixedHeight(1); sep.setStyleSheet(f"background:rgba(124,92,252,0.2);border:none;")
        vl.addWidget(sep)

        stats_row=QHBoxLayout(); stats_row.setSpacing(12)
        self._stat_total   = self._make_stat("TOTAL KEYS","0")
        self._stat_active  = self._make_stat("ACTIVE","0",GREEN)
        self._stat_bound   = self._make_stat("DEVICE BOUND","0",CYAN)
        self._stat_revoked = self._make_stat("REVOKED","0",RED)
        for s in [self._stat_total,self._stat_active,self._stat_bound,self._stat_revoked]:
            stats_row.addWidget(s)
        vl.addLayout(stats_row)

        tool_row=QHBoxLayout(); tool_row.setSpacing(10)
        self._label_inp=QLineEdit()
        self._label_inp.setPlaceholderText("Note / label (optional)  e.g. 'User1 - Jan 2025'")
        self._label_inp.setFixedHeight(38)
        self._label_inp.setStyleSheet(f"""
            QLineEdit {{
                background:rgba(5,8,16,0.8);border:1.5px solid rgba(124,92,252,0.18);
                border-radius:8px;padding:8px 13px;color:{TEXT};
                font-size:12px;font-family:'Courier New';
            }}
            QLineEdit:focus {{ border-color:{ACCENT}; }}
        """)
        self._gen_btn=glow_btn("+ GENERATE ALIRA KEY",small=True)
        self._refresh_btn=outline_btn("↻ REFRESH")
        self._gen_btn.clicked.connect(self._generate_key)
        self._refresh_btn.clicked.connect(self._worker.load_keys)
        tool_row.addWidget(self._label_inp,1)
        tool_row.addWidget(self._gen_btn)
        tool_row.addWidget(self._refresh_btn)
        vl.addLayout(tool_row)

        self._table=QTableWidget()
        self._table.setColumnCount(9)
        self._table.setHorizontalHeaderLabels([
            "ACCESS KEY","LABEL","STATUS","USER NAME",
            "PC USERNAME","PC HOSTNAME","OS","CREATED","ACTIONS"
        ])
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background:rgba(5,8,16,0.6);
                border:1px solid rgba(124,92,252,0.15);
                border-radius:10px;color:{TEXT};
                gridline-color:rgba(255,255,255,0.04);
                font-family:'Courier New';font-size:10px;
            }}
            QHeaderView::section {{
                background:rgba(11,14,32,0.95);color:{MUTED};
                border:none;border-bottom:1px solid rgba(124,92,252,0.18);
                padding:7px 8px;font-size:9px;letter-spacing:1px;
                font-family:'Courier New';
            }}
            QTableWidget::item {{ padding:5px 8px;border-bottom:1px solid rgba(255,255,255,0.04); }}
            QTableWidget::item:selected {{ background:rgba(124,92,252,0.12); }}
            QScrollBar:vertical {{ background:rgba(5,8,16,0.5);width:7px;border-radius:3px; }}
            QScrollBar::handle:vertical {{ background:rgba(124,92,252,0.3);border-radius:3px; }}
            QScrollBar:horizontal {{ background:rgba(5,8,16,0.5);height:7px;border-radius:3px; }}
            QScrollBar::handle:horizontal {{ background:rgba(124,92,252,0.3);border-radius:3px; }}
        """)
        hdr=self._table.horizontalHeader()
        hdr.setSectionResizeMode(QHeaderView.Interactive)
        for i,w in enumerate([165,100,80,110,110,120,130,85,160]):
            self._table.setColumnWidth(i,w)
        hdr.setSectionResizeMode(8,QHeaderView.Fixed); self._table.setColumnWidth(8,160)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        vl.addWidget(self._table)

        self._info_lbl=QLabel("Loading keys...")
        self._info_lbl.setStyleSheet(f"color:{MUTED};font-size:11px;font-family:'Courier New';background:transparent;")
        vl.addWidget(self._info_lbl)

    def _make_stat(self,label,value,color=TEXT):
        frame=QFrame()
        frame.setStyleSheet(f"QFrame{{background:rgba(11,14,32,0.85);border:1px solid rgba(124,92,252,0.12);border-radius:9px;}}")
        fl=QVBoxLayout(frame); fl.setContentsMargins(14,10,14,10); fl.setSpacing(2)
        l1=QLabel(label); l1.setStyleSheet(f"color:{MUTED};font-size:9px;letter-spacing:2px;font-family:'Courier New';background:transparent;")
        l2=QLabel(value); l2.setStyleSheet(f"color:{color};font-size:20px;font-family:'Courier New';font-weight:700;background:transparent;")
        l2.setObjectName("val"); fl.addWidget(l1); fl.addWidget(l2)
        return frame

    def _stat_val(self,frame): return frame.findChild(QLabel,"val")

    def _generate_key(self):
        label=self._label_inp.text().strip()
        self._gen_btn.setEnabled(False); self._gen_btn.setText("CREATING...")
        self._info_lbl.setText("Firestore mein key save ho rahi hai...")
        self._info_lbl.setStyleSheet(f"color:{GOLD};font-size:11px;font-family:'Courier New';background:transparent;")
        self._worker.create_key(label)

    def _on_key_created(self, key):
        self._gen_btn.setEnabled(True); self._gen_btn.setText("+ GENERATE ALIRA KEY")
        self._label_inp.clear()
        self._info_lbl.setText(f"✓  Key created & copied:  {key}")
        self._info_lbl.setStyleSheet(f"color:{GREEN};font-size:11px;font-family:'Courier New';background:transparent;")
        QApplication.clipboard().setText(key)
        self._worker.load_keys()

    def _on_keys_loaded(self, keys):
        self._keys=keys; self._render_table(keys); self._update_stats(keys)
        self._info_lbl.setText(
            f"Last refresh: {datetime.now().strftime('%H:%M:%S')}  ·  {len(keys)} keys  ·  DB: {ACTIVE_DB}"
        )
        self._info_lbl.setStyleSheet(f"color:{MUTED};font-size:11px;font-family:'Courier New';background:transparent;")

    def _render_table(self, keys):
        self._table.setRowCount(0)
        for ri,k in enumerate(keys):
            self._table.insertRow(ri)
            key_id=k.get("key",k.get("id",""))
            active=k.get("active",False); device_id=k.get("device_id","")
            is_bound=bool(device_id)
            self._table.setItem(ri,0,make_cell(key_id,ACCENT))
            self._table.setItem(ri,1,make_cell(k.get("label",""),MUTED))
            self._table.setItem(ri,2,make_cell("ACTIVE" if active else "REVOKED",GREEN if active else RED))
            self._table.setItem(ri,3,make_cell(k.get("display_name",""),TEXT))
            self._table.setItem(ri,4,make_cell(k.get("pc_username",""),CYAN if k.get("pc_username") else MUTED))
            self._table.setItem(ri,5,make_cell(k.get("pc_hostname",""),CYAN if k.get("pc_hostname") else MUTED))
            self._table.setItem(ri,6,make_cell(k.get("pc_os",""),MUTED2 if k.get("pc_os") else MUTED))
            self._table.setItem(ri,7,make_cell(k.get("created_at","")[:10],MUTED))

            if is_bound:
                tt=(f"Device Info\n──────────────────────\n"
                    f"Username   : {k.get('pc_username','—')}\n"
                    f"Hostname   : {k.get('pc_hostname','—')}\n"
                    f"OS         : {k.get('pc_os','—')}\n"
                    f"PC Model   : {k.get('pc_model','—')}\n"
                    f"Processor  : {k.get('pc_processor','—')}\n"
                    f"Device ID  : {device_id[:20]}...")
                for col in range(8):
                    item=self._table.item(ri,col)
                    if item: item.setToolTip(tt)

            aw=QWidget(); aw.setStyleSheet("background:transparent;")
            al=QHBoxLayout(aw); al.setContentsMargins(4,2,4,2); al.setSpacing(5)

            def mk_btn(text,fg,bg):
                b=QPushButton(text); b.setFixedHeight(26); b.setCursor(Qt.PointingHandCursor)
                b.setStyleSheet(f"""
                    QPushButton{{background:{bg};border:1px solid {fg}40;border-radius:6px;
                    color:{fg};font-size:9px;letter-spacing:1px;font-family:'Courier New';padding:0 7px;}}
                    QPushButton:hover{{background:{fg}30;}}
                """)
                return b

            copy_btn=mk_btn("COPY",CYAN,"rgba(0,229,255,0.08)")
            copy_btn.clicked.connect(lambda _,k=key_id: self._copy_key(k))
            al.addWidget(copy_btn)
            if active:
                rev_btn=mk_btn("REVOKE",RED,"rgba(255,71,87,0.10)")
                rev_btn.clicked.connect(lambda _,k=key_id: self._revoke_key(k))
                al.addWidget(rev_btn)
            if is_bound:
                ub_btn=mk_btn("UNBIND",GOLD,"rgba(255,201,71,0.08)")
                ub_btn.clicked.connect(lambda _,k=key_id: self._unbind_device(k))
                al.addWidget(ub_btn)

            self._table.setCellWidget(ri,8,aw)
            self._table.setRowHeight(ri,40)

    def _update_stats(self,keys):
        total=len(keys); active=sum(1 for k in keys if k.get("active",False))
        bound=sum(1 for k in keys if k.get("device_id",""))
        self._stat_val(self._stat_total).setText(str(total))
        self._stat_val(self._stat_active).setText(str(active))
        self._stat_val(self._stat_bound).setText(str(bound))
        self._stat_val(self._stat_revoked).setText(str(total-active))

    def _copy_key(self,key):
        QApplication.clipboard().setText(key)
        self._info_lbl.setText(f"✓  Copied:  {key}")
        self._info_lbl.setStyleSheet(f"color:{GREEN};font-size:11px;font-family:'Courier New';background:transparent;")

    def _revoke_key(self,key):
        if QMessageBox.question(self,"Revoke",f"Revoke key  {key}?\n\nUser ka access immediately band ho jaayega.",
                                QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:
            self._worker.revoke_key(key)

    def _unbind_device(self,key):
        if QMessageBox.question(self,"Unbind",f"Unbind device from  {key}?\n\nKey naye device pe use ho sakegi.",
                                QMessageBox.Yes|QMessageBox.No)==QMessageBox.Yes:
            self._worker.unbind_device(key)

    def _on_key_revoked(self,key):
        self._info_lbl.setText(f"✓  Revoked:  {key}")
        self._info_lbl.setStyleSheet(f"color:{RED};font-size:11px;font-family:'Courier New';background:transparent;")
        self._worker.load_keys()

    def _on_key_unbound(self,key):
        self._info_lbl.setText(f"✓  Unbound:  {key}")
        self._info_lbl.setStyleSheet(f"color:{GOLD};font-size:11px;font-family:'Courier New';background:transparent;")
        self._worker.load_keys()

    def _on_error(self,msg):
        self._info_lbl.setText(f"❌  {msg}")
        self._info_lbl.setStyleSheet(f"color:{RED};font-size:11px;font-family:'Courier New';background:transparent;")
        self._gen_btn.setEnabled(True); self._gen_btn.setText("+ GENERATE ALIRA KEY")


# ════════════════════════════════════════════════════════
# MAIN WINDOW
# ════════════════════════════════════════════════════════
class AdminWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ALIRA Admin — Key Console")
        self.setMinimumSize(1200,680); self.resize(1400,760)
        self._worker=AdminWorker(); self._build()

    def _build(self):
        self._canvas=ParticleCanvas(self)
        self._canvas.setGeometry(0,0,self.width(),self.height())

        self._connect_panel=ConnectPanel(self._worker,self)
        self._connect_panel.setFixedWidth(480)
        self._pos_panel()
        self._connect_panel.sig_connected.connect(self._on_connected)

        top=QLabel("ALIRA  ·  ADMIN KEY CONSOLE",self)
        top.setGeometry(0,10,self.width(),18); top.setAlignment(Qt.AlignCenter)
        top.setStyleSheet(f"color:rgba(124,92,252,0.22);font-family:'Courier New';font-size:9px;letter-spacing:3px;background:transparent;")

        self._dashboard=AdminDashboard(self._worker,self)
        self._dashboard.setGeometry(0,0,self.width(),self.height())
        self._dashboard.hide()

    def _pos_panel(self):
        self._connect_panel.adjustSize()
        ch=max(self._connect_panel.sizeHint().height(),380)
        self._connect_panel.move((self.width()-480)//2, max(40,(self.height()-ch)//2))

    def resizeEvent(self,e):
        super().resizeEvent(e); W,H=self.width(),self.height()
        self._canvas.setGeometry(0,0,W,H); self._pos_panel()
        if not self._dashboard.isHidden():
            self._dashboard.setGeometry(0,30,W,H-30)

    def _on_connected(self):
        self._connect_panel.hide()
        self._dashboard.setGeometry(0,30,self.width(),self.height()-30)
        self._dashboard.show(); self._worker.load_keys()


# ════════════════════════════════════════════════════════
# ENTRY POINT
# ════════════════════════════════════════════════════════
if __name__ == "__main__":
    app=QApplication(sys.argv); app.setStyle("Fusion")
    pal=QPalette()
    pal.setColor(QPalette.Window,QColor(BG)); pal.setColor(QPalette.WindowText,QColor(TEXT))
    pal.setColor(QPalette.Base,QColor(BG2));  pal.setColor(QPalette.Text,QColor(TEXT))
    pal.setColor(QPalette.Button,QColor(BG3)); pal.setColor(QPalette.ButtonText,QColor(TEXT))
    pal.setColor(QPalette.Highlight,QColor(ACCENT)); pal.setColor(QPalette.HighlightedText,QColor("#ffffff"))
    app.setPalette(pal)
    win=AdminWindow(); win.show(); sys.exit(app.exec_())