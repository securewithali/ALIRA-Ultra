# -*- coding: utf-8 -*-
"""
ALIRA Website Studio — JARVIS "Live Forge + Studio" ka ALIRA version.

* Prompt do -> ALIRA Coder (Node agent) project folder me ALAG-ALAG files banata hai:
  index.html / style.css / script.js  (JARVIS ke prompt-rules ke saath: GSAP, picsum images, hero flair…)
* Live Forge HUD (matrix rain + terminal log) build ke dauran preview me chalta hai, phir site reveal hoti hai.
* Build ke baad AUTO-REVIEW: files padhkar static check (broken links, JS syntax, missing ids) +
  browser console errors => agent ko diye jaate hain aur wo str_replace se fix karta hai (Codex/Claude Code jaisa).
* Refine: "navbar sticky karo", "hero ka color badlo" — agent files padhta hai aur sirf wahi part edit karta hai.
* Your sites (history), Code viewer, device preview, Export ZIP, Open in browser, Deploy.
"""

from alira_slot import slot as _ALIRA_slot
import os, re, json, time, shutil, zipfile, subprocess, threading
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QScrollArea,
    QListWidget, QListWidgetItem, QStackedWidget, QFileDialog, QMessageBox, QSizePolicy, QShortcut,
    QLayout, QMenu,
)
from PyQt5.QtCore import Qt, QObject, QTimer, QUrl, pyqtSignal, QRegularExpression, QRect, QPoint, QSize
from PyQt5.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont, QKeySequence, QGuiApplication

try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
    HAS_WEBENGINE = True
except Exception:          # PyQtWebEngine installed nahi
    QWebEngineView = QWebEnginePage = None
    HAS_WEBENGINE = False

from alira_ui import T, F, PageBase, make_card, pill, css3d, lift, Segmented
import alira_actions as act

try:
    from ALIRA_coder_integration import ALIRACoderEngine
except Exception:          # node agent integration missing
    ALIRACoderEngine = None

STUDIO_DIR = Path(__file__).resolve().parent / "Projects" / "Studio"
META = ".ALIRA-site.json"
MAX_FIX_ROUNDS = 2

# ══════════════════════════════════════════════════════════════════
# PROMPTS  (JARVIS website-builder rules, multi-file + read-and-fix workflow)
# ══════════════════════════════════════════════════════════════════
BUILD_RULES = """You are an elite, Awwwards-winning frontend developer and UI/UX designer working like a coding agent inside a project folder.
Build a highly animated, visually stunning, clean, premium website for the user's brief as SEPARATE FILES in the CURRENT directory (do NOT create a sub-folder):

  index.html  - semantic HTML only. Link the other files: <link rel="stylesheet" href="style.css"> in <head> and <script src="script.js" defer></script> before </body>. Include a descriptive <title> and <meta name="viewport" content="width=device-width, initial-scale=1">.
  style.css   - ALL styling: CSS vTABBUbles for the theme, fluid typography, CSS Grid/Bento layouts, hover states, keyframe animations, fully RESPONSIVE (360px phones -> wide desktops).
  script.js   - ALL behaviour: GSAP + ScrollTrigger reveals, magnetic CTA buttons, sticky/mobile nav, smooth scroll, counters, etc. Guard against missing elements.

RULES:
1. TECH: GSAP via CDN in index.html: <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/gsap.min.js"></script> and <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.2/ScrollTrigger.min.js"></script> (put them BEFORE script.js). Google Fonts via <link> is fine.
2. IMAGES: NEVER invent Unsplash IDs/URLs. Use ONLY "https://picsum.photos/1920/1080?random=N" (N = 1..50) for photos and "https://i.pravatar.cc/150?img=N" for avatars. Icons = inline <svg>.
3. HERO FLAIR: glowing blurred background orbs, a slowly rotating circular text stamp or floating glassmorphism cards, plus GSAP "magnetic" CTA buttons.
4. CONTENT: rich, realistic copy in every section (no lorem ipsum, no empty sections).
5. THEME: choose exact hex colours that fit the subject (no default slate/gray). Tech/AI: near-black + neon accent. Cafe/food: espresso browns + cream. Corporate/SaaS: white + deep navy.
6. SECTIONS (5-6): Hero, About/Mission, Features/Services (bento), Showcase/Gallery, Testimonials or Pricing, CTA & Footer.

WORKFLOW (work like a developer, use your tools):
 1. update_todos with a short plan.
 2. write_file index.html, then style.css, then script.js.
 3. REVIEW: read_file each file back. Verify: every id/class that script.js or style.css targets exists in index.html; the <link>/<script> paths are correct; no JS syntax errors; nothing is left as a TODO/placeholder.
 4. FIX any problem with small, targeted str_replace edits (do not rewrite whole files unless truly necessary).
 5. Finish with a 2-line summary listing the files."""

REFINE_RULES = """The website project ALREADY EXISTS in the current directory (index.html, style.css, script.js ...).
CHANGE REQUEST: {request}

Work like a developer editing an existing codebase:
 1. list_files / grep / read_file to find the exact place to change (HTML structure -> index.html, look & layout -> style.css, behaviour -> script.js).
 2. Apply EXACTLY the requested change with targeted str_replace edits. Keep every other part (content, structure, images, scripts) unchanged. Do NOT regenerate whole files.
 3. Re-read the edited region to verify it is correct (selectors/ids still match across the files, no syntax errors).
 4. Finish with a short summary of what you changed and in which file.
This is a SMALL targeted edit: do NOT write a todo list and do NOT save memory — find, edit, verify once, then finish immediately."""

FIX_RULES = """The website project in the current directory was just reviewed automatically and these problems were found:

{issues}

Read the files involved (read_file / grep), find the root cause of EACH problem and fix it with targeted str_replace edits (or write_file for a missing file). Do not rewrite files that are fine. After fixing, re-read the changed parts to confirm. Finish with a short summary of the fixes.
Do NOT write a todo list and do NOT save memory — just fix, verify once, and finish immediately."""


