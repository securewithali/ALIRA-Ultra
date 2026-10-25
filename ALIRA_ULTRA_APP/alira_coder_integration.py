# -*- coding: utf-8 -*-
"""
ALIRA Coder Integration Module  v3.0  — FINAL FIX
===================================================
v3.0 Changes:
  ✅ ALIRACoderOverlay ab QDialog hai (Qt.FramelessWindowHint + Qt.Tool)
     — hamesha parent window ke upar float karta hai, guaranteed visible
  ✅ Parent window ke saath move/resize hota hai (eventFilter)
  ✅ Semi-transparent dark background with blur effect
  ✅ Panel always fills dialog
  ✅ Live code output + todo panel fully functional
"""

import os, json, time, tempfile, threading, subprocess
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QPushButton, QDialog, QApplication
)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer, QEvent
from PyQt5.QtGui import QColor, QPainter, QLinearGradient, QFont

# ─────────────────────────────────────────────────────────
# WEBSITE COMMAND DETECTOR
# ─────────────────────────────────────────────────────────
_WEBSITE_TRIGGERS = [
    "website banao","website bana","website bana do","website banana",
    "site banao","web page banao","webpage banao",
    "create website","build website","make website","build a website",
    "create a website","make a website","design website","design a website",
    "landing page banao","landing page bana","create landing page",
    "portfolio banao","portfolio bana","portfolio website",
    "create portfolio","make portfolio",
    "gaming website","business website","ecommerce website",
    "shop website","restaurant website","blog website",
    "dark website","modern website","neon website",
    "website with","website for","create web","build web",
    "webpage bana","web app bana","create web app",
    "website chahiye","ek website","meri website","naya website",
    "web site bana","website design karo","site design",
    "html website","html page bana","html file bana",
]

def is_website_command(text: str) -> bool:
    t = text.lower().strip()
    for trigger in _WEBSITE_TRIGGERS:
        if trigger in t: return True
    has_web    = any(w in t for w in ["website","web page","webpage","web app",
                                       "landing page","html page","portfolio site"])
    has_action = any(w in t for w in ["bana","banao","create","build","make",
                                       "design","chahiye","develop","likhna"])
    return has_web and has_action


