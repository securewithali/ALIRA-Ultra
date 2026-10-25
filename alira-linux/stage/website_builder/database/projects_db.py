# -*- coding: utf-8 -*-
"""ALIRA WebForge — Projects Database (JSON-backed)"""

import json
import threading
from datetime import datetime
from website_builder.config import DB_PATH


class ProjectsDB:
    _lock = threading.Lock()

    def __init__(self):
        self._path = DB_PATH
        self._data = self._load()

    def _load(self) -> dict:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save(self):
        self._path.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def get(self, project_name: str):
        with self._lock:
            return self._data.get(project_name)

    def save_project(self, project_name: str, info: dict):
        with self._lock:
            existing = self._data.get(project_name, {})
            existing.update(info)
            existing["updated_at"] = datetime.now().isoformat()
            if "created_at" not in existing:
                existing["created_at"] = existing["updated_at"]
            self._data[project_name] = existing
            self._save()

    def all_projects(self) -> list:
        with self._lock:
            return list(self._data.values())