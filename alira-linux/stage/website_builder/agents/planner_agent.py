from TABBU_modules.gemini_rest import FallbackModel
# -*- coding: utf-8 -*-
"""ALIRA WebForge — Planner Agent"""

import json
import re

_HAS_GENAI = False
try:
    try:
        import google.genai as genai
    except Exception:
        import google.generativeai as genai
    from website_builder.config import GEMINI_API_KEY
    try:
        # configure if available (some libs may not need this)
        if hasattr(genai, 'configure'):
            genai.configure(api_key=GEMINI_API_KEY)
    except Exception:
        # non-fatal: proceed without configured client
        pass
    _HAS_GENAI = True
except Exception:
    _HAS_GENAI = False

WEBSITE_KEYWORDS = [
    "website", "site", "webpage", "web page", "landing page",
    "portfolio", "blog", "store", "shop", "ecommerce", "e-commerce",
    "deploy", "publish", "preview", "github", "vercel", "hosting",
    "create web", "build web", "make web", "generate web",
    "update website", "edit website", "add section", "change theme",
]

ACTION_PATTERNS = {
    "create":  ["create", "make", "build", "generate", "banao", "bana", "likho"],
    "update":  ["update", "edit", "change", "modify", "add section", "improve", "badlo"],
    "preview": ["preview", "open", "show", "dekho", "local"],
    "deploy":  ["deploy", "publish", "live", "push", "upload"],
    "status":  ["status", "info", "url", "link", "check"],
}

THEME_MAP = {
    "dark":          "dark",
    "light":         "light",
    "glass":         "glassmorphism",
    "glassmorphism": "glassmorphism",
    "gaming":        "gaming",
    "neon":          "futuristic_neon",
    "futuristic":    "futuristic_neon",
    "corporate":     "corporate",
    "portfolio":     "portfolio",
    "ai":            "ai_startup",
    "startup":       "ai_startup",
    "minimal":       "light",
}

TYPE_MAP = {
    "portfolio": "portfolio",
    "gaming":    "gaming",
    "game":      "gaming",
    "ai":        "ai_startup",
    "startup":   "ai_startup",
    "business":  "business",
    "ecommerce": "ecommerce",
    "store":     "ecommerce",
    "shop":      "ecommerce",
    "blog":      "blog",
    "landing":   "landing",
    "saas":      "saas",
}


class PlannerAgent:
    def __init__(self):
        # Some SDKs (google.genai) may have a different API surface.
        # Only instantiate if the loaded module exposes the expected class.
        if True:  # REST fallback model — SDK pe depend nahi
            try:
                self._model = FallbackModel()  # Gemini REST + model fallback chain
            except Exception:
                self._model = None
        else:
            self._model = None

    def is_webforge_command(self, command: str) -> bool:
        cmd = command.lower()
        return any(kw in cmd for kw in WEBSITE_KEYWORDS)

    def detect_action(self, command: str) -> str:
        cmd = command.lower()
        for action, keywords in ACTION_PATTERNS.items():
            if any(kw in cmd for kw in keywords):
                return action
        return "create"

    def detect_type(self, command: str) -> str:
        cmd = command.lower()
        for key, val in TYPE_MAP.items():
            if key in cmd:
                return val
        return "portfolio"

    def detect_theme(self, command: str) -> str:
        cmd = command.lower()
        for key, val in THEME_MAP.items():
            if key in cmd:
                return val
        defaults = {"gaming": "gaming", "ai_startup": "ai_startup",
                    "ecommerce": "light", "portfolio": "dark"}
        return defaults.get(self.detect_type(command), "dark")

    def generate_project_name(self, command: str, wtype: str) -> str:
        stop = {"create","make","build","generate","website","site","a","an","the",
                "for","me","please","bana","banao","kar","do","mujhe","meri","mera","ek"}
        words = re.sub(r"[^a-z0-9 ]", "", command.lower()).split()
        parts = [w for w in words if w not in stop][:3]
        return "-".join(parts) if parts else wtype + "-site"

    def plan(self, command: str) -> dict:
        action = self.detect_action(command)
        wtype  = self.detect_type(command)
        theme  = self.detect_theme(command)
        name   = self.generate_project_name(command, wtype)

        if self._model:
            prompt = f"""
You are a website planner AI. Based on this user command, create a structured JSON plan.
User command: "{command}"
Detected type: {wtype}, theme: {theme}

Return ONLY valid JSON (no markdown):
{{
  "project_name": "{name}",
  "website_type": "{wtype}",
  "theme": "{theme}",
  "pages": ["index"],
  "sections": ["hero","about","services","contact"],
  "title": "Website title",
  "tagline": "Short tagline",
  "primary_color": "#hex",
  "secondary_color": "#hex",
  "font_family": "font name",
  "features": ["responsive","animations","SEO"],
  "tech_stack": "html_css_js"
}}
"""
            try:
                resp = self._model.generate_content(prompt)
                raw  = re.sub(r"```(?:json)?|```", "", resp.text.strip()).strip()
                plan = json.loads(raw)
            except Exception as e:
                print(f"[Planner] AI failed ({e}), using defaults")
                plan = self._default_plan(name, wtype, theme)
        else:
            plan = self._default_plan(name, wtype, theme)

        plan["action"]       = action
        plan["user_command"] = command
        return plan

    def _default_plan(self, name, wtype, theme) -> dict:
        return {
            "project_name":   name,
            "website_type":   wtype,
            "theme":          theme,
            "pages":          ["index"],
            "sections":       ["hero","about","services","contact"],
            "title":          name.replace("-"," ").title(),
            "tagline":        "Built with ALIRA WebForge AI",
            "primary_color":  "#0055FF",
            "secondary_color":"#00DDFF",
            "font_family":    "Segoe UI",
            "features":       ["responsive","animations","SEO"],
            "tech_stack":     "html_css_js",
        }