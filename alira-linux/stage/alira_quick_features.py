"""
ALIRA QUICK FEATURES v2 — sirf wo features jo pehle se ALIRA mein NAHI the.

(Already existing tools — password, QR, find_file, set_timer, notes, tasks, IP, battery,
system status, clipboard, clean_system, news, wikipedia — yahan dobara nahi banaye.
LLM-native cheezein — calculator, jokes, date/time — bhi nahi.)

    from ALIRA_quick_features import handle_quick, start_background
    start_background(notify=print)            # alarms/habit checker thread
    reply = handle_quick("alarm 7:30 uthna")  # str ya None

NEW (24): alarm (daily, persistent), pomodoro, stopwatch, expense tracker, water tracker,
habit tracker + streak, event/birthday countdown, journal, daily briefing, bookmarks,
disk space, uptime, WiFi info, ping/site-up, folder size, biggest files, duplicate finder,
recent files, live weather, live currency, crypto price, hash/base64, text tools, word count.
Data: ~/.ALIRA_data/*.json
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path.home() / ".ALIRA_data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
_lock = threading.RLock()
_I = re.I


def _load(name, default):
    try:
        with _lock, open(DATA_DIR / f"{name}.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save(name, data):
    try:
        with _lock, open(DATA_DIR / f"{name}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[QUICK] save {name}: {e}")


def _num(s):
    return float(str(s).replace(",", ""))


def _fmt(n):
    n = float(n)
    return str(int(n)) if n == int(n) else f"{n:,.2f}"


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def _dur(sec):
    sec = int(sec)
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return " ".join(x for x in (f"{h}h" if h else "", f"{m}m" if m else "", f"{s}s" if s or not sec else "") if x)


_FOLDERS = {"downloads": "Downloads", "download": "Downloads", "documents": "Documents", "document": "Documents",
            "desktop": "Desktop", "pictures": "Pictures", "photos": "Pictures", "music": "Music",
            "videos": "Videos", "video": "Videos"}


def _folder(name):
    name = (name or "downloads").strip().lower()
    if name in _FOLDERS:
        return Path.home() / _FOLDERS[name]
    p = Path(name)
    return p if p.is_dir() else None


def _walk(root, deadline, skip=("node_modules", "__pycache__", ".git")):
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in skip and not d.startswith(".")]
        for f in fn:
            yield os.path.join(dp, f)
        if time.time() > deadline:
            return


_notify = None
_bg_started = False


# ══════════════════════════════════════════════════════════════════
# ALARM (daily/one-time, persistent) + POMODORO + STOPWATCH
# ══════════════════════════════════════════════════════════════════
def f_alarm_add(m):
    h, mi = int(m.group("h")), int(m.group("mi") or 0)
    ap = (m.group("ap") or "").lower()
    ctx = m.string.lower()
    if ap == "pm" and h < 12 or (not ap and h < 12 and re.search(r"shaam|sham|raat|evening|night|dopahar", ctx)):
        h += 12 if h < 12 else 0
    if ap == "am" and h == 12:
        h = 0
    if not (0 <= h < 24 and 0 <= mi < 60):
        return "Time galat hai. Aise bolo: alarm 7:30 am."
    what = re.sub(r"\b(?:laga\s*(?:do|dena|de)|set\s*(?:kar\s*do)?|kar\s*do|rakh\s*do)\b", "", m.group("what") or "", flags=_I).strip(" .,") or "Alarm"
    daily = bool(re.search(r"\b(daily|roz|har\s*din|everyday|every\s*day)\b", m.string, _I))
    al = _load("alarms", [])
    al.append({"h": h, "m": mi, "what": what, "daily": daily, "last": ""})
    _save("alarms", al)
    return f"⏰ Alarm set: {h:02d}:{mi:02d} — {what}" + (" (roz)" if daily else "")


def f_alarm_list(m):
    al = _load("alarms", [])
    if not al:
        return "Koi alarm set nahi hai."
    return "⏰ Alarms:\n" + "\n".join(f"{i}. {a['h']:02d}:{a['m']:02d} — {a['what']}{' (roz)' if a['daily'] else ''}"
                                     for i, a in enumerate(al, 1))


def f_alarm_clear(m):
    i = m.groupdict().get("i")
    al = _load("alarms", [])
    if i:
        i = int(i) - 1
        if not 0 <= i < len(al):
            return "Itna bada alarm number nahi hai."
        r = al.pop(i)
        _save("alarms", al)
        return f"🗑️ Alarm hata diya: {r['h']:02d}:{r['m']:02d}"
    _save("alarms", [])
    return "🗑️ Saare alarms clear."


_poms = []


def f_pomodoro(m):
    def _fire():
        _push("🍅 Pomodoro khatam — 5 min ka break lo!")
    t = threading.Timer(25 * 60, _fire)
    t.daemon = True
    t.start()
    _poms.append(t)
    return "🍅 Pomodoro start: 25 min focus. Khatam hone par bataungi."


def f_pomodoro_stop(m):
    n = sum(1 for t in _poms if t.is_alive())
    for t in _poms:
        t.cancel()
    return f"🛑 {n} pomodoro band kiya."


_sw = {"t": None, "laps": []}


def f_stopwatch(m):
    act = m.group("act").lower()
    now = time.time()
    if act in ("start", "shuru", "chalu"):
        _sw["t"], _sw["laps"] = now, []
        return "⏱️ Stopwatch start!"
    if _sw["t"] is None:
        return "Stopwatch chal hi nahi raha. Bolo: stopwatch start."
    el = now - _sw["t"]
    if act == "lap":
        _sw["laps"].append(el)
        return f"⏱️ Lap {len(_sw['laps'])}: {el:.1f}s"
    _sw["t"] = None
    return f"⏱️ Stopped: {_dur(el)} ({el:.1f}s)"


# ══════════════════════════════════════════════════════════════════
# EXPENSE / WATER / HABIT / EVENTS / JOURNAL / BOOKMARKS
# ══════════════════════════════════════════════════════════════════
def f_expense_add(m):
    amt, what = _num(m.group("amt")), (m.group("what") or "misc").strip() or "misc"
    ex = _load("expenses", [])
    ex.append({"d": _today(), "amt": amt, "what": what})
    _save("expenses", ex)
    return f"💸 ₹{_fmt(amt)} ({what}) add. Aaj ka total: ₹{_fmt(sum(e['amt'] for e in ex if e['d'] == _today()))}"


def f_expense_total(m):
    ex = _load("expenses", [])
    if not ex:
        return "Abhi koi kharcha record nahi hai."
    t = m.string.lower()
    if re.search(r"aaj|today", t):
        sel, lab = [e for e in ex if e["d"] == _today()], "Aaj"
    elif re.search(r"mahin|month", t):
        sel, lab = [e for e in ex if e["d"][:7] == _today()[:7]], "Is mahine"
    else:
        sel, lab = ex, "Total"
    cats = {}
    for e in sel:
        cats[e["what"]] = cats.get(e["what"], 0) + e["amt"]
    top = ", ".join(f"{k}: ₹{_fmt(v)}" for k, v in sorted(cats.items(), key=lambda x: -x[1])[:5])
    return f"💰 {lab} kharcha: ₹{_fmt(sum(e['amt'] for e in sel))} ({len(sel)} entries)" + (f"\n{top}" if top else "")


def f_expense_clear(m):
    _save("expenses", [])
    return "🗑️ Kharcha history clear."


def f_water_add(m):
    w = _load("water", {})
    w[_today()] = w.get(_today(), 0) + 1
    _save("water", w)
    n = w[_today()]
    return f"💧 Aaj {n} glass paani (goal 8). " + ("🎯 Goal complete!" if n >= 8 else f"{8 - n} aur baaki.")


def f_water_status(m):
    return f"💧 Aaj {_load('water', {}).get(_today(), 0)}/8 glass paani piya."


def _streak(dates):
    s, d = 0, datetime.now().date()
    if d.isoformat() not in dates:
        d -= timedelta(days=1)
    while d.isoformat() in dates:
        s += 1
        d -= timedelta(days=1)
    return s


def f_habit_add(m):
    h = _load("habits", {})
    n = m.group("name").strip().lower()
    h.setdefault(n, [])
    _save("habits", h)
    return f"🌱 Habit add: {n}"


def f_habit_done(m):
    h = _load("habits", {})
    n = m.group("name").strip().lower()
    if n not in h:
        h[n] = []
    if _today() not in h[n]:
        h[n].append(_today())
    _save("habits", h)
    return f"✅ {n} done! 🔥 Streak: {_streak(set(h[n]))} din"


def f_habit_list(m):
    h = _load("habits", {})
    if not h:
        return "Koi habit track nahi ho rahi. Bolo: habit add gym."
    return "🌱 Habits:\n" + "\n".join(f"• {n}: {'✅ aaj done' if _today() in d else '⬜ baaki'} | 🔥 {_streak(set(d))} din"
                                     for n, d in h.items())


def f_habit_remove(m):
    h = _load("habits", {})
    n = m.group("name").strip().lower()
    if h.pop(n, None) is None:
        return f"'{n}' habit nahi mili."
    _save("habits", h)
    return f"🗑️ Habit hata di: {n}"


def _next_occurrence(day, month, year=None):
    now = datetime.now()
    if year:
        return datetime(year, month, day)
    d = datetime(now.year, month, day)
    return d if d.date() >= now.date() else datetime(now.year + 1, month, day)


def f_event_add(m):
    name = m.group("name").strip()
    day, mon = int(m.group("d")), int(m.group("mo"))
    yr = m.group("y")
    try:
        _next_occurrence(day, mon, int(yr) if yr else None)
    except ValueError:
        return "Date galat hai. Aise bolo: event add birthday 15-08."
    ev = _load("events", [])
    ev.append({"name": name, "d": day, "m": mon, "y": int(yr) if yr else None})
    _save("events", ev)
    return f"📅 Event save: {name} ({day:02d}-{mon:02d})"


def _events_sorted():
    out = []
    for e in _load("events", []):
        try:
            dt = _next_occurrence(e["d"], e["m"], e.get("y"))
        except ValueError:
            continue
        out.append(((dt.date() - datetime.now().date()).days, e["name"], dt))
    return sorted(x for x in out if x[0] >= 0)


def f_event_list(m):
    ev = _events_sorted()
    if not ev:
        return "Koi upcoming event nahi hai."
    return "📅 Upcoming:\n" + "\n".join(f"• {n} — {dt.strftime('%d %b')} ({'aaj!' if d == 0 else f'{d} din baaki'})"
                                       for d, n, dt in ev[:10])


def f_event_remove(m):
    ev, name = _load("events", []), m.group("name").strip().lower()
    new = [e for e in ev if e["name"].lower() != name]
    if len(new) == len(ev):
        return f"'{name}' event nahi mila."
    _save("events", new)
    return f"🗑️ Event hata diya: {name}"


def f_journal_add(m):
    j = _load("journal", [])
    j.append({"t": datetime.now().strftime("%d-%m-%Y %H:%M"), "text": m.group("body").strip()})
    _save("journal", j)
    return "📔 Journal mein likh diya."


def f_journal_list(m):
    j = _load("journal", [])
    if not j:
        return "Journal abhi khaali hai."
    return "📔 Journal (last 5):\n" + "\n".join(f"[{e['t']}] {e['text']}" for e in j[-5:])


def f_briefing(m):
    n = datetime.now()
    lines = [f"🌅 {n.strftime('%A, %d %B %Y')} — {n.strftime('%I:%M %p')}"]
    try:
        import psutil
        b = psutil.sensors_battery()
        if b:
            lines.append(f"🔋 Battery {b.percent:.0f}% {'(charging)' if b.power_plugged else ''}")
    except Exception:
        pass
    al = _load("alarms", [])
    if al:
        lines.append("⏰ Alarms: " + ", ".join(f"{a['h']:02d}:{a['m']:02d} {a['what']}" for a in al[:4]))
    ev = [x for x in _events_sorted() if x[0] <= 7]
    if ev:
        lines.append("📅 " + ", ".join(f"{nm} ({'aaj' if d == 0 else f'{d} din'})" for d, nm, _ in ev[:4]))
    hb = _load("habits", {})
    pend = [k for k, d in hb.items() if _today() not in d]
    if pend:
        lines.append("🌱 Aaj ki habits baaki: " + ", ".join(pend[:5]))
    lines.append(f"💧 Paani: {_load('water', {}).get(_today(), 0)}/8")
    sp = sum(e["amt"] for e in _load("expenses", []) if e["d"] == _today())
    if sp:
        lines.append(f"💸 Aaj ka kharcha: ₹{_fmt(sp)}")
    return "\n".join(lines)


def f_bm_add(m):
    bm = _load("bookmarks", {})
    bm[m.group("name").strip().lower()] = m.group("url").strip()
    _save("bookmarks", bm)
    return f"🔖 Bookmark saved: {m.group('name').strip()}"


def f_bm_list(m):
    bm = _load("bookmarks", {})
    return ("🔖 Bookmarks:\n" + "\n".join(f"• {k} → {v}" for k, v in bm.items())) if bm else "Koi bookmark nahi hai."


def f_bm_open(m):
    bm, k = _load("bookmarks", {}), m.group("name").strip().lower()
    if k not in bm:
        return f"'{k}' naam ka bookmark nahi mila."
    url = bm[k] if bm[k].startswith("http") else "https://" + bm[k]
    import webbrowser
    webbrowser.open(url)
    return f"🌐 Khol diya: {url}"


# ══════════════════════════════════════════════════════════════════
# SYSTEM / FILES / NETWORK
# ══════════════════════════════════════════════════════════════════
def f_disk(m):
    import psutil
    out = []
    for p in psutil.disk_partitions(all=False):
        if "cdrom" in p.opts or not p.fstype:
            continue
        try:
            u = psutil.disk_usage(p.mountpoint)
        except Exception:
            continue
        out.append(f"• {p.device} {u.used / 1e9:.0f}/{u.total / 1e9:.0f} GB ({u.percent:.0f}% full, {u.free / 1e9:.0f} GB free)")
    return "💽 Disk:\n" + "\n".join(out)


def f_uptime(m):
    import psutil
    return f"⏲️ PC {_dur(time.time() - psutil.boot_time())} se chal raha hai."


def f_wifi(m):
    try:
        out = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, timeout=6,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    except Exception:
        return "WiFi info nahi mili."
    g = lambda k: (re.search(rf"^\s*{k}\s*:\s*(.+)$", out, re.M) or [None, "?"])[1].strip()
    if "SSID" not in out:
        return "📶 WiFi connected nahi hai."
    return f"📶 WiFi: {g('SSID')} | Signal: {g('Signal')} | Speed: {g('Receive rate .Mbps.')} Mbps | Band: {g('Radio type')}"


def f_ping(m):
    host = re.sub(r"^https?://", "", m.group("host").strip()).split("/")[0]
    if not re.match(r"^[a-z0-9.\-]+$", host, _I):
        return None
    import socket
    for port in (443, 80):
        t0 = time.time()
        try:
            socket.create_connection((host, port), 5).close()
            return f"🟢 {host} chal raha hai — {int((time.time() - t0) * 1000)} ms"
        except socket.gaierror:
            return f"🔴 {host} ka address (DNS) nahi mila."
        except OSError:
            continue
    return f"🔴 {host} reach nahi ho raha."


def f_foldersize(m):
    p = _folder(m.group("folder"))
    if not p or not p.exists():
        return "Folder nahi mila."
    tot = n = 0
    for f in _walk(p, time.time() + 12):
        try:
            tot += os.path.getsize(f)
            n += 1
        except OSError:
            pass
    return f"📁 {p.name}: {n} files, {tot / 1e9:.2f} GB" if tot > 1e9 else f"📁 {p.name}: {n} files, {tot / 1e6:.1f} MB"


def f_bigfiles(m):
    p = _folder(m.group("folder"))
    if not p:
        return "Folder nahi mila."
    sizes = []
    for f in _walk(p, time.time() + 12):
        try:
            sizes.append((os.path.getsize(f), f))
        except OSError:
            pass
    sizes.sort(reverse=True)
    if not sizes:
        return "Koi file nahi mili."
    return f"🐘 {p.name} ki sabse badi files:\n" + "\n".join(f"• {s / 1e6:.0f} MB — {os.path.basename(f)}" for s, f in sizes[:6])


def f_dupes(m):
    p = _folder(m.group("folder"))
    if not p:
        return "Folder nahi mila."
    by_size = {}
    for f in _walk(p, time.time() + 10):
        try:
            sz = os.path.getsize(f)
            if sz > 1024:
                by_size.setdefault(sz, []).append(f)
        except OSError:
            pass
    groups, wasted = [], 0
    for sz, fs in by_size.items():
        if len(fs) < 2 or sz > 300e6:
            continue
        h = {}
        for f in fs:
            try:
                d = hashlib.md5(open(f, "rb").read()).hexdigest()
                h.setdefault(d, []).append(f)
            except OSError:
                pass
        for v in h.values():
            if len(v) > 1:
                groups.append(v)
                wasted += sz * (len(v) - 1)
    if not groups:
        return f"✅ {p.name} mein duplicate files nahi mili."
    return (f"♻️ {len(groups)} duplicate group mile, ~{wasted / 1e6:.0f} MB waste (sirf report, kuch delete nahi kiya):\n"
            + "\n".join("• " + " = ".join(os.path.basename(x) for x in g[:3]) for g in groups[:6]))


def f_recent(m):
    p = _folder(m.group("folder"))
    if not p:
        return "Folder nahi mila."
    files = []
    for f in _walk(p, time.time() + 8):
        try:
            files.append((os.path.getmtime(f), f))
        except OSError:
            pass
    files.sort(reverse=True)
    if not files:
        return "Koi file nahi mili."
    return f"🕘 {p.name} ki latest files:\n" + "\n".join(
        f"• {datetime.fromtimestamp(t).strftime('%d %b %H:%M')} — {os.path.basename(f)}" for t, f in files[:6])


def f_weather(m):
    city = m.group("city").strip()
    try:
        import requests
        r = requests.get(f"https://wttr.in/{city}?format=%l:+%c+%t+(feels+%f),+humidity+%h,+wind+%w", timeout=6,
                         headers={"User-Agent": "curl"})
        return f"🌤️ {r.text.strip()}" if r.ok else "Weather service abhi available nahi."
    except Exception:
        return "Weather ke liye internet chahiye."


_CUR = set("USD INR EUR GBP JPY AUD CAD CNY AED SAR PKR BDT NPR LKR SGD CHF RUB BRL ZAR KRW THB MYR IDR TRY NZD HKD SEK NOK".split())


def f_currency(m):
    amt, a, b = _num(m.group("amt")), m.group("a").upper(), m.group("b").upper()
    if a not in _CUR or b not in _CUR:
        return None
    try:
        import requests
        r = requests.get(f"https://open.er-api.com/v6/latest/{a}", timeout=6).json()
        rate = r["rates"][b]
    except Exception:
        return None
    return f"💱 {_fmt(amt)} {a} = {amt * rate:,.2f} {b} (live rate {rate:.4f})"


_COINS = {"bitcoin": "bitcoin", "btc": "bitcoin", "ethereum": "ethereum", "eth": "ethereum", "dogecoin": "dogecoin",
          "doge": "dogecoin", "solana": "solana", "sol": "solana", "xrp": "ripple", "ripple": "ripple",
          "bnb": "binancecoin", "cardano": "cardano", "litecoin": "litecoin"}


def f_crypto(m):
    cid = _COINS.get(m.group("coin").lower())
    if not cid:
        return None
    try:
        import requests
        r = requests.get("https://api.coingecko.com/api/v3/simple/price",
                         params={"ids": cid, "vs_currencies": "usd,inr", "include_24hr_change": "true"}, timeout=6).json()[cid]
    except Exception:
        return "Crypto price ke liye internet chahiye."
    return f"🪙 {cid.title()}: ${r['usd']:,.2f} / ₹{r['inr']:,.0f} ({r.get('usd_24h_change', 0):+.1f}% 24h)"


# ══════════════════════════════════════════════════════════════════
# TEXT / ENCODE
# ══════════════════════════════════════════════════════════════════
def f_text(m):
    op, b = m.group("op").lower().replace(" ", ""), m.group("body")
    return {"uppercase": b.upper(), "upper": b.upper(), "lowercase": b.lower(), "lower": b.lower(),
            "reverse": b[::-1], "title": b.title(), "titlecase": b.title()}.get(op)


def f_wordcount(m):
    b = m.group("body")
    return f"🔢 Words: {len(b.split())}, Characters: {len(b)}, Sentences: {len(re.findall(r'[.!?]+', b)) or 1}"


def f_encode(m):
    op, b = m.group("op").lower().replace(" ", ""), m.group("body").strip()
    try:
        if op == "base64encode":
            return "🔒 " + base64.b64encode(b.encode()).decode()
        if op == "base64decode":
            return "🔓 " + base64.b64decode(b.encode()).decode(errors="replace")
        return f"#️⃣ {op}: {getattr(hashlib, op)(b.encode()).hexdigest()}"
    except Exception as e:
        return f"Encode error: {e}"


def f_help(m):
    return (
        "⚡ ALIRA Quick Features (naye):\n"
        "⏰ 'alarm 7:30 am uthna', 'alarm roz 9 baje medicine', 'alarms dikhao', 'alarm clear' | 🍅 'pomodoro start/stop' | ⏱️ 'stopwatch start/lap/stop'\n"
        "💸 'kharcha 200 chai', 'total kharcha', 'aaj ka kharcha' | 💧 'paani piya', 'water status'\n"
        "🌱 'habit add gym', 'habit done gym', 'habits' | 📅 'event add birthday 15-08', 'events' | 📔 'journal: aaj ...', 'journal dikhao'\n"
        "🌅 'daily briefing' | 🔖 'bookmark add yt youtube.com', 'bookmark open yt'\n"
        "💽 'disk space' | ⏲️ 'uptime' | 📶 'wifi info' | 🏓 'ping google.com'\n"
        "📁 'downloads ka size' | 🐘 'biggest files in downloads' | ♻️ 'duplicate files downloads' | 🕘 'recent files downloads'\n"
        "🌤️ 'weather in Delhi' | 💱 '100 usd to inr' | 🪙 'bitcoin price'\n"
        "🔒 'base64 encode x', 'sha256 x' | 🔠 'uppercase: text', 'word count: text'"
    )


# ══════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════
_NUM = r"\d[\d,]*(?:\.\d+)?"
_FOLD = r"(?P<folder>[a-z]+|[a-z]:\\[^\s]+)"
_TIME = r"(?P<h>\d{1,2})(?::(?P<mi>\d{2}))?\s*(?P<ap>am|pm)?"
_ROUTES = [
    (r"\b(?:quick\s+features?|features?\s+list|quick\s+commands?|naye\s+features?)\b", f_help),
    (r"\b(?:alarms?\s+(?:clear|delete|hatao|band)|(?:clear|delete|hatao)\s+(?:all\s+)?alarms?)\b(?:\s+(?P<i>\d+))?", f_alarm_clear),
    (r"\b(?:delete|hatao|remove)\s+alarm\s+(?P<i>\d+)\b", f_alarm_clear),
    (r"\b(?:alarms?\s+(?:list|dikhao|show|batao)|(?:show|list|mere|my)\s+alarms?)\b", f_alarm_list),
    (r"\balarm\b(?:\s+(?:laga\w*|set|rakh\w*))?\s*(?:roz|daily)?\s*(?:subah|shaam|sham|raat|dopahar)?\s*(?:at|ko)?\s*" + _TIME
     + r"\s*(?:baje)?\s*(?P<what>[^\d].*)?$", f_alarm_add),
    (r"^\s*(?:subah|shaam|sham|raat|dopahar)?\s*" + _TIME + r"\s*baje\s+(?:ka\s+)?alarm\b\s*(?P<what>.*)", f_alarm_add),
    (r"\bpomodoro\s+(?:stop|band|cancel)\b", f_pomodoro_stop),
    (r"\bpomodoro\b", f_pomodoro),
    (r"\bstop\s?watch\b.*?\b(?P<act>start|shuru|chalu|stop|band|lap)\b|\b(?P<act2>start|shuru|chalu|stop|band|lap)\b.*?\bstop\s?watch\b", "stopwatch"),
    (r"\b(?:clear|delete)\s+(?:expenses?|kharcha)\b|\b(?:kharcha|expenses?)\s+clear\b", f_expense_clear),
    (r"\b(?:total|aaj\s+ka|is\s+mahine\s+ka|monthly|today'?s?)\s+(?:kharcha|expenses?|spending)\b|\b(?:kharcha|expenses?)\s+(?:total|summary|dikhao|batao)\b", f_expense_total),
    (r"\b(?:kharcha|expense|spent|kharch)\s+(?:₹|rs\.?\s*)?(?P<amt>" + _NUM + r")\s*(?:rs|rupees|rupay[ae]?|₹)?\s*(?:on|for|ka|ki|ke\s+liye)?\s*(?P<what>[a-z ]*)$", f_expense_add),
    (r"\b(?:water|paani|pani)\s+(?:status|tracker|kitna|count)\b|\bkitna\s+(?:paani|pani|water)\b", f_water_status),
    (r"\b(?:paani|pani)\s+(?:piya|pee\s*liya|pi\s*liya)\b|\b(?:drank|had)\s+(?:a\s+)?(?:glass\s+of\s+)?water\b", f_water_add),
    (r"\bhabit\s+(?:add|jodo|start)\s+(?P<name>.+)$", f_habit_add),
    (r"\bhabit\s+(?:done|complete|ho\s+gayi)\s+(?P<name>.+)$|\b(?P<name2>[a-z ]+?)\s+habit\s+(?:done|complete)\b", "habit_done"),
    (r"\bhabit\s+(?:remove|delete|hatao)\s+(?P<name>.+)$", f_habit_remove),
    (r"\b(?:habits?|habit\s+(?:list|status|streak))\b\s*(?:list|dikhao|status|streak)?\s*$", f_habit_list),
    (r"\bevent\s+(?:remove|delete|hatao)\s+(?P<name>.+)$", f_event_remove),
    (r"\bevent\s+add\s+(?P<name>.+?)\s+(?P<d>\d{1,2})[-/.](?P<mo>\d{1,2})(?:[-/.](?P<y>\d{4}))?\s*$", f_event_add),
    (r"\b(?:events?|upcoming\s+events?|birthdays?)\s*(?:list|dikhao|show)?\s*$", f_event_list),
    (r"^\s*(?:journal|diary)\s*(?:add|likho)?\s*[:\-]\s*(?P<body>.+)$", f_journal_add),
    (r"\b(?:journal|diary)\s+(?:dikhao|padho|show|read|list)\b", f_journal_list),
    (r"\b(?:daily\s+)?(?:briefing|summary)\b|\baaj\s+ka\s+(?:plan|summary)\b|\bmorning\s+briefing\b", f_briefing),
    (r"\bbookmarks?\s+(?:list|dikhao|show)\b|\b(?:show|list|mere)\s+bookmarks?\b", f_bm_list),
    (r"\bbookmark\s+add\s+(?P<name>\S+)\s+(?P<url>\S+)", f_bm_add),
    (r"\bbookmark\s+open\s+(?P<name>.+)$", f_bm_open),
    (r"\b(?:disk|storage|drive)\s+(?:space|usage|status|kitna|check)\b|\bkitni\s+(?:storage|space)\b", f_disk),
    (r"\buptime\b|\bpc\s+kab\s+se\s+chal\b", f_uptime),
    (r"\bwi-?fi\s+(?:info|status|signal|speed|kaun\s*sa)\b|\bkaun\s*sa\s+wi-?fi\b", f_wifi),
    (r"\bping\s+(?P<host>[a-z0-9.\-]+)\b|\bis\s+(?P<host2>[a-z0-9\-]+\.[a-z.]+)\s+(?:up|down|working)\b", "ping"),
    (r"\b(?:biggest|largest|sabse\s+badi?)\s+files?\s*(?:in|of|mein|me|ka)?\s*" + _FOLD, f_bigfiles),
    (r"\bduplicate\s+files?\s*(?:in|of|mein|me)?\s*" + _FOLD, f_dupes),
    (r"\b(?:recent|latest|newest|naye)\s+files?\s*(?:in|of|mein|me)?\s*" + _FOLD, f_recent),
    (r"\b(?:folder\s+size\s+|size\s+of\s+)" + _FOLD + r"|\b" + r"(?P<folder2>downloads?|documents?|desktop|pictures|music|videos)\s+(?:ka\s+)?(?:folder\s+)?size\b|\b(?P<folder3>downloads?|documents?|desktop|pictures|music|videos)\s+(?:kitni|ka)\s+(?:jagah|space)\b", "foldersize"),
    (r"\b(?:weather|mausam|temperature)\s+(?:in|of|at|ka|me|mein)?\s*(?P<city>[a-z][a-z ]+?)\s*\??$", f_weather),
    (r"(?P<amt>" + _NUM + r")\s*(?P<a>[a-z]{3})\s+(?:to|ko|in|into|mein)\s+(?P<b>[a-z]{3})\b", f_currency),
    (r"\b(?P<coin>bitcoin|btc|ethereum|eth|dogecoin|doge|solana|sol|xrp|ripple|bnb|cardano|litecoin)\s+(?:price|rate|ka\s+(?:price|rate|bhav))\b|\b(?:price|rate|bhav)\s+(?:of|for)\s+(?P<coin2>bitcoin|btc|ethereum|eth|dogecoin|doge|solana|sol|xrp|ripple|bnb|cardano|litecoin)\b", "crypto"),
    (r"\b(?:word\s*count|count\s+words|kitne\s+words)\s*[:\-]\s*(?P<body>.+)$", f_wordcount),
    (r"^\s*(?P<op>uppercase|lowercase|upper|lower|reverse|title\s?case|title)\s*[:\-]\s*(?P<body>.+)$", f_text),
    (r"^\s*(?P<op>base64\s+encode|base64\s+decode|md5|sha1|sha256)\s*[:\-]?\s+(?P<body>.+)$", f_encode),
]

# Alag-alag branch group-names wale routes ke liye adapters (regex mein duplicate group name allowed nahi)
_ADAPT = {
    "stopwatch": lambda m: f_stopwatch(_G(act=m.group("act") or m.group("act2"))),
    "habit_done": lambda m: f_habit_done(_G(name=m.group("name") or m.group("name2"))),
    "ping": lambda m: f_ping(_G(host=m.group("host") or m.group("host2"))),
    "foldersize": lambda m: f_foldersize(_G(folder=m.groupdict().get("folder") or m.groupdict().get("folder2")
                                            or m.groupdict().get("folder3"))),
    "crypto": lambda m: f_crypto(_G(coin=m.group("coin") or m.group("coin2"))),
}


class _G:
    def __init__(self, **d):
        self._d, self.string = d, ""

    def group(self, k):
        return self._d.get(k)

    def groupdict(self):
        return self._d


_TABLE = [(re.compile(_rx, _I | re.S), _ADAPT[_fn] if isinstance(_fn, str) else _fn) for _rx, _fn in _ROUTES]

FEATURE_COUNT = len(_TABLE)


def is_quick_command(text: str) -> bool:
    return any(rx.search(text.strip()) for rx, _ in _TABLE)


def handle_quick(text: str, notify=None):
    """Quick command chalao. Result str, ya None agar ye quick command nahi hai."""
    global _notify
    if notify:
        _notify = notify
    t = (text or "").strip()
    if not t or len(t) > 600:
        return None
    for rx, fn in _TABLE:
        m = rx.search(t)
        if not m:
            continue
        try:
            out = fn(m)
        except Exception as e:
            print(f"[QUICK] {getattr(fn, '__name__', 'fn')} error: {e}")
            out = None
        if out:
            return out
    return None


# ══════════════════════════════════════════════════════════════════
# BACKGROUND — alarms
# ══════════════════════════════════════════════════════════════════
def _push(msg):
    print(f"[QUICK] {msg}")
    if _notify:
        try:
            _notify(msg)
        except Exception as e:
            print(f"[QUICK] notify: {e}")


def _alarm_loop():
    while True:
        try:
            now = datetime.now()
            al, changed = _load("alarms", []), False
            keep = []
            for a in al:
                if a["h"] == now.hour and a["m"] == now.minute and a.get("last") != _today():
                    _push(f"⏰ Alarm! {a['what']} ({a['h']:02d}:{a['m']:02d})")
                    a["last"], changed = _today(), True
                    if not a["daily"]:
                        continue
                keep.append(a)
            if changed:
                _save("alarms", keep)
        except Exception as e:
            print(f"[QUICK] alarm loop: {e}")
        time.sleep(20)


def start_background(notify=None):
    """Alarm checker thread start karo (ek hi baar)."""
    global _notify, _bg_started
    if notify:
        _notify = notify
    if not _bg_started:
        _bg_started = True
        threading.Thread(target=_alarm_loop, daemon=True, name="Quick-Alarms").start()


if __name__ == "__main__":
    import sys
    print(handle_quick(" ".join(sys.argv[1:]) or "features list") or "(no match)")
