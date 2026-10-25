# -*- coding: utf-8 -*-
"""
ALIRA WebForge — Main Manager
=============================
Usage:
    from website_builder.webforge_manager import WebForgeManager
    wf = WebForgeManager()
    result = wf.handle_command("Create a dark gaming website")
"""

import traceback
from pathlib import Path

from website_builder.config               import validate_keys
from website_builder.agents.planner_agent  import PlannerAgent
from website_builder.agents.content_agent  import ContentAgent
from website_builder.agents.generator_agent import GeneratorAgent
from website_builder.project.project_manager import ProjectManager
from website_builder.preview.preview_server  import start_preview
from website_builder.deploy.github_service   import GitHubService
from website_builder.deploy.vercel_service   import VercelService
from website_builder.database.projects_db    import ProjectsDB


class WebForgeManager:
    def __init__(self):
        self._planner   = PlannerAgent()
        self._content   = ContentAgent()
        self._generator = GeneratorAgent()
        self._pm        = ProjectManager()
        self._github    = GitHubService()
        self._vercel    = VercelService()
        self._db        = ProjectsDB()

    # ── Public API ────────────────────────────────────────────────
    def is_webforge_command(self, command: str) -> bool:
        return self._planner.is_webforge_command(command)

    def handle_command(self, command: str, parent_widget=None) -> dict:
        try:
            # 1. Validate keys
            check = validate_keys()
            if not check["ok"]:
                return self._err(f"Missing .env keys: {', '.join(check['missing'])}")

            # 2. Plan
            print(f"[WebForge] Planning: {command}")
            plan   = self._planner.plan(command)
            action = plan.get("action", "create")
            pname  = plan.get("project_name", "my-website")

            # 3. Dispatch
            if action == "create":        return self._create_and_deploy(plan, parent_widget)
            elif action == "update":      return self._update_and_redeploy(plan, parent_widget)
            elif action == "preview":     return self._open_preview(pname)
            elif action == "deploy":      return self._deploy_only(pname, parent_widget)
            elif action == "status":      return self._get_status(pname)
            else:                         return self._create_and_deploy(plan, parent_widget)

        except Exception as e:
            traceback.print_exc()
            return self._err(str(e)[:200])

    # ── Pipeline ──────────────────────────────────────────────────
    def _create_and_deploy(self, plan: dict, parent=None) -> dict:
        pname = plan["project_name"]
        print(f"[WebForge] Creating: {pname}")

        # Generate content
        content = self._content.generate(plan)

        # Generate files
        html   = self._generator.generate_html(plan, content)
        css    = self._generator.generate_css(plan)
        js     = self._generator.generate_js(plan)
        readme = self._generator.generate_readme(plan)

        # Save locally
        project_dir = self._pm.write_files(pname, {
            "index.html":    html,
            "css/style.css": css,
            "js/script.js":  js,
            "README.md":     readme,
        })

        # Local preview
        preview_url = start_preview(project_dir, pname)

        # GitHub push
        gh_result  = self._github.push_project(pname, project_dir)
        github_url = gh_result.get("github_url", "")
        if not gh_result.get("ok"):
            print(f"[WebForge] GitHub warning: {gh_result.get('error','')}")

        # Vercel deploy
        live_url = ""
        if github_url:
            vc       = self._vercel.deploy_from_github(pname, pname)
            live_url = vc.get("vercel_url", vc.get("live_url", ""))
            if not vc.get("ok"):
                print(f"[WebForge] Vercel warning: {vc.get('error','')}")

        # Update README with live URL
        if live_url:
            readme_final = self._generator.generate_readme(plan, live_url)
            (project_dir / "README.md").write_text(readme_final, encoding="utf-8")
            self._github.push_file(pname, "README.md", readme_final,
                                   f"ALIRA WebForge: add live URL")

        # Save to DB
        self._db.save_project(pname, {
            "project_name": pname,
            "local_path":   str(project_dir),
            "github_url":   github_url,
            "vercel_url":   live_url,
            "preview_url":  preview_url,
        })

        result = {
            "success":      True,
            "message":      f"✅ '{pname}' created and deployed!",
            "project_name": pname,
            "preview_url":  preview_url,
            "github_url":   github_url,
            "live_url":     live_url,
        }

        # Show QR popup
        self._show_popup(result, parent)
        return result

    def _update_and_redeploy(self, plan: dict, parent=None) -> dict:
        pname    = plan["project_name"]
        db_entry = self._db.get(pname)

        if not self._pm.project_exists(pname):
            return self._create_and_deploy(plan, parent)

        content = self._content.generate(plan)
        project_dir = self._pm.write_files(pname, {
            "index.html":    self._generator.generate_html(plan, content),
            "css/style.css": self._generator.generate_css(plan),
            "js/script.js":  self._generator.generate_js(plan),
        })

        gh_result  = self._github.push_project(pname, project_dir)
        github_url = gh_result.get("github_url", db_entry.get("github_url","") if db_entry else "")
        live_url   = db_entry.get("vercel_url","") if db_entry else ""
        if github_url:
            vc = self._vercel.deploy_from_github(pname, pname)
            live_url = vc.get("vercel_url", live_url)

        preview_url = start_preview(project_dir, pname)
        self._db.save_project(pname, {"github_url": github_url, "vercel_url": live_url, "preview_url": preview_url})

        result = {"success": True, "message": f"✅ '{pname}' updated and redeployed!",
                  "project_name": pname, "preview_url": preview_url,
                  "github_url": github_url, "live_url": live_url}
        self._show_popup(result, parent)
        return result

    def _open_preview(self, pname: str) -> dict:
        if not self._pm.project_exists(pname):
            return self._err(f"Project '{pname}' not found locally")
        url = start_preview(self._pm.get_project_dir(pname), pname)
        return {"success": True, "message": f"Preview: {url}", "project_name": pname,
                "preview_url": url, "github_url": "", "live_url": ""}

    def _deploy_only(self, pname: str, parent=None) -> dict:
        db_entry    = self._db.get(pname)
        project_dir = self._pm.get_project_dir(pname)
        if not self._pm.project_exists(pname):
            return self._err(f"Project '{pname}' not found — create it first")

        gh         = self._github.push_project(pname, project_dir)
        github_url = gh.get("github_url", db_entry.get("github_url","") if db_entry else "")
        live_url   = ""
        if github_url:
            vc = self._vercel.deploy_from_github(pname, pname)
            live_url = vc.get("vercel_url","")

        self._db.save_project(pname, {"github_url": github_url, "vercel_url": live_url})
        result = {"success": True, "message": f"✅ '{pname}' deployed!", "project_name": pname,
                  "preview_url": "", "github_url": github_url, "live_url": live_url}
        self._show_popup(result, parent)
        return result

    def _get_status(self, pname: str) -> dict:
        db_entry = self._db.get(pname)
        if not db_entry:
            return self._err(f"No project found: '{pname}'")
        return {"success": True, "message": f"Status: '{pname}'",
                "project_name": pname, "preview_url": db_entry.get("preview_url",""),
                "github_url": db_entry.get("github_url",""), "live_url": db_entry.get("vercel_url","")}

    # ── Helpers ───────────────────────────────────────────────────
    def _show_popup(self, result: dict, parent=None):
        try:
            from website_builder.deploy.qr_display import show_deploy_success
            if result.get("live_url") or result.get("github_url"):
                show_deploy_success(result, parent)
        except Exception as e:
            print(f"[WebForge] Popup error: {e}")

    @staticmethod
    def _err(msg: str) -> dict:
        print(f"[WebForge] ❌ {msg}")
        return {"success": False, "message": f"❌ {msg}",
                "project_name": "", "preview_url": "", "github_url": "", "live_url": ""}