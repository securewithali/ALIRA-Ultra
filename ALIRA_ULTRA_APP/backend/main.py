# -*- coding: utf-8 -*-
"""
ALIRA Licensing Backend  —  FastAPI + Firebase Admin SDK
=======================================================
Deploy karo: https://api.SecureWithAli.in

Endpoints:
  POST /verify-license   — Access key verify + device bind
  POST /heartbeat        — Session token valid hai check karo
  POST /admin/revoke     — Admin: key revoke karo
  POST /admin/unbind     — Admin: device unbind karo
  GET  /health           — Server alive check

Firebase Admin SDK SIRF IS SERVER PE — client ke paas KABHI nahi jaata.
"""

import os, json, secrets, logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import firebase_admin
from firebase_admin import credentials, firestore

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    _HAS_SLOWAPI = True
except ImportError:
    _HAS_SLOWAPI = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ALIRA-backend")

# ── Firebase Admin init ──────────────────────────────────────────────────────
# JSON SIRF SERVER PE — env vTABBUble se path lo, hardcode mat karo
_cred_path = os.environ.get(
    "GOOGLE_APPLICATION_CREDENTIALS",
    "/secure/speen-to-earn-firebase-adminsdk.json"
)
if not os.path.isfile(_cred_path):
    raise RuntimeError(
        f"Firebase credentials not found at: {_cred_path}\n"
        "Set GOOGLE_APPLICATION_CREDENTIALS environment vTABBUble."
    )

cred = credentials.Certificate(_cred_path)
firebase_admin.initialize_app(cred, {"projectId": "speen-to-earn"})
db = firestore.client()
logger.info("Firebase Admin SDK initialized.")

