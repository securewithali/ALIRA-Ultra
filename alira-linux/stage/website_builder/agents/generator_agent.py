# -*- coding: utf-8 -*-
"""ALIRA WebForge — Generator Agent (HTML/CSS/JS)"""

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

THEME_CSS_VARS = {
    "dark":          {"bg":"#0a0a0a","bg2":"#111827","text":"#f9fafb","accent":"#3b82f6","accent2":"#06b6d4","card":"#1f2937","border":"rgba(255,255,255,0.1)"},
    "light":         {"bg":"#ffffff","bg2":"#f8fafc","text":"#0f172a","accent":"#2563eb","accent2":"#0891b2","card":"#f1f5f9","border":"rgba(0,0,0,0.08)"},
    "glassmorphism": {"bg":"#0f0c29","bg2":"#302b63","text":"#ffffff","accent":"#a78bfa","accent2":"#38bdf8","card":"rgba(255,255,255,0.08)","border":"rgba(255,255,255,0.18)"},
    "gaming":        {"bg":"#050505","bg2":"#0d0d0d","text":"#ffffff","accent":"#ff0055","accent2":"#ff6600","card":"#111111","border":"rgba(255,0,85,0.3)"},
    "futuristic_neon":{"bg":"#020014","bg2":"#0a0028","text":"#e0e0ff","accent":"#00ffcc","accent2":"#ff00ff","card":"#0d0030","border":"rgba(0,255,204,0.25)"},
    "ai_startup":    {"bg":"#050b18","bg2":"#0c1526","text":"#f0f4ff","accent":"#6366f1","accent2":"#06b6d4","card":"#0f1d38","border":"rgba(99,102,241,0.25)"},
    "portfolio":     {"bg":"#0d1117","bg2":"#161b22","text":"#e6edf3","accent":"#58a6ff","accent2":"#3fb950","card":"#21262d","border":"rgba(88,166,255,0.2)"},
    "corporate":     {"bg":"#ffffff","bg2":"#f5f7fa","text":"#1a202c","accent":"#1a56db","accent2":"#047857","card":"#edf2f7","border":"rgba(0,0,0,0.1)"},
    "ecommerce":     {"bg":"#fafafa","bg2":"#f0f0f0","text":"#1a1a1a","accent":"#ff6900","accent2":"#ffd700","card":"#ffffff","border":"rgba(0,0,0,0.1)"},
}


