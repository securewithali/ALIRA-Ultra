# -*- coding: utf-8 -*-
"""
ALIRA v8.0 — ALIRA Coder AI Agent Integrated
=======================================================================
v7.4 ke saare fixes INTACT + NEW:
  ✅ ALIRA WebForge AI — voice command se website banao + deploy karo
  ✅ website_builder/ folder se import hota hai
  ✅ GitHub push + Vercel deploy + QR code popup automatic
  ✅ Camera Vision module (builder section removed — clean)
  ✅ Screen Share module (unchanged)
  ✅ All original ALIRA features preserved

ORIGINAL v7.4 FEATURES (preserved):
  ✅ Real-time screen sharing
  ✅ Camera Vision (Gemini real-time)
  ✅ SILENCE_RMS = 25, SILENCE_FRAMES = 16  # ~320ms chup = baat khatam (pehle 30 = 600ms => jawab late aata tha)
  ✅ VAD, error UI, timeout detection
  ✅ Session renewal, keepalive, reconnect

MIC THREAD v2 (merged):
  ✅ Error spam throttle — same error baar baar nahi aayega
  ✅ Auto device fallback: configured → auto-detect → default → 0,1,2
  ✅ PortAudio re-init on crash (EXE pe hota hai)
  ✅ Smooth retry with backoff
"""

from ALIRA_slot import slot as _ALIRA_slot
import sys, os, asyncio, threading, base64, json, math, random, time, collections

# Windows console/terminal codepage is often NOT UTF-8 (e.g. cp1252) -
# without this, the ✅/❌ etc. prints below raise UnicodeEncodeError and
# crash the import (surfaces as "[ERROR] Failed to import TABBU" upstream).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import numpy as np
import sounddevice as sd
from datetime import datetime
from pathlib import Path

import cv2

try:
    from PyQt5 import QtWebEngineWidgets   # noqa: F401 — QApplication se pehle import (Website Studio live preview)
except Exception:
    pass
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QSizePolicy, QFileDialog,
    QDialog, QComboBox, QDialogButtonBox, QLineEdit, QStackedWidget,
    QListWidget, QListWidgetItem, QInputDialog, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QObject, QRect, QSize, QThread, QEvent
from PyQt5.QtGui import (
    QColor, QPainter, QPen, QBrush, QLinearGradient,
    QRadialGradient, QPalette, QFont, QPixmap, QImage
)
import websockets, websockets.exceptions

# UI widgets alag file (TABBU_ui.py) mein hain
from TABBU_ui import (
    ChatWidget, MicSelectDialog, TaskManagerDialog,
)
# Naya red/black dashboard UI (ALIRA_ui.py)
from ALIRA_ui import (
    Sidebar, HeroPanel, StatsCard, QuickToolsCard, RecentActivityCard, HeaderBar,
    InputBar, ChipsRow, StatusBar, T as _UI, load_fonts, ApiKeySetupDialog,
)
from ALIRA_studio import StudioPage
from ALIRA_pages import (
    Bus, ChatPage, VoicePage, PCControlPage, AppsToolsPage, AutomationPage, FilesPage,
    MediaPage, WebSearchPage, SystemMonitorPage, SettingsPage, AboutPage,
)


# ══════════════════════════════════════════════════════════════════
# CAMERA VISION MODULE
# ══════════════════════════════════════════════════════════════════
try:
    from camera_vision_module import (
        CameraVisionManager, CameraVisionPanel, VisionFrameInjector
    )
    _HAS_CAM_VISION = True
    print("[ALIRA] Camera vision module loaded ✅")
except ImportError:
    _HAS_CAM_VISION = False
    print("[ALIRA] camera_vision_module not found")
    class CameraVisionManager(QObject):
        sig_vision_frame = pyqtSignal(str) if False else None
        sig_ui_frame     = None
        sig_started      = None
        sig_stopped      = None
        sig_error        = None
        sig_status       = None
        def __init__(self): pass
        def start(self): pass
        def stop(self): pass
        def toggle(self): pass
        def set_auto_vision(self, on): pass
        def describe_now(self, *a): pass
        @property
        def is_active(self): return False
    class CameraVisionPanel(QWidget):
        def __init__(self, mgr, parent=None):
            super().__init__(parent)
            QVBoxLayout(self).addWidget(QLabel("Camera Vision\nnot available"))
    class VisionFrameInjector:
        def __init__(self, *a): pass
        def push_frame(self, b): pass
        def send_camera_start_notify(self): pass
        def send_camera_stop_notify(self): pass


# ══════════════════════════════════════════════════════════════════
# SCREEN SHARE MODULE
# ══════════════════════════════════════════════════════════════════
try:
    from screen_share_module import (
        ScreenShareManager, ScreenShareButton, ScreenFrameSender
    )
    _HAS_SCREEN_SHARE = True
    print("[ALIRA] Screen share module loaded ✅")
except ImportError:
    _HAS_SCREEN_SHARE = False
    print("[ALIRA] screen_share_module not found — pip install mss pillow")
    class ScreenShareManager:
        sig_started     = None
        sig_stopped     = None
        sig_error       = None
        sig_status      = None
        sig_frame_ready = None
        def __init__(self, fps=1.0): self._active = False
        def start(self): pass
        def stop(self): pass
        def toggle(self): pass
        @property
        def is_active(self): return False
    class ScreenShareButton(QPushButton):
        def __init__(self, p=None):
            super().__init__("🖥️  N/A", p)
            self.setFixedSize(112, 36)
        def set_sharing(self, on): pass
    class ScreenFrameSender:
        def __init__(self, *a, **kw): pass
        def push_frame(self, b): pass
        def send_screen_start_notify(self, t=None): pass
        def send_screen_stop_notify(self): pass


# ══════════════════════════════════════════════════════════════════
# WEBFORGE — AI WEBSITE BUILDER  (website_builder/ folder)
# ══════════════════════════════════════════════════════════════════
try:
    from website_builder.webforge_manager import WebForgeManager
    _webforge     = WebForgeManager()
    _HAS_WEBFORGE = True
    print("[ALIRA] WebForge AI Website Builder loaded ✅")
except ImportError as _wf_err:
    _HAS_WEBFORGE = False
    _webforge     = None
    print(f"[ALIRA] WebForge not available: {_wf_err}")
    print("[ALIRA] Fix: pip install python-dotenv requests google-genai qrcode[pil]")
    print("[ALIRA] Also make sure website_builder/ folder exists next to main.py")


# ══════════════════════════════════════════════════════════════════
# ALIRA CODER — AI CODING AGENT (ALIRA_coder_integration.py)
# ══════════════════════════════════════════════════════════════════
try:
    from ALIRA_coder_integration import (
        ALIRACoderOverlay, is_website_command as _is_website_command
    )
    _HAS_ALIRA_CODER = True
    print("[ALIRA] ALIRA Coder AI Agent loaded ✅")
except ImportError as _mc_err:
    _HAS_ALIRA_CODER = False
    ALIRACoderOverlay = None
    print(f"[ALIRA] ALIRA Coder not available: {_mc_err}")

    def _is_website_command(text: str) -> bool:
        t = text.lower()
        # Website keywords
        has_website = any(w in t for w in [
            "website", "web page", "webpage", "web app", "landing page",
            "portfolio", "site bana", "web bana"
        ])
        # Action keywords
        has_action = any(w in t for w in [
            "bana", "banao", "bana do", "banana", "chahiye",
            "create", "build", "make", "design", "develop"
        ])
        return has_website and has_action


# ══════════════════════════════════════════════════════════════════
# WEBFORGE EVENT — thread-safe UI update
# ══════════════════════════════════════════════════════════════════
class _WebForgeEvent(QEvent):
    TYPE = QEvent.Type(QEvent.registerEventType())
    def __init__(self, msg: str, success: bool = True):
        super().__init__(self.TYPE)
        self.msg     = msg
        self.success = success


# ══════════════════════════════════════════════════════════════════
# QUICK FEATURES (ALIRA_quick_features.py) — 30+ offline commands
# ══════════════════════════════════════════════════════════════════
try:
    from ALIRA_quick_features import handle_quick as _handle_quick, start_background as _quick_start
    _HAS_QUICK = True
    print("[ALIRA] Quick Features loaded ✅")
except Exception as _qf_err:
    _HAS_QUICK = False
    _handle_quick = None
    _quick_start  = None
    print(f"[ALIRA] Quick Features not available: {_qf_err}")


# ══════════════════════════════════════════════════════════════════
# EDGE GLOW (ALIRA_edge_glow.py) — screen ke kinaron par state-wise rang-birangi border
# ══════════════════════════════════════════════════════════════════
try:
    from ALIRA_edge_glow import EdgeGlow
    _HAS_EDGE = True
except Exception as _eg_err:
    _HAS_EDGE = False
    EdgeGlow = None
    print(f"[ALIRA] Edge glow not available: {_eg_err}")


# ══════════════════════════════════════════════════════════════════
# FLOATING ORB / SCREEN GUARDIAN / AUTOSTART
# ══════════════════════════════════════════════════════════════════
import ALIRA_prefs as _prefs
try:
    from ALIRA_float_orb import FloatingOrb
    from ALIRA_guardian import ScreenGuardian
    import ALIRA_autostart as _autostart
    _HAS_ORB = True
except Exception as _orb_err:
    _HAS_ORB = False
    FloatingOrb = ScreenGuardian = _autostart = None
    print(f"[ALIRA] Floating orb not available: {_orb_err}")


def _load_edge_pref() -> bool:
    try:
        return bool(json.loads(_get_config_path_early().read_text()).get("edge_glow", True))
    except Exception:
        return True


def _save_edge_pref(on: bool):
    try:
        path = _get_config_path_early()
        c = json.loads(path.read_text()) if path.exists() else {}
        c["edge_glow"] = bool(on)
        path.write_text(json.dumps(c, indent=2))
    except Exception as e:
        print(f"[CONFIG] Error saving edge glow: {e}")


class _QuickEvent(QEvent):
    TYPE = QEvent.Type(QEvent.registerEventType())
    def __init__(self, msg: str, speak: bool = True):
        super().__init__(self.TYPE)
        self.msg   = msg
        self.speak = speak


# ══════════════════════════════════════════════════════════════════
# ALIRA CODER EVENT — thread-safe done/error notification
# ══════════════════════════════════════════════════════════════════
class _ALIRACoderDoneEvent(QEvent):
    TYPE = QEvent.Type(QEvent.registerEventType())
    def __init__(self, summary: str, success: bool = True):
        super().__init__(self.TYPE)
        self.summary = summary
        self.success = success


# ══════════════════════════════════════════════════════════════════
# AUDIO / MIC CONFIG
# ══════════════════════════════════════════════════════════════════
MIC_RATE       = 16000
SPK_RATE       = 24000
FRAMES         = int(MIC_RATE * 20 / 1000)
SILENCE_RMS    = 35  # Raised: Realtek bg noise ~10-15, speech ~50+
SILENCE_FRAMES = 16  # ~320ms chup = baat khatam (pehle 30 = 600ms => jawab late aata tha)
MIC_GAIN       = 2.5
AUDIO_BUF_MS   = 40   # chhota playback buffer = jaldi awaaz shuru

_MIC_DEVICE = None
_SPK_DEVICE = None

def _get_best_mic_device():
    devices = sd.query_devices()
    prefer  = ["headset","headphone","earphone","microphone","usb","webcam","external"]
    avoid   = ["stereo mix","what u hear","virtual","loopback","speaker","monitor","output"]
    best_idx, best_score = None, -1
    for i, d in enumerate(devices):
        if d["max_input_channels"] < 1: continue
        name = d["name"].lower()
        if any(k in name for k in avoid): continue
        score = sum(2 for k in prefer if k in name)
        if d.get("default_samplerate", 0) in (16000, 44100, 48000): score += 1
        if score > best_score: best_score = score; best_idx = i
    if best_idx is not None:
        print(f"[MIC] Auto-selected: [{best_idx}] {devices[best_idx]['name']}")
    return best_idx

def list_audio_devices():
    print("\n=== MICROPHONES ===")
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            print(f"  [{i:2d}] {d['name']}{' ← DEFAULT' if i==sd.default.device[0] else ''}")
    print("\n=== SPEAKERS ===")
    for i, d in enumerate(sd.query_devices()):
        if d["max_output_channels"] > 0:
            print(f"  [{i:2d}] {d['name']}{' ← DEFAULT' if i==sd.default.device[1] else ''}")

def _enc(o): return json.dumps(o).encode()


# ══════════════════════════════════════════════════════════════════
# OPTIONAL MODULES (TABBU_modules, whatsapp, office, prompts)
# ══════════════════════════════════════════════════════════════════
try:
    from TABBU_modules.TABBU_advanced_features import (
        ADVANCED_FEATURES_TOOLS, dispatch_advanced_feature,
        init_advanced_features, TABBUMemory, ClipboardAutomation,
        PDFReader, AssignmentDialog, extract_text_from_image, _analyze_image_with_gemini,
    )
    _HAS_ADV = True
except ImportError:
    try:
        from TABBU_modules.TABBU_advanced_features import (
            ADVANCED_FEATURES_TOOLS, dispatch_advanced_feature,
            init_advanced_features, TITANMemory as TABBUMemory,
        )
        _HAS_ADV = True
    except ImportError:
        _HAS_ADV = False
        ADVANCED_FEATURES_TOOLS = []
        async def dispatch_advanced_feature(n, a): return "n/a"
        def init_advanced_features(api_key=None): pass
        class TABBUMemory:
            @staticmethod
            def add_note(*a, **kw): pass
            @staticmethod
            def add_conversation(*a, **kw): pass
            @staticmethod
            def save(): pass

try:
    from whatsapp_file_sender import WA_FILE_TOOL_DECLARATIONS, wa_file_dispatch, WA_FILE_TOOL_MAP
except ImportError:
    WA_FILE_TOOL_DECLARATIONS = []; WA_FILE_TOOL_MAP = {}
    async def wa_file_dispatch(n, a): return "ok"

try:    from prompt        import TABBU_PROMPT
except: TABBU_PROMPT  = "You are ALIRA, a warm caring AI assistant. Greet warmly. Short replies. Match user language."
try:    from normal_prompt import NORMAL_PROMPT
except: NORMAL_PROMPT = "You are ALIRA, a professional AI assistant. Greet formally. Concise replies. Match user language."

TABBU_PROMPT   = TABBU_PROMPT.replace("TITAN", "ALIRA").replace("TABBU", "ALIRA")
NORMAL_PROMPT = NORMAL_PROMPT.replace("TITAN", "ALIRA").replace("TABBU", "ALIRA")

try:
    from TABBU_modules.tools import TOOL_DECLARATIONS, dispatch as _base_dispatch, TOOL_MAP as _TOOL_MAP
    _HAS_BASE = True
except ImportError:
    TOOL_DECLARATIONS = []; _HAS_BASE = False; _TOOL_MAP = {}
    async def _base_dispatch(n, a): return "ok"

try:
    from TABBU_modules.TABBU_advanced_tools import (
        ADVANCED_TOOL_DECLARATIONS, advanced_dispatch, init_advanced, memory_save,
        _tasks_load as _tm_tasks_load, _tasks_save as _tm_tasks_save,
        _parse_due as _tm_parse_due, _set_reminder as _tm_set_reminder,
    )
    _BASE_TOOLS = TOOL_DECLARATIONS + ADVANCED_TOOL_DECLARATIONS + WA_FILE_TOOL_DECLARATIONS
    _HAS_TASK_MANAGER = True
except ImportError:
    _BASE_TOOLS = TOOL_DECLARATIONS + WA_FILE_TOOL_DECLARATIONS
    async def advanced_dispatch(n, a): return "ok"
    async def memory_save(r, c): pass
    def init_advanced(**kw): pass
    _HAS_TASK_MANAGER = False
    def _tm_tasks_load(): return []
    def _tm_tasks_save(tasks): pass
    def _tm_parse_due(text): return ""
    def _tm_set_reminder(title, due_iso): pass