# ══════════════════════════════════════════════════════════════════
# LIVE FORGE HUD  (JARVIS 'Web Synthesis' shell, ALIRA colours)
# ══════════════════════════════════════════════════════════════════
HUD_HTML = """<html><head><meta charset="utf-8"><style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%;overflow:hidden;background:#05030a;font-family:'Courier New',monospace}
#matrix{position:absolute;inset:0;width:100%;height:100%;z-index:1}
#scan{position:absolute;left:0;width:100%;height:3px;background:linear-gradient(90deg,transparent,#ff2e43,transparent);z-index:11;opacity:.6;animation:scan 3s linear infinite}
@keyframes scan{0%{top:-4px}100%{top:100%}}
#hud{position:absolute;inset:0;z-index:10;display:flex;flex-direction:column;align-items:center;justify-content:center;background:radial-gradient(circle at center,rgba(40,0,8,.25) 0%,rgba(0,0,0,.9) 80%)}
#title{font-size:clamp(28px,6vw,64px);font-weight:900;letter-spacing:6px;color:#ff2e43;text-shadow:0 0 10px #ff2e43,0 0 30px #ff2e43,0 0 60px #b3122a;animation:pulse 1.8s ease-in-out infinite;text-align:center}
@keyframes pulse{0%,100%{text-shadow:0 0 10px #ff2e43,0 0 30px #ff2e43,0 0 60px #b3122a}50%{text-shadow:0 0 22px #ff2e43,0 0 55px #ff2e43,0 0 95px #b3122a}}
#sub{margin-top:12px;font-size:13px;letter-spacing:5px;color:#ff2e4399}
#log{margin-top:30px;width:78%;max-width:700px;height:190px;overflow:hidden;border:1px solid #ff2e4444;padding:12px;background:rgba(30,0,8,.45);font-size:12px;color:#ff6b7d;box-shadow:0 0 20px #ff2e4422 inset}
#log div{opacity:0;animation:fade .4s forwards;white-space:pre-wrap}
@keyframes fade{to{opacity:1}}
.cur{display:inline-block;width:8px;height:13px;background:#ff2e43;animation:blink 1s step-end infinite;vertical-align:middle;margin-left:2px}
@keyframes blink{50%{opacity:0}}
</style></head><body>
<canvas id="matrix"></canvas><div id="scan"></div>
<div id="hud"><div id="title">M.Y.R.A LIVE FORGE</div><div id="sub">// WEB SYNTHESIS ENGINE ONLINE</div><div id="log"></div></div>
<script>
const c=document.getElementById('matrix'),x=c.getContext('2d');
function rs(){c.width=innerWidth;c.height=innerHeight}rs();addEventListener('resize',rs);
const g='アイウエオカキクケコサシスセソ0123456789ALIRA<>/{}'.split(''),fs=16;
let cols=Math.floor(c.width/fs),d=Array(cols).fill(1);
setInterval(()=>{x.fillStyle='rgba(0,0,0,0.08)';x.fillRect(0,0,c.width,c.height);x.fillStyle='#ff2e43';x.font=fs+'px monospace';
for(let i=0;i<d.length;i++){x.fillText(g[Math.floor(Math.random()*g.length)],i*fs,d[i]*fs);if(d[i]*fs>c.height&&Math.random()>.975)d[i]=0;d[i]++}},45);
const L=document.getElementById('log');
window.__log=function(t){const e=document.createElement('div');e.innerHTML='> '+String(t).replace(/</g,'&lt;')+'<span class="cur"></span>';L.appendChild(e);while(L.children.length>9)L.removeChild(L.firstChild)};
window.__title=function(a,b){document.getElementById('title').innerText=a;document.getElementById('sub').innerText=b};
['INITIALIZING NEURAL RENDER CORE...','CONNECTING TO GEMINI SYNTHESIS NODE...','PARSING USER DIRECTIVE...'].forEach((t,i)=>setTimeout(()=>__log(t),400*(i+1)));
</script></body></html>"""

IDLE_HTML = """<html><body style="margin:0;background:#07060a;color:#9C99A4;font-family:'Segoe UI',sans-serif;display:flex;align-items:center;justify-content:center;height:100vh">
<div style="text-align:center;max-width:380px;line-height:1.6"><div style="font-size:42px">✦</div>
<div style="color:#fff;font-size:20px;font-weight:600;margin:6px 0">Live preview yahan dikhega</div>
Left mein batao kaisi website chahiye — ALIRA files banayegi, khud padh kar check karegi aur fix karegi.</div></body></html>"""

# Preview "Smooth" mode: embedded Chromium (software compositing) par blur + backdrop-filter + shadows +
# infinite animations milkar scroll ko ~1 FPS kar dete hain. Ye JS sirf PREVIEW me inhe halka karti hai
# (saved files nahi badalti) — 'Browser' button / Full FX par poora look milta hai.
LITE_JS = r"""(function(){
var s=document.getElementById('ALIRA-lite');
if(!s){s=document.createElement('style');s.id='ALIRA-lite';document.head.appendChild(s);}
/* 1) bade blur wale SIRF sajawati elements (bina text/image: glow orbs) hide */
var all=document.querySelectorAll('body *');
for(var i=0;i<all.length;i++){var e=all[i],f=getComputedStyle(e).filter,m=/blur\(([\d.]+)px\)/.exec(f||'');
 if(m&&parseFloat(m[1])>=12&&!(e.textContent||'').trim()&&!e.querySelector('img,video,canvas,svg')){e.style.setProperty('display','none','important');}}
/* 2) baaki sab: blur/backdrop/shadow band, infinite animations ek iteration me khatam (end state par) */
s.textContent='*,*::before,*::after{filter:none!important;backdrop-filter:none!important;-webkit-backdrop-filter:none!important;box-shadow:none!important;text-shadow:none!important;animation-duration:.001s!important;animation-iteration-count:1!important;animation-delay:0s!important;transition-duration:.15s!important}';
})();"""

STARTERS = [
    "A dark futuristic landing page for an AI robotics start-up with a hero, three features and a pricing table",
    "A warm, cosy website for a neighbourhood coffee shop with menu, gallery and opening hours",
    "A clean portfolio for a UI designer with selected projects, about section and contact form",
    "A bold fitness gym website with class timetable, trainers and membership plans",
]
STEPS = ["Plan & todos", "index.html", "style.css", "script.js", "Review & fix"]


# ══════════════════════════════════════════════════════════════════
# helpers: projects, static check
# ══════════════════════════════════════════════════════════════════
def _slug(text, n=26):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "site").lower()).strip("-")[:n].strip("-")
    return s or "site"

