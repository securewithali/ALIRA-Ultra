# -*- coding: utf-8 -*-
"""ALIRA WebForge — QR Code + Deploy Success Popup"""

from alira_slot import slot as _alira_slot
import io

try:
    import qrcode
    _HAS_QR = True
except ImportError:
    _HAS_QR = False

try:
    from PyQt5.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QApplication
    )
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QPixmap
    _HAS_QT = True
except ImportError:
    _HAS_QT = False


def make_qr_pixmap(url: str, size: int = 200):
    if not _HAS_QR or not _HAS_QT: return None
    try:
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M,
                           box_size=5, border=3)
        qr.add_data(url); qr.make(fit=True)
        img = qr.make_image(fill_color="#00DDFF", back_color="#040810")
        buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
        pix = QPixmap(); pix.loadFromData(buf.read())
        return pix.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    except Exception as e:
        print(f"[QR] {e}"); return None


class DeploySuccessDialog(QDialog):
    def __init__(self, result: dict, parent=None):
        super().__init__(parent)
        if not _HAS_QT: return
        self.setWindowTitle("🚀 ALIRA WebForge — Deployed!")
        self.setFixedSize(430, 560)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self._result = result
        self._build()

    def _build(self):
        outer = QVBoxLayout(self); outer.setContentsMargins(0, 0, 0, 0)
        card  = QFrame()
        card.setStyleSheet("""QFrame{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
            stop:0 #080F22,stop:1 #040810);border:2px solid #00DDFF;border-radius:20px;}""")
        vl = QVBoxLayout(card); vl.setContentsMargins(28, 24, 28, 24); vl.setSpacing(14)

        # Title
        t = QLabel("🚀  Website Deployed!"); t.setAlignment(Qt.AlignCenter)
        t.setStyleSheet("color:#00DDFF;font-size:18px;font-weight:bold;background:transparent;")
        vl.addWidget(t)
        pn = QLabel(self._result.get("project_name","")); pn.setAlignment(Qt.AlignCenter)
        pn.setStyleSheet("color:#7799AA;font-size:11px;background:transparent;")
        vl.addWidget(pn)

        # Divider
        d = QFrame(); d.setFrameShape(QFrame.HLine)
        d.setStyleSheet("background:rgba(0,220,255,0.2);max-height:1px;border:none;")
        vl.addWidget(d)

        # QR Code
        live = self._result.get("live_url", "")
        if live and _HAS_QR:
            qr_lbl = QLabel(); qr_lbl.setAlignment(Qt.AlignCenter)
            pix = make_qr_pixmap(live, 180)
            if pix: qr_lbl.setPixmap(pix)
            qr_lbl.setStyleSheet("background:transparent;padding:6px;")
            vl.addWidget(qr_lbl)
            scan = QLabel("📱 Scan to open live website"); scan.setAlignment(Qt.AlignCenter)
            scan.setStyleSheet("color:#446677;font-size:10px;background:transparent;")
            vl.addWidget(scan)

        # URLs
        for label, key, color in [
            ("🌐 Live URL",  "live_url",   "#00DDFF"),
            ("🐙 GitHub",    "github_url", "#44FF88"),
            ("👁 Preview",   "preview_url","#FFAA33"),
        ]:
            url = self._result.get(key, "")
            if not url: continue
            row = QHBoxLayout(); row.setSpacing(6)
            lbl = QLabel(f"{label}:")
            lbl.setStyleSheet("color:#556677;font-size:10px;background:transparent;")
            lbl.setFixedWidth(68)
            ul = QLabel(url)
            ul.setStyleSheet(f"color:{color};font-size:10px;font-family:'Courier New';background:transparent;")
            ul.setTextInteractionFlags(Qt.TextSelectableByMouse)
            cp = QPushButton("📋"); cp.setFixedSize(24, 24); cp.setCursor(Qt.PointingHandCursor)
            cp.setStyleSheet("QPushButton{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);border-radius:6px;font-size:10px;}QPushButton:hover{background:rgba(255,255,255,0.14);}")
            _u = url
            cp.clicked.connect(lambda _, u=_u: QApplication.clipboard().setText(u))
            row.addWidget(lbl); row.addWidget(ul, 1); row.addWidget(cp)
            vl.addLayout(row)

        # Divider
        d2 = QFrame(); d2.setFrameShape(QFrame.HLine)
        d2.setStyleSheet("background:rgba(0,220,255,0.2);max-height:1px;border:none;")
        vl.addWidget(d2)

        # Buttons
        br = QHBoxLayout(); br.setSpacing(10)
        import webbrowser
        ob = QPushButton("🌐 Open Website"); ob.setFixedHeight(38); ob.setCursor(Qt.PointingHandCursor)
        ob.setStyleSheet("""QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 #003355,stop:1 #005588);border:1px solid #00AAFF;border-radius:10px;
            color:#00DDFF;font-size:11px;font-weight:bold;}
            QPushButton:hover{background:#005588;border-color:#00DDFF;}""")
        ob.clicked.connect(lambda: webbrowser.open(live) if live else None)
        cb = QPushButton("✓ Done"); cb.setFixedHeight(38); cb.setCursor(Qt.PointingHandCursor)
        cb.setStyleSheet("QPushButton{background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.15);border-radius:10px;color:#889AAA;font-size:11px;}QPushButton:hover{background:rgba(255,255,255,0.12);}")
        cb.clicked.connect(_alira_slot(self.accept))
        br.addWidget(ob); br.addWidget(cb)
        vl.addLayout(br)
        outer.addWidget(card)


def show_deploy_success(result: dict, parent=None):
    if not _HAS_QT:
        print(f"[WebForge] Deployed! Live: {result.get('live_url','')}")
        return
    dlg = DeploySuccessDialog(result, parent)
    dlg.exec_()