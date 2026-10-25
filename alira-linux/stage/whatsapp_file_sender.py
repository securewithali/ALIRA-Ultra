# -*- coding: utf-8 -*-
"""
TITAN — WhatsApp File Sender v4
================================
File dhoondhо — C drive, D drive, OneDrive, everywhere.
"""

import os, asyncio, time, subprocess, ctypes, string
from pathlib import Path
from datetime import datetime

try:    import pyautogui;         HAS_GUI = True
except: HAS_GUI = False

try:    import pyperclip;         HAS_CLIP = True
except: HAS_CLIP = False

try:    import pygetwindow as gw; HAS_GW = True
except: HAS_GW = False

# ── Constants ─────────────────────────────────────────────
WA_APP_ID  = r"shell:AppsFolder\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"
USER_HOME  = Path(os.path.expanduser("~"))

SENDABLE_EXTS = {
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".txt", ".csv", ".rtf", ".odt", ".ods",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".svg",
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".3gp", ".flv",
    ".mp3", ".wav", ".aac", ".m4a", ".ogg",
    ".zip", ".rar", ".7z", ".tar", ".gz",
    ".py", ".js", ".html", ".css", ".json", ".xml", ".apk",
}

TYPE_MAP = {
    "pdf":        {".pdf"},
    "word":       {".doc", ".docx", ".odt"},
    "excel":      {".xls", ".xlsx", ".csv", ".ods"},
    "powerpoint": {".ppt", ".pptx"},
    "image":      {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"},
    "photo":      {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"},
    "video":      {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".3gp"},
    "audio":      {".mp3", ".wav", ".aac", ".m4a", ".ogg"},
    "music":      {".mp3", ".wav", ".aac", ".m4a", ".ogg"},
    "zip":        {".zip", ".rar", ".7z", ".tar", ".gz"},
    "text":       {".txt", ".rtf"},
    "code":       {".py", ".js", ".html", ".css", ".json"},
    "document":   {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt"},
}

SKIP_DIRS = {
    '$recycle.bin', 'system volume information', 'windows',
    'program files', 'program files (x86)', 'programdata',
    'appdata', '$windows.~bt', '$windows.~ws', 'recovery',
    'system32', 'syswow64', 'node_modules', '__pycache__',
    '.git', 'boot', 'perflogs', 'intel', 'amd',
}


# ══════════════════════════════════════════════════════════
# DRIVE + FOLDER DETECTION
# ══════════════════════════════════════════════════════════

def _get_all_drives() -> list:
    """Saari available drives dhoondhо — C, D, E, F etc."""
    drives = []
    for letter in string.ascii_uppercase:
        drive = f"{letter}:\\"
        try:
            if os.path.exists(drive):
                os.listdir(drive)  # readable check
                drives.append(Path(drive))
        except PermissionError:
            pass
        except Exception:
            pass
    return drives


def _get_search_roots(folder: str = "") -> list:
    """Search roots decide karo — folder specify hai ya nahi."""

    if folder:
        fl = folder.lower().strip()

        # Direct absolute path
        if len(folder) > 2 and os.path.isdir(folder):
            return [Path(folder)]

        # Drive letter — "D:\", "D drive", "D:\\" (English-only)
        if fl and fl[0].isalpha() and len(fl) <= 8:
            for suffix in [':', ':\\', ':/', ' drive']:
                if fl.endswith(suffix) or fl == fl[0]:
                    drive = f"{fl[0].upper()}:\\"
                    if os.path.exists(drive):
                        return [Path(drive)]

        matched = []

        # Known folder keywords (English only)
        folder_map = {
            "desktop":   ["Desktop"],
            "documents": ["Documents"],
            "downloads": ["Downloads"],
            "pictures":  ["Pictures"],
            "photos":    ["Pictures"],
            "videos":    ["Videos"],
            "music":     ["Music"],
        }

        for key, subs in folder_map.items():
            if key in fl or fl in key:
                # Local + OneDrive
                for od in ["", "OneDrive", "OneDrive - Personal"]:
                    base = USER_HOME / od if od else USER_HOME
                    if not base.exists():
                        continue
                    for sub in subs:
                        p = base / sub
                        if p.exists():
                            matched.append(p)

        # OneDrive keyword
        if "onedrive" in fl or "one drive" in fl:
            for od in ["OneDrive", "OneDrive - Personal", "OneDrive - Business"]:
                p = USER_HOME / od
                if p.exists():
                    matched.append(p)

        # All drives mein us naam ka folder dhoondhо
        if not matched:
            all_drives = _get_all_drives()
            for drive in all_drives:
                # Direct folder in drive root
                p = drive / folder
                if p.exists() and p.is_dir():
                    matched.append(p)
                # In Users folder
                users_dir = drive / "Users" / USER_HOME.name
                if users_dir.exists():
                    p2 = users_dir / folder
                    if p2.exists() and p2.is_dir():
                        matched.append(p2)
                # Deep search in drive root (1 level)
                try:
                    for item in drive.iterdir():
                        if item.is_dir() and fl in item.name.lower():
                            matched.append(item)
                except Exception:
                    pass

        return matched if matched else [USER_HOME]

    # ── No folder — search order ──────────────────────────
    roots = []

    # 1. User common folders (fast, most files here)
    for sub in ["Desktop", "Documents", "Downloads",
                "Pictures", "Videos", "Music"]:
        p = USER_HOME / sub
        if p.exists():
            roots.append(p)

    # 2. OneDrive
    for od in ["OneDrive", "OneDrive - Personal", "OneDrive - Business"]:
        p = USER_HOME / od
        if p.exists():
            roots.append(p)

    # 3. User home root
    roots.append(USER_HOME)

    # 4. Other drives (D, E, F...)
    for drive in _get_all_drives():
        if str(drive).upper().startswith("C"):
            continue  # C already covered above
        roots.append(drive)

    # 5. C:\ last (slowest)
    c = Path("C:\\")
    if c.exists():
        roots.append(c)

    return roots


# ══════════════════════════════════════════════════════════
# FILE FINDER
# ══════════════════════════════════════════════════════════

def _find_files(filename: str = "", folder: str = "",
                file_type: str = "", newest: bool = False) -> list:
    """os.walk se sabhi drives mein file dhoondhо."""
    results = []
    seen    = set()

    # Extension filter
    ext_filter = set()
    if file_type:
        ft = file_type.lower().strip().lstrip(".")
        for key, exts in TYPE_MAP.items():
            if key in ft or ft in key:
                ext_filter.update(exts)
        if not ext_filter:
            ext_filter.add("." + ft if not ft.startswith(".") else ft)

    fname_low = filename.lower().strip() if filename else ""
    roots     = _get_search_roots(folder)

    for root_dir in roots:
        try:
            for root, dirs, files in os.walk(str(root_dir), followlinks=False):
                # Skip system dirs
                dirs[:] = [
                    d for d in dirs
                    if not d.startswith('.')
                    and d.lower() not in SKIP_DIRS
                ]

                for f in files:
                    if f.startswith('.'):
                        continue

                    fp  = os.path.normpath(os.path.join(root, f))
                    if fp in seen:
                        continue

                    ext = Path(f).suffix.lower()

                    # Extension check
                    if ext_filter:
                        if ext not in ext_filter:
                            continue
                    elif ext not in SENDABLE_EXTS:
                        continue

                    # Filename match
                    if fname_low and fname_low not in f.lower():
                        continue

                    results.append(fp)
                    seen.add(fp)

                    if len(results) >= 100:
                        break

                if len(results) >= 100:
                    break

        except PermissionError:
            pass
        except Exception as e:
            print(f"[Find] {root_dir}: {e}")

        if len(results) >= 100:
            break

    # Sort newest first
    try:
        results.sort(key=lambda x: os.path.getmtime(x), reverse=True)
    except Exception:
        pass

    return [results[0]] if (newest and results) else results[:20]


async def find_file(filename: str = "", folder: str = "",
                    file_type: str = "", newest: bool = False, **kwargs) -> str:
    """File dhoondhо — sabhi drives mein — aur list karo."""
    files = await asyncio.to_thread(
        _find_files, filename, folder, file_type, newest
    )

    if not files:
        drives = [str(d) for d in _get_all_drives()]
        parts  = []
        if filename:  parts.append(f"'{filename}'")
        if folder:    parts.append(f"folder '{folder}'")
        if file_type: parts.append(f"type '{file_type}'")
        return (
            f"❌ File nahi mili: {', '.join(parts) or 'koi bhi'}\n"
            f"   Searched drives: {', '.join(drives)}\n"
            f"   Sahi naam ya folder batao"
        )

    lines = [f"📁 {len(files)} file(s) mili:\n"]
    for i, fp in enumerate(files[:10], 1):
        name = Path(fp).name
        try:
            size  = os.path.getsize(fp)
            mtime = datetime.fromtimestamp(
                os.path.getmtime(fp)).strftime("%d-%m-%Y")
            sz = (f"{size/1024:.0f}KB"
                  if size < 1048576 else f"{size/1048576:.1f}MB")
        except Exception:
            sz = "?"; mtime = "?"
        lines.append(f"  {i}. {name} ({sz}, {mtime})")
        lines.append(f"     📍 {fp}")
    if len(files) > 10:
        lines.append(f"\n  ...aur {len(files)-10} files")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════
# WHATSAPP HELPERS
# ══════════════════════════════════════════════════════════

def _set_clip(text: str):
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        ctypes.windll.user32.PostMessageW(hwnd, 0x0050, 0, 0x04090409)
        time.sleep(0.05)
    except Exception:
        pass
    try:
        pyperclip.copy(text)
    except Exception:
        pass


async def _focus_or_open_wa() -> bool:
    """WhatsApp window dhoondhо ya open karo — EXE compatible."""
    import ctypes as _ct
    _u32 = _ct.windll.user32

    def _find_wa_hwnd():
        found = []
        def _cb(hwnd, _):
            try:
                l = _u32.GetWindowTextLengthW(hwnd)
                if l > 0:
                    b = _ct.create_unicode_buffer(l + 1)
                    _u32.GetWindowTextW(hwnd, b, l + 1)
                    if "WhatsApp" in b.value and _u32.IsWindowVisible(hwnd):
                        found.append(hwnd)
            except Exception:
                pass
            return True
        _PROC = _ct.WINFUNCTYPE(_ct.c_bool, _ct.c_int, _ct.c_int)
        _u32.EnumWindows(_PROC(_cb), 0)
        return found[0] if found else None

    def _bring_front(hwnd):
        try:
            _u32.ShowWindow(hwnd, 9)
            time.sleep(0.3)
            _u32.SetForegroundWindow(hwnd)
            _u32.BringWindowToTop(hwnd)
            _u32.ShowWindow(hwnd, 3)
            time.sleep(1.0)
            return True
        except Exception:
            return False

    hwnd = _find_wa_hwnd()
    if hwnd:
        return _bring_front(hwnd)

    opened = False
    try:
        ps = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        subprocess.Popen([ps, "-NoProfile", "-Command", f"Start-Process '{WA_APP_ID}'"],
                         creationflags=subprocess.CREATE_NO_WINDOW)
        opened = True
    except Exception:
        pass
    if not opened:
        try:
            subprocess.Popen(["cmd", "/c", "start", "whatsapp:"],
                             creationflags=subprocess.CREATE_NO_WINDOW)
            opened = True
        except Exception:
            pass
    if not opened:
        return False

    for _ in range(18):
        await asyncio.sleep(0.5)
        hwnd = _find_wa_hwnd()
        if hwnd:
            return _bring_front(hwnd)

    print("[WA] Window detect nahi hua, continue anyway...")
    await asyncio.sleep(1.0)
    return True


async def _wa_search_contact(contact: str):
    """
    WhatsApp mein contact search karo aur chat open karo.
    Ctrl+F se search bar open → contact type karo → first result pe Enter.
    """
    import pyautogui as _pag

    contact = contact.strip()
    if not contact:
        return

    # Step 1: Search bar open karo
    _pag.hotkey('ctrl', 'f')
    await asyncio.sleep(1.2)

    # Step 2: Previous text clear karo
    _pag.hotkey('ctrl', 'a')
    await asyncio.sleep(0.15)
    _pag.press('delete')
    await asyncio.sleep(0.2)

    # Step 3: Contact naam type karo (clipboard se — special chars ke liye)
    _set_clip(contact)
    _pag.hotkey('ctrl', 'v')
    await asyncio.sleep(2.8)   # Results load hone ka wait

    # Step 4: First result select karo
    _pag.press('down')
    await asyncio.sleep(0.5)
    _pag.press('enter')
    await asyncio.sleep(2.0)   # Chat open hone ka wait

    # Step 5: Escape se search bar band karo — chat focus aaye
    _pag.hotkey('ctrl', 'v')

    await asyncio.sleep(0.5)


def _copy_file_to_clipboard(filepath: str) -> bool:
    try:
        safe = filepath.replace("'", "`'")
        ps   = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
        script = (
            "Add-Type -AssemblyName System.Windows.Forms; "
            "$fc = New-Object System.Collections.Specialized.StringCollection; "
            f"$fc.Add('{safe}') | Out-Null; "
            "[System.Windows.Forms.Clipboard]::SetFileDropList($fc)"
        )
        r = subprocess.run(
            [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=10
        )
        return r.returncode == 0
    except Exception as e:
        print(f"[ClipFile] {e}")
        return False


# ══════════════════════════════════════════════════════════
# SEND FUNCTIONS
# ══════════════════════════════════════════════════════════

async def wa_send_file(contact: str, filepath: str = "",
                       filename: str = "", folder: str = "",
                       file_type: str = "", caption: str = "") -> str:
    if not HAS_GUI:
        return "❌ pyautogui install nahi hai"

    if not filepath:
        files = await asyncio.to_thread(
            _find_files, filename, folder, file_type, False
        )
        if not files:
            msg = "❌ File nahi mili"
            if filename: msg += f": '{filename}'"
            if folder:   msg += f" (folder: '{folder}')"
            return msg
        if len(files) == 1:
            filepath = files[0]
        else:
            lines = [f"⚠️ {len(files)} files mili:\n"]
            for i, fp in enumerate(files[:8], 1):
                lines.append(f"  {i}. {Path(fp).name}\n     {fp}")
            lines.append("\n💡 Exact naam batao")
            return "\n".join(lines)

    if not os.path.exists(filepath):
        return f"❌ File nahi mili: {filepath}"

    fname = Path(filepath).name
    sz    = (f"{os.path.getsize(filepath)/1024:.0f} KB"
             if os.path.getsize(filepath) < 1048576
             else f"{os.path.getsize(filepath)/1048576:.1f} MB")

    ok = await _focus_or_open_wa()
    if not ok: return "❌ WhatsApp nahi khul saka"
    await asyncio.sleep(0.8)

    # Contact search karo
    await _wa_search_contact(contact)
    await asyncio.sleep(1.0)

    # File clipboard mein daalo
    ok = await asyncio.to_thread(_copy_file_to_clipboard, filepath)
    if not ok: return f"❌ File clipboard mein nahi aayi: {fname}"
    await asyncio.sleep(0.5)

    # Chat input box pe click karo — screen ke lower-center mein hota hai
    # escape/tab avoid karo — chat focus kho deta hai
    import pyautogui as _pag
    scr_w, scr_h = _pag.size()

    # WhatsApp Desktop layout: message box screen ke 60% height pe, 50% width pe
    # (maximize window assume karo — _focus_or_open_wa mein maximize kiya hai)
    chat_x = int(scr_w * 0.60)   # center-right (chat area)
    chat_y = int(scr_h * 0.92)   # bottom (message input bar)

    _pag.click(chat_x, chat_y)
    await asyncio.sleep(0.5)

    # File paste karo
    _pag.hotkey('ctrl', 'v')
    await asyncio.sleep(2.5)

    # Caption agar hai
    if caption:
        _set_clip(caption)
        await asyncio.sleep(0.3)
        _pag.hotkey('ctrl', 'v')
        await asyncio.sleep(0.5)

    # Send karo
    _pag.press('enter')
    await asyncio.sleep(1.2)

    return (
        f"✅ File bhej di!\n"
        f"   📎 {fname} ({sz})\n"
        f"   👤 To: {contact}"
        + (f"\n   💬 Caption: {caption}" if caption else "")
    )


async def wa_send_newest_file(contact: str, folder: str = "Downloads",
                               file_type: str = "", caption: str = "") -> str:
    files = await asyncio.to_thread(_find_files, "", folder, file_type, True)
    if not files:
        return f"❌ {folder} mein koi {file_type or ''} file nahi mili"
    return await wa_send_file(contact=contact, filepath=files[0], caption=caption)


async def wa_send_multiple_files(contact: str, filepaths: list,
                                  caption: str = "") -> str:
    if not filepaths: return "❌ Koi file path nahi diya"
    results = []
    for i, fp in enumerate(filepaths):
        r = await wa_send_file(
            contact=contact, filepath=fp,
            caption=caption if i == 0 else ""
        )
        results.append(r)
        await asyncio.sleep(1.5)
    return "\n".join(results)


async def find_and_send_file(contact: str, filename: str = "",
                              folder: str = "", file_type: str = "",
                              caption: str = "", newest: bool = False) -> str:
    """
    File dhoondhо (C/D/OneDrive sabhi jagah) aur WhatsApp pe bhejo.
    Commands:
    - "Ali ko Documents mein report.pdf bhejo"
    - "D drive mein budget.xlsx Ali ko bhejo"
    - "Downloads ki sabse naya PDF Priya ko send karo"
    """
    if newest:
        return await wa_send_newest_file(contact, folder, file_type, caption)

    files = await asyncio.to_thread(_find_files, filename, folder, file_type, False)

    if not files:
        drives = [str(d) for d in _get_all_drives()]
        msg    = "❌ File nahi mili"
        if filename:  msg += f": '{filename}'"
        if folder:    msg += f" (folder: '{folder}')"
        if file_type: msg += f" (type: {file_type})"
        msg += f"\n   Searched: {', '.join(drives)}"
        msg += "\n💡 Sahi naam ya folder batao"
        return msg

    if len(files) == 1:
        return await wa_send_file(
            contact=contact, filepath=files[0], caption=caption
        )

    lines = [f"📁 {len(files)} files mili:\n"]
    for i, fp in enumerate(files[:8], 1):
        name  = Path(fp).name
        mtime = datetime.fromtimestamp(
            os.path.getmtime(fp)).strftime("%d-%m-%Y")
        lines.append(f"  {i}. {name} ({mtime})\n     {fp}")
    lines.append("\n💡 Exact naam batao ya 'sabse naya wali bhejo' bolo")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════
# TOOL DECLARATIONS
# ══════════════════════════════════════════════════════════

def _p(props: dict, req: list = None) -> dict:
    s = {"type": "object",
         "properties": {k: {"type": v} for k, v in props.items()}}
    if req: s["required"] = req
    return s


WA_FILE_TOOL_DECLARATIONS = [
    {
        "name": "find_and_send_file",
        "description": (
            "File dhoondhо (C drive, D drive, OneDrive — sabhi jagah) "
            "aur WhatsApp pe bhejo. "
            "Commands: 'report.pdf Ali ko bhejo', "
            "'D drive budget.xlsx Ali ko bhejo', "
            "'Downloads ki latest PDF Priya ko send karo'"
        ),
        "parameters": _p({
            "contact": "string", "filename": "string",
            "folder": "string", "file_type": "string",
            "caption": "string", "newest": "boolean",
        }, ["contact"])
    },
    {
        "name": "find_file",
        "description": (
            "File dhoondhо — C/D/OneDrive sabhi jagah. "
            "Path bhi batata hai."
        ),
        "parameters": _p({
            "filename": "string", "folder": "string",
            "file_type": "string", "newest": "boolean",
        })
    },
    {
        "name": "wa_send_file",
        "description": "Specific file WhatsApp pe bhejo",
        "parameters": _p({
            "contact": "string", "filepath": "string",
            "filename": "string", "folder": "string",
            "file_type": "string", "caption": "string",
        }, ["contact"])
    },
    {
        "name": "wa_send_newest_file",
        "description": "Folder ki sabse naya file WhatsApp pe bhejo",
        "parameters": _p({
            "contact": "string", "folder": "string",
            "file_type": "string", "caption": "string",
        }, ["contact"])
    },
]

WA_FILE_TOOL_MAP = {
    "find_and_send_file":  find_and_send_file,
    "find_file":           find_file,
    "wa_send_file":        wa_send_file,
    "wa_send_newest_file": wa_send_newest_file,
}


async def wa_file_dispatch(name: str, args: dict) -> str:
    fn = WA_FILE_TOOL_MAP.get(name)
    if fn: return await fn(**args)
    return f"❌ Tool nahi mila: {name}"