def _title_of(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html[:8000], re.I | re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

def _read(p, limit=400_000):
    try:
        return Path(p).read_text(encoding="utf-8", errors="replace")[:limit]
    except Exception:
        return ""

def new_project_dir(prompt):
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    d = STUDIO_DIR / f"{_slug(prompt)}-{time.strftime('%m%d-%H%M%S')}"
    d.mkdir(parents=True, exist_ok=True)
    meta = {"prompt": prompt[:600], "created": time.time(), "updated": time.time(), "edits": []}
    (d / META).write_text(json.dumps(meta), encoding="utf-8")
    return d

def touch_meta(d, edit=None):
    p = Path(d) / META
    try: m = json.loads(p.read_text(encoding="utf-8"))
    except Exception: m = {"prompt": "", "created": time.time(), "edits": []}
    m["updated"] = time.time()
    if edit: m.setdefault("edits", []).append(edit[:300])
    try: p.write_text(json.dumps(m), encoding="utf-8")
    except Exception: pass
    return m

def list_projects(limit=60):
    out = []
    if not STUDIO_DIR.exists(): return out
    for d in STUDIO_DIR.iterdir():
        if not d.is_dir(): continue
        idx = d / "index.html"
        try: m = json.loads((d / META).read_text(encoding="utf-8"))
        except Exception: m = {}
        out.append({"dir": d, "title": (_title_of(_read(idx, 8000)) if idx.exists() else "") or d.name,
                    "brief": m.get("prompt", ""), "mtime": m.get("updated") or d.stat().st_mtime,
                    "files": sum(1 for f in d.iterdir() if f.is_file() and not f.name.startswith(".")), "ok": idx.exists()})
    out.sort(key=lambda r: r["mtime"], reverse=True)
    return out[:limit]

def project_files(d):
    """Text files (html/css/js/json/md/svg) of a project, index.html first."""
    exts = {".html", ".css", ".js", ".json", ".md", ".svg", ".txt"}
    fs = [f for f in Path(d).rglob("*") if f.is_file() and f.suffix.lower() in exts and not f.name.startswith(".")
          and ".ALIRA-coder" not in str(f) and "node_modules" not in str(f)]
    order = {"index.html": 0, "style.css": 1, "script.js": 2}
    fs.sort(key=lambda f: (order.get(f.name, 9), f.name))
    return fs[:24]

def ago(ts):
    m = int((time.time() - ts) // 60)
    return "just now" if m < 1 else f"{m} min ago" if m < 60 else f"{m // 60} h ago" if m < 1440 else f"{m // 1440} d ago"

def _node_exe():
    for p in (r"C:\Program Files\nodejs\node.exe", r"C:\Program Files (x86)\nodejs\node.exe"):
        if os.path.exists(p): return p
    return "node"

def static_check(d):
    """Files padhkar problems dhundo — agent ko 'fix' prompt me diye jaate hain."""
    d = Path(d); issues = []
    idx = d / "index.html"
    if not idx.exists():
        return ["index.html bana hi nahi — create karo."]
    html = _read(idx)
    if not re.search(r"<!doctype html", html, re.I): issues.append("index.html: <!DOCTYPE html> missing")
    if not re.search(r"<title>", html, re.I): issues.append("index.html: <title> missing")
    if not re.search(r'name=["\']viewport["\']', html, re.I): issues.append('index.html: <meta name="viewport"> missing (not responsive)')
    if len(re.sub(r"<[^>]+>", "", html).strip()) < 400: issues.append("index.html: bahut kam content — sections adhoore lag rahe hain")
    # linked local assets exist?
    refs = re.findall(r'<link[^>]+href=["\']([^"\']+\.css)["\']', html, re.I) + re.findall(r'<script[^>]+src=["\']([^"\']+\.js)["\']', html, re.I)
    for r in refs:
        if r.startswith(("http:", "https:", "//", "data:")): continue
        if not (d / r.split("?")[0]).exists(): issues.append(f"index.html links '{r}' but that file does not exist")
    if not any(not r.startswith(("http", "//")) and r.endswith(".css") for r in refs) and "<style" not in html.lower():
        issues.append("index.html: koi stylesheet link nahi hai (style.css link karo)")
    # JS syntax + selector targets
    ids = set(re.findall(r'\bid=["\']([^"\']+)["\']', html))
    classes = set(c for g in re.findall(r'\bclass=["\']([^"\']+)["\']', html) for c in g.split())
    for js in sorted(d.glob("*.js")):
        try:
            r = subprocess.run([_node_exe(), "--check", str(js)], capture_output=True, text=True, timeout=15,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode != 0:
                first = [l for l in (r.stderr or "").splitlines() if l.strip()][:3]
                issues.append(f"{js.name}: JavaScript syntax error — " + " | ".join(first)[:240])
        except Exception:
            pass
        src = _read(js)
        for i in set(re.findall(r'getElementById\(\s*[\'"]([\w-]+)[\'"]', src)):
            if i not in ids: issues.append(f"{js.name} uses getElementById('{i}') but index.html has no id=\"{i}\"")
        for sel in set(re.findall(r'querySelector(?:All)?\(\s*[\'"]([#.][\w-]+)[\'"]', src)):
            if sel.startswith("#") and sel[1:] not in ids: issues.append(f"{js.name} queries '{sel}' but no such id in index.html")
            if sel.startswith(".") and sel[1:] not in classes: issues.append(f"{js.name} queries '{sel}' but no such class in index.html")
    for css in sorted(d.glob("*.css")):
        src = _read(css)
        if src.count("{") != src.count("}"): issues.append(f"{css.name}: unbalanced {{ }} braces (CSS broken)")
        if len(src.strip()) < 300: issues.append(f"{css.name}: almost empty — styling incomplete")
    return issues[:12]


# ══════════════════════════════════════════════════════════════════
# Engine: build / refine / auto-review+fix loop
# ══════════════════════════════════════════════════════════════════
class StudioEngine(QObject):
    sig_log   = pyqtSignal(str)
    sig_step  = pyqtSignal(int)
    sig_files = pyqtSignal()
    sig_ready = pyqtSignal(str)          # index.html first created
    sig_done  = pyqtSignal(str, str)     # project dir, summary
    sig_error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dir = None; self.working = False; self.mode = ""; self.rounds = 0; self._ready_sent = False
        self.runtime_checker = None      # callable(dir, cb) — page browser console check
        self._wd = QTimer(self); self._wd.setSingleShot(True); self._wd.timeout.connect(_ALIRA_slot(self._watchdog))
        self._coder = ALIRACoderEngine() if ALIRACoderEngine else None
        if self._coder:
            self._coder.sig_tool.connect(self._on_tool)
            self._coder.sig_tool_result.connect(self._on_result)
            self._coder.sig_notice.connect(self.sig_log)
            self._coder.sig_done.connect(self._on_agent_done)
            self._coder.sig_error.connect(self._on_agent_error)

    def available(self):
        return bool(self._coder and self._coder.is_available())

    # ── public ──
    def build(self, prompt):
        d = new_project_dir(prompt); self.dir = d
        self._begin("build", BUILD_RULES + "\n\nUSER BRIEF: " + prompt, True)
        return d

    def refine(self, d, request):
        self.dir = Path(d); touch_meta(d, request)
        self._begin("refine", REFINE_RULES.format(request=request), False)

    def cancel(self):
        self._wd.stop()
        if self._coder: self._coder.stop()
        self.working = False; self.sig_log.emit("Stopped.")

    # ── internals ──
    def _begin(self, mode, task, expect_files):
        self.mode = mode; self.working = True; self.rounds = 0; self._ready_sent = False
        self.sig_step.emit(0)
        self.sig_log.emit({"build": "Brief padh rahi hoon, plan bana rahi hoon…", "refine": "Files padh rahi hoon, change dhundh rahi hoon…"}[mode])
        self._start(task, expect_files)

    LIMIT_S = {"build": 600, "refine": 300, "fix": 300}

    def _start(self, task, expect_files):
        # watchdog: kamzor model todo-list me atak jaye to bhi time limit par jo files bani hain unka review ho
        self._wd.start(self.LIMIT_S["build" if (self.mode == "build" and self.rounds == 0) else ("fix" if self.rounds else "refine")] * 1000)
        self._coder.run(task, str(self.dir), "gemini", None, raw=True, expect_files=expect_files)

    def _watchdog(self):
        if not self.working: return
        self.sig_log.emit("Time limit — jo files ban chuki hain unka review kar rahi hoon…")
        try: self._coder.stop()
        except Exception: pass
        self._on_agent_done("Agent ne time limit tak kaam kiya; files review ke liye ready hain.")

    def _on_tool(self, label):
        self.sig_log.emit(label)
        low = label.lower()
        for i, name in ((1, "index.html"), (2, "style.css"), (3, "script.js")):
            if name in low and ("writing" in low or "creat" in low):
                self.sig_step.emit(i)
        if any(k in low for k in ("reading", "editing", "replac", "grep")) and self.mode != "build":
            self.sig_step.emit(4)
        elif any(k in low for k in ("reading", "editing", "replac")):
            self.sig_step.emit(4)

    def _on_result(self, summary, ok):
        self.sig_log.emit(("✓ " if ok else "✗ ") + summary[:90])
        if re.search(r"created|updated|replaced|edited|wrote", summary, re.I):
            self.sig_files.emit()
            if (not self._ready_sent and self.dir and (self.dir / "index.html").exists()
                    and ((self.dir / "style.css").exists() or self.mode == "refine")):
                self._ready_sent = True; self.sig_ready.emit(str(self.dir))

    def _on_agent_done(self, summary):
        self._wd.stop()
        self.last_summary = summary
        self.sig_step.emit(4); self.sig_files.emit()
        self.sig_log.emit("Review: files padh kar check kar rahi hoon…")
        issues = static_check(self.dir)

        def finish(runtime_issues):
            allissues = list(dict.fromkeys(issues + list(runtime_issues or [])))
            if allissues and self.rounds < MAX_FIX_ROUNDS and self.working:
                self.rounds += 1
                self.sig_log.emit(f"Review: {len(allissues)} issue mile — code padhkar fix kar rahi hoon (round {self.rounds}/{MAX_FIX_ROUNDS})")
                for it in allissues[:4]: self.sig_log.emit("  • " + it[:100])
                self._start(FIX_RULES.format(issues="\n".join(f"- {i}" for i in allissues)), False)
                return
            self.working = False
            touch_meta(self.dir)
            self.sig_log.emit("Review ✓ — koi issue nahi" if not allissues else f"Review: {len(allissues)} chhote warnings bache")
            self.sig_files.emit()
            self.sig_done.emit(str(self.dir), summary)

        if self.runtime_checker:
            self.runtime_checker(self.dir, finish)
        else:
            finish([])

    def _on_agent_error(self, msg):
        self._wd.stop()
        self.working = False
        self.sig_error.emit(msg)


# ══════════════════════════════════════════════════════════════════
# Code viewer highlighter
# ══════════════════════════════════════════════════════════════════
class CodeHighlighter(QSyntaxHighlighter):
    def __init__(self, doc):
        super().__init__(doc); self.lang = "html"; self._rules = []; self.set_lang("html")

    def set_lang(self, lang):
        self.lang = lang
        def fmt(color, bold=False, italic=False):
            f = QTextCharFormat(); f.setForeground(QColor(color))
            if bold: f.setFontWeight(QFont.Bold)
            if italic: f.setFontItalic(True)
            return f
        r = []
        if lang == "html":
            r = [(r"</?[\w-]+", fmt("#FF6B7D", True)), (r"\b[\w-]+(?==)", fmt("#F5C542")), (r"\"[^\"]*\"|'[^']*'", fmt("#7FDBA0")), (r"/?>", fmt("#FF6B7D", True))]
        elif lang == "css":
            r = [(r"[.#]?[\w-]+(?=[^{}]*\{)", fmt("#FF6B7D")), (r"[\w-]+(?=\s*:)", fmt("#F5C542")), (r"#[0-9a-fA-F]{3,8}\b|\b\d+(\.\d+)?(px|rem|em|%|vh|vw|s|ms|deg)?\b", fmt("#7FB7FF")), (r"\"[^\"]*\"|'[^']*'", fmt("#7FDBA0"))]
        elif lang == "js":
            kw = r"\b(const|let|var|function|return|if|else|for|while|new|class|import|export|from|async|await|try|catch|throw|document|window|true|false|null|undefined|this|addEventListener)\b"
            r = [(kw, fmt("#FF6B7D", True)), (r"\b\d+(\.\d+)?\b", fmt("#7FB7FF")), (r"\"[^\"]*\"|'[^']*'|`[^`]*`", fmt("#7FDBA0")), (r"\b[A-Za-z_]\w*(?=\()", fmt("#F5C542"))]
        self._rules = [(QRegularExpression(p), f) for p, f in r]
        self._cmt = (fmt("#6C6975", italic=True))
        self.rehighlight()

    def highlightBlock(self, text):
        for rx, f in self._rules:
            it = rx.globalMatch(text)
            while it.hasNext():
                m = it.next(); self.setFormat(m.capturedStart(), m.capturedLength(), f)
        cm = {"html": r"<!--.*?-->", "css": r"/\*.*?\*/", "js": r"//[^\n]*|/\*.*?\*/"}.get(self.lang)
        if cm:
            it = QRegularExpression(cm).globalMatch(text)
            while it.hasNext():
                m = it.next(); self.setFormat(m.capturedStart(), m.capturedLength(), self._cmt)


if HAS_WEBENGINE:
    class _ConsolePage(QWebEnginePage):
        """Hidden page: site load karke browser-console errors jama karta hai."""
        def __init__(self, parent=None):
            super().__init__(parent); self.messages = []
        def javaScriptConsoleMessage(self, level, message, line, source):
            self.messages.append((int(level), message, line, source))


_IGNORE = re.compile(r"picsum\.photos|pravatar|fonts\.g|favicon|cdn\.tailwindcss|ERR_INTERNET|ERR_NAME_NOT_RESOLVED|ERR_CONNECTION|CORS|DevTools", re.I)


# ══════════════════════════════════════════════════════════════════
# Studio page
# ══════════════════════════════════════════════════════════════════
class FlowLayout(QLayout):
    """Toolbar wrap: jagah kam ho to buttons agli line par chale jaate hain (kat-te / chhupte nahi)."""

    def __init__(self, parent=None, h=8, v=8):
        super().__init__(parent)
        self._items, self._h, self._v = [], h, v
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item): self._items.append(item)
    def count(self): return len(self._items)
    def itemAt(self, i): return self._items[i] if 0 <= i < len(self._items) else None
    def takeAt(self, i): return self._items.pop(i) if 0 <= i < len(self._items) else None
    def expandingDirections(self): return Qt.Orientations(Qt.Orientation(0))
    def hasHeightForWidth(self): return True
    def heightForWidth(self, w): return self._do(QRect(0, 0, w, 0), True)

    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do(rect, False)

    def sizeHint(self): return self.minimumSize()

    def minimumSize(self):
        size = QSize()
        for it in self._items:
            size = size.expandedTo(it.minimumSize())
        m = self.contentsMargins()
        return size + QSize(m.left() + m.right(), m.top() + m.bottom())

    def _do(self, rect, test):
        x, y, lh = rect.x(), rect.y(), 0
        for it in self._items:
            if it.isEmpty():                      # hidden widget
                continue
            sz = it.sizeHint()
            if x + sz.width() > rect.right() + 1 and lh > 0:
                x, y, lh = rect.x(), y + lh + self._v, 0
            if not test:
                it.setGeometry(QRect(QPoint(x, y), sz))
            x += sz.width() + self._h
            lh = max(lh, sz.height())
        return y + lh - rect.y()


class StudioPage(PageBase):
    GIRL_FRAC, GIRL_MIN, GIRL_MAX = 0.14, 140, 190

    def __init__(self, bus):
        super().__init__("Website Studio", "Prompt do — alag HTML/CSS/JS files banti hain, ALIRA khud padhkar fix karti hai", "code")
        self.bus = bus; self.scroll.hide()
        self.project = None; self.engine = StudioEngine(self); self.engine.runtime_checker = self.runtime_check
        self._device = "desktop"; self.fx = "lite"; self._t0 = 0; self._steps_done = -1; self._site_shown = False; self._cur_file = None
        self._reload_timer = QTimer(self, singleShot=True, interval=700, timeout=self._reload_preview)
        self._clock = QTimer(self, interval=1000, timeout=self._tick)

        content = QWidget(); content.setStyleSheet("background:transparent;")
        hl = QHBoxLayout(content); hl.setContentsMargins(0, 0, 0, 0); hl.setSpacing(12)
        self._left_card = self._build_left(); self._right_card = self._build_right()
        self._left_user = False; self._compact = False
        hl.addWidget(self._left_card, 0); hl.addWidget(self._right_card, 1)
        self.layout().addWidget(content, 1)

        self.engine.sig_log.connect(self._on_log); self.engine.sig_step.connect(self._on_step)
        self.engine.sig_files.connect(self._on_files); self.engine.sig_ready.connect(self._on_ready)
        self.engine.sig_done.connect(self._on_done); self.engine.sig_error.connect(self._on_error)
        QShortcut(QKeySequence("Ctrl+Return"), self.input, activated=self._submit)
        self._show_idle(); self._refresh_sites(); self._sync_buttons()

    # ── layout ──────────────────────────────────────────────────
    def _build_left(self):
        card, vl = make_card(); card.setFixedWidth(340); vl.setContentsMargins(12, 12, 12, 12); vl.setSpacing(8)
        self.tabs = Segmented([("agent", "Agent"), ("sites", "Your sites")], "agent"); self.tabs.changed.connect(self._left_tab)
        vl.addWidget(self.tabs)
        self.lstack = QStackedWidget(); vl.addWidget(self.lstack, 1)

        # agent view
        av = QWidget(); avl = QVBoxLayout(av); avl.setContentsMargins(0, 0, 0, 0); avl.setSpacing(8)
        self.hint = QLabel("Batao kaisi website chahiye. Main index.html, style.css aur script.js alag-alag banaungi, "
                           "phir khud padh kar check karke fix karungi. Baad mein change maango — wahi site update hogi.")
        self.hint.setWordWrap(True); self.hint.setStyleSheet(f"color:{T['muted']};{F(400,12)}")
        avl.addWidget(self.hint)
        self.starters = QWidget(); sl = QVBoxLayout(self.starters); sl.setContentsMargins(0, 0, 0, 0); sl.setSpacing(5)
        for s in STARTERS:
            b = QPushButton(s); b.setCursor(Qt.PointingHandCursor); b.setStyleSheet(css3d("QPushButton", "ghost", 10, F(400, 11), "#D9D6DE", "text-align:left;padding:7px 10px;"))
            b.clicked.connect(lambda _=False, t=s: self.input.setPlainText(t)); sl.addWidget(b)
        avl.addWidget(self.starters)
        self.msgs = QVBoxLayout(); self.msgs.setSpacing(6); self.msgs.setAlignment(Qt.AlignTop)
        mw = QWidget(); mw.setStyleSheet("background:transparent;"); mw.setLayout(self.msgs)
        self.msg_scroll = QScrollArea(); self.msg_scroll.setWidgetResizable(True); self.msg_scroll.setFrameShape(QFrame.NoFrame)
        self.msg_scroll.setStyleSheet("QScrollArea{background:transparent;border:none;}QScrollBar:vertical{width:6px;background:transparent;}"
                                      "QScrollBar::handle:vertical{background:rgba(255,255,255,0.18);border-radius:3px;}QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0;}")
        self.msg_scroll.setWidget(mw); avl.addWidget(self.msg_scroll, 1)
        # progress
        self.prog = QFrame(); self.prog.setStyleSheet("QFrame{background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.08);border-radius:10px;}QLabel{border:none;}")
        pl = QVBoxLayout(self.prog); pl.setContentsMargins(10, 8, 10, 8); pl.setSpacing(3)
        self.prog_title = QLabel("Building your site"); self.prog_title.setStyleSheet(f"color:#fff;{F(600,12)}")
        pl.addWidget(self.prog_title)
        self.step_lbls = []
        for s in STEPS:
            l = QLabel(); l.setStyleSheet(f"{F(400,11)}"); pl.addWidget(l); self.step_lbls.append(l)
        avl.addWidget(self.prog); self.prog.hide()
        self.editing = QLabel(""); self.editing.setStyleSheet(f"color:{T['muted']};{F(400,11)}"); avl.addWidget(self.editing)
        self.input = QPlainTextEdit(); self.input.setFixedHeight(84)
        self.input.setPlaceholderText("Kaisi website? (jaise: dark portfolio for a photographer)\nYa change: 'navbar sticky karo'")
        self.input.setStyleSheet(f"QPlainTextEdit{{background:rgba(255,255,255,0.05);color:#fff;border:1px solid rgba(255,255,255,0.14);border-radius:10px;padding:8px;{F(400,13)}}}"
                                 f"QPlainTextEdit:focus{{border:1px solid {T['red']};}}")
        avl.addWidget(self.input)
        row = QHBoxLayout(); row.setSpacing(8)
        self.btn_go = pill("Build", "sparkle", "primary", 38); self.btn_go.clicked.connect(_ALIRA_slot(self._submit))
        self.btn_stop = pill("Stop", "x", "danger", 38); self.btn_stop.clicked.connect(_ALIRA_slot(self._stop))
        self.btn_new = pill("New", "plus", "ghost", 38); self.btn_new.clicked.connect(_ALIRA_slot(self._new_site))
        row.addWidget(self.btn_go, 1); row.addWidget(self.btn_stop); row.addWidget(self.btn_new); avl.addLayout(row)
        self.lstack.addWidget(av)

        # sites view
        sv = QWidget(); svl = QVBoxLayout(sv); svl.setContentsMargins(0, 0, 0, 0); svl.setSpacing(8)
        self.sites = QListWidget(); self.sites.setStyleSheet(
            f"QListWidget{{background:rgba(255,255,255,0.03);color:#EDEBF0;border:1px solid rgba(255,255,255,0.08);border-radius:10px;{F(400,12)}outline:0;}}"
            f"QListWidget::item{{padding:8px;border-radius:6px;}}QListWidget::item:selected{{background:rgba(255,46,67,0.28);}}")
        self.sites.itemDoubleClicked.connect(lambda it: self._open_site(it.data(Qt.UserRole)))
        svl.addWidget(self.sites, 1)
        r2 = QHBoxLayout(); r2.setSpacing(6)
        for t, ic, fn, k in (("Open", "external", lambda: self._open_selected(), "primary"), ("Delete", "trash", self._delete_selected, "danger"), ("Folder", "folder", lambda: self._folder(self._selected_dir()), "ghost")):
            b = pill(t, ic, k, 34); b.clicked.connect(_ALIRA_slot(fn)); r2.addWidget(b)
        svl.addLayout(r2); self.lstack.addWidget(sv)
        return card

    def _build_right(self):
        card, vl = make_card(); vl.setContentsMargins(12, 10, 12, 12); vl.setSpacing(8)
        bar = FlowLayout(h=8, v=8)
        self.view_seg = Segmented([("preview", "Preview"), ("code", "Code")], "preview"); self.view_seg.changed.connect(self._set_view)
        self.dev_seg = Segmented([("desktop", "Desktop"), ("tablet", "Tablet"), ("mobile", "Phone")], "desktop"); self.dev_seg.changed.connect(self._set_device)
        self.fx_seg = Segmented([("lite", "Smooth"), ("full", "Full FX")], "lite"); self.fx_seg.changed.connect(self._set_fx)
        self.fx_seg.setToolTip("Smooth = preview me heavy blur/shadow/animation halke (scroll fast). Full FX = poora look (dheema ho sakta hai)")
        self.b_panel = pill("", "chat", "ghost", 34); self.b_panel.setFixedWidth(46)
        self.b_panel.setToolTip("Agent / sites panel dikhao ya chhupao"); self.b_panel.clicked.connect(_ALIRA_slot(self._toggle_left))
        self.b_more = self._make_more(); self.b_more.hide()
        bar.addWidget(self.b_panel); bar.addWidget(self.view_seg); bar.addWidget(self.dev_seg); bar.addWidget(self.fx_seg); bar.addWidget(self.b_more)
        self.b_copy = pill("Copy", "file", "ghost", 34); self.b_copy.clicked.connect(_ALIRA_slot(self._copy_code))
        self.b_zip = pill("Export", "download", "ghost", 34); self.b_zip.clicked.connect(_ALIRA_slot(self._export))
        self.b_open = pill("Browser", "external", "primary", 34); self.b_open.clicked.connect(_ALIRA_slot(self._open_browser))
        self.b_dir = pill("", "folder", "ghost", 34); self.b_dir.setFixedWidth(46); self.b_dir.clicked.connect(lambda: self._folder(self.project)); self.b_dir.setToolTip("Folder kholo")
        self.b_dep = pill("Deploy", "globe", "ghost", 34); self.b_dep.clicked.connect(_ALIRA_slot(self._deploy))
        for b in (self.b_copy, self.b_zip, self.b_dep, self.b_dir, self.b_open): bar.addWidget(b)
        self._action_texts = {self.b_copy: "Copy", self.b_zip: "Export", self.b_dep: "Deploy", self.b_open: "Browser"}
        for b, t in self._action_texts.items(): b.setToolTip(t)
        vl.addLayout(bar)
        self.rstack = QStackedWidget(); vl.addWidget(self.rstack, 1)

        # preview
        pv = QWidget(); pv.setStyleSheet("background:rgba(0,0,0,0.35);border-radius:10px;")
        self.pv_l = QHBoxLayout(pv); self.pv_l.setContentsMargins(0, 0, 0, 0); self.pv_l.addStretch(1)
        if HAS_WEBENGINE:
            self.web = QWebEngineView(); self.web.setStyleSheet("background:#05030a;border-radius:10px;")
            try:
                from PyQt5.QtWebEngineWidgets import QWebEngineSettings
                self.web.settings().setAttribute(QWebEngineSettings.ScrollAnimatorEnabled, True)   # smooth wheel scrolling
            except Exception:
                pass
            self.web.loadFinished.connect(self._apply_fx)
            self.pv_l.addWidget(self.web, 100)
        else:
            self.web = None
            msg = QLabel("Live preview ke liye PyQtWebEngine chahiye:\n   pip install PyQtWebEngine\n\nTab tak 'Browser' button se site dekho.")
            msg.setAlignment(Qt.AlignCenter); msg.setStyleSheet(f"color:{T['muted']};{F(400,13)}"); self.pv_l.addWidget(msg, 100)
        self.pv_l.addStretch(1)
        self.rstack.addWidget(pv)

        # code
        cv = QWidget(); cvl = QVBoxLayout(cv); cvl.setContentsMargins(0, 0, 0, 0); cvl.setSpacing(6)
        self.file_row = QHBoxLayout(); self.file_row.setSpacing(6); cvl.addLayout(self.file_row)
        self.code = QPlainTextEdit(); self.code.setReadOnly(True); self.code.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.code.setFont(QFont("Consolas", 10))
        self.code.setStyleSheet("QPlainTextEdit{background:rgba(0,0,0,0.4);color:#E8E6EC;border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:8px;}")
        self.hl = CodeHighlighter(self.code.document()); cvl.addWidget(self.code, 1)
        self.rstack.addWidget(cv)
        self.status = QLabel(""); self.status.setStyleSheet(f"color:{T['muted']};{F(400,11)}"); vl.addWidget(self.status)
        return card

    # ── public api (voice / other pages) ─────────────────────────
    def is_working(self): return self.engine.working

    def start_build(self, prompt):
        """Voice/typed 'website banao ...' yahin se shuru hota hai."""
        if self.engine.working: return False
        self.tabs.set_current("agent"); self.lstack.setCurrentIndex(0)
        self.project = None; self.input.setPlainText(prompt); self._submit(); return True

    # ── submit / flow ────────────────────────────────────────────
    def _submit(self):
        text = self.input.toPlainText().strip()
        if not text or self.engine.working: return
        if not self.engine.available():
            self._msg("error", "ALIRA Coder (node) available nahi. ALIRA_coder/ mein 'npm install && npm run build' chalao."); return
        self.input.clear(); self.starters.hide(); self.hint.hide()
        self._msg("user", text)
        self._t0 = time.time(); self._steps_done = -1; self._site_shown = False
        if self.project and (Path(self.project) / "index.html").exists():
            self.engine.refine(self.project, text); self._site_shown = True
        else:
            self.project = self.engine.build(text)
            self._show_hud()
        self.prog_title.setText("Updating your site" if self.engine.mode == "refine" else "Building your site")
        self.prog.show(); self._on_step(0); self._clock.start(); self._sync_buttons(); self._set_editing()

    def _stop(self):
        self.engine.cancel(); self._clock.stop(); self.prog.hide(); self._msg("agent", "Roka gaya."); self._sync_buttons()

    def _new_site(self):
        if self.engine.working: return
        self.project = None; self.starters.show(); self.hint.show(); self._clear_msgs(); self._show_idle(); self._set_editing(); self._sync_buttons(); self.code.clear()

    def _on_log(self, text):
        if HAS_WEBENGINE and self.web and not self._site_shown:
            self.web.page().runJavaScript("window.__log && __log(%s)" % json.dumps(text[:120]))

    def _on_step(self, i):
        self._steps_done = max(self._steps_done, i)
        for k, l in enumerate(self.step_lbls):
            if k < self._steps_done: l.setText(f"✓  {STEPS[k]}"); l.setStyleSheet(f"color:#fff;{F(400,11)}")
            elif k == self._steps_done: l.setText(f"◐  {STEPS[k]}"); l.setStyleSheet(f"color:{T['red']};{F(600,11)}")
            else: l.setText(f"○  {STEPS[k]}"); l.setStyleSheet(f"color:{T['dim']};{F(400,11)}")

    def _tick(self):
        n = len(project_files(self.project)) if self.project else 0
        self.prog_title.setText(f"{'Updating' if self.engine.mode == 'refine' else 'Building'} your site · {int(time.time() - self._t0)}s · {n} files")

    def _on_ready(self, d):      # index.html pehli baar bana — HUD hata ke site dikhao
        self._show_site(); self._refresh_code()

    def _on_files(self):
        self._refresh_code(); self._reload_timer.start(); self._update_status()

    def _on_done(self, d, summary):
        self._clock.stop(); self.prog.hide(); self._on_step(5)
        self.project = Path(d); self._show_site(); self._reload_preview(); self._refresh_code(); self._refresh_sites()
        self._msg("agent", (summary or "Done.").replace("DONE:", "").strip()[:600] + f"\n\n📁 {self.project.name}")
        self._sync_buttons(); self._set_editing(); self._update_status()
        self.bus.toast.emit("✓ Website ready: " + self.project.name)

    def _on_error(self, msg):
        self._clock.stop(); self.prog.hide(); self._msg("error", msg[:400]); self._sync_buttons()
        if self.project and (Path(self.project) / "index.html").exists(): self._show_site()
        else: self._show_idle()

    # ── preview ──────────────────────────────────────────────────
    def _show_hud(self):
        self._site_shown = False
        if self.web: self.web.setHtml(HUD_HTML, QUrl("about:blank"))

    def _show_idle(self):
        self._site_shown = False
        if self.web: self.web.setHtml(IDLE_HTML, QUrl("about:blank"))

    def _show_site(self):
        if not (self.web and self.project): return
        idx = Path(self.project) / "index.html"
        if idx.exists():
            self._site_shown = True; self.web.load(QUrl.fromLocalFile(str(idx)))

    def _reload_preview(self):
        if self.web and self._site_shown and self.project and (Path(self.project) / "index.html").exists():
            self.web.load(QUrl.fromLocalFile(str(Path(self.project) / "index.html")))

    # ── responsive (mini window) ────────────────────────────────
    def _make_more(self):
        b = pill("", "sliders", "ghost", 34); b.setFixedWidth(46); b.setToolTip("Device preview aur effects")
        b.setStyleSheet(b.styleSheet() + "QPushButton::menu-indicator{image:none;width:0;}")
        m = QMenu(b)
        m.setStyleSheet("QMenu{background:#15121A;color:#EDEBF0;border:1px solid rgba(255,46,67,0.5);border-radius:10px;padding:6px;}"
                        "QMenu::item{padding:8px 18px;border-radius:6px;}QMenu::item:selected{background:rgba(255,46,67,0.28);}"
                        "QMenu::separator{height:1px;background:rgba(255,255,255,0.1);margin:4px 8px;}")
        for k, t in (("desktop", "Desktop preview"), ("tablet", "Tablet preview"), ("mobile", "Phone preview")):
            m.addAction(t).triggered.connect(lambda _=False, kk=k: self._set_device(kk))
        m.addSeparator()
        for k, t in (("lite", "Smooth effects"), ("full", "Full FX")):
            m.addAction(t).triggered.connect(lambda _=False, kk=k: self._set_fx(kk))
        b.setMenu(m)
        return b

    def _toggle_left(self):
        self._left_user = True
        self._left_card.setVisible(not self._left_card.isVisible())
        self._responsive()

    def _responsive(self):
        if not hasattr(self, "_left_card") or not hasattr(self, "_action_texts"):
            return
        w = self.width()
        if not self._left_user:                       # user ne haath nahi lagaya => chhoti window par auto-collapse
            self._left_card.setVisible(w >= 820)
        self._left_card.setFixedWidth(300 if w < 1000 else 340)
        avail = w - getattr(self, "_gw", 190) - 24
        rw = avail - ((self._left_card.width() + 12) if self._left_card.isVisible() else 0)
        compact = rw < 560
        if compact != self._compact:
            self._compact = compact
            self.dev_seg.setVisible(not compact); self.fx_seg.setVisible(not compact); self.b_more.setVisible(compact)
            for b, t in self._action_texts.items():
                if compact and b is not self.b_open:           # primary "Browser" button text ke saath rahe
                    b.setText(""); b.setFixedWidth(46)
                else:
                    b.setText("  " + t); b.setMinimumWidth(0); b.setMaximumWidth(16777215)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._responsive()

    def _set_device(self, k):
        self._device = k; self.dev_seg.set_current(k)
        if self.web:
            w = {"desktop": 16777215, "tablet": 820, "mobile": 390}[k]
            self.web.setMaximumWidth(w); self.pv_l.setStretch(1, 100 if k == "desktop" else 0)
            self.web.setMinimumWidth(0 if k == "desktop" else w)

    def _apply_fx(self, ok=True):
        if ok and self.web and self._site_shown and self.fx == "lite":
            self.web.page().runJavaScript(LITE_JS)

    def _set_fx(self, k):
        self.fx = k; self.fx_seg.set_current(k); self._reload_preview()

    def _set_view(self, k):
        self.view_seg.set_current(k); self.rstack.setCurrentIndex(0 if k == "preview" else 1)
        if k == "code": self._refresh_code()

    # ── runtime check (browser console) ─────────────────────────
    def runtime_check(self, d, cb):
        idx = Path(d) / "index.html"
        if not (HAS_WEBENGINE and idx.exists()):
            cb([]); return
        page = _ConsolePage(self); done = {"v": False}

        def finish():
            if done["v"]: return
            done["v"] = True; issues = []
            for lvl, msg, line, src in page.messages:
                if lvl < 2 and "not defined" not in msg: continue
                if _IGNORE.search(msg + " " + str(src)): continue
                issues.append(f"Browser console error in {os.path.basename(str(src).split('?')[0]) or 'page'}:{line} — {msg[:160]}")
            page.deleteLater(); cb(list(dict.fromkeys(issues))[:8])
        page.loadFinished.connect(lambda ok: QTimer.singleShot(2500, finish))
        QTimer.singleShot(15000, finish)
        page.load(QUrl.fromLocalFile(str(idx)))

    # ── code view ───────────────────────────────────────────────
    def _refresh_code(self):
        files = project_files(self.project) if self.project else []
        names = [f.name for f in files]
        have = [self.file_row.itemAt(i).widget().text() for i in range(self.file_row.count()) if self.file_row.itemAt(i).widget()]
        if names != have:
            while self.file_row.count():
                w = self.file_row.takeAt(0).widget()
                if w: w.deleteLater()
            for f in files:
                b = QPushButton(f.name); b.setCursor(Qt.PointingHandCursor); b.setFixedHeight(30)
                b.clicked.connect(lambda _=False, p=f: self._show_file(p)); self.file_row.addWidget(b)
            self.file_row.addStretch(1)
        if files and (self._cur_file not in files):
            self._cur_file = files[0]
        if self._cur_file and self._cur_file in files: self._show_file(self._cur_file)
        elif not files: self.code.setPlainText("")

    def _show_file(self, p):
        self._cur_file = p; txt = _read(p, 300_000)
        sb = self.code.verticalScrollBar().value()
        self.hl.set_lang({".html": "html", ".css": "css", ".js": "js"}.get(p.suffix.lower(), "none"))
        self.code.setPlainText(txt); self.code.verticalScrollBar().setValue(sb)
        for i in range(self.file_row.count()):
            w = self.file_row.itemAt(i).widget()
            if w: w.setStyleSheet(css3d("QPushButton", "active" if w.text() == p.name else "ghost", 8, F(500, 11), "#fff", "padding:0 12px;"))

    def _copy_code(self):
        QGuiApplication.clipboard().setText(self.code.toPlainText()); self.bus.toast.emit("✓ Code copy hua")

    # ── actions ─────────────────────────────────────────────────
    def _open_browser(self):
        if self.project and (Path(self.project) / "index.html").exists(): act.open_path(Path(self.project) / "index.html")
        else: self.bus.toast.emit("✗ Pehle koi site banao")

    def _folder(self, d):
        if d: act.open_path(d)

    def _export(self):
        if not self.project: self.bus.toast.emit("✗ Pehle koi site banao"); return
        name = Path(self.project).name + ".zip"
        path, _ = QFileDialog.getSaveFileName(self, "Export website", str(Path.home() / "Desktop" / name), "Zip (*.zip)")
        if not path: return
        try:
            with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
                for f in Path(self.project).rglob("*"):
                    if f.is_file() and not f.name.startswith(".") and ".ALIRA-coder" not in str(f):
                        z.write(f, f.relative_to(self.project))
            self.bus.toast.emit("✓ Exported: " + os.path.basename(path))
        except Exception as e:
            self.bus.toast.emit(f"✗ Export fail: {e}")

    def _deploy(self):
        if not self.project: self.bus.toast.emit("✗ Pehle koi site banao"); return
        self.bus.deploy_site.emit(str(self.project))

    # ── sites list ──────────────────────────────────────────────
    def _left_tab(self, k):
        self.tabs.set_current(k); self.lstack.setCurrentIndex(0 if k == "agent" else 1)
        if k == "sites": self._refresh_sites()

    def _refresh_sites(self):
        self._rows = list_projects(); self.sites.clear()
        for r in self._rows:
            it = QListWidgetItem(f"{r['title']}\n{r['brief'][:60]}\n{ago(r['mtime'])} · {r['files']} files")
            it.setData(Qt.UserRole, str(r["dir"])); self.sites.addItem(it)
        self.tabs._btns["sites"].setText(f"Your sites ({len(self._rows)})")

    def _selected_dir(self):
        it = self.sites.currentItem(); return it.data(Qt.UserRole) if it else None

    def _open_selected(self):
        d = self._selected_dir()
        if d: self._open_site(d)

    def _open_site(self, d):
        if self.engine.working or not d: return
        self.project = Path(d); self._site_shown = False
        self._left_tab("agent"); self.starters.hide(); self.hint.hide()
        self._show_site(); self._refresh_code(); self._set_editing(); self._sync_buttons(); self._update_status()
        self._msg("agent", f"'{self.project.name}' khul gayi. Neeche change likho — main files padhkar sirf wahi part edit karungi.")

    def _delete_selected(self):
        d = self._selected_dir()
        if not d: return
        if QMessageBox.question(self, "Delete site", f"{Path(d).name} delete kar dun?") != QMessageBox.Yes: return
        shutil.rmtree(d, ignore_errors=True)
        if self.project and Path(self.project) == Path(d): self.project = None; self._show_idle()
        self._refresh_sites(); self._set_editing(); self._sync_buttons()

    # ── small ui helpers ────────────────────────────────────────
    @staticmethod
    def _md(text):
        """Chhota markdown -> HTML (**bold**, `code`, ### heading, '- ' list)."""
        import html as _h
        out = []
        for line in _h.escape(text).split("\n"):
            ls = line.strip()
            if ls.startswith("#"):
                line = "<b style='color:#fff'>" + ls.lstrip("#").strip() + "</b>"
            elif ls.startswith(("- ", "* ")):
                line = "&bull; " + ls[2:]
            line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
            line = re.sub(r"`([^`]+)`", r"<code style='color:#FF9AA6'>\1</code>", line)
            out.append(line)
        return "<br>".join(out)

    def _msg(self, role, text):
        l = QLabel(); l.setWordWrap(True); l.setTextInteractionFlags(Qt.TextSelectableByMouse)
        if role == "agent": l.setTextFormat(Qt.RichText); l.setText(self._md(text))
        else: l.setTextFormat(Qt.PlainText); l.setText(text)
        if role == "user":
            l.setStyleSheet(f"background:rgba(255,46,67,0.18);border:1px solid rgba(255,46,67,0.4);border-radius:10px;padding:8px 10px;color:#fff;{F(400,12)}")
        elif role == "error":
            l.setStyleSheet(f"background:rgba(255,46,67,0.10);border:1px solid rgba(255,46,67,0.4);border-radius:10px;padding:8px 10px;color:#FF9AA6;{F(400,12)}")
        else:
            l.setStyleSheet(f"background:rgba(255,255,255,0.05);border:1px solid rgba(255,255,255,0.08);border-radius:10px;padding:8px 10px;color:#EDEBF0;{F(400,12)}")
        self.msgs.addWidget(l)
        QTimer.singleShot(30, lambda: self.msg_scroll.verticalScrollBar().setValue(self.msg_scroll.verticalScrollBar().maximum()))

    def _clear_msgs(self):
        while self.msgs.count():
            w = self.msgs.takeAt(0).widget()
            if w: w.deleteLater()

    def _set_editing(self):
        self.editing.setText(f"✎ Editing: {Path(self.project).name}" if self.project else "")

    def _sync_buttons(self):
        w = self.engine.working
        refining = bool(self.project and (Path(self.project) / "index.html").exists())
        self.btn_go.setText("  Update" if refining else "  Build")
        self.btn_go.setEnabled(not w); self.btn_stop.setVisible(w); self.btn_new.setEnabled(not w); self.input.setEnabled(not w)
        has = bool(self.project)
        for b in (self.b_copy, self.b_zip, self.b_open, self.b_dir, self.b_dep): b.setEnabled(has and not w)

    def _update_status(self):
        if self.project:
            fs = project_files(self.project); kb = sum(f.stat().st_size for f in fs if f.exists()) // 1024
            self.status.setText(f"{self.project}  ·  {len(fs)} files  ·  {kb} KB")
        else:
            self.status.setText("")

    def on_show(self):
        self._refresh_sites(); self._sync_buttons()