# ── FastAPI setup ────────────────────────────────────────────────────────────
if _HAS_SLOWAPI:
    limiter = Limiter(key_func=get_remote_address)
    app = FastAPI(title="ALIRA License API", version="1.0.0", docs_url=None, redoc_url=None)
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
else:
    app = FastAPI(title="ALIRA License API", version="1.0.0", docs_url=None, redoc_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# ── Config ───────────────────────────────────────────────────────────────────
ADMIN_SECRET      = os.environ.get("ALIRA_ADMIN_SECRET", "change-this-in-production")
SESSION_TTL_HOURS = int(os.environ.get("SESSION_TTL_HOURS", "720"))   # 30 din

# ── Pydantic models ──────────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    access_key:     str
    device_id:      str
    device_label:   Optional[str] = ""
    pc_username:    Optional[str] = ""
    pc_hostname:    Optional[str] = ""
    pc_os:          Optional[str] = ""
    pc_model:       Optional[str] = ""
    pc_processor:   Optional[str] = ""
    gemini_api_key: Optional[str] = ""
    display_name:   Optional[str] = ""

class HeartbeatRequest(BaseModel):
    session_token: str
    device_id:     str

class AdminRevokeRequest(BaseModel):
    admin_secret: str
    access_key:   str

class AdminUnbindRequest(BaseModel):
    admin_secret: str
    access_key:   str

# ── Helpers ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _make_session_token() -> str:
    return secrets.token_urlsafe(48)

def _key_upper(k: str) -> str:
    return k.strip().upper()

def _fs_err(msg: str, code: int = 400):
    raise HTTPException(status_code=code, detail=msg)

def _parse_dt(val) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.replace(tzinfo=timezone.utc) if val.tzinfo is None else val
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except Exception:
            return None
    # Firestore Timestamp object
    try:
        return val.astimezone(timezone.utc)
    except Exception:
        return None

# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "time": _now_iso()}


@app.post("/verify-license")
async def verify_license(req: VerifyRequest, request: Request):
    """
    Access key verify karo, device bind karo, session token return karo.
    Firebase Admin SDK SIRF YAHAN chalta hai — client mein nahi.
    """
    key     = _key_upper(req.access_key)
    key_ref = db.collection("keys").document(key)
    key_doc = key_ref.get()

    # ── 1. Key exist karta hai? ─────────────────────────────────────────────
    if not key_doc.exists:
        logger.warning(f"Key not found: {key}")
        _fs_err(
            "❌ Access key not found.\n\n"
            "• Check the key carefully\n"
            "• Contact your admin for a valid key\n\n"
            f"Key entered: {key}"
        )

    kd = key_doc.to_dict()

    # ── 2. Active check ─────────────────────────────────────────────────────
    if not kd.get("active", False):
        _fs_err("❌ This key has been deactivated.\n\nContact your admin for a new key.")

    # ── 3. Expiry check ─────────────────────────────────────────────────────
    exp_dt = _parse_dt(kd.get("expiresAt"))
    if exp_dt and datetime.now(timezone.utc) > exp_dt:
        _fs_err("❌ License expired.\n\nRenew your subscription to continue.")

    # ── 4. Device binding check ─────────────────────────────────────────────
    bound_device = kd.get("device_id", "").strip()
    if bound_device and bound_device != req.device_id:
        bound_label = kd.get("device_label", "Unknown Device")
        # Hostname match allow karo (NIC swap etc.)
        my_host    = (req.pc_hostname or "").lower()
        same_host  = my_host and len(my_host) > 2 and my_host in bound_label.lower()
        if not same_host:
            _fs_err(
                f"❌ This key is locked to another device.\n\n"
                f"Locked to: {bound_label}\n\n"
                f"Options:\n"
                f"• Ask admin to UNBIND the key\n"
                f"• Get a new key from admin"
            )
        # Same hostname — device_id update karo
        logger.info(f"Same hostname match — rebinding key {key} to new device_id")

    # ── 5. Session token banao ───────────────────────────────────────────────
    session_token  = _make_session_token()
    session_key    = session_token[:32]
    session_expiry = datetime.now(timezone.utc) + timedelta(hours=SESSION_TTL_HOURS)

    # ── 6. Key document update karo ─────────────────────────────────────────
    update_data = {
        "device_id":    req.device_id,
        "device_label": req.device_label or "",
        "pc_username":  req.pc_username  or "",
        "pc_hostname":  req.pc_hostname  or "",
        "pc_os":        req.pc_os        or "",
        "pc_model":     req.pc_model     or "",
        "pc_processor": req.pc_processor or "",
        "last_seen":    _now_iso(),
    }
    if not bound_device:
        update_data["bound_at"] = _now_iso()
    if req.display_name:
        update_data["display_name"] = req.display_name
    if req.gemini_api_key:
        update_data["gemini_api_key"] = req.gemini_api_key

    key_ref.update(update_data)

    # ── 7. Session Firestore mein save karo ─────────────────────────────────
    db.collection("sessions").document(session_key).set({
        "sessionToken": session_token,
        "accessKey":    key,
        "deviceId":     req.device_id,
        "createdAt":    _now_iso(),
        "expiresAt":    session_expiry.isoformat(),
        "active":       True,
    })

    # ── 8. Device document upsert ────────────────────────────────────────────
    db.collection("devices").document(req.device_id[:64]).set({
        "deviceId":  req.device_id,
        "accessKey": key,
        "firstSeen": kd.get("bound_at", _now_iso()),
        "lastSeen":  _now_iso(),
        "label":     req.device_label or "",
    }, merge=True)

    user_name = (
        kd.get("display_name") or req.display_name or
        kd.get("userName")     or "User"
    )
    plan    = kd.get("plan", "PRO")
    exp_str = kd.get("expiresAt", "")
    if hasattr(exp_str, "isoformat"):
        exp_str = exp_str.isoformat()

    logger.info(f"License verified: {key} | device: {req.device_id[:12]}...")

    return {
        "success":        True,
        "user_name":      user_name,
        "plan":           plan,
        "expires_at":     str(exp_str),
        "session_token":  session_token,
        "gemini_api_key": kd.get("gemini_api_key", req.gemini_api_key or ""),
    }


@app.post("/heartbeat")
async def heartbeat(req: HeartbeatRequest, request: Request):
    """
    Session token valid hai ya nahi check karo.
    App har 15 min mein ye call kare — revoked keys detect honge.
    """
    session_doc = db.collection("sessions").document(req.session_token[:32]).get()

    if not session_doc.exists:
        return {"valid": False, "reason": "session_not_found"}

    sd = session_doc.to_dict()

    if not sd.get("active", False):
        return {"valid": False, "reason": "session_revoked"}

    if sd.get("deviceId") != req.device_id:
        return {"valid": False, "reason": "device_mismatch"}

    exp_dt = _parse_dt(sd.get("expiresAt"))
    if exp_dt and datetime.now(timezone.utc) > exp_dt:
        return {"valid": False, "reason": "session_expired"}

    key_doc = db.collection("keys").document(sd.get("accessKey", "")).get()
    if not key_doc.exists or not key_doc.to_dict().get("active", False):
        return {"valid": False, "reason": "key_deactivated"}

    db.collection("sessions").document(req.session_token[:32]).update(
        {"lastSeen": _now_iso()}
    )
    return {"valid": True}


@app.post("/admin/revoke")
async def admin_revoke(req: AdminRevokeRequest):
    """Admin: access key revoke karo"""
    if req.admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")
    key = _key_upper(req.access_key)
    db.collection("keys").document(key).update({"active": False})
    # Sab related sessions bhi revoke karo
    for s in db.collection("sessions").where("accessKey", "==", key).stream():
        s.reference.update({"active": False})
    logger.info(f"Admin revoked key: {key}")
    return {"success": True, "message": f"Key {key} revoked"}


@app.post("/admin/unbind")
async def admin_unbind(req: AdminUnbindRequest):
    """Admin: device unbind karo (user naye PC pe activate kar sake)"""
    if req.admin_secret != ADMIN_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")
    key = _key_upper(req.access_key)
    db.collection("keys").document(key).update({
        "device_id":    "",
        "device_label": "",
        "bound_at":     "",
    })
    logger.info(f"Admin unbound key: {key}")
    return {"success": True, "message": f"Key {key} unbound — user can now activate on new device"}