# ─────────────────────────────────────────────────────────
# ALIRA CODER ENGINE
# ─────────────────────────────────────────────────────────
class ALIRACoderEngine(QObject):
    sig_tool        = pyqtSignal(str)
    sig_tool_result = pyqtSignal(str, bool)
    sig_text        = pyqtSignal(str)
    sig_todos       = pyqtSignal(list)
    sig_notice      = pyqtSignal(str)
    sig_started     = pyqtSignal(str, str)
    sig_done        = pyqtSignal(str)
    sig_error       = pyqtSignal(str)
    sig_code_line   = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc          = None
        self._progress_file = None
        self._running       = False
        self._ctx           = {"attempt": 0}
        self._before        = {}
        self._attempt_over  = False
        self._coder_dir     = Path(__file__).parent / "alira_coder"
        # ✅ FIX: dist/run.js sirf runMain EXPORT karta hai (khud kuch nahi chalata) —
        # pehle `node dist/run.js` silently kuch nahi karta tha. Asli entry:
        # `node dist/cli.js run <task> ...` (cli.ts "run" subcommand -> runMain).
        self._node_entry    = self._coder_dir / "dist" / "cli.js"

    def is_available(self):
        return self._node_entry.exists()

    def _node(self):
        for p in [
            r"C:\Program Files\nodejs\node.exe",
            r"C:\Program Files (x86)\nodejs\node.exe",
            os.path.expanduser(r"~\AppData\Roaming\nvm\current\node.exe"),
        ]:
            if os.path.exists(p): return p
        return "node"

    MAX_ATTEMPTS = 3   # Gemini kabhi beech mein fail / bina kaam kiye "done" bolta hai => retry

    def run(self, task, output_dir=None, provider="gemini", model=None, raw=False, expect_files=True):
        if self._running:
            self.sig_error.emit("ALIRA Coder already running!"); return
        if not self.is_available():
            self.sig_error.emit(
                f"ALIRA Coder build nahi mili!\n{self._node_entry}\n"
                "Fix: alira_coder/ mein 'npm install && npm run build' chalao"); return

        if output_dir is None: output_dir = str(Path.home() / "alira_Websites")
        os.makedirs(output_dir, exist_ok=True)
        # ✅ FIX: provider=gemini par global config ka model ("qwen2.5-coder") jaata tha => 404.
        if model is None and provider == "gemini":
            model = "gemini-3.5-flash-lite"

        full_task = task
        if not raw and (is_website_command(task) or "website" in task.lower()):
            full_task = (
                f"{task}\n\n[ALIRA instructions] Build this as a complete, modern, responsive website. "
                "Create ONE NEW subfolder (short kebab-case name based on the project) inside the current "
                "working directory and put ALL files there (index.html, style.css, script.js, assets). "
                "Use real polished content (no lorem ipsum), semantic accessible HTML, mobile-first CSS. "
                "Finish with a one-line summary and the folder name."
            )

        self._running   = True
        self._ctx       = {"task": full_task, "dir": output_dir, "provider": provider, "model": model, "attempt": 0,
                           "expect_files": expect_files}
        self._launch()

    def _snapshot(self, d):
        out = {}
        for root, _dirs, files in os.walk(d):
            for f in files:
                fp = os.path.join(root, f)
                try: out[fp] = os.path.getmtime(fp)
                except OSError: pass
        return out

    def _launch(self, extra=""):
        c = self._ctx; c["attempt"] += 1
        self._attempt_over = False
        self._before = self._snapshot(c["dir"])
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='_mc.jsonl', delete=False, encoding='utf-8')
        self._progress_file = tmp.name; tmp.close()

        cmd = [self._node(), str(self._node_entry), "run", c["task"] + extra,
               "--dir", c["dir"], "--progress-file", self._progress_file, "--provider", c["provider"]]
        if c["model"]: cmd += ["--model", c["model"]]

        env = os.environ.copy()
        ef  = Path(__file__).parent / ".env"
        if ef.exists():
            for line in ef.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    k, v = line.split('=', 1); env[k.strip()] = v.strip().strip('"').strip("'")
        # API key: .env me na ho to ALIRA ki saved config (~/.TABBU/config.json) se lo
        if not env.get("GEMINI_API_KEY"):
            try:
                cfg = json.loads((Path.home() / ".TABBU" / "config.json").read_text(encoding="utf-8"))
                k = cfg.get("api_key") or cfg.get("gemini_api_key")
                if k: env["GEMINI_API_KEY"] = k
            except Exception:
                pass

        try:
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding='utf-8', errors='replace',
                env=env, cwd=str(self._coder_dir),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except FileNotFoundError:
            self._running = False
            self.sig_error.emit("Node.js nahi mila!\nhttps://nodejs.org install karo\n"
                                "Phir: ALIRA_coder/ mein 'npm install && npm run build'"); return
        self._proc = proc
        pf = self._progress_file; attempt = c["attempt"]

        def _out():
            tail = []
            for line in proc.stdout:
                line = line.rstrip('\n')
                if line:
                    tail.append(line); tail[:] = tail[-12:]
                    self.sig_code_line.emit(line)
            rc = proc.wait()
            if rc != 0 and attempt == self._ctx["attempt"]:
                self._attempt_failed(f"ALIRA Coder process error (exit {rc})\n" + "\n".join(tail[-4:]))

        def _tail():
            pos = 0
            while self._running and attempt == self._ctx["attempt"] and proc.poll() is None:
                pos = self._read_events(pf, pos)
                time.sleep(0.15)
            self._read_events(pf, pos)         # process khatam hone ke baad bacha hua bhi padho

        threading.Thread(target=_out,  daemon=True, name="MC-Out").start()
        threading.Thread(target=_tail, daemon=True, name="MC-Tail").start()

    def _read_events(self, pf, pos):
        try:
            if os.path.exists(pf):
                with open(pf, 'r', encoding='utf-8') as f:
                    f.seek(pos)
                    for line in f:
                        ln = line.strip()
                        if ln:
                            try: self._dispatch(json.loads(ln))
                            except Exception: pass
                    pos = f.tell()
        except Exception:
            pass
        return pos

    def _dispatch(self, ev):
        t = ev.get("type","")
        if   t == "started":      self.sig_started.emit(ev.get("provider","?"), ev.get("model","?"))
        elif t == "tool":         self.sig_tool.emit(ev.get("label","Working..."))
        elif t == "tool_result":  self.sig_tool_result.emit(ev.get("summary",""), ev.get("ok", True))
        elif t == "todos":        self.sig_todos.emit(ev.get("todos",[]))
        elif t == "notice":       self.sig_notice.emit(ev.get("text",""))
        elif t == "done":         self._attempt_done(ev.get("summary","Website ready!"))
        elif t == "error":        self._attempt_failed(ev.get("message","Error"))

    # ── retry logic ───────────────────────────────────────────
    def _new_files(self):
        now = self._snapshot(self._ctx["dir"])
        return [f for f, mt in now.items() if f not in self._before or mt > self._before[f]]

    def _attempt_done(self, summary):
        if self._attempt_over: return
        self._attempt_over = True
        made = self._new_files()
        if not made and not self._ctx.get("expect_files", True):
            self._running = False
            self.sig_done.emit(summary)        # review/fix round: kuch badalna zaroori nahi
            return
        if not made and self._ctx["attempt"] < self.MAX_ATTEMPTS:
            self.sig_notice.emit(f"Model ne koi file nahi banayi — retry {self._ctx['attempt']}/{self.MAX_ATTEMPTS - 1}")
            self._relaunch("\n\nIMPORTANT: You MUST actually create the files now using your file-writing tools. Do not just describe the plan.")
            return
        if not made:
            self._running = False
            self.sig_error.emit("ALIRA Coder ne koi file nahi banayi (model ne kaam nahi kiya). Dobara try karo ya prompt detail mein do.")
            return
        self._running = False
        self.sig_done.emit(summary)

    def _attempt_failed(self, msg):
        if self._attempt_over: return
        self._attempt_over = True
        fatal = any(k in msg for k in ("API key", "API_KEY", "401", "403", "429", "quota", "Node.js nahi"))
        if not fatal and self._ctx["attempt"] < self.MAX_ATTEMPTS:
            self.sig_notice.emit(f"Error aaya — retry {self._ctx['attempt']}/{self.MAX_ATTEMPTS - 1}: {msg.splitlines()[0][:70]}")
            self._relaunch("\n\n[Previous attempt was interrupted. Check the files already created in the working directory "
                           "and complete ONLY the remaining parts; do not recreate finished files.]")
            return
        self._running = False
        self.sig_error.emit(msg)

    def _relaunch(self, extra):
        old = self._proc
        if old and old.poll() is None:
            try: old.terminate()
            except Exception: pass
        time.sleep(1.5)
        if self._running:
            self._launch(extra)

    def stop(self):
        self._running = False
        if self._proc and self._proc.poll() is None:
            try: self._proc.terminate(); self._proc.wait(timeout=3)
            except:
                try: self._proc.kill()
                except: pass
        if self._progress_file and os.path.exists(self._progress_file):
            try: os.remove(self._progress_file)
            except: pass
        self._proc = None