try:
    from TABBU_office_manage import (
        TITAN_OFFICE_TOOLS, office_dispatch, OFFICE_TOOL_NAMES, watch_location_realtime
    )
    _HAS_OFFICE = True
except ImportError:
    _HAS_OFFICE = False; TITAN_OFFICE_TOOLS = []; OFFICE_TOOL_NAMES = set()
    async def office_dispatch(n, a): return "Office module nahi mila"
    async def watch_location_realtime(n): pass

# ✅ FIX: ALIRA Coder was NEVER an actual Gemini tool — it was only triggered
# by a blind client-side keyword match on the transcript, while the system
# prompt told the model to just talk about building instead of using a real
# tool. If the user's phrasing didn't hit the hardcoded trigger list, nothing
# happened — ALIRA "couldn't access" the builder even though she meant to.
# Giving her a real functionCall makes the trigger as reliable as every other
# one of her 130+ tools (the model decides intent, not a keyword list).
_ALIRA_CODER_TOOLS = [{
    "name": "build_website",
    "description": (
        "Trigger ALIRA Coder — the AI website-building engine — to generate and "
        "save a complete website (HTML/CSS/JS) in the background. Call this "
        "IMMEDIATELY whenever the user asks to build/create/design a website, "
        "landing page, portfolio, or webpage, in ANY language/phrasing. Do NOT "
        "write HTML/CSS/JS yourself and do NOT use write_code for this — this "
        "tool hands the job to the dedicated builder engine."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": (
                    "A clear, complete build instruction combining exactly what "
                    "the user asked for — theme, purpose, sections, style, etc."
                )
            }
        },
        "required": ["description"]
    }
}] if _HAS_ALIRA_CODER else []

_ALL_TOOLS_RAW = _BASE_TOOLS + ADVANCED_FEATURES_TOOLS + TITAN_OFFICE_TOOLS + _ALIRA_CODER_TOOLS
# ✅ FIX: kai tool names (find_file, read_screen, read_active_window) do baar
# declare ho rahe the (base + advanced/office lists mein). Purana 2.5 model
# duplicate functionDeclarations tolerate kar leta tha, lekin naya
# gemini-3.1-flash-live-preview strict validation karta hai aur setup ke turant
# baad "1011 internal error" de ke session band kar deta tha. Ab duplicate
# names hata ke sirf pehla occurrence rakhte hain.
def _dedupe_tools(tools):
    seen, out = set(), []
    for t in tools:
        if t["name"] not in seen:
            seen.add(t["name"]); out.append(t)
    return out

_ALL_TOOLS = _dedupe_tools(_ALL_TOOLS_RAW)
_ADV_NAMES = {t["name"] for t in ADVANCED_FEATURES_TOOLS}

async def dispatch(name, args):
    if name in _TOOL_MAP:         return await _base_dispatch(name, args)
    if name in WA_FILE_TOOL_MAP:  return await wa_file_dispatch(name, args)
    if name in _ADV_NAMES:        return await dispatch_advanced_feature(name, args)
    if name in OFFICE_TOOL_NAMES: return await office_dispatch(name, args)
    return await advanced_dispatch(name, args)


# ══════════════════════════════════════════════════════════════════
# API KEY LOADING
# ══════════════════════════════════════════════════════════════════
def _get_config_path_early():
    p = Path.home() / ".TABBU"
    p.mkdir(exist_ok=True)
    return p / "config.json"

def load_env():
    if os.getenv("GEMINI_API_KEY"):
        return
    try:
        new_cfg = _get_config_path_early()
        if new_cfg.exists():
            c = json.loads(new_cfg.read_text())
            key = c.get("api_key") or c.get("gemini_api_key", "")
            if key:
                os.environ["GEMINI_API_KEY"] = key
                return
        for old_name in [".TABBU_config.json", ".TITAN_config.json"]:
            p = Path.home() / old_name
            if p.exists():
                c = json.loads(p.read_text())
                key = c.get("gemini_api_key") or c.get("api_key", "")
                if key:
                    os.environ["GEMINI_API_KEY"] = key
                    try:
                        new_cfg.write_text(json.dumps({"api_key": key}, indent=2))
                    except: pass
                    return
        for name in [".env", ".env.local"]:
            ep = Path(__file__).parent / name
            if ep.exists():
                for line in ep.read_text().splitlines():
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        os.environ[k.strip()] = v.strip()
                if os.getenv("GEMINI_API_KEY"):
                    return
    except Exception as e:
        print(f"[ENV] {e}")

load_env()
_API_KEY = os.getenv("GEMINI_API_KEY", "")

_WS_URL = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"
)

VOICE_OPTIONS  = {"female": "Aoede", "male": "Charon"}
_CURRENT_VOICE = "female"

SESSION_RENEW_AFTER  = 1800  # 30 minutes — bada kiya
KEEPALIVE_INTERVAL   = 15  # 15s — safer interval
RESPONSE_TIMEOUT_SEC = 30  # 30s — long tasks ke liye


# ══════════════════════════════════════════════════════════════════
# CONVERSATION MEMORY
# ══════════════════════════════════════════════════════════════════
class ConversationMemory:
    MAX_TURNS = 50  # zyada history rakho
    def __init__(self):
        self._turns = []; self._lock = threading.Lock()
        # Disk se pichli memory load karo
        try:
            _mem_path = Path.home() / ".TABBU" / "ALIRA_session_memory.json"
            if _mem_path.exists():
                saved = json.loads(_mem_path.read_text(encoding="utf-8"))
                if isinstance(saved, list):
                    self._turns = saved[-self.MAX_TURNS:]
                    print(f"[MEMORY] Loaded {len(self._turns)} turns from disk")
        except Exception as e:
            print(f"[MEMORY] Load failed: {e}")
    def add(self, role, text):
        if not text.strip(): return
        with self._lock:
            self._turns.append({"role": role, "text": text.strip()})
            if len(self._turns) > self.MAX_TURNS:
                self._turns = self._turns[-self.MAX_TURNS:]
            # Persistent save — reconnect pe memory na jaye
            try:
                _mem_path = Path.home() / ".TABBU" / "ALIRA_session_memory.json"
                _mem_path.parent.mkdir(exist_ok=True)
                _mem_path.write_text(
                    json.dumps(self._turns, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
            except Exception:
                pass
    def get_context_prompt(self):
        with self._lock: turns = list(self._turns)
        if not turns: return ""
        lines = [
            "\n\n## IMPORTANT — CONVERSATION HISTORY (Session reconnected — memory preserved):",
            "## Continue EXACTLY from where we left off. Do NOT re-greet. Do NOT start over.",
            "## If a task was in progress, RESUME it immediately.",
            ""
        ]
        # Last 30 turns dikhao
        for t in turns[-30:]:
            prefix = "User" if t["role"] == "user" else "ALIRA"
            lines.append(f"{prefix}: {t['text']}")
        lines.append("")
        lines.append("[SESSION RESUMED — Continue naturally as if nothing happened. Do NOT say Hello/Hi again.]")
        return "\n".join(lines)
    def clear(self):
        with self._lock:
            self._turns.clear()
            try:
                _mem_path = Path.home() / ".TABBU" / "ALIRA_session_memory.json"
                if _mem_path.exists(): _mem_path.unlink()
            except Exception: pass

_conv_memory = ConversationMemory()

# ── Live voice model switch ───────────────────────────────────────
# key -> (UI label, model id, API version/endpoint)
LIVE_MODELS = {
    "3.1":        ("Gemini 3.1 Flash Live (Default)",        "gemini-3.1-flash-live-preview",                "v1beta"),
    "native":     ("2.5 Flash Native Audio",                 "gemini-2.5-flash-native-audio-latest",         "v1alpha"),
    "native-dec": ("2.5 Native Audio (Dec 2025 Preview)",    "gemini-2.5-flash-native-audio-preview-12-2025", "v1alpha"),
    "3.8":        ("Gemini 3.8 Live (naya)",                 "gemini-3.8-live",                              "v1beta"),
}
_LIVE_MODEL_KEY = "3.1"

def _ws_url():
    """Selected model ke endpoint (v1beta/v1alpha) ke hisaab se Live WebSocket URL."""
    ver = LIVE_MODELS[_LIVE_MODEL_KEY][2]
    return ("wss://generativelanguage.googleapis.com/ws/"
            f"google.ai.generativelanguage.{ver}.GenerativeService.BidiGenerateContent")

def _load_live_model_key():
    try:
        c = json.loads(_get_config_path_early().read_text())
        k = c.get("live_model", "3.1")
        return k if k in LIVE_MODELS else "3.1"
    except Exception:
        return "3.1"

def _save_live_model_key(key):
    try:
        path = _get_config_path_early()
        c = json.loads(path.read_text()) if path.exists() else {}
        c["live_model"] = key
        path.write_text(json.dumps(c, indent=2))
    except Exception as e:
        print(f"[CONFIG] Error saving live model: {e}")

_LIVE_MODEL_KEY = _load_live_model_key()

def _make_setup(prompt, include_history=False, handle=None):
    voice_name  = VOICE_OPTIONS.get(_CURRENT_VOICE, "Aoede")
    full_prompt = prompt.replace("TITAN", "ALIRA").replace("TABBU", "ALIRA")

    # ✅ FIX: Session continuity + tool usage instructions
    continuity_block = """

## CRITICAL SESSION RULES:
- Tum ALIRA ho — koi bhi session restart/refresh hone par BINA re-greet kiye continue karo
- Agar pehle koi task chal raha tha → usse IMMEDIATELY resume karo
- Memory/history agar di gayi hai → use follow karo exactly
- "Hello" ya "Hi" SIRF pehli baar user se milne pe bolna hai
- Session disconnect = normal technical event — user ko batane ki zarurat nahi
- Har kaam poora karo — beech mein mat chodo

## WEBSITE BUILDING — IMPORTANT:
- Agar user "website banao", "website bana", "create website", "build website" ya koi bhi website-related command de (kisi bhi language/phrasing mein)...
- IMMEDIATELY call the `build_website` tool with a clear description of what user asked for — this is a REAL tool, not optional, CALL IT.
- KABHI BHI `write_code` tool use mat karo website ke liye
- KABHI BHI khud HTML/CSS/JS file mat likho
- Tool call karne ke baad bolo: "ALIRA Coder start ho rahi hai — website ban rahi hai!"
- ALIRA Coder automatically background mein website build kar dega, aur ready hote hi khud deploy bhi ho jaayega
- Tumhara kaam sirf tool call karna aur user ko encourage karna hai, code likhna nahi
"""
    full_prompt = full_prompt + continuity_block
    try:
        _un = _prefs.user_name()
    except Exception:
        _un = ""
    if _un:
        full_prompt += (f"\n## USER KA NAAM:\n- User ka naam **{_un}** hai. Baat-cheet mein kabhi-kabhi (har line mein nahi) "
                        f"unhe {_un} naam se bulao — natural lage tabhi, pehli baar milne par greeting mein zaroor.\n")

    try:
        import ALIRA_lang as _lang
        full_prompt += _lang.prompt_block()
    except Exception as _e:
        print(f"[ALIRA] language block: {_e}")

    if include_history:
        ctx = _conv_memory.get_context_prompt()
        if ctx: full_prompt = full_prompt + ctx

    # ✅ Session fix: contextWindowCompression + sessionResumption — bina iske
    # audio+video (camera/screen) session ~2 min mein, audio-only ~10-15 min mein
    # server kaat deta hai. Ab server context compress karta hai aur resumption
    # handle se reconnect seamless hota hai (memory/context server side intact).
    resumption = {"handle": handle} if handle else {}
    return {
        "setup": {
            "contextWindowCompression": {"slidingWindow": {}},
            "sessionResumption": resumption,
            "inputAudioTranscription": {},
            "outputAudioTranscription": {},
            "model": "models/" + LIVE_MODELS[_LIVE_MODEL_KEY][1],
            "generation_config": {
                "temperature": 0.7,
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {"voice_name": voice_name}
                    }
                }
            },
            "system_instruction": {"parts": [{"text": full_prompt}]},
            "tools": [{"functionDeclarations": _ALL_TOOLS}] if _ALL_TOOLS else []
        }
    }


# ══════════════════════════════════════════════════════════════════
# NOTE: sidebar live camera preview no longer opens its own cv2.VideoCapture.
# ✅ FIX: previously LeftSidebar had its OWN CameraThread opening the webcam
# independently of CameraVisionManager (the real AI-vision feature in the
# right-panel "Vision" tab). Two separate cv2.VideoCapture handles fighting
# over the same physical webcam meant whichever opened second usually failed
# ("Koi camera nahi mila") — that was the root cause of "vision mode kaam
# nahi kar raha". Sidebar preview now just displays frames forwarded from
# the single shared CameraVisionManager (see LeftSidebar.update_camera_frame).
# ══════════════════════════════════════════════════════════════════