class GeneratorAgent:
    def __init__(self):
      if True:  # REST fallback model — SDK pe depend nahi
        try:
          self._model = FallbackModel()  # Gemini REST + model fallback chain
        except Exception:
          self._model = None
      else:
        self._model = None

    def _theme(self, theme: str) -> dict:
        return THEME_CSS_VARS.get(theme, THEME_CSS_VARS["dark"])

    def generate_html(self, plan: dict, content: dict) -> str:
        if not self._model:
            return self._fallback_html(plan, content)

        tv = self._theme(plan.get("theme", "dark"))
        prompt = f"""
You are a world-class web developer. Generate a COMPLETE, BEAUTIFUL, PRODUCTION-READY single-page website.

Plan: {json.dumps(plan, indent=2)}
Content: {json.dumps(content, indent=2)}
Theme VTABBUbles: {json.dumps(tv, indent=2)}

REQUIREMENTS:
1. Return ONLY complete index.html — no explanation, no markdown fences.
2. Inline all CSS in <style> tag, inline all JS in <script> tag.
3. Mobile-responsive with CSS Grid/Flexbox.
4. Smooth scroll + Intersection Observer animations.
5. Navigation bar with all section links + hamburger for mobile.
6. Sections: {', '.join(plan.get('sections', ['hero','about','services','contact']))}.
7. Footer with copyright.
8. Use theme CSS vTABBUbles exactly as provided.
9. Glass cards if glassmorphism theme. Particle/glow effects if gaming/neon theme.
10. SEO meta tags: title, description, og:title, og:description.
11. Modern premium look — NOT generic.
12. Smooth hover effects on all buttons and cards.

Generate the complete HTML now:
"""
        try:
            resp = self._model.generate_content(
                prompt,
                generation_config={"temperature": 0.7, "max_output_tokens": 8192}
            )
            html = resp.text.strip()
            html = re.sub(r"^```(?:html)?\s*", "", html)
            html = re.sub(r"\s*```$", "", html)
            return html
        except Exception as e:
            print(f"[Generator] HTML failed: {e}")
            return self._fallback_html(plan, content)

    def generate_css(self, plan: dict) -> str:
        tv = self._theme(plan.get("theme", "dark"))
        return f"""/* ALIRA WebForge — {plan.get('title','Website')} */
:root {{
  --bg: {tv['bg']}; --bg2: {tv['bg2']}; --text: {tv['text']};
  --accent: {tv['accent']}; --accent2: {tv['accent2']};
  --card: {tv['card']}; --border: {tv['border']};
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg); color:var(--text); font-family:'{plan.get('font_family','Segoe UI')}',sans-serif; }}
a {{ color:var(--accent); text-decoration:none; }}
"""

    def generate_js(self, plan: dict) -> str:
        return """// ALIRA WebForge Script
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('a[href^="#"]').forEach(a => {
    a.addEventListener('click', e => {
      e.preventDefault();
      const el = document.querySelector(a.getAttribute('href'));
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    });
  });
  const obs = new IntersectionObserver(entries => {
    entries.forEach(e => { if (e.isIntersecting) e.target.classList.add('visible'); });
  }, { threshold: 0.1 });
  document.querySelectorAll('.animate').forEach(el => obs.observe(el));
  const tog = document.querySelector('.nav-toggle');
  const nav = document.querySelector('.nav-menu');
  if (tog && nav) tog.addEventListener('click', () => nav.classList.toggle('open'));
});
"""

    def generate_readme(self, plan: dict, live_url: str = "") -> str:
        return f"""# {plan.get('title', plan.get('project_name','Website'))}
> {plan.get('tagline','Built with ALIRA WebForge AI')}

## 🚀 Live URL
{live_url if live_url else '_Deploying..._'}

## About
- **Type:** {plan.get('website_type','website')}
- **Theme:** {plan.get('theme','dark')}
- **Stack:** {plan.get('tech_stack','HTML, CSS, JS')}

_Generated by ALIRA WebForge AI_
"""

    def _fallback_html(self, plan: dict, content: dict) -> str:
        tv      = self._theme(plan.get("theme", "dark"))
        title   = plan.get("title", "My Website")
        tagline = plan.get("tagline", "Built with ALIRA WebForge")
        hero    = content.get("hero", {})
        heading = hero.get("heading", title)
        sub     = hero.get("subheading", tagline)
        cta     = hero.get("cta_primary", "Get Started")
        svcs    = content.get("services", {}).get("items", [])
        svc_html = ""
        for s in svcs:
            svc_html += f'<div class="card"><div class="card-icon">{s.get("icon","⚡")}</div><h3>{s.get("title","")}</h3><p>{s.get("description","")}</p></div>'
        contact  = content.get("contact", {})
        footer   = content.get("footer", {})
        seo      = content.get("seo", {})
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{seo.get('meta_title', title)}</title>
<meta name="description" content="{seo.get('meta_description', tagline)}">
<meta property="og:title" content="{seo.get('og_title', title)}">
<meta property="og:description" content="{seo.get('og_description', tagline)}">
<style>
:root{{--bg:{tv['bg']};--bg2:{tv['bg2']};--text:{tv['text']};--accent:{tv['accent']};--accent2:{tv['accent2']};--card:{tv['card']};--border:{tv['border']};}}
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{background:var(--bg);color:var(--text);font-family:'{plan.get('font_family','Segoe UI')}',sans-serif;}}
nav{{position:fixed;top:0;width:100%;background:var(--bg2);border-bottom:1px solid var(--border);padding:1rem 2rem;display:flex;justify-content:space-between;align-items:center;z-index:100;}}
nav .brand{{font-size:1.4rem;font-weight:bold;color:var(--accent);}}
nav ul{{display:flex;gap:2rem;list-style:none;}}
nav a{{color:var(--text);opacity:0.8;transition:opacity 0.3s;}}
nav a:hover{{opacity:1;color:var(--accent);}}
section{{padding:6rem 2rem;max-width:1100px;margin:0 auto;}}
#hero{{text-align:center;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding-top:5rem;}}
#hero h1{{font-size:clamp(2rem,5vw,4rem);font-weight:900;margin-bottom:1.5rem;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;}}
#hero p{{font-size:1.2rem;opacity:0.75;max-width:600px;margin:0 auto 2.5rem;line-height:1.7;}}
.btn{{display:inline-block;padding:0.9rem 2.5rem;background:var(--accent);color:#fff;border-radius:50px;font-weight:bold;font-size:1rem;transition:all 0.3s;margin:0.4rem;}}
.btn:hover{{transform:translateY(-2px);box-shadow:0 8px 25px rgba(0,0,0,0.3);opacity:0.9;}}
.btn-outline{{background:transparent;border:2px solid var(--accent);color:var(--accent);}}
h2{{font-size:2.2rem;font-weight:800;margin-bottom:3rem;text-align:center;}}
h2 span{{color:var(--accent);}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:1.8rem;}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:16px;padding:2rem;transition:transform 0.3s,box-shadow 0.3s;}}
.card:hover{{transform:translateY(-6px);box-shadow:0 20px 40px rgba(0,0,0,0.2);}}
.card-icon{{font-size:2.5rem;margin-bottom:1rem;}}
.card h3{{font-size:1.1rem;font-weight:700;margin-bottom:0.6rem;}}
.card p{{opacity:0.7;line-height:1.6;font-size:0.95rem;}}
#contact{{text-align:center;}}
.contact-info{{display:flex;flex-wrap:wrap;justify-content:center;gap:2rem;margin-top:2rem;}}
.contact-item{{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:1.5rem 2rem;}}
footer{{background:var(--bg2);border-top:1px solid var(--border);text-align:center;padding:2.5rem;opacity:0.7;margin-top:4rem;}}
@media(max-width:768px){{nav ul{{display:none;}}}}
.animate{{opacity:0;transform:translateY(24px);transition:opacity 0.6s,transform 0.6s;}}
.animate.visible{{opacity:1;transform:translateY(0);}}
</style>
</head>
<body>
<nav>
  <span class="brand">{title}</span>
  <ul>
    <li><a href="#about">About</a></li>
    <li><a href="#services">Services</a></li>
    <li><a href="#contact">Contact</a></li>
  </ul>
