# -*- coding: utf-8 -*-
"""ALIRA WebForge — Project Manager"""

from pathlib import Path
from website_builder.config import PROJECTS_DIR


class ProjectManager:
    def create_project(self, project_name: str) -> Path:
        project_dir = PROJECTS_DIR / project_name
        for sub in ["css", "js", "assets"]:
            (project_dir / sub).mkdir(parents=True, exist_ok=True)
        return project_dir

    def write_files(self, project_name: str, files: dict) -> Path:
        project_dir = self.create_project(project_name)
        for rel_path, content in files.items():
            full = project_dir / rel_path
            full.parent.mkdir(parents=True, exist_ok=True)
            full.write_text(content, encoding="utf-8")
            print(f"[ProjectManager] Wrote: {full}")
        return project_dir

    def get_project_dir(self, project_name: str) -> Path:
        return PROJECTS_DIR / project_name

    def project_exists(self, project_name: str) -> bool:
        return (PROJECTS_DIR / project_name / "index.html").exists()

    def list_all_files(self, project_name: str) -> list:
        d = PROJECTS_DIR / project_name
        return [f for f in d.rglob("*") if f.is_file()] if d.exists() else []