# ─────────────────────────────────────────────────────────
# ANIMATED HEADER
# ─────────────────────────────────────────────────────────
class _AnimatedHeader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(58)
        self._phase = 0.0
        QTimer(self, interval=40, timeout=self._tick).start()

    def _tick(self):
        import math
        self._phase = (self._phase + 0.06) % (2 * math.pi)
        self.update()

    def paintEvent(self, _):
        import math
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        gr = QLinearGradient(0, 0, self.width(), 0)
        gr.setColorAt(0, QColor("#000E1C")); gr.setColorAt(0.5, QColor("#001530"))
        gr.setColorAt(1, QColor("#000E1C"))
        p.fillRect(self.rect(), gr)
        a = int(90 + 70 * math.sin(self._phase))
        from PyQt5.QtGui import QPen
        p.setPen(QPen(QColor(0, 220, 150, a), 2))
        p.drawLine(0, self.height()-1, self.width(), self.height()-1)
        p.setFont(QFont("Segoe UI Emoji", 20)); p.setPen(QColor("#00FFB0"))
        p.drawText(14, 40, "⬡")
        p.setFont(QFont("Consolas", 15, QFont.Bold))
        g = int(170 + 70 * math.sin(self._phase))
        p.setPen(QColor(0, g, 130)); p.drawText(52, 38, "ALIRA CODER")
        p.setFont(QFont("Consolas", 9)); p.setPen(QColor(0, 160, 110, 200))
        p.drawText(54, 52, "AI Website Builder  •  Live")
        p.end()


