# -*- coding: utf-8 -*-
"""ALIRA WebForge — Vercel Service"""

import time, requests
from website_builder.config import VERCEL_TOKEN, VERCEL_TEAM_ID, GITHUB_USERNAME

BASE = "https://api.vercel.com"


class VercelService:
    def __init__(self):
        self._h  = {"Authorization": f"Bearer {VERCEL_TOKEN}", "Content-Type": "application/json"}
        self._tp = {"teamId": VERCEL_TEAM_ID} if VERCEL_TEAM_ID else {}

    def _get(self, path):
        return requests.get(f"{BASE}{path}", headers=self._h, params=self._tp, timeout=30)

    def _post(self, path, data):
        return requests.post(f"{BASE}{path}", headers=self._h, params=self._tp, json=data, timeout=60)

    def get_project(self, name: str):
        r = self._get(f"/v9/projects/{name}")
        return r.json() if r.status_code == 200 else None

    def create_project(self, name: str, repo: str) -> dict:
        data = {
            "name": name, "framework": None,
            "gitRepository": {"type": "github", "repo": f"{GITHUB_USERNAME}/{repo}"},
        }
        return self._post("/v10/projects", data).json()

    def deploy_from_github(self, project_name: str, repo_name: str) -> dict:
        if not VERCEL_TOKEN:
            return {"ok": False, "error": "VERCEL_TOKEN missing in .env"}

        if not self.get_project(project_name):
            res = self.create_project(project_name, repo_name)
            if "error" in res:
                return {"ok": False, "error": str(res.get("error", res))[:200]}

        data = {
            "name": project_name,
            "gitSource": {"type": "github", "repo": repo_name,
                          "org": GITHUB_USERNAME, "ref": "main"},
            "projectSettings": {"framework": None},
        }
        r = self._post("/v13/deployments", data)
        if r.status_code not in (200, 201):
            return {"ok": False, "error": f"Deploy failed: {r.status_code} — {r.text[:200]}"}

        d         = r.json()
        deploy_id = d.get("id", "")
        url       = d.get("url", "")
        live_url  = self._poll(deploy_id, url)
        return {"ok": True, "deploy_id": deploy_id, "live_url": live_url,
                "vercel_url": live_url}

    def _poll(self, deploy_id: str, initial_url: str, timeout: int = 120) -> str:
        start = time.time()
        while time.time() - start < timeout:
            time.sleep(5)
            r = self._get(f"/v13/deployments/{deploy_id}")
            if r.status_code != 200: break
            d     = r.json()
            state = d.get("readyState", d.get("state", ""))
            print(f"[Vercel] state: {state}")
            if state in ("READY", "ready"):
                u = d.get("url", initial_url)
                return f"https://{u}" if not u.startswith("http") else u
            if state in ("ERROR", "CANCELED", "error"): break
        return f"https://{initial_url}" if not initial_url.startswith("http") else initial_url