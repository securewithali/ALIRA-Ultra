# -*- coding: utf-8 -*-
"""ALIRA WebForge — GitHub Service"""

import base64, requests
from pathlib import Path
from website_builder.config import GITHUB_TOKEN, GITHUB_USERNAME

BASE = "https://api.github.com"


class GitHubService:
    def __init__(self):
        self._h = {
            "Authorization": f"token {GITHUB_TOKEN}",
            "Accept":        "application/vnd.github.v3+json",
            "Content-Type":  "application/json",
        }

    def repo_exists(self, repo: str) -> bool:
        r = requests.get(f"{BASE}/repos/{GITHUB_USERNAME}/{repo}", headers=self._h, timeout=30)
        return r.status_code == 200

    def create_repo(self, repo: str, desc: str = "") -> dict:
        data = {"name": repo, "description": desc or f"ALIRA WebForge — {repo}",
                "private": False, "auto_init": False}
        r = requests.post(f"{BASE}/user/repos", headers=self._h, json=data, timeout=30)
        if r.status_code in (201, 422):
            return {"ok": True, "url": f"https://github.com/{GITHUB_USERNAME}/{repo}"}
        return {"ok": False, "error": r.text[:200]}

    def _sha(self, repo: str, path: str):
        r = requests.get(f"{BASE}/repos/{GITHUB_USERNAME}/{repo}/contents/{path}",
                         headers=self._h, timeout=30)
        return r.json().get("sha") if r.status_code == 200 else None

    def push_file(self, repo: str, path: str, content, msg: str) -> bool:
        if isinstance(content, str): content = content.encode("utf-8")
        b64  = base64.b64encode(content).decode()
        sha  = self._sha(repo, path)
        data = {"message": msg, "content": b64}
        if sha: data["sha"] = sha
        r = requests.put(f"{BASE}/repos/{GITHUB_USERNAME}/{repo}/contents/{path}",
                         headers=self._h, json=data, timeout=30)
        return r.status_code in (200, 201)

    def push_project(self, repo: str, project_dir: Path) -> dict:
        if not GITHUB_TOKEN or not GITHUB_USERNAME:
            return {"ok": False, "error": "GITHUB_TOKEN or GITHUB_USERNAME missing in .env"}
        if not self.repo_exists(repo):
            res = self.create_repo(repo)
            if not res["ok"]: return res

        msg    = f"ALIRA WebForge update: {repo}"
        pushed = []
        failed = []
        for fp in project_dir.rglob("*"):
            if not fp.is_file(): continue
            rel = fp.relative_to(project_dir).as_posix()
            try:
                ok = self.push_file(repo, rel, fp.read_bytes(), msg)
                (pushed if ok else failed).append(rel)
            except Exception as e:
                failed.append(f"{rel}({e})")

        url = f"https://github.com/{GITHUB_USERNAME}/{repo}"
        print(f"[GitHub] Pushed {len(pushed)} files → {url}")
        return {"ok": len(pushed) > 0, "github_url": url, "pushed": len(pushed), "failed": failed}