# ══════════════════════════════════════════════════════════════════
# GEMINI WORKER
# ══════════════════════════════════════════════════════════════════
class GeminiWorker(QObject):
    sig_status      = pyqtSignal(str, str)
    sig_user_live   = pyqtSignal(str)
    sig_TABBU_live   = pyqtSignal(str)
    sig_user_msg    = pyqtSignal(str)
    sig_TABBU_msg    = pyqtSignal(str)
    sig_sys_msg     = pyqtSignal(str)
    sig_error_msg   = pyqtSignal(str)
    sig_warn_msg    = pyqtSignal(str)
    sig_tool_call   = pyqtSignal(str)
    sig_tool_result = pyqtSignal(str)
    sig_connected   = pyqtSignal(bool)
    sig_energy      = pyqtSignal(float)
    sig_build_website = pyqtSignal(str)   # ✅ real tool-driven ALIRA Coder trigger
    sig_mic_state   = pyqtSignal(bool)    # tap mode: jawab ke baad mic auto-off
    sig_model_fallback = pyqtSignal(str)  # kharab model -> default par auto wapas

    SESSION_RENEW_AFTER = 3000  # 50 min — resumption handle se seamless
    KEEPALIVE_INTERVAL  = 15   # 15s keepalive
    MAX_RECONNECT_WAIT  = 8
    RECONNECT_BASE      = 1.5     # jaldi-jaldi reconnect nahi (pehle 0.5s)
    MIN_SESSION_GAP     = 3.0     # do connects ke beech kam se kam itna gap

    def __init__(self):
        super().__init__()
        self.mic_on        = True
        self.running       = True
        self._retry        = 0
        self._ws           = None
        self._loop         = None
        self._prompt       = TABBU_PROMPT
        self._mic_q        = None
        self._session_num  = 0
        self._greeted_once = False
        self._screen_q     = None
        self._resume_handle = None   # Gemini sessionResumption handle
        self.listen_mode    = "continuous"   # wake | tap | continuous | stop
        self._quick_fail    = 0           # lagataar jaldi-fail sessions (model fallback ke liye)
        self._bot_audio_until = 0.0       # ALIRA ki awaaz kab tak bajegi (echo gate)
        self._awake_until   = 0.0
        self._session_started = 0.0
        self._last_connect  = 0.0

    def set_mic(self, on):     self.mic_on = on
    def stop(self):            self.running = False
    def set_prompt(self, p):
        self._prompt = p.replace("TITAN", "ALIRA").replace("TABBU", "ALIRA")
        self._resume_handle = None   # naya prompt = fresh session
    def reset_greet(self):     self._greeted_once = False

    WAKE_WORDS = ("ALIRA", "mira", "maira", "meera", "miyra", "mayra", "मायरा", "मीरा", "मायरा")

    def set_listen_mode(self, mode):
        self.listen_mode = mode; self._awake_until = 0.0

    def info(self):
        """Settings page ke liye live session info."""
        age = int(time.monotonic() - self._session_started) if self._session_started and self._ws else 0
        return {"num": self._session_num, "uptime": f"{age // 60}m {age % 60}s" if self._ws else "disconnected",
                "resumable": bool(self._resume_handle), "model": LIVE_MODELS[_LIVE_MODEL_KEY][0],
                "endpoint": LIVE_MODELS[_LIVE_MODEL_KEY][2], "has_key": bool(_API_KEY)}
    def get_ws(self):          return self._ws
    def get_loop(self):        return self._loop

    def reconnect(self):
        if self._ws and self._loop:
            asyncio.run_coroutine_threadsafe(self._force_close(), self._loop)

    async def _force_close(self):
        try: await self._ws.close()
        except: pass

    def send_text(self, text):
        self._awake_until = time.time() + 30   # typed message = wake word
        if self._ws and self._loop:
            msg = {"clientContent": {
                "turns": [{"role": "user", "parts": [{"text": text}]}],
                "turnComplete": True
            }}
            asyncio.run_coroutine_threadsafe(self._safe_send(_enc(msg)), self._loop)

    async def _safe_send(self, data):
        try: await self._ws.send(data)
        except Exception as e:
            print(f"[ALIRA] send: {e}")
            self.sig_error_msg.emit(f"Send failed: {e}")

    def push_screen_frame(self, b64_jpeg: str):
        if self._screen_q:
            try: self._screen_q.put_nowait(b64_jpeg)
            except: pass

    def start_thread(self):
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try: loop.run_until_complete(self._main())
        finally: loop.close()

    async def _main(self):
        global _LIVE_MODEL_KEY
        import queue as Q
        self._mic_q    = Q.Queue(maxsize=600)
        self._screen_q = Q.Queue(maxsize=30)
        threading.Thread(target=self._mic_thread, daemon=True).start()
        first = True
        while self.running:
            try:
                await self._session(first)
                first = False
                self._retry = 0
                # ✅ Normal session end — drain stale frames
                await asyncio.sleep(0.2)
            except Exception as e:
                err_type = type(e).__name__
                err_msg  = str(e)
                print(f"[ALIRA] Session error: {err_type}: {err_msg}")
                self.sig_connected.emit(False)

                # ✅ Galat API key: baar-baar retry mat karo (rate-limit / spam)
                if "API key not valid" in err_msg or "API_KEY_INVALID" in err_msg:
                    self.sig_error_msg.emit("API key galat hai — Settings → API key badlo")
                    self.sig_status.emit("error", "BAD API KEY")
                    await asyncio.sleep(30)
                    continue

                # ✅ Model fallback: non-default model 2 baar lagataar jaldi (<25s) server
                # error de to khud default (3.1) par wapas — warna har ~25s reconnect hota.
                _age = time.monotonic() - self._session_started if self._session_started else 999
                if (_LIVE_MODEL_KEY != "3.1" and _age < 25 and
                        any(c in err_msg for c in ("1011", "1007", "1008", "1013"))):
                    self._quick_fail += 1
                elif _age >= 25:
                    self._quick_fail = 0
                if self._quick_fail >= 2:
                    bad = _LIVE_MODEL_KEY
                    _LIVE_MODEL_KEY = "3.1"; _save_live_model_key("3.1")
                    self._resume_handle = None; self._quick_fail = 0
                    self.sig_warn_msg.emit(f"{LIVE_MODELS[bad][0]} abhi server par stable nahi (error) — Gemini 3.1 par wapas aa gaye")
                    self.sig_model_fallback.emit("3.1")

                # ✅ CONTENT_TYPE_AUDIO — quick reconnect, no error shown to user
                is_audio_err = ("CONTENT_TYPE_AUDIO" in err_msg or
                                "1007" in err_msg or
                                "audio content type" in err_msg.lower())

                if is_audio_err:
                    print("[ALIRA] Audio type error — quick reconnect (1.5s)")
                    self.sig_status.emit("standby", "RECONNECTING...")
                    # Memory intact hai — sirf session restart karo
                    await asyncio.sleep(1.5)
                else:
                    # 1011/1006/1001/1000 = server-side/normal drop — resumption handle
                    # se chupchap reconnect, UI pe error spam nahi
                    quiet = any(c in err_msg for c in ("1011", "1006", "1001", "1000", "goAway"))
                    if not quiet:
                        self.sig_error_msg.emit(f"{err_type}: {err_msg[:80]}")
                    wait = min(self.RECONNECT_BASE * (2 ** min(self._retry, 4)), self.MAX_RECONNECT_WAIT)
                    self._retry += 1
                    self.sig_status.emit("standby", f"RECONNECTING ({self._retry})...")
                    await asyncio.sleep(wait)

            # Stale mic frames drain karo
            drained = 0
            while not self._mic_q.empty():
                try: self._mic_q.get_nowait(); drained += 1
                except: break
            if drained > 10: print(f"[ALIRA] Drained {drained} stale frames")

    # ══════════════════════════════════════════════════════════════
    # MIC THREAD — FIXED v2
    # Improvements over v1:
    #   ✅ Error spam throttle — same error baar baar nahi aayega
    #   ✅ Auto device fallback: configured → auto-detect → default → 0,1,2
    #   ✅ PortAudio re-init on crash (EXE pe hota hai)
    #   ✅ Smooth retry with backoff
    # ══════════════════════════════════════════════════════════════
    def _mic_thread(self):
        _last_err_t        = 0.0
        _err_cooldown      = 5.0   # seconds — same error max 1x per 5s
        _consecutive_fails = 0

        def _try_open_mic(device_idx):
            try:
                stream = sd.InputStream(
                    device=device_idx,
                    samplerate=MIC_RATE,
                    channels=1,
                    dtype="int16",
                    blocksize=FRAMES,
                    latency="low"
                )
                return stream
            except Exception:
                return None

        def _get_device_fallback_list():
            candidates = []
            if _MIC_DEVICE is not None:
                candidates.append(_MIC_DEVICE)
            best = _get_best_mic_device()
            if best is not None and best not in candidates:
                candidates.append(best)
            try:
                default_mic = sd.default.device[0]
                if default_mic is not None and default_mic not in candidates:
                    candidates.append(default_mic)
            except Exception:
                pass
            try:
                devices = sd.query_devices()
                for i, d in enumerate(devices):
                    if d["max_input_channels"] > 0 and i not in candidates:
                        candidates.append(i)
                        if len(candidates) >= 6:
                            break
            except Exception:
                pass
            return candidates

        while self.running:
            # PortAudio re-init — EXE pe crash fix
            try:
                sd._terminate()
                sd._initialize()
            except Exception:
                pass

            opened_stream  = None
            used_device    = None

            for dev_idx in _get_device_fallback_list():
                stream = _try_open_mic(dev_idx)
                if stream is not None:
                    opened_stream      = stream
                    used_device        = dev_idx
                    _consecutive_fails = 0
                    break

            if opened_stream is None:
                _consecutive_fails += 1
                now = time.time()
                if now - _last_err_t > _err_cooldown:
                    _last_err_t = now
                    self.sig_error_msg.emit("Mic: Koi microphone nahi mila — connect karo")
                    print(f"[MIC] No mic found (attempt {_consecutive_fails})")
                wait = min(2.0 * _consecutive_fails, 10.0)
                time.sleep(wait)
                continue

            try:
                dev_name = sd.query_devices(used_device)["name"]
            except Exception:
                dev_name = f"Device {used_device}"
            print(f"[MIC] Started — [{used_device}] {dev_name}")

            last_err_msg = ""

            try:
                with opened_stream as mic:
                    while self.running:
                        try:
                            pcm, _ = mic.read(FRAMES)
                        except Exception as read_err:
                            now     = time.time()
                            err_str = str(read_err)
                            if now - _last_err_t > _err_cooldown or err_str != last_err_msg:
                                _last_err_t  = now
                                last_err_msg = err_str
                                self.sig_error_msg.emit(f"Mic error: {err_str[:50]}")
                                print(f"[MIC] Read error: {err_str}")
                            break  # re-open with fallback

                        pcm_float = pcm.astype(np.float32) * MIC_GAIN
                        pcm_float = np.clip(pcm_float, -32768, 32767)
                        pcm       = pcm_float.astype(np.int16)

                        if not self.mic_on:
                            time.sleep(0.02)
                            continue

                        rms = float(np.sqrt(np.mean(pcm_float ** 2)))
                        try:   self.sig_energy.emit(rms)
                        except: pass
                        try:   self._mic_q.put_nowait((pcm.tobytes(), rms))
                        except: pass

            except Exception as outer_err:
                now     = time.time()
                err_str = str(outer_err)
                if now - _last_err_t > _err_cooldown:
                    _last_err_t = now
                    self.sig_error_msg.emit(f"Mic stream: {err_str[:50]}")
                    print(f"[MIC] Stream crash: {err_str}")

            if self.running:
                time.sleep(1.0)

    async def _session(self, first: bool = False):
        # ✅ Do connects ke beech minimum gap — tight reconnect loop nahi
        gap = time.monotonic() - self._last_connect
        if self._last_connect and gap < self.MIN_SESSION_GAP:
            await asyncio.sleep(self.MIN_SESSION_GAP - gap)
        self._last_connect = time.monotonic()
        session_start = time.monotonic()
        self._session_started = session_start
        self._session_num += 1
        is_reconnect  = self._session_num > 1
        resumed_with  = self._resume_handle
        go_away       = {"flag": False}

        async with websockets.connect(
            f"{_ws_url()}?key={_API_KEY}",
            max_size=None, ping_interval=None, ping_timeout=None,
            close_timeout=10, compression=None, open_timeout=30,
        ) as ws:
            self._ws = ws
            self.sig_connected.emit(True)
            self._retry = 0

            # ✅ FIX: Hamesha history include karo agar koi turns hain
            _has_history = len(_conv_memory._turns) > 0
            await ws.send(_enc(_make_setup(self._prompt, include_history=_has_history and not resumed_with,
                                           handle=resumed_with)))

            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=20)
                msg = json.loads(raw)
                if "setupComplete" not in msg and "setup_complete" not in msg:
                    print(f"[ALIRA] Unexpected first msg: {str(raw)[:120]}")
            except asyncio.TimeoutError:
                raise ConnectionError("Setup ack timeout — check API key/network")
            except Exception:
                if resumed_with:           # handle expire/invalid — next try fresh session
                    print("[ALIRA] Resume handle rejected — fresh session next")
                    self._resume_handle = None
                raise

            self.sig_status.emit("standby", "STANDBY")
            if resumed_with:
                print("[ALIRA] Session resumed via handle (seamless) ✅")
            elif not is_reconnect and not _has_history:
                self.sig_sys_msg.emit("⚡  ALIRA ONLINE")
            elif _has_history:
                self.sig_sys_msg.emit("🔄 Session resumed — memory intact ✅")
            else:
                self.sig_sys_msg.emit("⚡  ALIRA ONLINE")

            import queue as Q
            _aq   = Q.Queue(maxsize=600)
            _stop = threading.Event()

            if resumed_with:
                self._greeted_once = True   # context server-side intact — na greet, na resume msg
            elif not self._greeted_once and not _has_history:
                self._greeted_once = True
                async def _send_greet():
                    await asyncio.sleep(1.0)
                    mode_is_ALIRA = ("ALIRA" in self._prompt or "warm" in self._prompt.lower())
                    g = (
                        "Greet me warmly, say your name is ALIRA. Ask how I am. Friendly, short."
                        if mode_is_ALIRA else
                        "Greet professionally as ALIRA. Ask how you can help. Brief."
                    )
                    try:
                        await ws.send(_enc({"clientContent": {
                            "turns": [{"role": "user", "parts": [{"text": g}]}],
                            "turnComplete": True
                        }}))
                    except Exception as e:
                        print(f"[ALIRA] greet send failed: {e}")
                asyncio.ensure_future(_send_greet())
            elif _has_history and is_reconnect:
                # ✅ Reconnect pe seedha resume karo — no re-greet
                self._greeted_once = True
                async def _send_resume():
                    await asyncio.sleep(0.8)
                    # Pichla kaam kya tha — batao ALIRA ko
                    last_turns = _conv_memory._turns[-4:]
                    last_ctx = " | ".join(
                        f"{'User' if t['role']=='user' else 'ALIRA'}: {t['text'][:60]}"
                        for t in last_turns
                    )
                    resume_msg = (
                        f"[SYSTEM: Session reconnected. Memory intact. "
                        f"Last context: {last_ctx}. "
                        f"Resume naturally from where we left off. "
                        f"DO NOT re-greet. DO NOT say hello again. "
                        f"If any task was in progress, continue it immediately.]"
                    )
                    try:
                        await ws.send(_enc({"clientContent": {
                            "turns": [{"role": "user", "parts": [{"text": resume_msg}]}],
                            "turnComplete": True
                        }}))
                        print("[ALIRA] Resume context injected ✅")
                    except Exception as e:
                        print(f"[ALIRA] resume inject failed: {e}")
                asyncio.ensure_future(_send_resume())

            def _play():
                BUF = int(SPK_RATE * AUDIO_BUF_MS / 1000)
                buf = np.array([], dtype=np.float32)
                st  = sd.OutputStream(device=_SPK_DEVICE, samplerate=SPK_RATE, channels=1,
                                      dtype="float32", blocksize=BUF, latency="low")
                st.start()
                while not _stop.is_set():
                    try:
                        chunk = _aq.get(timeout=0.08)
                        if chunk is None:
                            if len(buf):
                                pad = BUF - (len(buf) % BUF or BUF)
                                if pad: buf = np.concatenate([buf, np.zeros(pad, np.float32)])
                                st.write(buf); buf = np.array([], dtype=np.float32)
                            continue
                        buf = np.concatenate([buf, chunk])
                        while len(buf) >= BUF:
                            st.write(buf[:BUF]); buf = buf[BUF:]
                    except Q.Empty:
                        if len(buf) >= BUF:
                            st.write(buf[:BUF]); buf = buf[BUF:]
                st.stop(); st.close()

            pt = threading.Thread(target=_play, daemon=True)
            pt.start()

            async def send():
                was_live      = False
                silent        = 0
                stream_ended  = False
                frames_sent   = 0   # kitne audio frames bheje gaye
                speech_confirm = 0  # consecutive speech frames — debounce ke liye
                preroll = collections.deque(maxlen=5)   # baat shuru hone se pehle ke ~100ms frames

                def _audio_msg(pb):
                    return _enc({"realtimeInput": {"audio": {
                        "mimeType": "audio/pcm;rate=16000", "data": base64.b64encode(pb).decode()}}})

                while self.running:
                    # Screen frames bhejo
                    while self._screen_q and not self._screen_q.empty():
                        try:
                            b64_frame  = self._screen_q.get_nowait()
                            screen_msg = {"realtimeInput": {"video": {"mimeType": "image/jpeg", "data": b64_frame}}}
                            try:
                                await ws.send(_enc(screen_msg))
                            except websockets.exceptions.ConnectionClosed:
                                return
                            except Exception as _ve:
                                print(f"[ALIRA] Screen frame skip: {_ve}")
                                break
                        except: break

                    try: pcm_bytes, rms = self._mic_q.get_nowait()
                    except: await asyncio.sleep(0.005); continue

                    if not self.mic_on:
                        was_live = False; silent = 0; stream_ended = False; frames_sent = 0; continue

                    # ✅ Echo gate: ALIRA bol rahi ho to speaker ki awaaz mic mein aati hai —
                    # tab sirf bahut tez awaaz (user ka barge-in) ko speech maano.
                    _bot_talking = time.time() < self._bot_audio_until + 0.35
                    is_speech = rms >= (SILENCE_RMS * (1.8 if _bot_talking else 1.0))
                    preroll.append(pcm_bytes)

                    if is_speech:
                        silent = 0; stream_ended = False
                        speech_confirm += 1   # consecutive speech frames count

                        # ✅ DEBOUNCE: min 3 consecutive speech frames ke baad hi
                        # was_live=True karo — single RMS spike se trigger nahi hoga
                        if speech_confirm >= 2 and not was_live:
                            was_live    = True
                            frames_sent = 0
                            self.sig_status.emit("listening", "LISTENING")
                            # ✅ baat ke shuruaati frames (debounce mein kat rahe the) pehle bhejo
                            try:
                                for _pb in list(preroll)[:-1]:
                                    await ws.send(_audio_msg(_pb)); frames_sent += 1
                            except websockets.exceptions.ConnectionClosed:
                                return
                            except Exception:
                                pass
                        elif speech_confirm < 2:
                            continue   # abhi confirm nahi hua — audio mat bhejo

                        if was_live:
                            try:
                                await ws.send(_enc({"realtimeInput": {"audio": {
                                    "mimeType": "audio/pcm;rate=16000",
                                    "data": base64.b64encode(pcm_bytes).decode()
                                }}}))
                                frames_sent += 1
                            except websockets.exceptions.ConnectionClosed:
                                return
                            except Exception as _ae:
                                if "CONTENT_TYPE_AUDIO" in str(_ae):
                                    print("[ALIRA] Audio chunk skipped — model busy")
                                    await asyncio.sleep(0.2)
                                    continue
                                return
                    else:
                        speech_confirm = 0   # silence = speech streak reset
                        if was_live:
                            silent += 1
                            # ✅ baat ke beech ki halki awaaz (soft consonants/pauses) bhi bhejo —
                            # pehle ye frames kat jaate the aur ALIRA ko shabd adhoore sunte the.
                            if not stream_ended:
                                try: await ws.send(_audio_msg(pcm_bytes))
                                except websockets.exceptions.ConnectionClosed: return
                                except Exception: pass
                            if silent >= SILENCE_FRAMES and not stream_ended:
                                was_live     = False
                                stream_ended = True

                                # ✅ KEY FIX: audioStreamEnd SIRF tab bhejo jab kuch audio
                                # actually bheja gaya ho (min 5 frames = ~100ms of real speech)
                                # Warna server ko empty stream milti hai → 1007 error
                                MIN_FRAMES_FOR_END = 5
                                if frames_sent < MIN_FRAMES_FOR_END:
                                    print(f"[ALIRA] audioStreamEnd SKIPPED — sirf {frames_sent} frames bheje (noise, not speech)")
                                    frames_sent = 0
                                    continue   # audioStreamEnd mat bhejo — false trigger tha

                                self.sig_status.emit("thinking", "THINKING...")
                                print(f"[ALIRA] audioStreamEnd — {frames_sent} frames, silence {silent}, rms={rms:.1f}")
                                frames_sent = 0
                                try:
                                    await ws.send(_enc({"realtimeInput": {"audioStreamEnd": True}}))
                                except websockets.exceptions.ConnectionClosed:
                                    return
                                except Exception as _se:
                                    if "CONTENT_TYPE_AUDIO" in str(_se):
                                        print("[ALIRA] audioStreamEnd skipped — model busy")
                                        stream_ended = True
                                    else:
                                        return

            async def _handle_tool_call(call):
                # ✅ Tool dispatch apne independent task mein — recv() loop kabhi
                # block nahi hota, isliye WS ping/recv aur mic-send pipeline zinda
                # rehte hain lambe/slow tool calls (website build, file I/O, etc.)
                # ke dauraan bhi. Yehi pehle "tool call ke turant baad reconnect"
                # bug ka root cause tha.
                n = call["name"]; a = call.get("args", {})
                self.sig_tool_call.emit(f"⚙  {n}")
                self.sig_status.emit("thinking", "TOOL: " + n[:14])
                if n == "build_website":
                    # ✅ GUI-owned (ALIRACoderOverlay is a QDialog) — hand off via
                    # signal instead of dispatch() so it runs on the Qt thread.
                    desc = str(a.get("description") or "").strip() or "Build a website."
                    self.sig_build_website.emit(desc)
                    res = "ALIRA Coder started in the background — building the website now."
                else:
                    try:
                        res = await dispatch(n, a)
                        if _HAS_ADV: TABBUMemory.add_note(f"T:{n}", str(res)[:200], ["tool"])
                    except Exception as e:
                        res = f"❌ {e}"
                        self.sig_error_msg.emit(f"Tool {n} failed: {str(e)[:60]}")
                self.sig_tool_result.emit(f"✓ {n}: {str(res)[:100]}")
                try:
                    await ws.send(_enc({"toolResponse": {"functionResponses": [{
                        "id": call["id"], "name": n,
                        "response": {"result": str(res)}
                    }]}}))
                except websockets.exceptions.ConnectionClosed:
                    pass  # recv()/keepalive already picking up the closed connection

            async def recv():
                TABBU_buf = ""; user_buf = ""; speaking = False

                def _allowed():
                    # Wake Word mode: sirf tab bolo jab user ne 'ALIRA' kaha (30s conversation window)
                    if self.listen_mode != "wake": return True
                    low = user_buf.lower()
                    if any(w in low for w in self.WAKE_WORDS): self._awake_until = time.time() + 30
                    return time.time() < self._awake_until
                while self.running:
                    # ✅ recv() session renewal check removed — keepalive handles it
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=90.0)  # 90s — long tasks
                        msg = json.loads(raw)
                    except asyncio.TimeoutError:
                        # 90s mein koi response nahi — yeh normal hai for long tasks
                        # Session still valid hai — just reset recv loop
                        print("[ALIRA] recv 90s timeout — session still alive, continuing")
                        continue  # return mat karo — session end mat karo
                    except websockets.exceptions.ConnectionClosed as e:
                        err_str = str(e)
                        # ✅ FIX: CONTENT_TYPE_AUDIO = model busy tha, reconnect karo
                        if "CONTENT_TYPE_AUDIO" in err_str or "1007" in err_str:
                            print(f"[ALIRA] Audio type error (1007) — graceful reconnect")
                            self.sig_warn_msg.emit(
                                "Session refresh ho rahi hai — task continue karega..."
                            )
                        else:
                            print(f"[ALIRA] Connection closed: {e}")
                            if not go_away["flag"] and getattr(e, "code", None) not in (1000, 1001, 1011):
                                self.sig_error_msg.emit(f"Connection closed: {e.code}")
                        # ✅ FIX: raise (not return) — _main() ka unified backoff/reconnect
                        # logic handle karega. Silent return se pehle tight 0.2s loop
                        # ban jaata tha (koi exception hi nahi milti thi _main() ko).
                        raise
                    except Exception as e:
                        print(f"[recv] {e}")
                        self.sig_error_msg.emit(f"Receive error: {str(e)[:60]}")
                        continue

                    # ✅ FIX: tool call ko background task mein chalao — recv() loop
                    # ko block mat karo. Pehle `await dispatch(...)` seedha recv() ke
                    # andar tha, isliye jab tak tool complete na ho, ws.recv() dobara
                    # call hi nahi hota tha — keepalive/mic bhi effectively stall ho
                    # jaate the, aur server se koi close/ping miss hone par turant
                    # "reconnecting" dikhta tha. Ab tool apne alag task mein chalta hai.
                    for call in msg.get("toolCall", {}).get("functionCalls", []):
                        asyncio.ensure_future(_handle_tool_call(call))

                    # ✅ Resumption handle — reconnect pe isi se session continue hota hai
                    sru = msg.get("sessionResumptionUpdate")
                    if sru and sru.get("resumable") and sru.get("newHandle"):
                        self._resume_handle = sru["newHandle"]

                    # ✅ goAway: server batata hai ki connection jald band hoga (~10 min
                    # lifetime). Handle ke saath turant clean reconnect — user ko pata nahi chalta.
                    if "goAway" in msg and not go_away["flag"]:
                        go_away["flag"] = True
                        print(f"[ALIRA] goAway: {msg['goAway']} — seamless reconnect")
                        async def _graceful():
                            await asyncio.sleep(2.0)
                            try: await ws.close(1000, "goAway reconnect")
                            except Exception: pass
                        asyncio.ensure_future(_graceful())

                    sc = msg.get("serverContent", {})
                    if not sc: continue

                    if sc.get("interrupted"):
                        self._bot_audio_until = 0.0
                        self.sig_status.emit("listening", "LISTENING")
                        TABBU_buf = ""; speaking = False
                        while not _aq.empty():
                            try: _aq.get_nowait()
                            except: break

                    for part in sc.get("modelTurn", {}).get("parts", []):
                        d = part.get("inlineData")
                        if d and d.get("mimeType","").startswith("audio/pcm"):
                            if not _allowed(): continue     # wake word nahi suna — chup raho
                            if not speaking:
                                speaking = True
                                self.sig_status.emit("speaking", "SPEAKING")
                            raw_b = base64.b64decode(d["data"])
                            chunk = np.frombuffer(raw_b, dtype=np.int16).astype(np.float32) / 32768.0
                            self._bot_audio_until = max(self._bot_audio_until, time.time()) + len(chunk) / SPK_RATE
                            try: _aq.put_nowait(chunk)
                            except: pass

                    # ✅ FIX: sahi keys outputTranscription/inputTranscription ({"text": ..});
                    # purane outputTranscript/inputTranscript bhi support (older models)
                    ot = (sc.get("outputTranscription") or {}).get("text", "") or sc.get("outputTranscript", "")
                    if ot and _allowed():
                        TABBU_buf += ot; self.sig_TABBU_live.emit(TABBU_buf)

                    it = (sc.get("inputTranscription") or {}).get("text", "") or sc.get("inputTranscript", "")
                    if it:
                        user_buf += it; self.sig_user_live.emit(user_buf)

                    if sc.get("turnComplete") or sc.get("generationComplete"):
                        _aq.put(None)
                        if TABBU_buf.strip():
                            self.sig_TABBU_msg.emit(TABBU_buf.strip())
                            _conv_memory.add("TABBU", TABBU_buf.strip())
                            asyncio.create_task(memory_save("ALIRA", TABBU_buf.strip()))
                            if _HAS_ADV: TABBUMemory.add_conversation("ALIRA", TABBU_buf.strip())
                        TABBU_buf = ""
                        if user_buf.strip():
                            self.sig_user_msg.emit(user_buf.strip())
                            _conv_memory.add("user", user_buf.strip())
                            asyncio.create_task(memory_save("user", user_buf.strip()))
                            if _HAS_ADV: TABBUMemory.add_conversation("user", user_buf.strip())
                        user_buf = ""; speaking = False
                        if self.listen_mode == "tap":          # tap mode: jawab ke baad mic auto-off
                            self.mic_on = False; self.sig_mic_state.emit(False)
                        self.sig_status.emit("standby", "STANDBY")
                        self.sig_TABBU_live.emit(""); self.sig_user_live.emit("")

            async def keepalive():
                last_kp = time.monotonic()
                # ✅ FIX: Audio keepalive BILKUL NAHI — 1007 ka main cause tha
                # WebSocket naturally alive rehta hai — sirf session renewal check karo
                while self.running:
                    await asyncio.sleep(5)
                    now = time.monotonic(); age = now - session_start
                    if age >= self.SESSION_RENEW_AFTER:
                        print(f"[ALIRA] Session renewal at {age:.0f}s")
                        try: await ws.close(1000, "Session renewal")
                        except: pass
                        return
                    # ✅ WebSocket connection alive hai ya nahi — test with ws.ping()
                    # (yeh WebSocket protocol ping hai, audio nahi)
                    if now - last_kp >= self.KEEPALIVE_INTERVAL:
                        try:
                            await ws.ping()   # Pure WS ping — koi audio nahi
                            last_kp = now
                            print(f"[ALIRA] ♡ ping age={age:.0f}s")
                        except websockets.exceptions.ConnectionClosed:
                            self.sig_error_msg.emit("Connection lost — reconnecting")
                            # ✅ FIX: raise, taaki _main() ka backoff logic chale —
                            # silent return se tight reconnect loop ban jaata tha
                            raise
                        except Exception as e:
                            # ping() unsupported? ignore silently — connection is still alive
                            last_kp = now
                            print(f"[ALIRA] ♡ ping skip ({e}) age={age:.0f}s")

            try:
                tasks = [
                    asyncio.ensure_future(send()),
                    asyncio.ensure_future(recv()),
                    asyncio.ensure_future(keepalive()),
                ]
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for t in pending:
                    t.cancel()
                    try: await t
                    except (asyncio.CancelledError, Exception): pass
                # ✅ FIX: agar koi task exception ke saath khatam hua (jaise
                # recv() ka ConnectionClosed), usse yahan se _main() tak propagate
                # karo. Pehle yeh exception yahin dab jaati thi, is liye _session()
                # "normal" return karta tha aur _main() sirf 0.2s sleep karke turant
                # dobara connect karta tha — koi backoff/status update ke bina, jo
                # "bar bar 1 sec ke andar reconnect" wala symptom tha.
                for t in done:
                    exc = t.exception()
                    if exc:
                        raise exc
            finally:
                _stop.set(); _aq.put(None); pt.join(timeout=2.0)
                self._ws = None
                age = time.monotonic() - session_start
                print(f"[ALIRA] Session #{self._session_num} ended after {age:.1f}s")