# ─────────────────────────────────────────────────────────
# TODO ITEM
# ─────────────────────────────────────────────────────────
class _TodoItem(QWidget):
    _IC = {"pending":"○","in_progress":"◐","completed":"✔","failed":"✗"}
    _CL = {"pending":"#445566","in_progress":"#00FFAA","completed":"#00CC66","failed":"#FF4444"}

    def __init__(self, item, parent=None):
        super().__init__(parent)
        self.setFixedHeight(26)
        st = item.get("status","pending"); txt = item.get("content","")
        lo = QHBoxLayout(self); lo.setContentsMargins(8,1,8,1); lo.setSpacing(6)
        ic = QLabel(self._IC.get(st,"○")); ic.setFixedWidth(14)
        ic.setStyleSheet(f"color:{self._CL.get(st,'#445566')};font-size:12px;background:transparent;")
        c  = "#448866" if st=="completed" else "#00FFAA" if st=="in_progress" else \
             "#FF6666" if st=="failed" else "#556677"
        sk = "text-decoration:line-through;" if st=="completed" else ""
        bk = "font-weight:bold;" if st=="in_progress" else ""
        tx = QLabel(txt[:60]); tx.setStyleSheet(f"color:{c};font-size:10px;background:transparent;{sk}{bk}")
        lo.addWidget(ic); lo.addWidget(tx, 1)


# ─────────────────────────────────────────────────────────
# CODE LINE
# ─────────────────────────────────────────────────────────
class _CodeLine(QLabel):
    @staticmethod
    def _col(line):
        l = line.lower()
        if any(x in l for x in ["✔","done","complete","success","created","written","saved","built"]): return "#00CC66"
        if any(x in l for x in ["✗","error","fail","err","exception","traceback"]):                    return "#FF5555"
        if any(x in l for x in ["→","reading","writing","running","building","generating","fetching"]): return "#00AAFF"
        if any(x in l for x in ["todo","task","plan","step","installing"]):                             return "#FFAA00"
        if line.startswith("  └") or line.startswith("    "):                                          return "#336655"
        if line.startswith("[") or line.startswith("//"):                                              return "#888888"
        return "#7AABAA"

    def __init__(self, line, parent=None):
        super().__init__(line[:140], parent)
        self.setStyleSheet(
            f"color:{self._col(line)};font-family:Consolas,monospace;font-size:10px;"
            "background:transparent;padding:0px 6px;")
        self.setTextInteractionFlags(Qt.TextSelectableByMouse)


