# -*- coding: utf-8 -*-
"""
ALIRA License Client  v1.0
==========================
Client side SIRF YEH FILE use karta hai — Firebase Admin SDK NAHI.
Backend API se baat karta hai: https://api.SecureWithAli.in

Functions:
  verify_license(access_key, device_info) → LicenseResult
  heartbeat(session_token, device_id)     → bool
  load_license()                          → dict | None
  save_license(data)                      → None
  clear_license()                         → None
  is_activated()                          → bool
"""

import os, json, secrets, hashlib, socket, uuid, platform
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
import urllib.request
import urllib.error

# ── Backend URL ──────────────────────────────────────────────────────────────
# Production: https://api.SecureWithAli.in
# EXE / pip install dono same URL use karte hain
BACKEND_URL = os.environ.get(
    "ALIRA_BACKEND_URL",
    "https://api.SecureWithAli.in"
).rstrip("/")

# ── Local license file location ──────────────────────────────────────────────
# Windows: C:\Users\<user>\AppData\Roaming\ALIRA\license.json
_APPDATA = os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming"))
LICENSE_DIR  = Path(_APPDATA) / "ALIRA"
LICENSE_FILE = LICENSE_DIR / "license.json"

# ── Dataclass-style result ────────────────────────────────────────────────────

class LicenseResult:
    def __init__(self, success: bool, user_name: str = "", plan: str = "",
                 expires_at: str = "", session_token: str = "",
                 gemini_api_key: str = "", error: str = ""):
        self.success        = success
        self.user_name      = user_name
        self.plan           = plan
        self.expires_at     = expires_at
        self.session_token  = session_token
        self.gemini_api_key = gemini_api_key
        self.error          = error

    def __bool__(self):
        return self.success

    def __repr__(self):
        return (f"LicenseResult(success={self.success}, user={self.user_name}, "
                f"plan={self.plan})")

# ── Device fingerprint ───────────────────────────────────────────────────────

def get_device_id() -> str:
    """Unique device ID banao — MAC + hostname se"""
    try:
        mac      = hex(uuid.getnode()).replace("0x", "").upper()
        hostname = socket.gethostname()
        raw      = f"{mac}-{hostname}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32].upper()
    except Exception:
        return hashlib.sha256(b"fallback-device").hexdigest()[:32].upper()

def get_device_info() -> dict:
    """PC ki basic info collect karo"""
    try:
        hostname = socket.gethostname()
        try:    username = os.getlogin()
        except Exception: username = os.environ.get("USERNAME", "")
        return {
            "device_id":    get_device_id(),
            "device_label": f"{hostname} ({username})",
            "pc_username":  username,
            "pc_hostname":  hostname,
            "pc_os":        f"{platform.system()} {platform.release()}",
            "pc_model":     platform.node(),
            "pc_processor": platform.processor()[:100] if platform.processor() else "",
        }
    except Exception:
        return {"device_id": get_device_id(), "device_label": "Unknown Device"}

# ── Local license helpers ─────────────────────────────────────────────────────

def load_license() -> dict:
    """Local license.json padho"""
    try:
        if LICENSE_FILE.exists():
            data = json.loads(LICENSE_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}

