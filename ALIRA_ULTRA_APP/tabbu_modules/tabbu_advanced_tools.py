# -*- coding: utf-8 -*-
"""
TITAN Advanced Tools — v3.0
===========================
OCR: pytesseract + Tesseract (auto-install karta hai)
"""

import os, json, asyncio, datetime, sqlite3, threading, time, re
import subprocess, tempfile, hashlib, ctypes, sys
from pathlib import Path

# ── Optional imports ──────────────────────────────────────
try:    import requests;    HAS_REQUESTS = True
except: HAS_REQUESTS = False

try:    import pyautogui;   HAS_GUI = True
except: HAS_GUI = False

try:    import pyperclip;   HAS_CLIP = True
except: HAS_CLIP = False

try:    from PIL import Image as _PIL, ImageEnhance; HAS_PIL = True
except: HAS_PIL = False

try:    import mss;         HAS_MSS = True
except: HAS_MSS = False

try:    import numpy as np; HAS_NP = True
except: HAS_NP = False

# ── pytesseract setup ─────────────────────────────────────
HAS_TESS = False
_TESS_CMD = ""

def _setup_tesseract():
    """Tesseract dhoondhо ya install karo."""
    global HAS_TESS, _TESS_CMD

    # Known install paths
    paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.join(os.environ.get("LOCALAPPDATA",""),
                     "Programs","Tesseract-OCR","tesseract.exe"),
        os.path.join(os.environ.get("USERPROFILE",""),
                     "AppData","Local","Tesseract-OCR","tesseract.exe"),
    ]

    for p in paths:
        if os.path.exists(p):
            _TESS_CMD = p
            HAS_TESS  = True
            return True

    # Try PATH
    try:
        r = subprocess.run(["where","tesseract"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip():
            _TESS_CMD = r.stdout.strip().splitlines()[0]
            HAS_TESS  = True
            return True
    except Exception:
        pass

    return False

_setup_tesseract()


def _ensure_pytesseract():
    """pytesseract package install karo agar nahi hai."""
    try:
        import pytesseract
        return True
    except ImportError:
        print("[OCR] Installing pytesseract...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pytesseract", "--quiet"],
            capture_output=True
        )
        try:
            import pytesseract
            return True
        except ImportError:
            return False


def _ensure_pillow():
    """Pillow install karo."""
    try:
        from PIL import Image
        return True
    except ImportError:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "Pillow", "--quiet"],
            capture_output=True
        )
        try:
            from PIL import Image
            return True
        except ImportError:
            return False


