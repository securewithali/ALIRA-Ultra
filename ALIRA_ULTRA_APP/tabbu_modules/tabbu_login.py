# -*- coding: utf-8 -*-
"""
ALIRA v3 — Login / Register Page
Run: python ALIRA_login.py
Firebase Authentication + Firestore data storage
"""
from ALIRA_slot import slot as _ALIRA_slot
import sys, json, threading, math, random
from datetime import datetime, timezone

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QFrame, QGraphicsOpacityEffect,
    QStackedWidget, QSizePolicy
)
from PyQt5.QtCore  import (
    Qt, QTimer, QThread, pyqtSignal, QObject,
    QPropertyAnimation, QEasingCurve, QRect, pyqtProperty
)
from PyQt5.QtGui   import (
    QColor, QPainter, QPen, QBrush, QLinearGradient,
    QRadialGradient, QPalette, QFont, QPixmap, QRegion
)

import urllib.request, urllib.parse

HAS_FIREBASE = True

# ── Firebase config ───────────────────────────────────────
FIREBASE_CONFIG = {
    "apiKey":            "AIzaSyBnCcB4PwUvKsWGNk-B_iJGIgqoWKlPlgw",
    "authDomain":        "gen-lang-client-0451150300.firebaseapp.com",
    "databaseURL":       "",
    "projectId":         "gen-lang-client-0451150300",
    "storageBucket":     "gen-lang-client-0451150300.firebasestorage.app",
    "messagingSenderId": "130691627400",
    "appId":             "1:130691627400:web:c324835128f88c2c26623d",
}
_API_KEY = FIREBASE_CONFIG["apiKey"]
_PROJECT = FIREBASE_CONFIG["projectId"]
_DB_ID   = "(default)"
_AUTH_BASE = "https://identitytoolkit.googleapis.com/v1/accounts"
_FS_BASE   = f"https://firestore.googleapis.com/v1/projects/{_PROJECT}/databases/{_DB_ID}/documents"


def _firebase_post(endpoint: str, payload: dict) -> dict:
    """Firebase Auth REST call karo."""
    url  = f"{_AUTH_BASE}:{endpoint}?key={_API_KEY}"
    data = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode("utf-8"))


def _fs_patch(path: str, doc: dict, token: str, masks: list = None):
    """Firestore document update karo."""
    url = f"{_FS_BASE}/{path}?access_token={token}"
    if masks:
        url += "".join(f"&updateMask.fieldPaths={m}" for m in masks)
    data = json.dumps(doc).encode("utf-8")
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
        method="PATCH"
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"Firestore warning: {e}")
        return None

# ── Colors ────────────────────────────────────────────────
BG      = "#050810"
BG2     = "#080d18"
BG3     = "#0d1525"
ACCENT  = "#e8406a"
ACCENT2 = "#ff6b9d"
CYAN    = "#00d4ff"
GOLD    = "#ffd060"
TEXT    = "#e8eaf6"
MUTED   = "#6b7394"
GREEN   = "#2ecc71"
RED     = "#e74c3c"