</nav>
<section id="hero">
  <h1>{heading}</h1>
  <p>{sub}</p>
  <div>
    <a class="btn" href="#services">{cta}</a>
    <a class="btn btn-outline" href="#contact">Contact Us</a>
  </div>
</section>
<section id="about" class="animate">
  <h2>About <span>Us</span></h2>
  <p style="text-align:center;opacity:0.75;max-width:700px;margin:0 auto;line-height:1.8;">{content.get('about',{}).get('description','We create amazing digital experiences.')}</p>
</section>
<section id="services">
  <h2>What We <span>Offer</span></h2>
  <div class="grid">{svc_html}</div>
</section>
<section id="contact" class="animate">
  <h2>Get In <span>Touch</span></h2>
  <p style="opacity:0.7;margin-bottom:2rem;">{contact.get('subheading','We would love to hear from you')}</p>
  <div class="contact-info">
    <div class="contact-item">📧 {contact.get('email','hello@ALIRA.ai')}</div>
    <div class="contact-item">📞 {contact.get('phone','+1 (555) 000-0000')}</div>
    <div class="contact-item">📍 {contact.get('address','123 Main Street')}</div>
  </div>
</section>
<footer>
  <p>{footer.get('tagline','Built with ALIRA WebForge AI')}</p>
  <p style="margin-top:0.5rem;font-size:0.85rem;">{footer.get('copyright',f'© 2025 {title}. All rights reserved.')}</p>
</footer>
<script>
document.addEventListener('DOMContentLoaded', () => {{
  document.querySelectorAll('a[href^="#"]').forEach(a => {{
    a.addEventListener('click', e => {{
      e.preventDefault();
      const el = document.querySelector(a.getAttribute('href'));
      if (el) el.scrollIntoView({{ behavior: 'smooth' }});
    }});
  }});
  const obs = new IntersectionObserver(entries => {{
    entries.forEach(e => {{ if (e.isIntersecting) e.target.classList.add('visible'); }});
  }}, {{ threshold: 0.1 }});
  document.querySelectorAll('.animate').forEach(el => obs.observe(el));
}});
</script>
</body>
</html>"""