def _install_tesseract_auto() -> str:
    """
    Tesseract Windows installer download + install karo silently.
    winget ya direct download use karo.
    """
    # Method 1: winget (Windows 10/11)
    try:
        r = subprocess.run(
            ["winget", "install", "UB-Mannheim.TesseractOCR",
             "--silent", "--accept-source-agreements",
             "--accept-package-agreements"],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode == 0:
            _setup_tesseract()
            return "✅ Tesseract installed via winget!"
    except Exception:
        pass

    # Method 2: Chocolatey
    try:
        r = subprocess.run(
            ["choco", "install", "tesseract", "-y", "--no-progress"],
            capture_output=True, text=True, timeout=120
        )
        if r.returncode == 0:
            _setup_tesseract()
            return "✅ Tesseract installed via chocolatey!"
    except Exception:
        pass

    return (
        "⚠️ Auto-install failed. Manual install karo:\n"
        "1. https://github.com/UB-Mannheim/tesseract/wiki se download karo\n"
        "2. Install karo (default path: C:\\Program Files\\Tesseract-OCR\\)\n"
        "3. TITAN restart karo"
    )


# ── Directories ───────────────────────────────────────────
BASE_DIR   = Path(os.path.expanduser("~")) / "Documents" / "TITAN_Data"
MEMORY_DIR = BASE_DIR / "memory"
TASKS_DIR  = BASE_DIR / "tasks"
DEBUG_DIR  = BASE_DIR / "debug"

for d in [BASE_DIR, MEMORY_DIR, TASKS_DIR, DEBUG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

MEMORY_DB  = str(MEMORY_DIR / "TITAN_memory.db")
TASKS_FILE = str(TASKS_DIR  / "tasks.json")

# ── Global state ──────────────────────────────────────────
_GEMINI_API_KEY    = ""
_suggestion_cb     = None
_session_id        = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
_proactive_running = False
_proactive_thread  = None
_last_screen_hash  = ""
_last_suggest_time = 0
SUGGEST_COOLDOWN   = 45


def init_advanced(api_key: str = "", suggestion_cb=None):
    global _GEMINI_API_KEY, _suggestion_cb
    if api_key:   _GEMINI_API_KEY = api_key
    if suggestion_cb: _suggestion_cb = suggestion_cb
    _init_db()
    # Packages ensure karo
    _ensure_pillow()
    _ensure_pytesseract()
    if not HAS_TESS:
        print("[OCR] Tesseract not found. Run: ocr_install() tool")


# ══════════════════════════════════════════════════════════
# 1. CONTEXT MEMORY
# ══════════════════════════════════════════════════════════

def _init_db():
    conn = sqlite3.connect(MEMORY_DB)
    c    = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL, role TEXT NOT NULL,
        content TEXT NOT NULL, session TEXT DEFAULT '')""")
    c.execute("""CREATE TABLE IF NOT EXISTS code_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL, language TEXT NOT NULL,
        filename TEXT NOT NULL, code TEXT NOT NULL,
        description TEXT DEFAULT '', filepath TEXT DEFAULT '')""")
    c.execute("""CREATE TABLE IF NOT EXISTS facts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts TEXT NOT NULL, key TEXT NOT NULL UNIQUE, value TEXT NOT NULL)""")
    conn.commit(); conn.close()

_init_db()

def _db(): return sqlite3.connect(MEMORY_DB)

async def memory_save(role: str, content: str) -> str:
    def _w():
        c = _db()
        c.execute("INSERT INTO messages (ts,role,content,session) VALUES (?,?,?,?)",
                  (datetime.datetime.now().isoformat(), role, content, _session_id))
        c.commit(); c.close()
    await asyncio.to_thread(_w)
    return "saved"

async def memory_search(query: str, limit: int = 8) -> str:
    def _s():
        conn  = _db()
        words = query.lower().split()
        cond  = " OR ".join(["LOWER(content) LIKE ?" for _ in words])
        params = [f"%{w}%" for w in words] + [limit]
        rows  = conn.execute(
            f"SELECT ts,role,content FROM messages WHERE {cond} ORDER BY ts DESC LIMIT ?",
            params).fetchall()
        conn.close(); return rows
    rows = await asyncio.to_thread(_s)
    if not rows: return f"🧠 '{query}' ke baare mein koi purani baat nahi mili"
    out = [f"🧠 Memory — '{query}':\n"]
    for ts, role, content in rows:
        who  = "👤 Tum" if role=="user" else "🌸 TITAN"
        when = ts[:16].replace("T"," ")
        out.append(f"[{when}] {who}:\n  {content[:250]}{'...' if len(content)>250 else ''}")
    return "\n\n".join(out)

async def memory_save_code(language:str, filename:str, code:str,
                            description:str="", filepath:str="") -> str:
    def _w():
        conn = _db()
        conn.execute("INSERT INTO code_history (ts,language,filename,code,description,filepath) VALUES (?,?,?,?,?,?)",
                     (datetime.datetime.now().isoformat(), language, filename, code, description, filepath))
        conn.commit(); conn.close()
    await asyncio.to_thread(_w)
    return f"✅ Code yaad rakha: {filename}"

async def memory_get_last_code(language:str="", query:str="", limit:int=3) -> str:
    def _g():
        conn = _db()
        if language and query:
            rows = conn.execute(
                "SELECT ts,language,filename,code,description,filepath FROM code_history "
                "WHERE LOWER(language) LIKE ? AND (LOWER(description) LIKE ? OR LOWER(filename) LIKE ?) "
                "ORDER BY ts DESC LIMIT ?",
                (f"%{language.lower()}%",f"%{query.lower()}%",f"%{query.lower()}%",limit)).fetchall()
        elif language:
            rows = conn.execute(
                "SELECT ts,language,filename,code,description,filepath FROM code_history "
                "WHERE LOWER(language) LIKE ? ORDER BY ts DESC LIMIT ?",
                (f"%{language.lower()}%",limit)).fetchall()
        elif query:
            rows = conn.execute(
                "SELECT ts,language,filename,code,description,filepath FROM code_history "
                "WHERE LOWER(description) LIKE ? OR LOWER(filename) LIKE ? OR LOWER(code) LIKE ? "
                "ORDER BY ts DESC LIMIT ?",
                (f"%{query.lower()}%",f"%{query.lower()}%",f"%{query.lower()}%",limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT ts,language,filename,code,description,filepath FROM code_history "
                "ORDER BY ts DESC LIMIT ?",(limit,)).fetchall()
        conn.close(); return rows
    rows = await asyncio.to_thread(_g)
    if not rows: return "🧠 Koi code history nahi mili"
    out = []
    for ts,lang,fname,code,desc,fpath in rows:
        when   = ts[:16].replace("T"," ")
        header = f"📄 [{when}] {fname} ({lang})"
        if desc: header += f"\n   {desc}"
        if fpath and os.path.exists(fpath): header += f"\n   📁 {fpath}"
        out.append(f"{header}\n```{lang}\n{code}\n```")
    return "\n\n---\n\n".join(out)

async def memory_save_fact(key:str, value:str) -> str:
    def _w():
        conn = _db()
        conn.execute("INSERT OR REPLACE INTO facts (ts,key,value) VALUES (?,?,?)",
                     (datetime.datetime.now().isoformat(), key.strip(), value.strip()))
        conn.commit(); conn.close()
    await asyncio.to_thread(_w)
    return f"🧠 Yaad kar liya: {key} = {value}"

async def memory_get_fact(key:str) -> str:
    def _g():
        conn = _db()
        row  = conn.execute("SELECT value,ts FROM facts WHERE LOWER(key) LIKE ? ORDER BY ts DESC LIMIT 1",
                            (f"%{key.lower()}%",)).fetchone()
        conn.close(); return row
    row = await asyncio.to_thread(_g)
    if not row: return f"🧠 '{key}' ke baare mein kuch save nahi hai"
    return f"🧠 {key}: {row[0]}"

async def memory_list_facts() -> str:
    def _g():
        conn = _db()
        rows = conn.execute("SELECT key,value,ts FROM facts ORDER BY ts DESC").fetchall()
        conn.close(); return rows
    rows = await asyncio.to_thread(_g)
    if not rows: return "🧠 Koi facts save nahi hain abhi"
    out = ["🧠 Saved Facts:\n"]
    for key,val,ts in rows: out.append(f"  • {key}: {val}")
    return "\n".join(out)

async def memory_stats() -> str:
    def _g():
        conn  = _db()
        msgs  = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        codes = conn.execute("SELECT COUNT(*) FROM code_history").fetchone()[0]
        facts = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        first = conn.execute("SELECT ts FROM messages ORDER BY ts ASC LIMIT 1").fetchone()
        conn.close(); return msgs, codes, facts, first
    msgs,codes,facts,first = await asyncio.to_thread(_g)
    since = first[0][:10] if first else "kuch nahi abhi"
    return f"🧠 TITAN Memory\n  Conversations: {msgs:,}\n  Code files: {codes}\n  Facts: {facts}\n  Since: {since}"

async def memory_clear(confirm:str="") -> str:
    if confirm.upper() != "YES":
        return "⚠️ confirm='YES' do"
    def _c():
        conn = _db()
        conn.execute("DELETE FROM messages"); conn.execute("DELETE FROM code_history")
        conn.commit(); conn.close()
    await asyncio.to_thread(_c)
    return "✅ Memory clear. Facts preserved."


# ══════════════════════════════════════════════════════════
# 2. VOICE NOTES → TASKS
# ══════════════════════════════════════════════════════════

def _tasks_load():
    try:
        with open(TASKS_FILE, encoding="utf-8") as f: return json.load(f)
    except: return []

def _tasks_save(tasks):
    with open(TASKS_FILE,"w",encoding="utf-8") as f:
        json.dump(tasks, f, ensure_ascii=False, indent=2)

def _parse_due(text:str) -> str:
    if not text: return ""
    now  = datetime.datetime.now()
    text = text.lower().strip()
    date = now.date()
    if any(w in text for w in ["kal","tomorrow","tmrw"]):
        date = now.date() + datetime.timedelta(days=1)
    elif any(w in text for w in ["parso","day after"]):
        date = now.date() + datetime.timedelta(days=2)
    day_map = {"monday":0,"tuesday":1,"wednesday":2,"thursday":3,"friday":4,"saturday":5,"sunday":6,
               "mon":0,"tue":1,"wed":2,"thu":3,"fri":4,"sat":5,"sun":6,
               "somvar":0,"mangalvar":1,"budhvar":2,"guruvar":3,"shukravar":4,"shanivar":5,"ravivar":6}
    for name,num in day_map.items():
        if name in text:
            delta = (num - now.weekday()) % 7 or 7
            date  = now.date() + datetime.timedelta(days=delta); break
    hour,minute = 9,0
    is_pm = any(w in text for w in ["pm","shaam","evening","raat","night","dopahar","afternoon"])
    is_am = any(w in text for w in ["am","subah","morning","sawere"])
    m = re.search(r"(\d{1,2}):(\d{2})", text)
    if m: hour,minute = int(m.group(1)),int(m.group(2))
    else:
        m = re.search(r"(\d{1,2})\s*(?:baje|am|pm)?", text)
        if m: hour = int(m.group(1))
    if is_pm and hour < 12: hour += 12
    elif is_am and hour == 12: hour = 0
    try: return datetime.datetime(date.year,date.month,date.day,hour,minute).isoformat()
    except: return ""

def _set_reminder(title:str, due_iso:str):
    try:
        dt        = datetime.datetime.fromisoformat(due_iso)
        ps        = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        task_name = f"TITAN_{hashlib.md5(title.encode()).hexdigest()[:8]}"
        msg       = f"TITAN Reminder: {title[:60]}"
        script    = (
            f"$T = New-ScheduledTaskTrigger -Once -At '{dt.strftime('%m/%d/%Y %H:%M')}';"
            f"$A = New-ScheduledTaskAction -Execute 'powershell.exe' "
            f"-Argument '-WindowStyle Hidden -Command \""
            f"[Windows.UI.Notifications.ToastNotificationManager,"
            f"Windows.UI.Notifications,ContentType=WindowsRuntime]|Out-Null;"
            f"$xml=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(1);"
            f"$xml.GetElementsByTagName(''text'')[0].InnerText=''{msg}'';"
            f"[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier(''TITAN'').Show($xml)"
            f"\"';"
            f"Register-ScheduledTask -TaskName '{task_name}' -Trigger $T -Action $A -Force|Out-Null"
        )
        subprocess.run([ps,"-NoProfile","-ExecutionPolicy","Bypass","-Command",script],
                       capture_output=True,timeout=10)
    except Exception as e: print(f"[Reminder] {e}")

async def task_create(title:str, description:str="", due:str="",
                       priority:str="normal", platform:str="local") -> str:
    due_iso = _parse_due(due)
    tid     = hashlib.md5(f"{title}{time.time()}".encode()).hexdigest()[:8]
    task    = {"id":tid,"title":title,"description":description,"due":due_iso,
               "priority":priority,"status":"pending","platform":platform,
               "created_at":datetime.datetime.now().isoformat()}
    tasks = _tasks_load(); tasks.append(task); _tasks_save(tasks)
    lines = [f"✅ Task created: {title}", f"   ID: {tid}", f"   Priority: {priority}"]
    if due_iso:
        lines.append(f"   Due: {due_iso[:16].replace('T',' ')}")
        _set_reminder(title, due_iso)
        lines.append("   ⏰ Reminder set!")
    if platform == "notion": lines.append(await _notion_add(task))
    elif platform == "trello": lines.append(await _trello_add(task))
    return "\n".join(lines)

async def task_list(status:str="pending", priority:str="") -> str:
    tasks    = _tasks_load()
    now      = datetime.datetime.now().isoformat()
    filtered = [t for t in tasks if t.get("status","pending") == status]
    if priority: filtered = [t for t in filtered if t.get("priority") == priority]
    filtered.sort(key=lambda x: x.get("due","") or "9999")
    if not filtered: return f"📋 Koi {status} tasks nahi"
    icons = {"urgent":"🔥","high":"⬆️","normal":"▶️","low":"⬇️"}
    lines = [f"📋 {status.capitalize()} Tasks ({len(filtered)}):\n"]
    for t in filtered:
        due = t.get("due","")
        overdue = "🔴 " if due and due < now else ""
        icon    = icons.get(t.get("priority","normal"),"▶️")
        dt      = due[:16].replace("T"," ") if due else "No deadline"
        lines.append(f"{overdue}{icon} [{t['id']}] {t['title']}")
        if t.get("description"): lines.append(f"    {t['description'][:80]}")
        lines.append(f"    📅 {dt}")
    return "\n".join(lines)

async def task_done(task_id:str) -> str:
    tasks = _tasks_load()
    for t in tasks:
        if t["id"]==task_id or task_id.lower() in t["title"].lower():
            t["status"]="done"; t["completed_at"]=datetime.datetime.now().isoformat()
            _tasks_save(tasks); return f"✅ Done: {t['title']}"
    return f"❌ Task nahi mila: {task_id}"

async def task_delete(task_id:str) -> str:
    tasks    = _tasks_load()
    new_list = [t for t in tasks if t["id"]!=task_id and task_id.lower() not in t["title"].lower()]
    if len(new_list) < len(tasks): _tasks_save(new_list); return f"🗑️ Deleted: {task_id}"
    return f"❌ Task nahi mila: {task_id}"

async def task_edit(task_id:str, title:str="", description:str="",
                     due:str="", priority:str="") -> str:
    tasks = _tasks_load()
    for t in tasks:
        if t["id"]==task_id or task_id.lower() in t["title"].lower():
            if title: t["title"]=title
            if description: t["description"]=description
            if due: t["due"]=_parse_due(due)
            if priority: t["priority"]=priority
            _tasks_save(tasks); return f"✅ Updated: {t['title']}"
    return f"❌ Task nahi mila: {task_id}"

async def _notion_add(task:dict) -> str:
    token = os.environ.get("NOTION_TOKEN",""); db_id = os.environ.get("NOTION_DB_ID","")
    if not token or not db_id or not HAS_REQUESTS: return "⚠️ Set NOTION_TOKEN + NOTION_DB_ID"
    try:
        headers = {"Authorization":f"Bearer {token}","Content-Type":"application/json","Notion-Version":"2022-06-28"}
        body    = {"parent":{"database_id":db_id},"properties":{
            "Name":{"title":[{"text":{"content":task["title"]}}]},
            "Priority":{"select":{"name":task["priority"].capitalize()}}}}
        if task.get("due"): body["properties"]["Date"]={"date":{"start":task["due"][:10]}}
        r = requests.post("https://api.notion.com/v1/pages",headers=headers,json=body,timeout=10)
        return "✅ Notion mein add hua!" if r.ok else f"⚠️ Notion: {r.status_code}"
    except Exception as e: return f"⚠️ Notion: {e}"

async def _trello_add(task:dict) -> str:
    key=os.environ.get("TRELLO_API_KEY",""); token=os.environ.get("TRELLO_TOKEN",""); lid=os.environ.get("TRELLO_LIST_ID","")
    if not all([key,token,lid,HAS_REQUESTS]): return "⚠️ Set TRELLO_API_KEY + TRELLO_TOKEN + TRELLO_LIST_ID"
    try:
        params={"name":task["title"],"desc":task.get("description",""),"idList":lid,"key":key,"token":token}
        if task.get("due"): params["due"]=task["due"]
        r = requests.post("https://api.trello.com/1/cards",params=params,timeout=10)
        return "✅ Trello mein add hua!" if r.ok else f"⚠️ Trello: {r.status_code}"
    except Exception as e: return f"⚠️ Trello: {e}"


# ══════════════════════════════════════════════════════════
# 3. OCR — pytesseract based (guaranteed working)
# ══════════════════════════════════════════════════════════

async def ocr_install() -> str:
    """Tesseract OCR install karo automatically."""
    _setup_tesseract()   # re-check pehle
    if HAS_TESS:
        return f"✅ Tesseract already installed:\n   {_TESS_CMD}"

    result = await asyncio.to_thread(_install_tesseract_auto)

    # Re-check after install
    _setup_tesseract()
    if HAS_TESS:
        return f"✅ Tesseract install ho gaya!\n   Path: {_TESS_CMD}\n\nAb 'screen padho' bol sakte ho!"

    return result + "\n\nInstall ke baad TITAN restart karo."


async def check_ocr_status() -> str:
    """OCR ka status check karo — Tesseract installed hai ya nahi."""
    _setup_tesseract()

    lines = ["🔍 OCR Status Check:\n"]

    # Tesseract
    lines.append(f"Tesseract found : {'✅ YES' if HAS_TESS else '❌ NO'}")
    if HAS_TESS:
        lines.append(f"Tesseract path  : {_TESS_CMD}")
        # Version check
        try:
            r = subprocess.run([_TESS_CMD, "--version"],
                               capture_output=True, text=True, timeout=5)
            ver = r.stdout.splitlines()[0] if r.stdout else r.stderr.splitlines()[0]
            lines.append(f"Version         : {ver}")
        except Exception:
            pass

    # pytesseract
    try:
        import pytesseract
        lines.append("pytesseract     : ✅ installed")
    except ImportError:
        lines.append("pytesseract     : ❌ not installed — pip install pytesseract")

    # PIL / Pillow
    lines.append(f"Pillow (PIL)    : {'✅' if HAS_PIL else '❌ pip install Pillow'}")

    # mss
    lines.append(f"mss (screenshot): {'✅' if HAS_MSS else '⚠️ pip install mss (optional)'}")

    # pyautogui
    lines.append(f"pyautogui       : {'✅' if HAS_GUI else '⚠️ pip install pyautogui (fallback)'}")

    # numpy
    lines.append(f"numpy           : {'✅' if HAS_NP else '⚠️ pip install numpy'}")

    if not HAS_TESS:
        lines.append("\n❌ FIX: TITAN se bolo 'ocr install karo'")
        lines.append("   Ya CMD mein: winget install UB-Mannheim.TesseractOCR")

    return "\n".join(lines)


def _ocr_with_tesseract(pil_img) -> str:
    """
    pytesseract se OCR karo — multiple strategies try karo.
    """
    if not pil_img:
        return ""

    # Re-check tesseract on every call (startup timing fix)
    if not HAS_TESS:
        _setup_tesseract()

    if not _ensure_pytesseract():
        return ""

    try:
        import pytesseract

        # Tesseract path set karo
        if _TESS_CMD:
            pytesseract.pytesseract.tesseract_cmd = _TESS_CMD
        else:
            # Last resort: common paths try karo
            for tp in [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]:
                if os.path.exists(tp):
                    pytesseract.pytesseract.tesseract_cmd = tp
                    break

        results = []

        # Strategy 1: Original RGB — UI text ke liye best
        try:
            t1 = pytesseract.image_to_string(
                pil_img, config="--psm 6 --oem 3"
            ).strip()
            if t1: results.append(t1)
        except Exception:
            pass

        # Strategy 2: Scale up 3x + grayscale — small text ke liye
        try:
            from PIL import ImageEnhance, ImageFilter, Image as _I
            w, h = pil_img.size
            # 3x scale — dark screens pe bhi kaam karta hai
            big  = pil_img.resize((w * 3, h * 3), _I.LANCZOS)
            gray = big.convert("L")
            # Invert check — dark background pe white text
            import numpy as _np
            arr  = _np.array(gray)
            if arr.mean() < 100:          # dark background — invert karo
                from PIL import ImageOps
                gray = ImageOps.invert(gray)
            # Contrast boost
            gray = ImageEnhance.Contrast(gray).enhance(2.5)
            t2   = pytesseract.image_to_string(
                gray, config="--psm 6 --oem 3"
            ).strip()
            if t2: results.append(t2)
        except Exception:
            pass

        # Strategy 3: Binarize (threshold) — low contrast text ke liye
        try:
            from PIL import Image as _I
            w, h  = pil_img.size
            big   = pil_img.resize((w * 2, h * 2), _I.LANCZOS)
            gray  = big.convert("L")
            # Adaptive threshold via point
            thresh = gray.point(lambda x: 0 if x < 128 else 255, "L")
            t3     = pytesseract.image_to_string(
                thresh, config="--psm 6 --oem 3"
            ).strip()
            if t3: results.append(t3)
        except Exception:
            pass

        # Best result choose karo — longest non-empty
        if not results:
            return ""

        best = max(results, key=lambda x: len(x))
        return best

    except pytesseract.TesseractNotFoundError:
        print("[OCR] Tesseract not found. TITAN se bolo: 'OCR install karo'")
        return ""
    except Exception as e:
        print(f"[OCR] Error: {e}")
        return ""


def _take_screenshot(region=None):
    """Fast screenshot — mss double-grab bug fixed."""
    try:
        if HAS_MSS and HAS_PIL:
            with mss.mss() as sct:
                mon  = region if region else sct.monitors[1]
                shot = sct.grab(mon)   # ek baar grab
                img  = _PIL.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
                return img
    except Exception:
        pass
    if HAS_GUI:
        img = pyautogui.screenshot()
        if region:
            l = region.get("left", 0); t = region.get("top", 0)
            w = region.get("width", 1920); h = region.get("height", 1080)
            img = img.crop((l, t, l + w, t + h))
        return img
    return None


def _get_active_hwnd_rect():
    try:
        class RECT(ctypes.Structure):
            _fields_ = [("left",ctypes.c_long),("top",ctypes.c_long),
                        ("right",ctypes.c_long),("bottom",ctypes.c_long)]
        rect = RECT()
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        return {"left":max(0,rect.left),"top":max(0,rect.top),
                "width":max(100,rect.right-rect.left),"height":max(100,rect.bottom-rect.top)}
    except Exception:
        return None


# ══════════════════════════════════════════════════════════
# 4. CODE DEBUGGER
# ══════════════════════════════════════════════════════════

def _ask_gemini(prompt:str, image_b64:str="") -> str:
    if not _GEMINI_API_KEY or not HAS_REQUESTS: return ""
    try:
        # ✅ FIX: gemini-2.0-flash retired hai ("no longer available" 404)
        parts = [{"text": prompt}]
        if image_b64:
            parts.insert(0, {"inline_data":{"mime_type":"image/png","data":image_b64}})
        # ✅ model fallback chain (429/404/503) — gemini_rest
        from TABBU_modules.gemini_rest import generate as _gen, text_of as _txt
        data, _used = _gen({"contents":[{"parts":parts}]}, _GEMINI_API_KEY, timeout=30)
        return _txt(data)
    except Exception as e: print(f"[Gemini] {e}")
    return ""

def _img_to_b64(pil_img) -> str:
    if not pil_img or not HAS_PIL: return ""
    import io, base64
    buf = io.BytesIO(); pil_img.save(buf,"PNG")
    return base64.b64encode(buf.getvalue()).decode()

def _open_in_vscode(filepath:str, line:int=1):
    try:
        vscode_paths = [
            os.path.join(os.environ.get("LOCALAPPDATA",""),"Programs","Microsoft VS Code","Code.exe"),
            r"C:\Program Files\Microsoft VS Code\Code.exe",
        ]
        vsc = next((p for p in vscode_paths if os.path.exists(p)), None)
        if vsc: subprocess.Popen([vsc,"--goto",f"{filepath}:{line}"]); return True
        r = subprocess.run(["where","code"],capture_output=True,text=True)
        if r.returncode == 0: subprocess.Popen(["code","--goto",f"{filepath}:{line}"]); return True
    except Exception: pass
    return False

def _apply_fix_to_file(filepath:str, original_code:str, fixed_code:str) -> bool:
    try:
        path   = Path(filepath)
        if not path.exists(): return False
        backup = path.with_suffix(path.suffix+".bak")
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        content = path.read_text(encoding="utf-8")
        if original_code and original_code in content:
            path.write_text(content.replace(original_code, fixed_code, 1), encoding="utf-8")
        else:
            path.write_text(fixed_code, encoding="utf-8")
        return True
    except Exception: return False

def _offline_error_fix(error_text:str) -> str:
    err = error_text.lower()
    if "modulenotfounderror" in err or "no module named" in err:
        m = re.search(r"no module named '([^']+)'", err)
        pkg = m.group(1) if m else "package"
        return f"**Root Cause:** `{pkg}` install nahi\n**Fix:**\n```\npip install {pkg}\n```"
    elif "syntaxerror" in err:
        return "**Root Cause:** Syntax error — bracket/colon/indent missing\n**Fix:** Error line check karo"
    elif "nameerror" in err:
        v = re.search(r"name '([^']+)' is not defined", err)
        vn = v.group(1) if v else "vTITANble"
        return f"**Root Cause:** `{vn}` defined nahi\n**Fix:**\n```python\n{vn} = None\n```"
    elif "typeerror" in err:
        return "**Root Cause:** Wrong data type\n**Fix:** `int(val)` ya `str(val)` use karo"
    elif "permissionerror" in err:
        return "**Root Cause:** Permission denied\n**Fix:** Admin mode mein CMD chalao"
    elif "indentationerror" in err:
        return "**Root Cause:** Indentation galat\n**Fix:** Sirf spaces use karo (4 per level)"
    return f"**Error:**\n{error_text[:300]}\n\n**Suggestion:** Full traceback TITAN ko do"

async def debug_screenshot(save_path:str="") -> str:
    """Screen screenshot lo aur errors dhoondhо."""
    def _cap(): return _take_screenshot(_get_active_hwnd_rect())
    img = await asyncio.to_thread(_cap)
    if not img: return "❌ Screenshot nahi le saka"
    if not save_path:
        save_path = str(DEBUG_DIR / f"debug_{datetime.datetime.now().strftime('%H%M%S')}.png")
    img.save(save_path)

    if not HAS_TESS:
        return (f"📸 Screenshot: {save_path}\n"
                f"⚠️ OCR ke liye Tesseract install karo: 'ocr install karo' bolo TITAN ko")

    text = await asyncio.to_thread(_ocr_with_tesseract, img)
    error_kw = ["error","exception","traceback","failed","syntaxerror","typeerror","nameerror"]
    found = [l for l in text.lower().splitlines() if any(k in l for k in error_kw)]

    if found:
        return (f"📸 {save_path}\n🔴 Errors found:\n" +
                "\n".join(f"  • {e}" for e in found[:10]) +
                f"\n\nFull text:\n{text[:500]}")
    return f"📸 {save_path}\n📄 Screen text:\n{text[:600]}"

async def debug_error(error_text:str="", file_path:str="",
                       take_screenshot:bool=True) -> str:
    """Error analyze karo aur fix suggest karo."""
    img = None; img_b64 = ""; file_code = ""

    if take_screenshot and not error_text:
        def _snap(): return _take_screenshot(_get_active_hwnd_rect())
        img = await asyncio.to_thread(_snap)
        if img:
            img_b64    = await asyncio.to_thread(_img_to_b64, img)
            error_text = await asyncio.to_thread(_ocr_with_tesseract, img)

    if not error_text:
        return "❌ Error text nahi mila — error_text do ya screen pe error dikhao"

    if file_path and os.path.exists(file_path):
        try: file_code = Path(file_path).read_text(encoding="utf-8")
        except: pass

    code_section = (f"CODE FILE ({file_path}):\n```\n{file_code[:3000]}\n```"
                    if file_code else "")

    prompt = (
        "You are an expert programmer debugging assistant.\n\n"
        f"ERROR:\n{error_text[:2000]}\n\n"
        f"{code_section}\n\n"
        "Provide:\n"
        "1. Root Cause — kya galat hai\n"
        "2. Fix — exact solution\n"
        "3. Fixed Code — corrected version\n\n"
        "Reply in Hinglish. Be concise."
    )

    fix = await asyncio.to_thread(_ask_gemini, prompt, img_b64)
    if not fix: fix = _offline_error_fix(error_text)

    note = ""
    if img:
        sp = str(DEBUG_DIR / f"error_{datetime.datetime.now().strftime('%H%M%S')}.png")
        img.save(sp); note = f"\n📸 Screenshot: {sp}"

    return f"🐛 Debug Analysis:\n\n{fix}{note}"

async def debug_apply_fix(file_path:str, fixed_code:str,
                           original_code:str="", open_vscode:bool=True) -> str:
    """Fix file mein apply karo — backup ban jaati hai."""
    if not file_path: return "❌ file_path dena zaroori hai"
    path = Path(file_path)
    if not path.exists():
        code_dir = Path(os.path.expanduser("~")) / "Documents" / "TITAN_Code"
        candidates = list(code_dir.glob(f"*{path.name}*"))
        if candidates: file_path = str(candidates[0]); path = Path(file_path)
        else: return f"❌ File nahi mili: {file_path}"

    ok = await asyncio.to_thread(_apply_fix_to_file, file_path, original_code, fixed_code)
    if not ok: return f"❌ Fix apply nahi hua: {file_path}"

    lines = [f"✅ Fix applied: {path.name}", f"   📁 {file_path}", f"   💾 Backup: {file_path}.bak"]
    if open_vscode:
        opened = await asyncio.to_thread(_open_in_vscode, file_path)
        lines.append("   💻 VS Code mein khula" if opened else "   📝 Default editor mein khula")
        if not opened:
            try: os.startfile(file_path)
            except: pass
    return "\n".join(lines)

async def debug_run_and_check(file_path:str) -> str:
    """Code run karo — error aaye toh auto-analyze karo."""
    if not os.path.exists(file_path): return f"❌ File nahi mili: {file_path}"
    ext     = Path(file_path).suffix.lower()
    cmd_map = {".py":["python",file_path],".js":["node",file_path],".bat":[file_path]}
    cmd     = cmd_map.get(ext)
    if not cmd: return f"❌ {ext} directly run nahi kar sakta"
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=30, cwd=str(Path(file_path).parent))
        if r.returncode == 0:
            return f"✅ Run successful!\n\nOutput:\n{r.stdout.strip()[:500]}"
        error = r.stderr.strip() or r.stdout.strip()
        fix   = await debug_error(error_text=error, file_path=file_path, take_screenshot=False)
        return f"🔴 Error:\n{error[:300]}\n\n{fix}"
    except subprocess.TimeoutExpired:
        return "⏱️ 30s mein complete nahi hua — infinite loop check karo"
    except Exception as e: return f"❌ Run error: {e}"


# ══════════════════════════════════════════════════════════
# 5. SCREEN READ (Tesseract based)
# ══════════════════════════════════════════════════════════

async def read_screen(region: str = "full") -> str:
    """
    Screen pe jo text dikh raha hai wo padho.
    Tesseract OCR use karta hai.
    region: full | top | bottom | left | right | center
    """
    # Tesseract check — re-run setup in case it was installed after start
    if not HAS_TESS:
        _setup_tesseract()

    if not HAS_TESS:
        return (
            "❌ Tesseract OCR install nahi hai.\n"
            "TITAN se bolo: 'OCR install karo'\n"
            "Ya manually: winget install UB-Mannheim.TesseractOCR"
        )

    # Screenshot lo — fixed version
    def _grab():
        try:
            if HAS_MSS and HAS_PIL:
                with mss.mss() as sct:
                    mon  = sct.monitors[1]        # primary monitor
                    shot = sct.grab(mon)           # single grab
                    return _PIL.frombytes(
                        "RGB", shot.size, shot.bgra, "raw", "BGRX"
                    )
        except Exception as e:
            print(f"[Screenshot MSS] {e}")
        try:
            if HAS_GUI:
                return pyautogui.screenshot()
        except Exception as e:
            print(f"[Screenshot GUI] {e}")
        return None

    img = await asyncio.to_thread(_grab)
    if not img:
        return "❌ Screenshot nahi le saka — pyautogui ya mss install karo"

    print(f"[Screen] Screenshot size: {img.size}")

    # Crop region
    w, h = img.size
    crops = {
        "full":   (0,     0,     w,     h),
        "top":    (0,     0,     w,     h // 2),
        "bottom": (0,     h // 2, w,    h),
        "left":   (0,     0,     w // 2, h),
        "right":  (w // 2, 0,   w,     h),
        "center": (w // 4, h // 4, 3 * w // 4, 3 * h // 4),
    }
    img = img.crop(crops.get(region.lower(), (0, 0, w, h)))
    print(f"[Screen] Cropped to: {img.size} ({region})")

    text = await asyncio.to_thread(_ocr_with_tesseract, img)
    print(f"[Screen] OCR result length: {len(text)}")

    if not text or len(text.strip()) < 3:
        # Save screenshot for debugging
        dbg_path = str(DEBUG_DIR / "screen_debug.png")
        try:
            img.save(dbg_path)
            return (
                f"❌ Screen pe koi text nahi mila.\n"
                f"   Screenshot saved: {dbg_path}\n"
                f"   Check karo ki Tesseract sahi install hua: {_TESS_CMD}"
            )
        except Exception:
            return "❌ Screen pe koi text nahi mila aur screenshot save bhi nahi hua."

    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 1]
    return f"🖥️ Screen ({region}):\n" + "\n".join(lines[:80])

async def read_active_window() -> str:
    """Active window ka text padho."""
    if not HAS_TESS:
        return "❌ Tesseract install karo: 'ocr install karo' bolo"

    try:
        buf  = ctypes.create_unicode_buffer(512)
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
        title = buf.value.strip()
    except: title = ""

    rect = _get_active_hwnd_rect()
    img  = await asyncio.to_thread(_take_screenshot, rect)
    if not img: return await read_screen("full")

    text = await asyncio.to_thread(_ocr_with_tesseract, img)
    if not text or len(text.strip()) < 3: return await read_screen("full")

    lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 1]
    return f"🪟 {title}:\n" + "\n".join(lines[:80])


# ══════════════════════════════════════════════════════════
# 6. PROACTIVE SUGGESTIONS
# ══════════════════════════════════════════════════════════

def _screen_hash() -> str:
    try:
        if HAS_MSS and HAS_PIL:
            with mss.mss() as sct:
                m = sct.monitors[1]
                s = sct.grab({"left":m["left"],"top":m["top"],"width":320,"height":240})
                return hashlib.md5(bytes(s.raw)).hexdigest()
        elif HAS_GUI:
            import io
            img = pyautogui.screenshot(region=(0,0,320,240))
            b   = io.BytesIO(); img.save(b,"PNG")
            return hashlib.md5(b.getvalue()).hexdigest()
    except Exception: pass
    return str(time.time())

def _active_window_title() -> str:
    try:
        buf  = ctypes.create_unicode_buffer(512)
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 512)
        return buf.value.strip()
    except: return ""

def _suggest_from_context(title:str) -> str:
    t = title.lower()
    if any(w in t for w in ["error","exception","traceback","crash","failed"]):
        return "🔴 Error dikh raha hai! 'Is error ko debug karo' bol do — main fix kar dungi!"
    if any(w in t for w in ["form","register","signup","apply","login","checkout"]):
        return "📝 Form dikh raha hai — 'form fill karo' bolo, main help kar sakti hoon!"
    if any(w in t for w in ["vs code","vscode","pycharm","code.exe","notepad++","sublime"]):
        return "💻 Code likh rahe ho? 'Debug karo' ya 'optimize karo' bol do!"
    if any(w in t for w in ["google","search","stackoverflow","github","chrome","firefox","edge"]):
        return "🔍 Search kar rahe ho? Batao — main directly answer de sakti hoon!"
    if "youtube" in t or "vlc" in t or "media player" in t:
        return "🎬 Video dekh rahe ho? 'Summarize karo' ya 'notes banao' bol do!"
    if any(w in t for w in ["outlook","gmail","mail","thunderbird"]):
        return "📧 Email khuli hai — 'reply draft karo' ya 'summarize karo' bol do!"
    if any(w in t for w in ["excel","spreadsheet","sheets"]):
        return "📊 Data kaam chal raha hai? 'Chart banao' ya 'analyze karo' bol do!"
    if any(w in t for w in [".pdf","acrobat","foxit","pdf viewer"]):
        return "📄 PDF khuli hai — 'PDF summarize karo' bol do!"
    if "whatsapp" in t:
        return "💬 WhatsApp khula hai — 'reply draft karo' bol do, main likh dungi!"
    if "task manager" in t:
        return "⚙️ Task Manager khula — 'heavy processes band karo' bol do!"
    return ""

def _proactive_loop():
    global _last_screen_hash, _last_suggest_time
    while _proactive_running:
        try:
            now   = time.time()
            title = _active_window_title()
            h     = _screen_hash()
            if h != _last_screen_hash and now - _last_suggest_time > SUGGEST_COOLDOWN:
                _last_screen_hash = h
                suggestion = _suggest_from_context(title)
                if suggestion and _suggestion_cb:
                    _suggestion_cb(suggestion)
                    _last_suggest_time = now
        except Exception: pass
        time.sleep(8)

async def proactive_on() -> str:
    global _proactive_running, _proactive_thread
    if _proactive_running: return "ℹ️ Already ON"
    _proactive_running = True
    _proactive_thread  = threading.Thread(target=_proactive_loop, daemon=True)
    _proactive_thread.start()
    return "✅ Proactive Mode ON! TITAN screen dekhti rahegi aur suggest karegi."

async def proactive_off() -> str:
    global _proactive_running
    _proactive_running = False
    return "✅ Proactive Mode OFF"

async def proactive_check() -> str:
    title      = _active_window_title()
    suggestion = _suggest_from_context(title)
    if suggestion: return f"💡 {suggestion}"
    return f"🖥️ Active: '{title}'\n   Koi specific suggestion nahi abhi."


# ══════════════════════════════════════════════════════════
# TOOL DECLARATIONS
# ══════════════════════════════════════════════════════════

def _p(props:dict, req:list=None) -> dict:
    s = {"type":"object","properties":{k:{"type":v} for k,v in props.items()}}
    if req: s["required"] = req
    return s

ADVANCED_TOOL_DECLARATIONS = [
    # Memory
    {"name":"memory_search","description":"Purani conversations mein search karo. 'Pichli baar tune X ke baare mein kya kaha'","parameters":_p({"query":"string","limit":"integer"},["query"])},
    {"name":"memory_get_last_code","description":"Pichla likha code wapas do. 'Tune pichla Python code kya likha'","parameters":_p({"language":"string","query":"string","limit":"integer"})},
    {"name":"memory_save_fact","description":"Important info permanently save karo. 'Mera phone yaad rakho'","parameters":_p({"key":"string","value":"string"},["key","value"])},
    {"name":"memory_get_fact","description":"Pehle save ki gayi info wapas do","parameters":_p({"key":"string"},["key"])},
    {"name":"memory_list_facts","description":"Saari saved facts list karo","parameters":_p({})},
    {"name":"memory_stats","description":"Memory ka overview","parameters":_p({})},
    {"name":"memory_clear","description":"Memory clear karo (confirm=YES required)","parameters":_p({"confirm":"string"},["confirm"])},
    # OCR Install + Status
    {"name":"ocr_install","description":"Tesseract OCR install karo automatically — screen read karne ke liye zaroori. 'OCR install karo' bole toh use karo.","parameters":_p({})},
    {"name":"check_ocr_status","description":"OCR ka status check karo — Tesseract installed hai ya nahi, kya packages missing hain","parameters":_p({})},
    # Screen Read
    {"name":"read_screen","description":"Screen pe jo text dikh raha hai wo padho. region: full/top/bottom/left/right/center","parameters":_p({"region":"string"})},
    {"name":"read_active_window","description":"Active window ka poora text padho","parameters":_p({})},
    # Tasks
    {"name":"task_create","description":"Task banao. 'Kal 3 baje doctor appointment' → task + reminder. platform: local/notion/trello","parameters":_p({"title":"string","description":"string","due":"string","priority":"string","platform":"string"},["title"])},
    {"name":"task_list","description":"Tasks list karo — pending/done/overdue","parameters":_p({"status":"string","priority":"string"})},
    {"name":"task_done","description":"Task complete mark karo","parameters":_p({"task_id":"string"},["task_id"])},
    {"name":"task_delete","description":"Task delete karo","parameters":_p({"task_id":"string"},["task_id"])},
    {"name":"task_edit","description":"Task update karo","parameters":_p({"task_id":"string","title":"string","description":"string","due":"string","priority":"string"},["task_id"])},
    # Debugger
    {"name":"debug_screenshot","description":"Screen screenshot lo aur errors dhoondhо. 'Is error ko dekho' type commands ke liye","parameters":_p({"save_path":"string"})},
    {"name":"debug_error","description":"Error analyze karo aur fix suggest karo. error_text paste karo ya take_screenshot=true","parameters":_p({"error_text":"string","file_path":"string","take_screenshot":"boolean"})},
    {"name":"debug_apply_fix","description":"Fix file mein apply karo. Backup automatic ban jaati hai. VS Code mein khulta hai.","parameters":_p({"file_path":"string","fixed_code":"string","original_code":"string","open_vscode":"boolean"},["file_path","fixed_code"])},
    {"name":"debug_run_and_check","description":"Code run karo — error aaye toh auto-analyze karo","parameters":_p({"file_path":"string"},["file_path"])},
    # Proactive
    {"name":"proactive_on","description":"Proactive mode ON — TITAN screen dekhegi aur help offer karegi","parameters":_p({})},
    {"name":"proactive_off","description":"Proactive mode OFF","parameters":_p({})},
    {"name":"proactive_check","description":"Abhi screen dekho aur suggestion do","parameters":_p({})},
]

ADVANCED_TOOL_MAP = {
    "memory_search":memory_search,"memory_get_last_code":memory_get_last_code,
    "memory_save_fact":memory_save_fact,"memory_get_fact":memory_get_fact,
    "memory_list_facts":memory_list_facts,"memory_stats":memory_stats,"memory_clear":memory_clear,
    "ocr_install":ocr_install,"check_ocr_status":check_ocr_status,
    "read_screen":read_screen,"read_active_window":read_active_window,
    "task_create":task_create,"task_list":task_list,"task_done":task_done,
    "task_delete":task_delete,"task_edit":task_edit,
    "debug_screenshot":debug_screenshot,"debug_error":debug_error,
    "debug_apply_fix":debug_apply_fix,"debug_run_and_check":debug_run_and_check,
    "proactive_on":proactive_on,"proactive_off":proactive_off,"proactive_check":proactive_check,
}

async def advanced_dispatch(name:str, args:dict) -> str:
    fn = ADVANCED_TOOL_MAP.get(name)
    if fn: return await fn(**args)
    return f"❌ Tool nahi mila: {name}"