# ══════════════════════════════════════════════════════════
# PARTICLE CANVAS  (animated background)
# ══════════════════════════════════════════════════════════
class ParticleCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._pts = [
            {
                'x': random.uniform(0,1),
                'y': random.uniform(0,1),
                'vx': random.uniform(-0.0003, 0.0003),
                'vy': random.uniform(-0.0002, 0.0002),
                'r': random.uniform(1,2.5),
                'a': random.uniform(0.1, 0.5),
            }
            for _ in range(55)
        ]
        self._t = 0.0
        t = QTimer(self); t.timeout.connect(_ALIRA_slot(self._tick)); t.start(33)

    def _tick(self):
        self._t += 0.01
        W, H = max(self.width(),1), max(self.height(),1)
        for p in self._pts:
            p['x'] = (p['x'] + p['vx']) % 1.0
            p['y'] = (p['y'] + p['vy']) % 1.0
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()

        # Dark BG
        p.fillRect(0, 0, W, H, QColor(BG))

        # Grid
        pen = QPen(QColor(0,212,255,12), 0.5)
        p.setPen(pen)
        for x in range(0, W, 44):
            p.drawLine(x, 0, x, H)
        for y in range(0, H, 44):
            p.drawLine(0, y, W, y)

        # Orb glow left
        gr = QRadialGradient(W*0.15, H*0.3, 220)
        gc = QColor(232, 64, 106, 35); gr.setColorAt(0, gc); gr.setColorAt(1, QColor(0,0,0,0))
        p.setBrush(QBrush(gr)); p.setPen(Qt.NoPen)
        p.drawEllipse(int(W*0.15-220), int(H*0.3-220), 440, 440)

        # Orb glow right
        gr2 = QRadialGradient(W*0.85, H*0.7, 180)
        gc2 = QColor(0,212,255,25); gr2.setColorAt(0, gc2); gr2.setColorAt(1, QColor(0,0,0,0))
        p.setBrush(QBrush(gr2)); p.setPen(Qt.NoPen)
        p.drawEllipse(int(W*0.85-180), int(H*0.7-180), 360, 360)

        # Particles + connections
        pts_abs = [(int(pt['x']*W), int(pt['y']*H)) for pt in self._pts]
        for i, (x1,y1) in enumerate(pts_abs):
            for j, (x2,y2) in enumerate(pts_abs):
                if j <= i: continue
                d = ((x2-x1)**2 + (y2-y1)**2)**0.5
                if d < 110:
                    a = int((1-d/110)*40)
                    lc = QColor(0,212,255,a); p.setPen(QPen(lc, 0.5))
                    p.drawLine(x1,y1,x2,y2)

        for i, (x,y) in enumerate(pts_abs):
            pt = self._pts[i]
            a  = int(pt['a'] * 200 * (0.7 + 0.3*math.sin(self._t*2 + i)))
            col = QColor(ACCENT) if i%3==0 else QColor(CYAN)
            col.setAlpha(a)
            p.setPen(Qt.NoPen); p.setBrush(QBrush(col))
            r = pt['r']
            p.drawEllipse(int(x-r), int(y-r), int(r*2), int(r*2))
        p.end()