# ─────────────────────────────────────────────────────────
# ALIRA CODER PANEL
# ─────────────────────────────────────────────────────────
class ALIRACoderPanel(QWidget):
    sig_close = pyqtSignal()
    sig_done  = pyqtSignal(str)
    sig_error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MCPanel")
        self.setStyleSheet(
            "#MCPanel{background:rgba(0,10,24,0.99);"
            "border:1px solid rgba(0,200,130,0.45);border-radius:12px;}")
        self._engine     = ALIRACoderEngine()
        self._line_count = 0
        self._setup_ui()
        self._connect_engine()

    def _setup_ui(self):
        vl = QVBoxLayout(self); vl.setContentsMargins(0,0,0,0); vl.setSpacing(0)
        vl.addWidget(_AnimatedHeader(self))

        # Status bar
        sb  = QWidget(); sb.setFixedHeight(32)
        sb.setStyleSheet("background:#000D1A;border-bottom:1px solid rgba(0,150,90,0.20);")
        sbh = QHBoxLayout(sb); sbh.setContentsMargins(12,0,12,0); sbh.setSpacing(8)
        self._dot = QLabel("●")
        self._dot.setStyleSheet("color:#FFAA00;font-size:11px;background:transparent;")
        self._status = QLabel("Initializing...")
        self._status.setStyleSheet("color:#00BB77;font-size:11px;background:transparent;")
        self._stop_btn = QPushButton("■  Stop"); self._stop_btn.setFixedSize(72, 24)
        self._stop_btn.setStyleSheet(
            "QPushButton{background:rgba(180,20,20,0.3);border:1px solid rgba(220,40,40,0.5);"
            "border-radius:4px;color:#FF8888;font-size:10px;font-weight:bold;}"
            "QPushButton:hover{background:rgba(220,30,30,0.55);}")
        self._stop_btn.clicked.connect(self._on_stop)
        sbh.addWidget(self._dot); sbh.addWidget(self._status, 1); sbh.addWidget(self._stop_btn)
        vl.addWidget(sb)

        # Content row
        cw = QWidget(); cw.setStyleSheet("background:transparent;")
        ch = QHBoxLayout(cw); ch.setContentsMargins(0,0,0,0); ch.setSpacing(0)

        # — Todos —
        tw = QWidget(); tw.setFixedWidth(210)
        tw.setStyleSheet("background:#000D18;border-right:1px solid rgba(0,100,65,0.28);")
        tvl = QVBoxLayout(tw); tvl.setContentsMargins(0,6,0,6); tvl.setSpacing(2)
        th  = QLabel("  📋  TASK LIST"); th.setFixedHeight(24)
        th.setStyleSheet("color:#00BB66;font-size:10px;font-weight:bold;"
                         "background:transparent;letter-spacing:1px;")
        tvl.addWidget(th)
        self._todo_layout = QVBoxLayout()
        self._todo_layout.setContentsMargins(0,0,0,0); self._todo_layout.setSpacing(1)
        tvl.addLayout(self._todo_layout); tvl.addStretch(1)
        ch.addWidget(tw)

        # — Code output —
        ow = QWidget(); ow.setStyleSheet("background:transparent;")
        ovl = QVBoxLayout(ow); ovl.setContentsMargins(0,0,0,0); ovl.setSpacing(0)
        oh  = QLabel("  ⚡  LIVE OUTPUT"); oh.setFixedHeight(24)
        oh.setStyleSheet("color:#0099CC;font-size:10px;font-weight:bold;background:#000D18;"
                         "letter-spacing:1px;border-bottom:1px solid rgba(0,110,160,0.22);")
        ovl.addWidget(oh)
        self._scroll = QScrollArea(); self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{background:#001020;width:5px;border-radius:2px;}"
            "QScrollBar::handle:vertical{background:#003344;border-radius:2px;}")
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._code_widget = QWidget(); self._code_widget.setStyleSheet("background:transparent;")
        self._code_vl = QVBoxLayout(self._code_widget)
        self._code_vl.setContentsMargins(2,4,2,8); self._code_vl.setSpacing(1)
        self._code_vl.addStretch(1)
        self._scroll.setWidget(self._code_widget)
        ovl.addWidget(self._scroll, 1); ch.addWidget(ow, 1)
        vl.addWidget(cw, 1)

        # Bottom bar
        bot = QWidget(); bot.setFixedHeight(36)
        bot.setStyleSheet("background:#000D1A;border-top:1px solid rgba(0,140,90,0.20);")
        bh  = QHBoxLayout(bot); bh.setContentsMargins(14,0,14,0)
        self._prog = QLabel("⬡  ALIRA Coder ready")
        self._prog.setStyleSheet("color:#224433;font-family:Consolas;font-size:10px;background:transparent;")
        bh.addWidget(self._prog, 1); vl.addWidget(bot)

    def _connect_engine(self):
        self._engine.sig_started.connect(self._on_started)
        self._engine.sig_tool.connect(self._on_tool)
        self._engine.sig_tool_result.connect(self._on_tool_result)
        self._engine.sig_text.connect(self._on_text)
        self._engine.sig_todos.connect(self._on_todos)
        self._engine.sig_notice.connect(self._on_notice)
        self._engine.sig_code_line.connect(self._on_code_line)
        self._engine.sig_done.connect(self._on_done)
        self._engine.sig_error.connect(self._on_error)

    def start_task(self, task, output_dir=None):
        self._line_count = 0
        self._clear_code(); self._clear_todos()
        self._dot.setStyleSheet("color:#FFAA00;font-size:11px;background:transparent;")
        self._status.setText("Starting ALIRA Coder...")
        self._prog.setText(f"⬡  {task[:55]}...")
        self._engine.run(task, output_dir)

    def _clear_code(self):
        while self._code_vl.count() > 1:
            item = self._code_vl.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def _clear_todos(self):
        while self._todo_layout.count():
            item = self._todo_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def _add_line(self, line):
        if self._line_count >= 300:
            item = self._code_vl.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        else:
            self._line_count += 1
        idx = max(0, self._code_vl.count() - 1)
        self._code_vl.insertWidget(idx, _CodeLine(line))
        QTimer.singleShot(10, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()))

    def _on_started(self, prov, model):
        self._dot.setStyleSheet("color:#00FF88;font-size:11px;background:transparent;")
        self._status.setText(f"Running  •  {prov}  •  {model}")
        self._add_line(f"[ALIRA CODER] Started — {prov} / {model}")

    def _on_tool(self, label):
        self._add_line(f"  →  {label}"); self._prog.setText(f"⬡  {label[:52]}")

    def _on_tool_result(self, summary, ok):
        self._add_line(f"    └ {'✔' if ok else '✗'}  {summary}")

    def _on_text(self, delta):
        for ln in delta.split('\n'):
            if ln.strip(): self._add_line(f"  {ln.strip()}")

    def _on_todos(self, todos):
        self._clear_todos()
        for it in todos: self._todo_layout.addWidget(_TodoItem(it))

    def _on_notice(self, text):
        self._add_line(f"  ℹ  {text}")

    def _on_code_line(self, line):
        self._add_line(line)

    def _on_done(self, summary):
        self._dot.setStyleSheet("color:#00FF66;font-size:11px;background:transparent;")
        self._status.setText("✔  Website Complete!")
        self._add_line(""); self._add_line("━"*55)
        self._add_line("  ✔  ALIRA CODER — TASK COMPLETE!")
        self._add_line("━"*55)
        for ln in summary.split('\n'):
            if ln.strip(): self._add_line(f"  {ln}")
        self._prog.setText("✔  Website ready hai!")
        self.sig_done.emit(summary)

    def _on_error(self, msg):
        self._dot.setStyleSheet("color:#FF4444;font-size:11px;background:transparent;")
        self._status.setText("✗  Error")
        self._add_line(f"[ERROR]  {msg}")
        self._prog.setText("✗  Error — check above")
        self.sig_error.emit(msg)

    def _on_stop(self):
        self._engine.stop()
        self._dot.setStyleSheet("color:#FF8800;font-size:11px;background:transparent;")
        self._status.setText("Stopped by user")
        self._add_line("[ALIRA CODER] Stopped.")
        self.sig_close.emit()

    def closePanel(self):
        self._engine.stop()