# ══════════════════════════════════════════════════════════════════
# API KEY DIALOG
# ══════════════════════════════════════════════════════════════════
def _get_config_path():
    config_dir = Path.home() / ".TABBU"
    config_dir.mkdir(exist_ok=True)
    return config_dir / "config.json"

def _load_api_key():
    try:
        config_path = _get_config_path()
        if config_path.exists():
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config.get('api_key', '')
    except Exception as e:
        print(f"[CONFIG] Error loading API key: {e}")
    return ''

def _save_config(api_key):
    try:
        config_path = _get_config_path()
        config = {}
        try:
            config = json.loads(config_path.read_text()) if config_path.exists() else {}
        except Exception:
            config = {}
        config.update({'api_key': api_key, 'gemini_api_key': api_key})
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        os.environ["GEMINI_API_KEY"] = api_key
        print(f"[CONFIG] Saved config to {config_path}")
    except Exception as e:
        print(f"[CONFIG] Error saving config: {e}")

# ══════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ══════════════════════════════════════════════════════════════════
_startup_hook = None      # Main_normal / __main__ splash ko progress dene ke liye set karta hai (callable(pct))


def _sp(pct):
    """Startup progress (window banne ke dauran) — splash ho to bar aage badhta hai."""
    h = _startup_hook
    if h:
        try:
            h(pct)
        except Exception:
            pass