def save_license(data: dict) -> None:
    """License data locally save karo (SIRF session token + user info — NO Firebase creds)"""
    try:
        LICENSE_DIR.mkdir(parents=True, exist_ok=True)
        # IMPORTANT: Firebase credentials KABHI save mat karo
        safe_data = {
            "session_token":  data.get("session_token", ""),
            "user_name":      data.get("user_name", ""),
            "plan":           data.get("plan", ""),
            "expires_at":     data.get("expires_at", ""),
            "device_id":      data.get("device_id", get_device_id()),
            "access_key":     data.get("access_key", ""),
            "gemini_api_key": data.get("gemini_api_key", ""),
            "display_name":   data.get("display_name", data.get("user_name", "")),
            "activated_at":   data.get("activated_at",
                                       datetime.now(timezone.utc).isoformat()),
        }
        LICENSE_FILE.write_text(json.dumps(safe_data, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[License] Save error: {e}")

def clear_license() -> None:
    """License file delete karo (re-activation ke liye)"""
    try:
        if LICENSE_FILE.exists():
            LICENSE_FILE.unlink()
    except Exception:
        pass

def is_activated() -> bool:
    """Quick local check — kya license.json exist karta hai valid data ke saath?"""
    lic = load_license()
    return bool(
        lic.get("session_token") and
        lic.get("access_key")    and
        lic.get("device_id") == get_device_id()
    )

# ── API helpers ───────────────────────────────────────────────────────────────

def _post(endpoint: str, payload: dict, timeout: int = 15) -> dict:
    """Backend API ko POST request bhejo"""
    url  = f"{BACKEND_URL}{endpoint}"
    body = json.dumps(payload).encode("utf-8")
    req  = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body_text = e.read().decode("utf-8")
            err_data  = json.loads(body_text)
            return {"error": err_data.get("detail", f"HTTP {e.code}"), "success": False}
        except Exception:
            return {"error": f"HTTP {e.code}", "success": False}
    except urllib.error.URLError as e:
        return {"error": "Server offline. Internet connection check karein.", "success": False}
    except Exception as e:
        return {"error": f"Network error: {e}", "success": False}

# ── Main API calls ────────────────────────────────────────────────────────────

def verify_license(
    access_key:     str,
    gemini_api_key: str = "",
    display_name:   str = "",
    device_info:    Optional[dict] = None,
) -> LicenseResult:
    """
    Backend se access key verify karo.
    Firebase credentials KABHI client ke paas nahi bhejte.
    """
    if device_info is None:
        device_info = get_device_info()

    payload = {
        "access_key":     access_key.strip().upper(),
        "device_id":      device_info.get("device_id", get_device_id()),
        "device_label":   device_info.get("device_label", ""),
        "pc_username":    device_info.get("pc_username", ""),
        "pc_hostname":    device_info.get("pc_hostname", ""),
        "pc_os":          device_info.get("pc_os", ""),
        "pc_model":       device_info.get("pc_model", ""),
        "pc_processor":   device_info.get("pc_processor", ""),
        "gemini_api_key": gemini_api_key,
        "display_name":   display_name,
    }

    print(f"[License] Verifying key with backend: {BACKEND_URL}")
    resp = _post("/verify-license", payload)

    if resp.get("success"):
        # Success — license locally save karo (NO Firebase creds)
        lic_data = {
            "session_token":  resp.get("session_token", ""),
            "user_name":      resp.get("user_name", ""),
            "plan":           resp.get("plan", "PRO"),
            "expires_at":     resp.get("expires_at", ""),
            "access_key":     access_key.strip().upper(),
            "device_id":      device_info.get("device_id", get_device_id()),
            "gemini_api_key": resp.get("gemini_api_key", gemini_api_key),
            "display_name":   display_name or resp.get("user_name", ""),
            "activated_at":   datetime.now(timezone.utc).isoformat(),
        }
        save_license(lic_data)
        print(f"[License] ✅ Activated! User: {resp.get('user_name')}, Plan: {resp.get('plan')}")
        return LicenseResult(
            success        = True,
            user_name      = resp.get("user_name", ""),
            plan           = resp.get("plan", "PRO"),
            expires_at     = resp.get("expires_at", ""),
            session_token  = resp.get("session_token", ""),
            gemini_api_key = resp.get("gemini_api_key", gemini_api_key),
        )
    else:
        err = resp.get("error", resp.get("detail", "Unknown error"))
        print(f"[License] ❌ Verification failed: {err}")
        return LicenseResult(success=False, error=str(err))


def heartbeat(session_token: Optional[str] = None,
              device_id:     Optional[str] = None) -> bool:
    """
    Backend se session valid hai check karo.
    Call karo har 15 min — revoked keys detect ho jaate hain.
    """
    if session_token is None or device_id is None:
        lic = load_license()
        session_token = session_token or lic.get("session_token", "")
        device_id     = device_id     or lic.get("device_id", get_device_id())

    if not session_token:
        return False

    resp = _post("/heartbeat", {
        "session_token": session_token,
        "device_id":     device_id,
    }, timeout=10)

    valid = resp.get("valid", False)
    if not valid:
        reason = resp.get("reason", "unknown")
        print(f"[License] ⚠️ Heartbeat failed: {reason}")
        if reason in ("session_revoked", "key_deactivated", "device_mismatch"):
            clear_license()
    return valid
