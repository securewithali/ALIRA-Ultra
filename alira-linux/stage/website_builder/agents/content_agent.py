# -*- coding: utf-8 -*-
"""ALIRA WebForge — Content Agent"""

import json, re
from TABBU_modules.gemini_rest import FallbackModel

_HAS_GENAI = False
try:
    try:
        import google.genai as genai
    except Exception:
        import google.generativeai as genai
    from website_builder.config import GEMINI_API_KEY
    try:
        if hasattr(genai, 'configure'):
            genai.configure(api_key=GEMINI_API_KEY)
    except Exception:
        pass
    _HAS_GENAI = True
except Exception:
    _HAS_GENAI = False


class ContentAgent:
    def __init__(self):
        if True:  # REST fallback model — SDK pe depend nahi
            try:
                self._model = FallbackModel()  # Gemini REST + model fallback chain
            except Exception:
                self._model = None
        else:
            self._model = None

    def generate(self, plan: dict) -> dict:
        if not self._model:
            return self._fallback(plan)
        prompt = f"""
You are a professional copywriter. Generate compelling website content.
Plan: {json.dumps(plan, indent=2)}

Return ONLY valid JSON (no markdown):
{{
  "hero": {{"heading":"","subheading":"","cta_primary":"Get Started","cta_secondary":"Learn More"}},
  "about": {{"heading":"","description":"","stats":[{{"number":"100+","label":"Projects"}},{{"number":"50K","label":"Users"}},{{"number":"99%","label":"Satisfaction"}}]}},
  "services": {{"heading":"","items":[
    {{"icon":"⚡","title":"","description":""}},
    {{"icon":"🚀","title":"","description":""}},
    {{"icon":"💡","title":"","description":""}},
    {{"icon":"🛡️","title":"","description":""}},
    {{"icon":"🎯","title":"","description":""}},
    {{"icon":"🔥","title":"","description":""}}
  ]}},
  "pricing": {{"heading":"","plans":[
    {{"name":"Starter","price":"$0","period":"/month","features":["f1","f2","f3"],"cta":"Get Started","popular":false}},
    {{"name":"Pro","price":"$29","period":"/month","features":["f1","f2","f3","f4","f5"],"cta":"Start Pro","popular":true}},
    {{"name":"Enterprise","price":"$99","period":"/month","features":["All features"],"cta":"Contact Us","popular":false}}
  ]}},
  "testimonials":[
    {{"name":"","role":"","text":"","avatar":"👤"}},
    {{"name":"","role":"","text":"","avatar":"👤"}},
    {{"name":"","role":"","text":"","avatar":"👤"}}
  ],
  "contact":{{"heading":"Get In Touch","subheading":"","email":"","phone":"","address":""}},
  "footer":{{"tagline":"","copyright":"© 2025 {plan.get('title','Website')}. All rights reserved."}},
  "seo":{{"meta_title":"","meta_description":"","og_title":"","og_description":""}}
}}
"""
        try:
            resp = self._model.generate_content(
                prompt,
                generation_config={"temperature": 0.8, "max_output_tokens": 4096}
            )
            raw = re.sub(r"```(?:json)?|```", "", resp.text.strip()).strip()
            return json.loads(raw)
        except Exception as e:
            print(f"[Content] Generation failed: {e}")
            return self._fallback(plan)

    def _fallback(self, plan: dict) -> dict:
        name = plan.get("title", "My Website")
        return {
            "hero":    {"heading": f"Welcome to {name}", "subheading": "Built with ALIRA WebForge AI",
                        "cta_primary": "Get Started", "cta_secondary": "Learn More"},
            "about":   {"heading": "About Us", "description": "We create amazing digital experiences.",
                        "stats": [{"number":"100+","label":"Projects"},{"number":"50K","label":"Users"},{"number":"99%","label":"Satisfaction"}]},
            "services":{"heading": "What We Offer", "items": [
                {"icon":"⚡","title":"Fast","description":"Lightning performance"},
                {"icon":"🚀","title":"Modern","description":"Latest tech stack"},
                {"icon":"💡","title":"Smart","description":"AI-powered features"},
                {"icon":"🛡️","title":"Secure","description":"Enterprise security"},
                {"icon":"🎯","title":"Focused","description":"Goal-oriented design"},
                {"icon":"🔥","title":"Scalable","description":"Grows with you"},
            ]},
            "contact": {"heading":"Get In Touch","subheading":"We'd love to hear from you",
                        "email":"hello@ALIRA.ai","phone":"+1 (555) 000-0000","address":"123 Main Street"},
            "footer":  {"tagline":"Built with ALIRA WebForge AI","copyright":f"© 2025 {name}. All rights reserved."},
            "seo":     {"meta_title":name,"meta_description":f"{name} — Built with ALIRA WebForge AI",
                        "og_title":name,"og_description":f"{name} — ALIRA WebForge AI"},
        }