class TABBUWindow(QMainWindow):
    def __init__(self, api_key=None):
        super().__init__()
        global _API_KEY
        _API_KEY = api_key or os.getenv("GEMINI_API_KEY", "")
        self.setWindowTitle("ALIRA — AI Voice Assistant v8.0 | ALIRA Coder")
        self.setWindowFlags(Qt.Window | Qt.FramelessWindowHint)
        # FIX: window kabhi screen se bada nahi — available area (taskbar chhod kar) ke andar fit
        try:
            _av = QApplication.primaryScreen().availableGeometry()
            _w, _h = min(1440, int(_av.width() * 0.96)), min(880, int(_av.height() * 0.96))
            self.setMinimumSize(min(1180, _av.width()), min(720, _av.height()))
            self.resize(_w, _h)
            self.move(_av.x() + (_av.width() - _w) // 2, _av.y() + (_av.height() - _h) // 2)
        except Exception:
            self.setMinimumSize(1180, 720); self.resize(1440, 880)
        self._mode   = "ALIRA"
        self._mic_on = True
        self._api_key = api_key
        _sp(72)
        self._build_ui()
        _sp(91)
        self._init_cam_vision()
        _sp(92)
        self._init_screenshare()
        _sp(93)
        self._init_edge_glow()
        _sp(94)
        self._init_float_orb()
        self._init_user_name()
        self._init_language()
        _sp(95)
        self._start_worker()
        _sp(97)

    # ── EDGE GLOW ────────────────────────────────────────────────
    def _init_edge_glow(self):
        self._voice_state = "standby"
        self._screenread_until = 0.0
        self._ss_first_frame_pending = False
        self._edge = None
        if _HAS_EDGE:
            try:
                self._edge = EdgeGlow()
                self._edge.set_enabled(_load_edge_pref())
            except Exception as e:
                print(f"[ALIRA] Edge glow init: {e}")
        self._bus.edge_glow.connect(self._on_edge_glow_toggle)

    def _edge_mode(self):
        """Priority: error > screen-read > speaking > thinking > listening > screenshare > camera."""
        vs = getattr(self, '_voice_state', 'standby')
        if vs == "error":
            return "error"
        if time.time() < getattr(self, '_screenread_until', 0.0):
            return "screenread"
        if vs in ("speaking", "thinking", "listening"):
            return vs
        if _HAS_SCREEN_SHARE and self._ss_mgr.is_active:
            return "screenshare"
        if _HAS_CAM_VISION and hasattr(self, '_cv_mgr') and self._cv_mgr.is_active:
            return "camera"
        return None

    def _update_edge_glow(self):
        if getattr(self, '_edge', None):
            self._edge.set_mode(self._edge_mode())

    def _on_edge_glow_toggle(self, on: bool):
        _save_edge_pref(on)
        self._bus.state["edge_glow"] = bool(on)
        if getattr(self, '_edge', None):
            self._edge.set_enabled(on)
            self._update_edge_glow()

    # ── FLOATING ORB / BACKGROUND MODE / GUARDIAN ────────────────
    def _init_float_orb(self):
        self._orb_mode = False
        self._float_orb = self._guardian = self._tray = None
        self._preview_token = 0
        b = self._bus
        if _HAS_ORB:
            try:
                self._float_orb = FloatingOrb()
                self._float_orb.action.connect(self._on_orb_action)
                self._guardian = ScreenGuardian(busy_fn=self._guardian_busy, api_key_fn=lambda: self._api_key)
                self._guardian.sig_alert.connect(self._on_guardian_alert)
                self._init_tray()
            except Exception as e:
                print(f"[ALIRA] Floating orb init: {e}")
                self._float_orb = None
        b.orb_on_minimize.connect(lambda on: (_prefs.set_("orb_on_minimize", bool(on)), b.state.__setitem__("orb_on_minimize", bool(on))))
        b.orb_float_size.connect(self._on_orb_float_size)
        b.orb_ui_scale.connect(self._on_orb_ui_scale)
        b.autostart.connect(self._on_autostart_toggle)
        b.guardian.connect(self._on_guardian_toggle)
        b.guardian_interval.connect(lambda v: (_prefs.set_("guardian_interval", int(v)), b.state.__setitem__("guardian_interval", int(v))))
        b.orb_preview.connect(lambda: self._preview_orb(6000))
        self._apply_orb_ui_scale(int(_prefs.get("orb_ui_scale", 100)))
        if self._guardian and _prefs.get("guardian", False):
            self._guardian.start()

    def _init_tray(self):
        from PyQt5.QtWidgets import QSystemTrayIcon, QMenu
        from PyQt5.QtGui import QIcon
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        ico = Path(__file__).resolve().parent / "TABBU_icon.ico"
        t = QSystemTrayIcon(QIcon(str(ico)) if ico.exists() else self.windowIcon(), self)
        t.setToolTip("ALIRA — AI Assistant")
        m = QMenu()
        m.addAction("ALIRA kholo", lambda: self._on_orb_action("open"))
        m.addAction("Mic on / off", lambda: self._on_orb_action("mic"))
        m.addAction("Screen Guardian on / off", lambda: self._on_orb_action("guardian"))
        m.addSeparator()
        m.addAction("ALIRA band karo", lambda: self._on_orb_action("quit"))
        t.setContextMenu(m)
        t.activated.connect(lambda r: self._on_orb_action("open") if r in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick) else None)
        t.show()
        self._tray, self._tray_menu = t, m

    def _enter_orb_mode(self):
        if not self._float_orb or self._orb_mode:
            return
        self._orb_mode = True
        self._was_maximized = bool(self.windowState() & Qt.WindowMaximized)
        self._saved_geom = self.normalGeometry()          # restore par wahi size/jagah
        self.hide()
        self._float_orb.show_orb()
        self._sync_orb_menu()

    def _show_main(self):
        """Orb/tray/dusri copy se: ALIRA ki main window wapas lao."""
        self._orb_mode = False
        if self._float_orb:
            self._float_orb.hide_orb()
        self.setWindowState(self.windowState() & ~Qt.WindowMinimized)
        if getattr(self, "_was_maximized", False):
            self.showMaximized()
        else:
            self.showNormal()
            g = getattr(self, "_saved_geom", None)
            if g is not None and g.width() >= self.minimumWidth() and g.height() >= self.minimumHeight():
                self.setGeometry(g)
        self.raise_()
        self.activateWindow()
        try:
            import ctypes
            hwnd = int(self.winId())
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except Exception:
            pass

    def start_in_background(self):
        """Autostart / --background: window nahi dikhegi, sirf orb + tray."""
        self._enter_orb_mode()
        if not self._float_orb:
            self.show()

    def changeEvent(self, e):
        if (e.type() == QEvent.WindowStateChange and self.isMinimized() and not getattr(self, "_orb_mode", False)
                and getattr(self, "_float_orb", None) and _prefs.get("orb_on_minimize", True)):
            QTimer.singleShot(0, self._enter_orb_mode)
        super().changeEvent(e)

    def _preview_orb(self, ms=5000):
        """Settings se: orb abhi dikhao (size/jagah set karne ke liye)."""
        if not self._float_orb or self._orb_mode:
            return
        self._preview_token += 1
        tok = self._preview_token
        self._float_orb.show_orb()
        self._sync_orb_menu()
        QTimer.singleShot(ms, lambda: (self._float_orb.hide_orb() if (tok == self._preview_token and not self._orb_mode) else None))

    def _on_orb_action(self, key):
        if key == "open":
            self._show_main()
        elif key == "settings":
            self._show_main(); self._show_page("settings")
        elif key == "mic":
            self._on_mic_toggle()
        elif key == "guardian":
            self._on_guardian_toggle(not (self._guardian and self._guardian.is_running))
        elif key == "screenshare":
            self._on_screenshare()
        elif key == "camera":
            self._on_camera()
        elif key == "quit":
            self._quit_app()
        QTimer.singleShot(250, self._sync_orb_menu)

    def _quit_app(self):
        try:
            self.close()
        except Exception:
            pass
        QApplication.instance().quit()

    def _sync_orb_menu(self):
        if not getattr(self, "_float_orb", None):
            return
        g = bool(self._guardian and self._guardian.is_running)
        ss = bool(_HAS_SCREEN_SHARE and self._ss_mgr.is_active)
        cam = bool(_HAS_CAM_VISION and hasattr(self, "_cv_mgr") and self._cv_mgr.is_active)
        self._float_orb.set_menu_state(mic=self._mic_on, guardian=g, screenshare=ss, camera=cam)
        lab = {"listening": "Listening", "speaking": "Speaking", "thinking": "Thinking", "error": "Error"}.get(
            getattr(self, "_voice_state", "standby"), "Ready")
        self._float_orb._menu.set_state_text("Mic off" if not self._mic_on else lab, "#9C99A4" if not self._mic_on else None)
        self._bus.state["guardian"] = g
        self._bus.state["autostart"] = bool(_HAS_ORB and _autostart.is_enabled())

    def _on_orb_float_size(self, v):
        self._bus.state["orb_float_size"] = int(v)
        if self._float_orb:
            self._float_orb.set_size(int(v))
            if not self._orb_mode:
                self._preview_orb(4000)

    def _on_orb_ui_scale(self, v):
        self._bus.state["orb_ui_scale"] = int(v)
        _prefs.set_("orb_ui_scale", int(v))
        self._apply_orb_ui_scale(int(v))

    def _apply_orb_ui_scale(self, pct):
        f = max(0.5, min(1.5, pct / 100.0))
        try:
            self._orb.set_orb_scale(f)
            self._p_voice.set_orb_size(int(230 * f))
        except Exception as e:
            print(f"[ALIRA] orb scale: {e}")

    def _on_autostart_toggle(self, on):
        if not _HAS_ORB:
            return
        ok = _autostart.enable(True) if on else _autostart.disable()
        if ok:
            self._chat.add_sys("🚀 ALIRA ab Windows start par khud chalu hogi (orb ke saath)" if on else "ALIRA ka Windows startup band kiya")
        else:
            self._chat.add_error("Startup setting badal nahi paayi")
        self._bus.state["autostart"] = _autostart.is_enabled()

    def _on_guardian_toggle(self, on):
        if not self._guardian:
            return
        _prefs.set_("guardian", bool(on))
        self._bus.state["guardian"] = bool(on)
        if on:
            self._guardian.start()
            self._chat.add_sys("👁 Screen Guardian ON — ALIRA screen dekhti rahegi aur kuch galat dikhe to batayegi")
        else:
            self._guardian.stop()
            self._chat.add_sys("👁 Screen Guardian OFF")
        self._sync_orb_menu()

    def _guardian_busy(self):
        return bool((_HAS_SCREEN_SHARE and self._ss_mgr.is_active)
                    or getattr(self, "_voice_state", "standby") in ("speaking", "thinking"))

    def _on_guardian_alert(self, text):
        self._chat.add_warning(f"👁 Screen Guardian: {text}")
        if self._float_orb:
            if not self._float_orb.isVisible():
                self._preview_orb(15000)              # orb dikha do taaki chetawani nazar aaye
            self._float_orb.say(text, "warn", 14000)
        if hasattr(self, "_worker"):
            self._worker.send_text(f"Ye chetawani user ko chhote mein bolkar suna do ('{_prefs.user_name() or 'Sir'},' se shuru, kuch aur add mat karo): " + text)

    def first_run_setup(self):
        """Ek baar: startup + Screen Guardian ke liye user ki sahmati."""
        if not _HAS_ORB or _prefs.get("setup_asked", False):
            return
        _prefs.set_("setup_asked", True)
        from PyQt5.QtWidgets import QCheckBox
        from ALIRA_ui import pill
        d = QDialog(self)
        d.setWindowTitle("ALIRA setup")
        d.setModal(True)
        d.setFixedWidth(520)
        d.setStyleSheet(f"QDialog{{background:{_UI['bg']};}}QLabel{{color:#EDEBF0;}}QCheckBox{{color:#EDEBF0;spacing:10px;}}")
        v = QVBoxLayout(d); v.setContentsMargins(26, 24, 26, 22); v.setSpacing(14)
        t = QLabel("ALIRA ko hamesha saath rakho"); t.setStyleSheet("color:#fff;font-size:20px;font-weight:800;")
        v.addWidget(t)
        sub = QLabel("Minimize karne par ALIRA ek chhote orb mein badal jaati hai — use kahin bhi rakh sakte ho. "
                     "Neeche ke options chalu karne se wo PC start hote hi orb ke saath aa jaati hai.")
        sub.setWordWrap(True); v.addWidget(sub)
        from PyQt5.QtWidgets import QLineEdit
        nm = QLineEdit(); nm.setMaxLength(30); nm.setPlaceholderText("Aapka naam (ALIRA isi naam se bulayegi)")
        nm.setText(_prefs.user_name())
        nm.setStyleSheet("QLineEdit{background:rgba(255,255,255,0.06);color:#fff;border:1px solid rgba(255,255,255,0.18);"
                         "border-radius:10px;padding:9px 12px;font-size:15px;}QLineEdit:focus{border:1px solid #FF2E43;}")
        v.addWidget(nm)
        c1 = QCheckBox("Windows start / restart par ALIRA khud chalu ho (background mein orb)")
        c1.setChecked(True); v.addWidget(c1)
        c2 = QCheckBox("Screen Guardian: ALIRA screen dekhe aur kuch galat lage to bataye")
        c2.setChecked(True); v.addWidget(c2)
        note = QLabel("Guardian ke liye screenshot Gemini ko jaata hai — sirf jab screen badli ho. Password / banking / "
                      "incognito window par kabhi nahi bheja jaata. Baad mein Settings se kabhi bhi band kar sakte ho.")
        note.setWordWrap(True); note.setStyleSheet("color:#9C99A4;font-size:11px;"); v.addWidget(note)
        row = QHBoxLayout(); row.addStretch()
        skip = pill("Abhi nahi", None, "ghost", 38); go = pill("Continue", None, "primary", 38)
        skip.clicked.connect(_ALIRA_slot(d.reject)); go.clicked.connect(_ALIRA_slot(d.accept))
        row.addWidget(skip); row.addWidget(go); v.addLayout(row)
        if d.exec_() == QDialog.Accepted:
            if nm.text().strip():
                self._on_user_name_set(nm.text())
            if c1.isChecked():
                self._on_autostart_toggle(True)
            if c2.isChecked():
                self._on_guardian_toggle(True)

    # ── USER NAME ────────────────────────────────────────────────
    def _init_user_name(self):
        self._bus.user_name.connect(self._on_user_name_set)
        try:
            self._orb.set_user_name(_prefs.user_name())
        except Exception as e:
            print(f"[ALIRA] user name init: {e}")

    def _on_user_name_set(self, name):
        n = _prefs.set_user_name(name)
        if not n:
            return
        self._bus.state["user_name"] = n
        try:
            self._orb.set_user_name(n)
        except Exception:
            pass
        self._chat.add_sys(f"👋 Namaste {n}! Ab ALIRA tumhe {n} naam se bulayegi")
        if hasattr(self, "_worker"):
            self._worker.send_text(f"User ka naam {n} hai (abhi set kiya). Ab se unhe {n} naam se bulao. "
                                   f"Ek chhota sa warm welcome bolo — {n} naam ke saath.")

    # ── LANGUAGE ─────────────────────────────────────────────────
    def _init_language(self):
        import ALIRA_lang
        self._bus.language.connect(self._on_language_set)
        self._bus.state["language"] = (ALIRA_lang.current() or ("auto",))[0]

    def _on_language_set(self, code):
        import ALIRA_lang
        try:
            it = ALIRA_lang.set_language(code)
        except ValueError:
            return
        self._bus.state["language"] = it[0] if it else "auto"
        name = it[1] if it else "Auto (Hinglish)"
        self._chat.add_sys(f"🌐 Language → {name} — reconnecting...")
        if hasattr(self, "_worker"):
            self._worker.reset_greet(); self._worker.reconnect()

    def _sync_language(self):
        import ALIRA_lang
        c = (ALIRA_lang.current() or ("auto",))[0]
        if c != self._bus.state.get("language", "auto"):
            self._bus.state["language"] = c

    def _sync_user_name(self):
        """Voice tool (set_user_name) ya dusri jagah se naam badla ho to UI mein dikhao."""
        n = _prefs.user_name()
        if n != self._bus.state.get("user_name", ""):
            self._bus.state["user_name"] = n
            try:
                self._orb.set_user_name(n)
            except Exception:
                pass

    def ask_name_if_missing(self):
        """Naam set nahi hai to ek baar poocho (pehli baar ke setup mein na aaya ho tab)."""
        if _prefs.user_name() or _prefs.get("name_asked", False):
            return
        _prefs.set_("name_asked", True)
        from PyQt5.QtWidgets import QLineEdit
        from ALIRA_ui import pill
        d = QDialog(self)
        d.setWindowTitle("Aapka naam")
        d.setModal(True)
        d.setFixedWidth(460)
        d.setStyleSheet(f"QDialog{{background:{_UI['bg']};}}QLabel{{color:#EDEBF0;}}"
                        "QLineEdit{background:rgba(255,255,255,0.06);color:#fff;border:1px solid rgba(255,255,255,0.18);"
                        "border-radius:10px;padding:9px 12px;font-size:15px;}QLineEdit:focus{border:1px solid #FF2E43;}")
        v = QVBoxLayout(d); v.setContentsMargins(26, 24, 26, 22); v.setSpacing(12)
        t = QLabel("ALIRA ko aapka naam batao"); t.setStyleSheet("color:#fff;font-size:20px;font-weight:800;")
        sub = QLabel("ALIRA aapko isi naam se bulayegi. Baad mein Settings → Profile se badal sakte ho.")
        sub.setWordWrap(True)
        ed = QLineEdit(); ed.setMaxLength(30); ed.setPlaceholderText("Aapka naam (jaise: Alih)")
        row = QHBoxLayout(); row.addStretch()
        later = pill("Baad mein", None, "ghost", 38); ok = pill("Save", None, "primary", 38)
        later.clicked.connect(_ALIRA_slot(d.reject)); ok.clicked.connect(_ALIRA_slot(d.accept)); ed.returnPressed.connect(_ALIRA_slot(d.accept))
        row.addWidget(later); row.addWidget(ok)
        for w in (t, sub, ed):
            v.addWidget(w)
        v.addLayout(row)
        if d.exec_() == QDialog.Accepted and ed.text().strip():
            self._on_user_name_set(ed.text())

    # ── UI BUILD ─────────────────────────────────────────────────
    def _build_ui(self):
        load_fonts()     # bundled Poppins
        _sp(73)
        self.setStyleSheet(f"QMainWindow{{background:{_UI['bg']};}}QWidget{{color:{_UI['text']};font-family:'Poppins','Segoe UI VTABBUble','Segoe UI',TABBUl;}}"
                           "QLabel{background:transparent;}QToolTip{background:#15121A;color:#fff;border:1px solid #FF2E43;padding:4px;}")
        shell = QWidget(); shell.setObjectName("shell")
        shell.setStyleSheet(f"#shell{{background:{_UI['bg']};border:1px solid rgba(255,46,67,0.28);}}")
        self.setCentralWidget(shell)
        shell_vl = QVBoxLayout(shell); shell_vl.setContentsMargins(1, 1, 1, 1); shell_vl.setSpacing(0)

        self._bus = Bus()
        self._bus.state["edge_glow"] = _load_edge_pref()
        self._bus.state["user_name"] = _prefs.user_name()
        self._bus.state.update(
            orb_on_minimize=bool(_prefs.get("orb_on_minimize", True)),
            orb_float_size=int(_prefs.get("float_orb_size", 96)),
            orb_ui_scale=int(_prefs.get("orb_ui_scale", 100)),
            guardian=bool(_prefs.get("guardian", False)),
            guardian_interval=int(_prefs.get("guardian_interval", 45)),
            autostart=bool(_HAS_ORB and _autostart.is_enabled()))
        mid = QHBoxLayout(); mid.setContentsMargins(0, 0, 0, 0); mid.setSpacing(0)
        self._sidebar = Sidebar(_HAS_WEBFORGE); mid.addWidget(self._sidebar)
        self._sidebar.sig_nav.connect(self._on_nav)

        col = QVBoxLayout(); col.setContentsMargins(0, 0, 0, 0); col.setSpacing(0)

        # top strip: Online ▾ + window controls (har page par)
        self._topbar = HeaderBar(_LIVE_MODEL_KEY, [(k, v[0]) for k, v in LIVE_MODELS.items()])
        self._topbar.sig_mode.connect(self._on_mode)
        self._topbar.sig_mic_select.connect(self._on_mic_select)
        self._topbar.sig_api_change.connect(self._on_api_change)
        self._topbar.sig_model.connect(self._on_model_switch)
        self._topbar.sig_voice.connect(self._on_voice)
        self._topbar.sig_camera.connect(self._on_camera)
        self._topbar.sig_screenshare.connect(self._on_screenshare)
        col.addWidget(self._topbar)

        # ── pages ──
        self._pages = QStackedWidget()
        home = QWidget(); hh = QHBoxLayout(home); hh.setContentsMargins(0, 0, 0, 0); hh.setSpacing(0)
        self._orb = HeroPanel()
        self._orb.sig_mode.connect(self._on_listen_mode); self._orb.sig_orb.connect(self._on_orb_tap)
        self._orb.sig_chip.connect(self._on_hero_chip)
        hh.addWidget(self._orb, 1)
        right = QWidget(); right.setFixedWidth(430)
        rv = QVBoxLayout(right); rv.setContentsMargins(0, 0, 18, 12); rv.setSpacing(14)
        self._stats = StatsCard(); rv.addWidget(self._stats)
        self._quick = QuickToolsCard(); self._quick.sig_tool.connect(self._on_quick_tool); rv.addWidget(self._quick, 1)
        self._recent = RecentActivityCard(); self._recent.sig_view_all.connect(lambda: self._show_page("chat")); rv.addWidget(self._recent)
        hh.addWidget(right)

        _sp(76)
        self._chat = ChatWidget()
        self._p_voice = VoicePage(self._bus)
        _sp(78)
        self._p_media = MediaPage(self._bus)
        _sp(79)
        self._p_studio = StudioPage(self._bus)
        self._p_studio.engine.sig_done.connect(self._on_studio_done)
        self._p_studio.engine.sig_error.connect(self._on_studio_error)
        _sp(81)
        _pg_chat = ChatPage(self._bus, self._chat); _sp(82)
        _pg_pc = PCControlPage(self._bus); _sp(83)
        _pg_apps = AppsToolsPage(self._bus); _sp(84)
        _pg_auto = AutomationPage(self._bus); _sp(85)
        _pg_files = FilesPage(self._bus); _sp(86)
        _pg_web = WebSearchPage(self._bus); _sp(87)
        _pg_mon = SystemMonitorPage(self._bus); _sp(88)
        _pg_set = SettingsPage(self._bus); _sp(89)
        _pg_about = AboutPage(self._bus); _sp(90)
        order = [("home", home), ("chat", _pg_chat), ("voice", self._p_voice),
                 ("pc", _pg_pc), ("apps", _pg_apps), ("automation", _pg_auto),
                 ("files", _pg_files), ("media", self._p_media), ("web", _pg_web),
                 ("studio", self._p_studio),
                 ("monitor", _pg_mon), ("settings", _pg_set),
                 ("about", _pg_about)]
        self._page_idx = {}
        for i, (k, w) in enumerate(order):
            self._pages.addWidget(w); self._page_idx[k] = i
        self._cam_panel_widget = self._p_media.cam_holder
        col.addWidget(self._pages, 1)

        # bottom: input bar + suggestion chips
        self._input = InputBar()
        self._input.sig_send.connect(self._on_send_text)
        self._input.sig_mic.connect(self._on_mic_toggle)
        self._input.sig_attach.connect(self._on_attach)
        self._input.sig_image.connect(self._on_camera)
        ib = QHBoxLayout(); ib.setContentsMargins(40, 4, 22, 0); ib.addWidget(self._input)
        col.addLayout(ib)
        self._chips = ChipsRow(); self._chips.sig_chip.connect(self._on_send_text)
        col.addWidget(self._chips)
        mid.addLayout(col, 1)
        shell_vl.addLayout(mid, 1)

        self._statusbar = StatusBar()
        self._statusbar.sig_globe.connect(lambda: self._on_nav("web"))
        self._statusbar.sig_keyboard.connect(self._on_mic_select)
        self._statusbar.sig_settings.connect(lambda: self._on_nav("settings"))
        self._statusbar.sig_fullscreen.connect(self._toggle_fullscreen)
        self._topbar.sig_status_text.connect(self._statusbar.set_status)
        shell_vl.addWidget(self._statusbar)

        # purane BottomControls attrs (cam_btn/voice_btn/screen_btn) ab header menu se
        self._ctrl = self._topbar

        # ── bus wiring (pages -> window) ──
        b = self._bus
        b.prompt.connect(self._on_send_text);        b.goto.connect(self._on_nav)
        b.listen_mode.connect(self._on_listen_mode); b.voice_toggle.connect(self._on_voice)
        b.model_pick.connect(self._on_model_switch); b.mic_select.connect(self._on_mic_select)
        b.api_change.connect(self._on_api_change);   b.persona_toggle.connect(self._on_mode)
        b.camera_toggle.connect(self._on_camera);    b.screenshare_toggle.connect(self._on_screenshare)
        b.coder.connect(self._open_ALIRA_coder_prompt); b.webforge.connect(self._open_webforge_prompt)
        b.fullscreen.connect(self._toggle_fullscreen); b.always_on_top.connect(self._on_always_top)
        b.deploy_site.connect(lambda d: self._deploy_dir(Path(d), Path(d).name))
        b.toast.connect(self._statusbar.flash);      b.sens_changed.connect(self._on_sens)
        self._listen_mode = "continuous"
        QTimer(self, interval=1500, timeout=self._publish_state).start()

        # ── ALIRA CODER OVERLAY ────────────────────────────────────
        # v3.0: QDialog — parent = self (TABBUWindow) — guaranteed visible
        if _HAS_ALIRA_CODER:
            self._ALIRA_coder_overlay = ALIRACoderOverlay(self)
            self._ALIRA_coder_overlay.sig_done.connect(self._on_ALIRA_coder_done)
            self._ALIRA_coder_overlay.sig_error.connect(self._on_ALIRA_coder_error)
            print("[ALIRA] ALIRA Coder overlay (QDialog) initialized")
        else:
            self._ALIRA_coder_overlay = None

    # ── pages / state ────────────────────────────────────────────
    def _show_page(self, name: str):
        name = {"vision": "media"}.get(name, name)
        self._pages.setCurrentIndex(self._page_idx.get(name, 0))
        self._sidebar.set_active(name if name in self._page_idx else "home")

    def _toggle_fullscreen(self):
        self.showNormal() if self.isFullScreen() else self.showFullScreen()

    def _on_always_top(self, on: bool):
        self.setWindowFlag(Qt.WindowStaysOnTopHint, bool(on)); self.show()

    def _set_orb_state(self, s: str):
        self._orb.set_state(s); self._p_voice.orb.set_state(s)
        if getattr(self, '_float_orb', None):
            self._float_orb.set_state(s)

    def _publish_state(self):
        st = self._bus.state
        w = getattr(self, "_worker", None)
        st.update(mic_on=self._mic_on, listen_mode=self._listen_mode, voice=_CURRENT_VOICE, model_key=_LIVE_MODEL_KEY,
                  models=[(k, v[0]) for k, v in LIVE_MODELS.items()], persona=self._mode,
                  cam_on=bool(_HAS_CAM_VISION and self._cv_mgr.is_active) if hasattr(self, "_cv_mgr") else False,
                  screen_on=bool(self._ss_mgr.is_active) if hasattr(self, "_ss_mgr") else False,
                  session=(w.info() if w else {}), rms=SILENCE_RMS, gain=MIC_GAIN)
        self._sync_orb_menu()
        self._sync_user_name(); self._sync_language()
        self._bus.state_changed.emit()

    def _on_sens(self, rms: int, gain: float):
        global SILENCE_RMS, MIC_GAIN
        SILENCE_RMS, MIC_GAIN = int(rms), float(gain)

    # ── listening modes: wake / tap / continuous / stop ──────────
    def _on_listen_mode(self, mode: str):
        if mode == "tap" and self._listen_mode == "tap":      # orb tap = talk
            self._on_speak(); return
        self._listen_mode = mode
        if hasattr(self, "_worker"): self._worker.set_listen_mode(mode)
        self._orb.set_mode(mode); self._p_voice.modes.set_mode(mode)
        if mode == "stop":
            self._on_mute()
        elif mode == "tap":
            self._on_mute(); self._statusbar.flash("Tap to Talk — orb/mic dabao aur bolo")
        else:
            self._on_speak()
            if mode == "wake": self._statusbar.flash("Wake Word — 'ALIRA' bolke baat shuru karo")
        self._publish_state()

    def _on_orb_tap(self):
        if self._listen_mode == "tap" or not self._mic_on:
            self._on_speak()
        else:
            self._on_mute()

    def _on_mic_state(self, on: bool):
        """Worker ne mic khud band kiya (tap mode: jawab ke baad)."""
        self._mic_on = on; self._input.set_mic_on(on)
        if not on: self._topbar.set_status("standby", "TAP TO TALK")

    # ── NAV / INPUT / QUICK TOOLS ────────────────────────────────
    def _on_nav(self, key: str):
        self._show_page(key)

    def _on_hero_chip(self, text: str):
        if text == "Chat with me":      self._show_page("chat")
        elif text == "Automate tasks":  self._show_page("automation")
        elif text == "Work with files": self._show_page("files")
        elif text == "And much more…":  self._show_page("apps")
        elif text == "Control your PC": self._show_page("pc")
        else:
            self._input.edit.setText("Search the web for ")
            self._input.edit.setFocus()

    def _on_send_text(self, text: str):
        text = (text or "").strip()
        if not text: return
        self._chat.finalize_user(text)
        self._recent.add(f"You: {text}")
        if hasattr(self, "_worker"): self._worker.send_text(text)
        if not self._trigger_ALIRA_coder(text):     # "website banao" jaise commands Website Studio chalate hain
            self._show_page("chat")

    def _on_mic_toggle(self):
        if self._listen_mode == "tap":      # tap mode: mic button = talk
            self._on_speak()
        elif self._mic_on: self._on_mute()
        else:              self._on_speak()

    def _on_attach(self):
        path, _ = QFileDialog.getOpenFileName(self, "File chuno")
        if path: self._on_send_text(f"Is file ko dekho aur summarize karo: {path}")

    def _on_quick_tool(self, key: str):
        if key == "view_all": self._show_page("chat"); return
        if key == "open_app":
            name, ok = QInputDialog.getText(self, "Open App", "Kaun sa app kholna hai?")
            if ok and name.strip(): self._on_send_text(f"Open {name.strip()}")
            return
        if key == "whatsapp":
            who, ok = QInputDialog.getText(self, "WhatsApp", "Kisko message bhejna hai? (naam/number)")
            if ok and who.strip(): self._on_send_text(f"WhatsApp par {who.strip()} ko message bhejna hai")
            return
        if key == "shutdown":
            if QMessageBox.question(self, "Shutdown", "PC band kar dun?") != QMessageBox.Yes: return
        cmds = {"screenshot": "Screenshot lo", "clipboard": "Clipboard mein kya hai batao",
                "volume": "Volume badlo", "brightness": "Brightness badlo",
                "lock": "PC lock kar do", "shutdown": "PC shutdown kar do"}
        if key in cmds: self._on_send_text(cmds[key])

    # ── CAMERA VISION ────────────────────────────────────────────
    def _init_cam_vision(self):
        self._cv_mgr = CameraVisionManager()
        if _HAS_CAM_VISION:
            vl = self._cam_panel_widget.layout()
            vl.setContentsMargins(0, 0, 0, 0); vl.setSpacing(0)
            self._cv_panel = CameraVisionPanel(self._cv_mgr)
            self._cv_panel.sig_describe_now.connect(self._on_cv_describe_now)
            vl.addWidget(self._cv_panel)
            self._cv_mgr.sig_started.connect(self._on_cv_started)
            self._cv_mgr.sig_stopped.connect(self._on_cv_stopped)
            self._cv_mgr.sig_error.connect(self._on_cv_error)
            self._cv_mgr.sig_vision_frame.connect(self._on_cv_frame)
            self._cv_mgr.sig_status.connect(lambda s: self._chat.add_sys(s))
            # ✅ FIX: sidebar ka mini-preview ab isi single shared manager se
            # frames leta hai — apna alag camera handle nahi kholta
            self._cv_mgr.sig_ui_frame.connect(self._sidebar.update_camera_frame)
        else:
            lbl = QLabel("📷 Camera Vision\nnot available\npip install opencv-python")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("color:#334455;font-size:12px;background:transparent;padding:20px;")
            lbl.setWordWrap(True)
            self._cam_panel_widget.layout().addWidget(lbl)

    def _on_cv_frame(self, b64_jpeg: str):
        if hasattr(self, '_worker'):
            self._worker.push_screen_frame(b64_jpeg)
            # FIX: pehle frame ke BAAD hi ALIRA ko bolo (frame aane se pehle bolne par
            # wo andaza lagakar fake describe karti thi)
            if getattr(self, '_cv_first_frame_pending', False):
                self._cv_first_frame_pending = False
                QTimer.singleShot(700, lambda: self._worker.send_text(
                    "Camera ka REAL frame abhi tumhe mil gaya hai. Sirf wahi batao jo frame mein "
                    "sach mein dikh raha hai. Andaza ya kalpana mat karo; jo clear na dikhe wo "
                    "bolo 'clear nahi dikh raha'."))

    def _on_cv_describe_now(self):
        if hasattr(self, '_worker') and _HAS_CAM_VISION:
            self._cv_mgr.describe_now(
                get_ws_func=self._worker.get_ws,
                get_loop_func=self._worker.get_loop
            )
            self._chat.add_sys("👁 Camera frame capture hua — ALIRA dekh rahi hai...")

    def _on_cv_started(self):
        self._chat.add_sys("📷 Camera Vision ON — pehla frame bhej rahi hoon...")
        self._sidebar.update_camera_status(True)
        self._ctrl.cam_btn.setText("Camera Off")
        # FIX: ab ALIRA ko pehle frame aane ke baad hi bola jaata hai (_on_cv_frame mein).
        # Agar 8 sec mein koi frame nahi aaya to user ko sach bata do — fake mat bolo.
        self._cv_first_frame_pending = True
        self._update_edge_glow()
        def _no_frame_check():
            if getattr(self, '_cv_first_frame_pending', False) and self._cv_mgr.is_active:
                self._cv_first_frame_pending = False
                self._chat.add_error("Camera ka frame ALIRA tak nahi pahunch raha — Gemini session connect nahi hai ya camera block hai.")
        QTimer.singleShot(8000, _no_frame_check)

    def _on_cv_stopped(self):
        self._update_edge_glow()
        self._chat.add_sys("📷 Camera Vision OFF")
        self._sidebar.update_camera_status(False)
        self._ctrl.cam_btn.setText("🎥  Camera On/Off")
        if hasattr(self, '_worker'):
            self._worker.send_text("Camera band ho gayi. Normal mode.")

    def _on_cv_error(self, err: str):
        self._chat.add_error(f"Camera: {err}")
        self._sidebar.update_camera_status(False)
        self._ctrl.cam_btn.setText("🎥  Camera On/Off")

    # ── SCREEN SHARE ─────────────────────────────────────────────
    def _init_screenshare(self):
        self._ss_mgr = ScreenShareManager(fps=1.0)
        if _HAS_SCREEN_SHARE:
            self._ss_mgr.sig_started.connect(self._on_ss_started)
            self._ss_mgr.sig_stopped.connect(self._on_ss_stopped)
            self._ss_mgr.sig_error.connect(self._on_ss_error)
            self._ss_mgr.sig_status.connect(lambda s: self._chat.add_sys(s))
            self._ss_mgr.sig_frame_ready.connect(self._on_ss_frame)

    def _on_ss_frame(self, b64_jpeg: str):
        if hasattr(self, '_worker'):
            self._worker.push_screen_frame(b64_jpeg)
            if getattr(self, '_ss_first_frame_pending', False):
                self._ss_first_frame_pending = False
                QTimer.singleShot(700, lambda: self._worker.send_text(
                    "User ne screen sharing ON kar di hai aur screen ka REAL frame tumhe mil gaya hai. "
                    "Sirf wahi batao jo frame mein sach mein dikh raha hai — andaza mat lagao. "
                    "Chhota sa bolo ki ab tum screen dekh sakti ho aur poocho kya madad chahiye."))

    def _on_ss_started(self):
        self._ctrl.screen_btn.set_sharing(True)
        self._sidebar.update_screenshare_status(True)
        self._chat.add_screen_share_badge(True)
        self._set_orb_state("screenshare")
        self._topbar.set_status("screenshare", "SCREEN SHARE ▣")
        self._ss_first_frame_pending = True      # ALIRA ko pehla frame jaane ke BAAD hi bolo (fake describe na ho)
        self._update_edge_glow()

    def _on_ss_stopped(self):
        self._ctrl.screen_btn.set_sharing(False)
        self._sidebar.update_screenshare_status(False)
        self._chat.add_screen_share_badge(False)
        self._set_orb_state("idle")
        self._topbar.set_status("standby", "STANDBY")
        self._ss_first_frame_pending = False
        self._update_edge_glow()
        if hasattr(self, '_worker'):
            self._worker.send_text("Screen sharing band ho gayi. Ab normal conversation mode.")

    def _on_ss_error(self, err: str):
        self._chat.add_error(f"Screen share error: {err}")
        self._ctrl.screen_btn.set_sharing(False)
        self._sidebar.update_screenshare_status(False)

    def _on_screenshare(self):
        if not _HAS_SCREEN_SHARE:
            self._chat.add_error("Screen share module missing — pip install mss pillow")
            return
        self._ss_mgr.toggle()

    # ══════════════════════════════════════════════════════════════
    # WEBFORGE — VOICE COMMAND INTERCEPT + PIPELINE
    # ══════════════════════════════════════════════════════════════
    def _on_user_msg_website(self, text: str):
        """
        ALIRA Coder intercept — website build commands.
        sig_user_msg (turnComplete) pe fire hota hai.
        """
        self._trigger_ALIRA_coder(text)

    def _on_user_live_website(self, text: str):
        """
        ALIRA Coder EARLY intercept — sig_user_live (streaming) pe.
        Jaise hi user ka sentence complete lagta hai, detect karo.
        Ye Gemini ke tool call se PEHLE trigger hota hai.
        """
        # Sirf full sentence detect karo (min words)
        if len(text.split()) < 3:
            return
        self._trigger_ALIRA_coder(text)

    def _trigger_ALIRA_coder(self, text: str, force: bool = False) -> bool:
        """Website/code build command -> Website Studio (alag HTML/CSS/JS files + auto-review & fix).
        force=True: user ne explicitly builder khola hai (keyword-gate skip). True = build shuru hua."""
        if not force and not _is_website_command(text):
            return False
        if self._p_studio.is_working():              # ✅ dedup: pehle se chal raha hai
            return False
        self._ALIRA_coder_running = True
        self._chat.add_webforge_badge(f"\u26a1 ALIRA Coder: {text[:50]}...")
        self._topbar.set_status("webforge", "ALIRA CODER ⬡")
        self._set_orb_state("webforge")
        self._sidebar.update_webforge_status(True, "Coding...")
        self._show_page("studio")
        return self._p_studio.start_build(text)

    def _on_studio_done(self, project_dir: str, summary: str):
        triggered = getattr(self, "_ALIRA_coder_running", False)
        self._ALIRA_coder_running = False
        self._set_orb_state("idle"); self._topbar.set_status("standby", "STANDBY")
        self._sidebar.update_webforge_status(False)
        if not triggered:
            return                                    # user ne Studio me khud type kiya — voice/deploy nahi
        name = Path(project_dir).name
        self._chat.add_webforge_badge(f"\u2705 Website ready: {name}", success=True)
        if hasattr(self, "_worker"):
            self._worker.send_text(
                "ALIRA Coder ne website successfully bana di (alag HTML/CSS/JS files, review aur fix ke saath). "
                "User ko warmly congratulate karo aur poocho aur kya badalna hai!")
        self._deploy_dir(Path(project_dir), name, auto=True)

    def _on_studio_error(self, msg: str):
        self._ALIRA_coder_running = False
        self._set_orb_state("idle"); self._topbar.set_status("standby", "STANDBY")
        self._sidebar.update_webforge_status(False)
        self._chat.add_error(f"ALIRA Coder Error: {msg[:100]}")

    def _deploy_dir(self, project_dir: Path, repo_name: str, auto: bool = False):
        """Project folder ko WebForge ke GitHub + Vercel se deploy karo (tokens ho to)."""
        if not (_HAS_WEBFORGE and _webforge):
            if not auto: self._statusbar.flash("✗ WebForge available nahi — deploy nahi ho sakta")
            return
        if not auto: self._statusbar.flash("⬆ Deploy shuru…")

        def _deploy():
            try:
                gh = _webforge._github.push_project(repo_name, project_dir)
                if not gh.get("ok"):
                    msg = f"GitHub push skipped: {gh.get('error')}"
                    print(f"[Studio->WebForge] {msg}")
                    if not auto:
                        from PyQt5.QtWidgets import QApplication
                        QApplication.instance().postEvent(self, _WebForgeEvent(msg=msg, success=False))
                    return
                vc = _webforge._vercel.deploy_from_github(repo_name, repo_name)
                live_url = vc.get("live_url", "")
                if vc.get("ok") and live_url:
                    msg = f"Live deploy ho gaya: {live_url} | GitHub: {gh.get('github_url','')}"
                else:
                    msg = f"GitHub pe push ho gaya: {gh.get('github_url','')} (Vercel deploy skip: {vc.get('error','')})"
                from PyQt5.QtWidgets import QApplication
                QApplication.instance().postEvent(self, _WebForgeEvent(msg=msg, success=True))
            except Exception as e:
                print(f"[Studio->WebForge] deploy error: {e}")

        threading.Thread(target=_deploy, daemon=True, name="Studio-Deploy").start()

    def _on_ALIRA_coder_done(self, summary: str):
        """ALIRA Coder ne kaam finish kiya."""
        self._ALIRA_coder_running = False   # ✅ reset guard
        self._set_orb_state("idle")
        self._topbar.set_status("standby", "STANDBY")
        self._sidebar.update_webforge_status(False)
        self._chat.add_webforge_badge(f"\u2705 {summary[:120]}", success=True)
        if hasattr(self, "_worker"):
            self._worker.send_text(
                "ALIRA Coder ne website successfully bana diya! "
                "Live files Projects/ folder mein save ho gayi hain. "
                "User ko warmly congratulate karo! Poocho aur kya chahiye?"
            )
        # LINK: ALIRA Coder banata hai, WebForge deploy karta hai — GitHub +
        # Vercel tokens hain to output ko automatically live karo, taaki dono
        # engine ek pipeline ki tarah kaam karein instead of do alag silos.
        self._auto_deploy_ALIRA_coder_output()

    def _auto_deploy_ALIRA_coder_output(self):
        """ALIRA Coder ke fresh output ko WebForge ke GitHub+Vercel se deploy karo."""
        if not (_HAS_WEBFORGE and _webforge):
            return
        output_dir = getattr(self, "_ALIRA_coder_output_dir", None)
        if not output_dir or not os.path.isdir(output_dir):
            return

        pre = getattr(self, "_ALIRA_coder_pre_dirs", set())
        try:
            now_dirs = [d for d in os.listdir(output_dir)
                        if os.path.isdir(os.path.join(output_dir, d))]
        except Exception:
            return
        new_dirs = [d for d in now_dirs if d not in pre]

        if new_dirs:
            new_dirs.sort(
                key=lambda d: os.path.getmtime(os.path.join(output_dir, d)),
                reverse=True
            )
            project_dir = Path(output_dir) / new_dirs[0]
            repo_name   = new_dirs[0]
        else:
            # ALIRA Coder ne subfolder nahi banaya - seedha output_dir mein likha
            project_dir = Path(output_dir)
            repo_name   = "ALIRA-coder-site"

        def _deploy():
            try:
                gh = _webforge._github.push_project(repo_name, project_dir)
                if not gh.get("ok"):
                    print(f"[ALIRA Coder->WebForge] GitHub push skipped: {gh.get('error')}")
                    return
                vc = _webforge._vercel.deploy_from_github(repo_name, repo_name)
                live_url = vc.get("live_url", "")
                if vc.get("ok") and live_url:
                    msg = f"Live deploy ho gaya: {live_url} | GitHub: {gh.get('github_url','')}"
                else:
                    msg = f"GitHub pe push ho gaya: {gh.get('github_url','')} (Vercel deploy skip: {vc.get('error','')})"
                from PyQt5.QtWidgets import QApplication
                QApplication.instance().postEvent(self, _WebForgeEvent(msg=msg, success=True))
            except Exception as e:
                print(f"[ALIRA Coder->WebForge] auto-deploy error: {e}")

        threading.Thread(target=_deploy, daemon=True, name="ALIRACoder-Deploy").start()

    def _on_ALIRA_coder_error(self, msg: str):
        """ALIRA Coder mein error aaya."""
        self._ALIRA_coder_running = False   # ✅ reset guard
        self._set_orb_state("idle")
        self._topbar.set_status("standby", "STANDBY")
        self._sidebar.update_webforge_status(False)
        self._ALIRA_coder_overlay.hide_panel()
        self._chat.add_error(f"ALIRA Coder Error: {msg[:100]}")

    # ══════════════════════════════════════════════════════════════════
    # LEFT SIDEBAR TOOL CLICKS — rows had no click handler at all before,
    # so none of these buttons did anything when clicked.
    # ══════════════════════════════════════════════════════════════════
    def _on_sidebar_tool(self, key: str):
        handlers = {
            "ALIRA_coder":   self._open_ALIRA_coder_prompt,
            "webforge":     self._open_webforge_prompt,
            "task_manager": self._open_task_manager,
            "settings":     self._on_api_change,
        }
        handler = handlers.get(key)
        if handler:
            handler()
            return
        # Not built yet — say so instead of doing nothing.
        names = {
            "image_generator": "Image Generator",
            "text_generator":  "Text Generator",
            "translator":      "Translator",
            "data_analysis":   "Data Analysis",
        }
        QMessageBox.information(
            self, "Coming Soon",
            f"{names.get(key, key)} abhi build nahi hua hai — jald aa raha hai!"
        )

    def _open_ALIRA_coder_prompt(self):
        """ALIRA Coder / 'Apps & Tools' button -> Website Studio page."""
        self._show_page("studio")
        try: self._p_studio.input.setFocus()
        except Exception: pass

    def _open_webforge_prompt(self):
        if not (_HAS_WEBFORGE and _webforge):
            QMessageBox.warning(self, "WebForge AI", "WebForge is not available in this build.")
            return
        if getattr(self, '_ALIRA_coder_running', False):
            QMessageBox.information(self, "WebForge AI", "ALIRA Coder abhi kaam kar raha hai — thoda ruko.")
            return
        text, ok = QInputDialog.getText(
            self, "WebForge AI",
            "Command batao (e.g. \"website ka status batao\", \"redeploy karo\", \"preview dikhao\")"
        )
        text = (text or "").strip()
        if not (ok and text):
            return

        self._chat.add_webforge_badge(f"WebForge command: {text[:45]}...")
        self._topbar.set_status("webforge", "WEBFORGE ⬡")
        self._set_orb_state("webforge")
        self._sidebar.update_webforge_status(True, "Working...")

        def _run():
            result = _webforge.handle_command(text, parent_widget=self)
            QApplication.instance().postEvent(
                self,
                _WebForgeEvent(
                    msg=self._format_webforge_result(result),
                    success=result.get("success", False)
                )
            )

        threading.Thread(target=_run, daemon=True, name="WebForge-Manual").start()

    def _open_task_manager(self):
        dlg = TaskManagerDialog(self)
        dlg.exec_()

    def _on_user_msg_webforge(self, text: str):
        """
        Har user message check karo.
        Agar WebForge command hai → background thread mein handle karo.
        Warna ALIRA normal response degi.
        """
        if not _HAS_WEBFORGE or not _webforge:
            return
        # ✅ FIX: ALIRA Coder + WebForge dono "website banao" jaisi commands pe
        # apne-apne alag keyword-list se PARALLEL fire ho jaate the — do
        # builders ek hi request pe ek saath chalte the, Projects/ folder
        # mein conflict/double-write karte the aur do alag status badges
        # dikhate the. Ab ALIRA Coder primary builder hai (real Gemini tool +
        # text trigger); WebForge yahan sirf tab chalta hai jab ALIRA Coder
        # available hi na ho, ya command actually EXISTING project ke baare
        # mein ho (status/preview/redeploy) — fresh "banao" request nahi.
        if _HAS_ALIRA_CODER and _is_website_command(text):
            return
        if getattr(self, '_ALIRA_coder_running', False):
            return
        if not _webforge.is_webforge_command(text):
            return

        # WebForge command detected! UI update karo
        self._chat.add_webforge_badge(f"WebForge command: {text[:45]}...")
        self._topbar.set_status("webforge", "WEBFORGE ⬡")
        self._set_orb_state("webforge")
        self._sidebar.update_webforge_status(True, "Building...")

        # Background thread mein run karo — UI block nahi hogi
        def _run():
            result = _webforge.handle_command(text, parent_widget=self)
            # Thread-safe UI update via custom event
            from PyQt5.QtWidgets import QApplication
            QApplication.instance().postEvent(
                self,
                _WebForgeEvent(
                    msg     = self._format_webforge_result(result),
                    success = result.get("success", False)
                )
            )

        threading.Thread(target=_run, daemon=True, name="WebForge-Build").start()

    def customEvent(self, event):
        """Thread-safe WebForge result handler"""
        if isinstance(event, _WebForgeEvent):
            # Chat badge
            self._chat.add_webforge_badge(event.msg, event.success)
            # Orb + status reset
            self._set_orb_state("idle")
            self._topbar.set_status("standby", "STANDBY")
            self._sidebar.update_webforge_status(False)
            # ALIRA ko bhi bolne do
            if hasattr(self, '_worker'):
                if event.success:
                    self._worker.send_text(
                        f"Website successfully banaya aur deploy kar diya! "
                        f"Live URL ready hai. QR code bhi show ho gaya screen pe. "
                        f"User ko warmly congratulate karo aur poocho koi aur kaam chahiye?"
                    )
                else:
                    self._worker.send_text(
                        f"WebForge mein thodi problem aayi. "
                        f"User ko batao kya hua aur kaise fix kare."
                    )
        elif isinstance(event, _QuickEvent):
            self._chat.add_sys(event.msg)
            if event.speak and hasattr(self, '_worker'):
                self._worker.send_text(
                    "Ye result user ko short mein bolkar suna do (kuch aur add mat karo): " + event.msg
                )
        else:
            super().customEvent(event)

    def _on_user_msg_quick(self, text: str):
        """Quick features (calculator, timer, notes, todo, ...) — background thread mein."""
        if not _HAS_QUICK or not text or _is_website_command(text):
            return

        def _post(msg, speak=True):
            from PyQt5.QtWidgets import QApplication
            QApplication.instance().postEvent(self, _QuickEvent(msg, speak))

        def _run():
            try:
                res = _handle_quick(text, notify=lambda m: _post(m, True))
            except Exception as e:
                print(f"[QUICK] {e}")
                return
            if res:
                _post(res, True)

        threading.Thread(target=_run, daemon=True, name="Quick-Feature").start()

    @staticmethod
    def _format_webforge_result(result: dict) -> str:
        if result.get("success"):
            lines = [f"✅ {result.get('message', 'Done!')}"]
            if result.get("live_url"):    lines.append(f"🌐 Live: {result['live_url']}")
            if result.get("github_url"):  lines.append(f"🐙 GitHub: {result['github_url']}")
            if result.get("preview_url"): lines.append(f"👁 Preview: {result['preview_url']}")
            return "\n".join(lines)
        return f"❌ {result.get('message', 'WebForge error')}"

    # ── STATUS / SIGNAL HANDLERS ─────────────────────────────────
    def _on_status(self, state, label):
        self._voice_state = state if state != "screenshare" else "standby"
        self._update_edge_glow()
        if self._ss_mgr.is_active and state == "standby":
            self._topbar.set_status("screenshare", "SCREEN SHARE ▣")
            self._set_orb_state("screenshare")
            return
        self._topbar.set_status(state, label)
        m = {"standby":"idle","listening":"listening","thinking":"thinking",
             "speaking":"speaking","error":"error","screenshare":"screenshare"}
        self._set_orb_state(m.get(state, "idle"))

    def _on_energy(self, e):
        if self._mic_on:
            self._orb.set_energy(e); self._p_voice.orb.set_energy(e); self._p_voice.level.set_level(e); self._statusbar.set_energy(e)
            self._sidebar.update_mic_level(e)
            if getattr(self, '_float_orb', None) and self._float_orb.isVisible():
                self._float_orb.set_energy(e)

    def _on_user_live(self, t):
        self._chat.update_live_user(t); self._live_user_txt = t
        self._p_voice.set_live(t, getattr(self, '_live_TABBU_txt', ''))
    def _on_TABBU_live(self, t):
        self._chat.update_live_TABBU(t); self._live_TABBU_txt = t
        self._p_voice.set_live(getattr(self, '_live_user_txt', ''), t)
    def _on_user_msg(self, t):    self._chat.finalize_user(t)
    def _on_TABBU_msg(self, t):
        self._chat.finalize_TABBU(t)
        if getattr(self, '_orb_mode', False) and getattr(self, '_float_orb', None):
            self._float_orb.say(t, 'info', 9000)    # orb mode: jawab orb ke paas bhi dikhe
    def _on_sys_msg(self, t):     self._chat.add_sys(t)
    def _on_error_msg(self, t):   self._chat.add_error(t)
    def _on_warn_msg(self, t):    self._chat.add_warning(t)
    def _on_tool_call(self, t):
        self._chat.add_sys(t); self._recent.add(str(t).strip()[:34])
        low = str(t).lower()
        if any(k in low for k in ("read_screen", "read_active_window", "analyze_screen")):
            self._screenread_until = time.time() + 4.5
            self._update_edge_glow()
            QTimer.singleShot(4700, self._update_edge_glow)
    def _on_tool_result(self, t): self._chat.add_sys(t)

    def _on_connected(self, ok):
        if not ok:
            self._chat.add_warning("Connection lost — reconnecting...")

    # ── BUTTON HANDLERS ──────────────────────────────────────────
    def _on_mic_select(self):
        dlg = MicSelectDialog(self, _MIC_DEVICE, _SPK_DEVICE, SILENCE_RMS, MIC_GAIN)
        dlg.sig_devices_set.connect(self._apply_devices)
        dlg.show()

    def _on_model_switch(self, key: str):
        global _LIVE_MODEL_KEY
        if key not in LIVE_MODELS or key == _LIVE_MODEL_KEY:
            return
        _LIVE_MODEL_KEY = key
        _save_live_model_key(_LIVE_MODEL_KEY)
        self._topbar.set_model_label(_LIVE_MODEL_KEY)
        self._chat.add_sys(f"⚡ Voice model → {LIVE_MODELS[key][0]} ({LIVE_MODELS[key][2]}) — reconnecting...")
        self._worker.stop()
        QTimer.singleShot(800, self._start_worker)

    def _on_api_change(self):
        dlg = ApiKeySetupDialog(self, current_api_key=self._api_key)
        if dlg.exec_() == QDialog.Accepted:
            new_api_key = dlg.get_api_key()
            if new_api_key:
                _save_config(new_api_key)
                global _API_KEY
                _API_KEY = new_api_key
                self._api_key = new_api_key
                self._chat.add_sys("🔑 API key updated → reconnecting...")
                self._worker.stop()
                QTimer.singleShot(1000, self._restart_worker)
            else:
                self._chat.add_error("❌ API key cannot be empty!")

    def _apply_devices(self, mic_idx, spk_idx):
        global _MIC_DEVICE, _SPK_DEVICE
        _MIC_DEVICE = mic_idx; _SPK_DEVICE = spk_idx
        self._chat.add_sys("🎙 Mic changed → reconnecting...")
        self._worker.stop()
        QTimer.singleShot(600, self._restart_worker)

    def _restart_worker(self):
        self._start_worker()
        self._chat.add_sys("✅ New mic/speaker active!")

    def _on_mute(self):
        self._mic_on = False; self._worker.set_mic(False); self._input.set_mic_on(False)
        self._set_orb_state("idle"); self._topbar.set_status("standby","MUTED 🔇")
        self._chat.add_sys("🔇 Mic muted")

    def _on_speak(self):
        self._mic_on = True; self._worker.set_mic(True); self._input.set_mic_on(True)
        self._topbar.set_status("listening","LISTENING")
        self._chat.add_sys("🎤 Mic active")

    def _on_camera(self):
        # ✅ FIX: yeh button pehle sirf ek decorative sidebar preview toggle
        # karta tha jo Gemini ko kuch bhejta hi nahi tha ("vision mode kaam
        # nahi kar raha" ka ek bada karan). Ab yeh seedha CameraVisionManager
        # (asli AI vision engine, Vision tab wala) ko control karta hai —
        # button, sidebar dot aur Vision tab panel teeno automatically sync
        # rehte hain (_on_cv_started/_on_cv_stopped/_on_cv_error ke through).
        if not _HAS_CAM_VISION:
            self._chat.add_error("Camera Vision module missing — pip install opencv-python")
            return
        self._cv_mgr.toggle()
        if self._cv_mgr.is_active:
            self._show_page("vision")   # Vision page pe le jao taaki live preview dikhe

    def _on_voice(self):
        global _CURRENT_VOICE
        _CURRENT_VOICE = "male" if _CURRENT_VOICE == "female" else "female"
        self._ctrl.voice_btn.setText(f"Voice: {_CURRENT_VOICE.title()}")
        self._chat.add_sys(f"Voice → {_CURRENT_VOICE.title()} — reconnecting...")
        self._worker.stop()
        QTimer.singleShot(1000, self._restart_worker)

    def _on_mode(self):
        self._mode = "normal" if self._mode == "ALIRA" else "ALIRA"
        p   = TABBU_PROMPT if self._mode == "ALIRA" else NORMAL_PROMPT
        self._topbar.set_mode_label("Mode: ALIRA 🌸" if self._mode == "ALIRA" else "Mode: Normal 👔")
        self._worker.reset_greet()
        self._worker.set_prompt(p); self._worker.reconnect()
        self._chat.add_sys(f"🔄 Mode: {'ALIRA 🌸' if self._mode=='ALIRA' else 'Normal 👔'}")

    # ── WORKER INIT ──────────────────────────────────────────────
    def _start_worker(self):
        try:                                         # installed apps ki list background mein taiyaar (open_app turant chale)
            import ALIRA_apps
            ALIRA_apps.warm()
        except Exception as e:
            print(f"[ALIRA] app index warm: {e}")
        init_advanced_features(api_key=_API_KEY)
        try: init_advanced(api_key=_API_KEY, suggestion_cb=lambda s: None)
        except: pass

        self._worker = GeminiWorker()
        self._worker.sig_status.connect(self._on_status)
        self._worker.sig_user_live.connect(self._on_user_live)
        self._worker.sig_TABBU_live.connect(self._on_TABBU_live)
        self._worker.sig_user_msg.connect(self._on_user_msg)
        self._worker.sig_TABBU_msg.connect(self._on_TABBU_msg)
        self._worker.sig_sys_msg.connect(self._on_sys_msg)
        self._worker.sig_error_msg.connect(self._on_error_msg)
        self._worker.sig_warn_msg.connect(self._on_warn_msg)
        self._worker.sig_tool_call.connect(self._on_tool_call)
        self._worker.sig_tool_result.connect(self._on_tool_result)
        self._worker.sig_connected.connect(self._on_connected)
        self._worker.sig_energy.connect(self._on_energy)
        self._worker.sig_mic_state.connect(self._on_mic_state)
        self._worker.sig_model_fallback.connect(lambda k: (self._topbar.set_model_label(k), self._publish_state()))
        self._worker.set_listen_mode(self._listen_mode)

        # ✅ WebForge intercept — user message bhi sunenge
        self._worker.sig_user_msg.connect(self._on_user_msg_webforge)

        # ✅ Quick Features intercept — calculator/timer/notes/todo/etc.
        self._worker.sig_user_msg.connect(self._on_user_msg_quick)
        if _HAS_QUICK:
            def _quick_alarm_post(msg):
                from PyQt5.QtWidgets import QApplication
                QApplication.instance().postEvent(self, _QuickEvent(msg, True))
            _quick_start(notify=_quick_alarm_post)   # alarms roz/one-time chalenge

        # ✅ ALIRA Coder intercept — EARLY (live streaming) + LATE (turnComplete)
        # Early: jaise hi user bolta hai, detect karo (Gemini tool call se PEHLE)
        self._worker.sig_user_live.connect(self._on_user_live_website)
        # Late: fallback agar live ne miss kiya
        self._worker.sig_user_msg.connect(self._on_user_msg_website)
        # ✅ PRIMARY: real Gemini tool call (build_website) — most reliable
        # trigger, doesn't depend on keyword-matching the transcript at all.
        # _trigger_ALIRA_coder's own dedup guard means this is safe to also
        # fire alongside the text-based triggers above without double-running.
        self._worker.sig_build_website.connect(lambda d: self._trigger_ALIRA_coder(d, True))

        self._worker.start_thread()

        if _HAS_OFFICE:
            def _start_loc():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(watch_location_realtime(3))
            threading.Thread(target=_start_loc, daemon=True).start()

    # ── RESIZE ───────────────────────────────────────────────────
    def resizeEvent(self, e):
        super().resizeEvent(e)
        if hasattr(self, '_ALIRA_coder_overlay') and self._ALIRA_coder_overlay:
            if self._ALIRA_coder_overlay.isVisible():
                self._ALIRA_coder_overlay._update_geometry()

    # ── CLOSE ────────────────────────────────────────────────────
    def closeEvent(self, e):
        if _HAS_CAM_VISION and hasattr(self, '_cv_mgr'):
            self._cv_mgr.shutdown()
        if _HAS_SCREEN_SHARE:
            self._ss_mgr.shutdown()
        if getattr(self, '_edge', None):
            self._edge.set_enabled(False)
            self._edge._hide_all()
        if getattr(self, '_guardian', None):
            self._guardian.stop()
        if getattr(self, '_float_orb', None):
            self._float_orb.hide_orb()
        if getattr(self, '_tray', None):
            self._tray.hide()
        self._worker.stop()
        if _HAS_ADV:
            TABBUMemory.save()
        super().closeEvent(e)


