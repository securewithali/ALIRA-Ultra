# -*- coding: utf-8 -*-
"""
ALIRA WebForge — Configuration
Loads all keys from .env — NO hardcoding ever.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    # Explicit path only - never bare load_dotenv(). Bare load_dotenv()
    # calls find_dotenv(), which walks the call stack via frame.f_back
    # to guess the caller's directory. When ALIRA runs from the packaged
    # ALIRA.exe launcher (a zipapp-style entry point), that stack is too
    # shallow and find_dotenv() raises a bare `AssertionError` (empty
    # message) - which isn't an ImportError, so it wasn't caught here,
    # and broke `import website_builder` (and anything importing it,
    # e.g. TABBU.py) for every pip-installed user.
    _env_path = Path.cwd() / ".env"
    if not _env_path.exists():
        _env_path = Path(__file__).resolve().parents[1] / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass  # dotenv optional — keys can come from environment directly

# ── API Keys (from .env only) ──────────────────────────────────
GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY", "")
GITHUB_TOKEN    = os.getenv("GITHUB_TOKEN", "")
GITHUB_USERNAME = os.getenv("GITHUB_USERNAME", "")
VERCEL_TOKEN    = os.getenv("VERCEL_TOKEN", "")
VERCEL_TEAM_ID  = os.getenv("VERCEL_TEAM_ID", "")

# ── Paths ──────────────────────────────────────────────────────
PROJECTS_DIR = Path(os.getenv("PROJECTS_DIR", "Projects"))
PROJECTS_DIR.mkdir(exist_ok=True)
DB_PATH      = PROJECTS_DIR / "webforge_projects.json"

# ── Deploy provider ────────────────────────────────────────────
DEFAULT_DEPLOY_PROVIDER = os.getenv("DEFAULT_DEPLOY_PROVIDER", "vercel")

def validate_keys() -> dict:
    missing = []
    if not GEMINI_API_KEY:   missing.append("GEMINI_API_KEY")
    if not GITHUB_TOKEN:     missing.append("GITHUB_TOKEN")
    if not GITHUB_USERNAME:  missing.append("GITHUB_USERNAME")
    if not VERCEL_TOKEN:     missing.append("VERCEL_TOKEN")
    return {"ok": len(missing) == 0, "missing": missing}