# ══════════════════════════════════════════════════════════
# CUSTOM INPUT FIELD
# ══════════════════════════════════════════════════════════
class GlowInput(QLineEdit):
    def __init__(self, placeholder="", echo=False, parent=None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        if echo:
            self.setEchoMode(QLineEdit.Password)
        self._focused = False
        self._update_style(False)

    def _update_style(self, focused):
        border = ACCENT if focused else "rgba(0,212,255,0.2)"
        glow   = f"box-shadow: 0 0 14px rgba(232,64,106,0.4);" if focused else ""
        self.setStyleSheet(f"""
            QLineEdit {{
                background: rgba(8,13,24,0.8);
                border: 1.5px solid {border};
                border-radius: 10px;
                padding: 12px 16px;
                color: {TEXT};
                font-size: 14px;
                font-family: 'Segoe UI';
            }}
            QLineEdit:focus {{
                border: 1.5px solid {ACCENT};
                background: rgba(13,21,37,0.9);
            }}
        """)

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self._update_style(True)

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self._update_style(False)


# ══════════════════════════════════════════════════════════
# FIREBASE WORKER  (Pure REST — no pyrebase needed)
# ══════════════════════════════════════════════════════════
class FirebaseWorker(QObject):
    sig_success = pyqtSignal(dict)
    sig_error   = pyqtSignal(str)
    sig_done    = pyqtSignal()

    def __init__(self):
        super().__init__()

    def login(self, email: str, password: str):
        threading.Thread(target=self._login, args=(email, password), daemon=True).start()

    def register(self, email: str, password: str, name: str):
        threading.Thread(target=self._register, args=(email, password, name), daemon=True).start()

    def _login(self, email, password):
        try:
            # Firebase Auth REST: signInWithPassword
            resp = _firebase_post("signInWithPassword", {
                "email": email,
                "password": password,
                "returnSecureToken": True
            })
            uid      = resp["localId"]
            id_token = resp["idToken"]

            # Get display name via lookup
            try:
                info = _firebase_post("lookup", {"idToken": id_token})
                display_name = (info.get("users", [{}])[0]
                                .get("displayName", email.split("@")[0]))
            except Exception:
                display_name = email.split("@")[0]

            self._save_login_record(uid, id_token, display_name)

            self.sig_success.emit({
                "uid":         uid,
                "email":       email,
                "displayName": display_name,
                "idToken":     id_token,
            })
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            err  = json.loads(body).get("error", {}).get("message", body)
            if "INVALID_PASSWORD" in err or "INVALID_LOGIN_CREDENTIALS" in err or "INVALID_EMAIL" in err:
                self.sig_error.emit("❌ Incorrect email or password")
            elif "EMAIL_NOT_FOUND" in err:
                self.sig_error.emit("❌ No account found with this email")
            elif "TOO_MANY_ATTEMPTS" in err or "BLOCKED" in err:
                self.sig_error.emit("❌ Too many attempts — please try again later")
            elif "USER_DISABLED" in err:
                self.sig_error.emit("❌ This account has been disabled")
            else:
                self.sig_error.emit(f"❌ Login failed: {err[:80]}")
        except Exception as e:
            self.sig_error.emit(f"❌ Connection error: {str(e)[:80]}")

    def _register(self, email, password, name):
        try:
            # Firebase Auth REST: signUp
            resp = _firebase_post("signUp", {
                "email": email,
                "password": password,
                "returnSecureToken": True
            })
            uid      = resp["localId"]
            id_token = resp["idToken"]

            # Update display name
            try:
                _firebase_post("update", {
                    "idToken":     id_token,
                    "displayName": name,
                    "returnSecureToken": False
                })
            except Exception:
                pass

            # Save profile to Firestore
            self._create_user_profile(uid, id_token, name, email)

            self.sig_success.emit({
                "uid":         uid,
                "email":       email,
                "displayName": name,
                "idToken":     id_token,
            })
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            err  = json.loads(body).get("error", {}).get("message", body)
            if "EMAIL_EXISTS" in err:
                self.sig_error.emit("❌ This email is already registered")
            elif "WEAK_PASSWORD" in err:
                self.sig_error.emit("❌ Password must be at least 6 characters")
            elif "INVALID_EMAIL" in err:
                self.sig_error.emit("❌ Invalid email format")
            elif "TOO_MANY_ATTEMPTS" in err:
                self.sig_error.emit("❌ Too many attempts — please try again later")
            else:
                self.sig_error.emit(f"❌ Registration failed: {err[:80]}")
        except Exception as e:
            self.sig_error.emit(f"❌ Connection error: {str(e)[:80]}")

    def _create_user_profile(self, uid, id_token, name, email):
        doc = {
            "fields": {
                "uid":         {"stringValue": uid},
                "displayName": {"stringValue": name},
                "email":       {"stringValue": email},
                "createdAt":   {"stringValue": datetime.now(timezone.utc).isoformat()},
                "preferences": {"mapValue": {"fields": {}}},
                "memory":      {"arrayValue": {"values": []}}
            }
        }
        _fs_patch(f"users/{uid}", doc, id_token)

    def _save_login_record(self, uid, id_token, display_name):
        doc = {
            "fields": {
                "lastLogin":   {"stringValue": datetime.now(timezone.utc).isoformat()},
                "displayName": {"stringValue": display_name},
            }
        }
        _fs_patch(f"users/{uid}", doc, id_token,
                  masks=["lastLogin", "displayName"])

    def save_message(self, uid, id_token, role, text):
        threading.Thread(
            target=self._save_message,
            args=(uid, id_token, role, text), daemon=True
        ).start()

    def _save_message(self, uid, id_token, role, text):
        import uuid as _uuid
        msg_id = str(_uuid.uuid4())
        doc = {
            "fields": {
                "uid":       {"stringValue": uid},
                "role":      {"stringValue": role},
                "text":      {"stringValue": text},
                "timestamp": {"stringValue": datetime.now(timezone.utc).isoformat()},
            }
        }
        _fs_patch(f"users/{uid}/messages/{msg_id}", doc, id_token)


# ══════════════════════════════════════════════════════════
# LOGIN CARD
# ══════════════════════════════════════════════════════════
class LoginCard(QFrame):
    sig_login_ok = pyqtSignal(dict)

    def __init__(self, firebase: FirebaseWorker, parent=None):
        super().__init__(parent)
        self._fb     = firebase
        self._mode   = "login"   # login | register
        self._loading = False
        self._build()
        self._fb.sig_success.connect(self._on_success)
        self._fb.sig_error.connect(self._on_error)

    def _build(self):
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(400)
        self.setStyleSheet(f"""
            QFrame {{
                background: rgba(8,13,24,0.92);
                border: 1px solid rgba(232,64,106,0.25);
                border-radius: 18px;
            }}
        """)

        vl = QVBoxLayout(self)
        vl.setContentsMargins(36, 32, 36, 32)
        vl.setSpacing(16)

        # Logo area
        logo_row = QHBoxLayout(); logo_row.setAlignment(Qt.AlignCenter)
        ring = QLabel("✦"); ring.setFixedSize(48,48); ring.setAlignment(Qt.AlignCenter)
        ring.setStyleSheet(f"border:2px solid {ACCENT};border-radius:24px;color:{ACCENT};font-size:20px;background:transparent;")
        logo_col = QVBoxLayout(); logo_col.setSpacing(0)
        logo_lbl = QLabel("ALIRA")
        logo_lbl.setStyleSheet(f"color:{ACCENT};font-size:26px;font-weight:900;letter-spacing:6px;background:transparent;")
        ver_lbl = QLabel("v4.0  ·  AI Voice Companion")
        ver_lbl.setStyleSheet(f"color:{MUTED};font-size:9px;letter-spacing:2px;font-family:'Courier New';background:transparent;")
        logo_col.addWidget(logo_lbl); logo_col.addWidget(ver_lbl)
        logo_row.addWidget(ring); logo_row.addSpacing(12); logo_row.addLayout(logo_col)
        vl.addLayout(logo_row)

        self._title = QLabel("WELCOME BACK")
        self._title.setAlignment(Qt.AlignCenter)
        self._title.setStyleSheet(f"color:{MUTED};font-size:11px;letter-spacing:5px;font-family:'Courier New';background:transparent;margin-top:2px;")
        vl.addWidget(self._title)

        vl.addSpacing(8)
        sep = QFrame(); sep.setFixedHeight(1)
        sep.setStyleSheet(f"background:rgba(232,64,106,0.2);border:none;")
        vl.addWidget(sep)
        vl.addSpacing(4)

        # Name field (only for register)
        self._name_field = GlowInput("Your full name")
        self._name_field.setFixedHeight(46)
        self._name_field.setVisible(False)
        vl.addWidget(self._name_field)

        # Email
        self._email_field = GlowInput("✉  Email address")
        self._email_field.setFixedHeight(46)
        vl.addWidget(self._email_field)

        # Password
        self._pass_field = GlowInput("🔒  Password", echo=True)
        self._pass_field.setFixedHeight(46)
        self._pass_field.returnPressed.connect(_ALIRA_slot(self._on_submit))
        vl.addWidget(self._pass_field)

        # Confirm password (register only)
        self._conf_field = GlowInput("Confirm password", echo=True)
        self._conf_field.setFixedHeight(46)
        self._conf_field.setVisible(False)
        self._conf_field.returnPressed.connect(_ALIRA_slot(self._on_submit))
        vl.addWidget(self._conf_field)

        # Error label
        self._err_lbl = QLabel("")
        self._err_lbl.setWordWrap(True)
        self._err_lbl.setAlignment(Qt.AlignCenter)
        self._err_lbl.setStyleSheet(f"color:{RED};font-size:12px;font-family:'Segoe UI';background:rgba(231,76,60,0.06);border:1px solid rgba(231,76,60,0.2);border-radius:6px;padding:4px 8px;min-height:18px;")
        vl.addWidget(self._err_lbl)

        # Submit button
        self._btn = QPushButton("LOGIN  →")
        self._btn.setFixedHeight(48)
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.clicked.connect(_ALIRA_slot(self._on_submit))
        self._btn_style(False)
        vl.addWidget(self._btn)

        # Toggle mode
        tog_row = QHBoxLayout(); tog_row.setAlignment(Qt.AlignCenter)
        self._tog_lbl = QLabel("Don't have an account?")
        self._tog_lbl.setStyleSheet(f"color:{MUTED};font-size:12px;background:transparent;")
        self._tog_btn = QPushButton("Create one")
        self._tog_btn.setFlat(True)
        self._tog_btn.setCursor(Qt.PointingHandCursor)
        self._tog_btn.setStyleSheet(f"color:{CYAN};font-size:12px;background:transparent;border:none;text-decoration:underline;")
        self._tog_btn.clicked.connect(_ALIRA_slot(self._toggle_mode))
        tog_row.addWidget(self._tog_lbl); tog_row.addWidget(self._tog_btn)
        vl.addLayout(tog_row)

    def _btn_style(self, loading):
        if loading:
            self._btn.setStyleSheet(f"""
                QPushButton {{
                    background:rgba(232,64,106,0.3); border:1.5px solid rgba(232,64,106,0.4);
                    border-radius:10px; color:rgba(255,255,255,0.5);
                    font-size:13px; letter-spacing:3px; font-family:'Courier New';
                }}
            """)
        else:
            self._btn.setStyleSheet(f"""
                QPushButton {{
                    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {ACCENT}, stop:1 #c0305a);
                    border:none; border-radius:10px;
                    color:white; font-size:13px; letter-spacing:3px;
                    font-family:'Courier New'; font-weight:700;
                }}
                QPushButton:hover {{
                    background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                        stop:0 {ACCENT2}, stop:1 {ACCENT});
                }}
                QPushButton:pressed {{ background:{ACCENT}; }}
            """)

    def _toggle_mode(self):
        self._err_lbl.setText("")
        if self._mode == "login":
            self._mode = "register"
            self._title.setText("JOIN ALIRA")
            self._btn.setText("CREATE ACCOUNT")
            self._tog_lbl.setText("Already have an account?")
            self._tog_btn.setText("Sign in")
            self._name_field.setVisible(True)
            self._conf_field.setVisible(True)
        else:
            self._mode = "login"
            self._title.setText("WELCOME BACK  ❤")
            self._btn.setText("LOGIN")
            self._tog_lbl.setText("Don't have an account?")
            self._tog_btn.setText("Create one")
            self._name_field.setVisible(False)
            self._conf_field.setVisible(False)

    def _on_submit(self):
        if self._loading: return
        self._err_lbl.setText("")

        email = self._email_field.text().strip()
        pwd   = self._pass_field.text()

        if not email or not pwd:
            self._err_lbl.setText("❌ Email and password are required")
            return

        if self._mode == "register":
            name = self._name_field.text().strip() or email.split('@')[0]
            conf = self._conf_field.text()
            if pwd != conf:
                self._err_lbl.setText("❌ Passwords do not match")
                return
            if len(pwd) < 6:
                self._err_lbl.setText("❌ Password must be at least 6 characters")
                return
            self._set_loading(True)
            self._fb.register(email, pwd, name)
        else:
            self._set_loading(True)
            self._fb.login(email, pwd)

    def _set_loading(self, v):
        self._loading = v
        self._btn.setEnabled(not v)
        self._btn.setText("LOADING..." if v else ("LOGIN" if self._mode=="login" else "CREATE ACCOUNT"))
        self._btn_style(v)

    def _on_success(self, user):
        self._set_loading(False)
        self.sig_login_ok.emit(user)

    def _on_error(self, msg):
        self._set_loading(False)
        self._err_lbl.setText(msg)


# ══════════════════════════════════════════════════════════
# LOGIN WINDOW
# ══════════════════════════════════════════════════════════
class LoginWindow(QMainWindow):
    sig_logged_in = pyqtSignal(dict)  # passes user dict to main app

    def __init__(self):
        super().__init__()
        self.setWindowTitle("ALIRA — Login")
        self.setFixedSize(860, 560)
        self._firebase = FirebaseWorker()
        self._build()

    def _build(self):
        # Background canvas
        self._canvas = ParticleCanvas(self)
        self._canvas.setGeometry(0, 0, 860, 560)

        # Centered card
        self._card = LoginCard(self._firebase, self)
        self._card.adjustSize()
        card_h = self._card.sizeHint().height()
        card_h = card_h if card_h > 100 else 480
        self._card.move(
            (860 - 400) // 2,
            max(30, (560 - card_h) // 2)
        )
        self._card.sig_login_ok.connect(self._on_login)

        # Top brand strip
        top = QLabel("ADVANCED REALTIME INTELLIGENCE ASSISTANT", self)
        top.setGeometry(0, 12, 860, 18)
        top.setAlignment(Qt.AlignCenter)
        top.setStyleSheet(f"color:rgba(0,212,255,0.22);font-family:'Courier New';font-size:9px;letter-spacing:3px;background:transparent;")

        # Bottom tag
        bot = QLabel("✨  Powered by Gemini 2.5  •  ALIRA v4.0  •  Made with ❤️ for Boss", self)
        bot.setGeometry(0, 534, 860, 20)
        bot.setAlignment(Qt.AlignCenter)
        bot.setStyleSheet(f"color:rgba(107,115,148,0.6);font-size:10px;font-family:'Segoe UI';background:transparent;")

    def resizeEvent(self, e):
        self._canvas.setGeometry(0, 0, self.width(), self.height())

    def _on_login(self, user):
        self.sig_logged_in.emit(user)
        self.hide()

    def get_firebase(self):
        return self._firebase


# ══════════════════════════════════════════════════════════
# GLOBAL SESSION  (shared between login + main app)
# ══════════════════════════════════════════════════════════
class Session:
    """Logged-in user ka data yahan store hoga"""
    uid         = ""
    email       = ""
    display_name = ""
    id_token    = ""
    firebase    = None

    @classmethod
    def set(cls, user: dict, fb: FirebaseWorker):
        cls.uid          = user.get('uid','')
        cls.email        = user.get('email','')
        cls.display_name = user.get('displayName','')
        cls.id_token     = user.get('idToken','')
        cls.firebase     = fb

    @classmethod
    def save_message(cls, role: str, text: str):
        """Har message automatically Firestore mein save hoga"""
        if cls.firebase and cls.uid and cls.id_token:
            cls.firebase.save_message(cls.uid, cls.id_token, role, text)

    @classmethod
    def is_logged_in(cls):
        return bool(cls.uid)


# ══════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════
def launch_login(on_success_callback):
    """
    Login window kholo.
    on_success_callback(user_dict) jab login/register ho jaye.
    """
    win = LoginWindow()
    win.sig_logged_in.connect(on_success_callback)
    win.show()
    return win


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor(BG))
    pal.setColor(QPalette.WindowText,      QColor(TEXT))
    pal.setColor(QPalette.Base,            QColor(BG2))
    pal.setColor(QPalette.Text,            QColor(TEXT))
    pal.setColor(QPalette.Button,          QColor(BG3))
    pal.setColor(QPalette.ButtonText,      QColor(TEXT))
    pal.setColor(QPalette.Highlight,       QColor(ACCENT))
    pal.setColor(QPalette.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)

    def on_login(user):
        print(f"\n✅ Login successful!")
        print(f"   Name:  {user.get('displayName')}")
        print(f"   Email: {user.get('email')}")
        print(f"   UID:   {user.get('uid')}")
        Session.set(user, win.get_firebase())
        # Yahaan ALIRA_live.py launch hoga
        # import ALIRA_gui; ALIRA_gui.launch()
        app.quit()

    win = LoginWindow()
    win.sig_logged_in.connect(on_login)
    win.show()
    sys.exit(app.exec_())