# Alias
TITANWindow = TABBUWindow


# ══════════════════════════════════════════════════════════════════
# ENTRY POINT
# ══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    if "--list-devices" in sys.argv:
        list_audio_devices(); sys.exit(0)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    pal = QPalette()
    pal.setColor(QPalette.Window,          QColor("#040810"))
    pal.setColor(QPalette.WindowText,      QColor("#CCDDEEFF"))
    pal.setColor(QPalette.Base,            QColor("#070E1C"))
    pal.setColor(QPalette.Text,            QColor("#CCDDEEFF"))
    pal.setColor(QPalette.Button,          QColor("#0A1428"))
    pal.setColor(QPalette.ButtonText,      QColor("#CCDDEEFF"))
    pal.setColor(QPalette.Highlight,       QColor("#1144AA"))
    pal.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(pal)

    _si = None
    if _HAS_ORB:
        if _autostart.handle_cli_flags():
            sys.exit(0)
        _si = _autostart.make_single_instance()
        if not _si.acquire():
            print("[ALIRA] Pehle se chal rahi hai — us window ko kholne ko bola.")
            sys.exit(0)
    _bg = bool(_HAS_ORB and _autostart.is_background_launch())
    _splash = None
    if not _bg and not os.environ.get("ALIRA_NO_SPLASH") and _prefs.get("splash", True):
        try:
            load_fonts()
            from ALIRA_splash import ALIRASplash
            _splash = ALIRASplash(); _splash.show(); _splash.set_progress(40); app.processEvents()
        except Exception as _e:
            print(f"[ALIRA] splash: {_e}"); _splash = None
    if _splash:
        _startup_hook = lambda p: _splash.jump(p)
    win = TABBUWindow()
    _startup_hook = None
    if _si:
        _si.sig_show.connect(win._show_main)
    if _bg:
        win.start_in_background()
    else:
        def _reveal():                                   # splash 100% hone ke BAAD hi main window
            win.show(); win.raise_(); win.activateWindow()
            QTimer.singleShot(3500, win.first_run_setup)
            QTimer.singleShot(4500, win.ask_name_if_missing)
        if _splash:
            _splash.finish(on_full=_reveal)
        else:
            _reveal()
    sys.exit(app.exec_())