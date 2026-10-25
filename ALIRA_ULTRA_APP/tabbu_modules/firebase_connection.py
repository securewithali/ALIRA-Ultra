# -*- coding: utf-8 -*-
"""
firebase_connection.py  [SECURE v3 — No Admin SDK]
===================================================
Face Auth ke liye Firebase Realtime DB / Firestore connection.
Firebase Admin SDK REMOVED — sirf pyrebase client SDK use karta hai.
Admin SDK SIRF backend server pe chalta hai.
"""
import os, sys
from pathlib import Path

# ── Public Firebase config (client-safe — no secrets) ────────────────────────
FIREBASE_CONFIG = {
    "apiKey":            "AIzaSyD6Vife6Bg8xH3SedFJC3GNK6mMVSftE8U",
    "authDomain":        "speen-to-earn.firebaseapp.com",
    "projectId":         "speen-to-earn",
    "storageBucket":     "speen-to-earn.firebasestorage.app",
    "messagingSenderId": "63415004467",
    "appId":             "1:63415004467:web:6c1c8e0003ec2261546246",
    "databaseURL":       "",
}

_pyrebase_db   = None
_init_tried    = False

def _get_pyrebase_db():
    global _pyrebase_db, _init_tried
    if _init_tried:
        return _pyrebase_db
    _init_tried = True
    try:
        import pyrebase
        fb = pyrebase.initialize_app(FIREBASE_CONFIG)
        _pyrebase_db = fb.database()
        print("[Firebase] Pyrebase client initialized (face auth)")
    except Exception as e:
        print(f"[Firebase] Pyrebase unavailable: {e} — face auth uses local mode")
    return _pyrebase_db

def get_firebase_db():
    """
    Face Auth ke liye DB.
    Returns pyrebase DB object ya None (graceful degradation).
    NOTE: Firebase Admin SDK use NAHI — sirf client SDK.
    """
    from TABBU_modules.license_client import load_license, get_device_id
    lic = load_license()
    if not lic.get("session_token"):
        return None
    return _get_pyrebase_db()

def verify_session_online() -> bool:
    """Backend heartbeat se session check karo."""
    from TABBU_modules.license_client import load_license, heartbeat, get_device_id
    lic = load_license()
    return heartbeat(
        session_token=lic.get("session_token",""),
        device_id=lic.get("device_id", get_device_id())
    )
