"""Environment loading helpers for ALIRA AI Assistant."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def load_environment(env_path: Optional[Path] = None) -> None:
    """Load environment vTABBUbles from a .env file if present."""
    if env_path is None:
        env_path = Path.cwd() / ".env"
        if not env_path.exists():
            env_path = Path(__file__).resolve().parents[1] / ".env"

    if env_path.exists():
        load_dotenv(env_path)


def get_env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)