# ─────────────────────────────────────────────────────────
# ALIRA CODER OVERLAY  ← v3.0 FINAL FIX
# QDialog with FramelessWindowHint — guaranteed visible
# ─────────────────────────────────────────────────────────
class ALIRACoderOverlay(QDialog):
    """
    v3.0: QDialog as overlay — 100% guaranteed visible.

    QWidget child overlay ka problem:
    - Qt child widget parent ke clip region se bahar nahi ja sakta
    - resize/geometry timing issues
    - Z-order issues with other children (GoalOrb, etc.)

    QDialog solution:
    - Frameless window on top of parent
    - Always visible, no clipping
    - eventFilter se parent ke saath move/resize
    """

    sig_done  = pyqtSignal(str)
    sig_error = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setModal(False)   # Non-blocking — ALIRA normal kaam karti rahe

        # Panel — poori dialog fill karo
        lo = QVBoxLayout(self); lo.setContentsMargins(10, 10, 10, 10); lo.setSpacing(0)
        self._panel = ALIRACoderPanel(self)
        self._panel.sig_done.connect(self._on_done)
        self._panel.sig_error.connect(self._on_error)
        self._panel.sig_close.connect(self.hide_panel)
        lo.addWidget(self._panel)

        # Parent window ke events track karo (move/resize ke liye)
        if parent:
            parent.installEventFilter(self)
            # Main window bhi (QMainWindow)
            top = parent.window()
            if top and top is not parent:
                top.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Parent move/resize hone pe apni position update karo."""
        if event.type() in (QEvent.Move, QEvent.Resize, QEvent.Show):
            if self.isVisible():
                self._fit_to_parent()
        return super().eventFilter(obj, event)

    def _fit_to_parent(self):
        """Parent window ke upar position set karo."""
        par = self.parent()
        if not par: return
        # Main window ka global position lao
        win = par.window()
        if win:
            geo = win.geometry()           # screen coordinates
            # Topbar height skip karo (~40px) — content area pe cover
            topbar_h = 40
            self.setGeometry(
                geo.x(),
                geo.y() + topbar_h,
                geo.width(),
                geo.height() - topbar_h
            )

    def show_panel(self, task: str, output_dir: str = None):
        """Panel dikhao aur task shuru karo."""
        self._fit_to_parent()
        self.show()
        self.raise_()
        self.activateWindow()
        self._panel.start_task(task, output_dir)

    def hide_panel(self):
        """Panel band karo."""
        self._panel.closePanel()
        self.hide()

    def _on_done(self, summary):
        self.sig_done.emit(summary)

    def _on_error(self, msg):
        self.sig_error.emit(msg)

    def paintEvent(self, e):
        """Dark semi-transparent background."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Full dark overlay
        p.fillRect(self.rect(), QColor(2, 8, 20, 230))
        p.end()

    def keyPressEvent(self, e):
        """Escape se panel band ho."""
        if e.key() == Qt.Key_Escape:
            self.hide_panel()
        else:
            super().keyPressEvent(e)