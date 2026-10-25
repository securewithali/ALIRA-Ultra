# -*- coding: utf-8 -*-
"""
ALIRA WebForge — Integration Patch for main.py (ALIRA_v7_4.py)
=============================================================
Ye file tumhare existing main.py mein WebForge integrate karne ke
step-by-step instructions deti hai.

3 jagah changes karne hain:
  1. Import section (top pe)
  2. TABBUWindow.__init__ ya _build_ui ke andar
  3. GeminiWorker.sig_TABBU_msg handler mein command routing

Bas copy-paste karo neeche diye gaye sections ko.
"""

# ═══════════════════════════════════════════════════════════
# STEP 1 — main.py ke TOP pe yeh import add karo
#          (existing imports ke baad)
# ═══════════════════════════════════════════════════════════

STEP_1_IMPORT = """
# ── WebForge AI Website Builder ─────────────────────────────────
try:
    from website_builder.webforge_manager import WebForgeManager
    _webforge = WebForgeManager()
    _HAS_WEBFORGE = True
    print("[ALIRA] WebForge module loaded ✅")
except ImportError as _wf_err:
    _HAS_WEBFORGE = False
    _webforge     = None
    print(f"[ALIRA] WebForge not available: {_wf_err}")
    print("[ALIRA] Run: pip install python-dotenv requests google-genai qrcode[pil]")
"""


# ═══════════════════════════════════════════════════════════
# STEP 2 — TABBUWindow._start_worker() ke andar, worker signals
#          connect karne ke BAAD, yeh line add karo:
# ═══════════════════════════════════════════════════════════

STEP_2_WORKER = """
        # WebForge — text messages intercept karne ke liye
        self._worker.sig_user_msg.connect(self._on_user_msg_webforge)
"""


# ═══════════════════════════════════════════════════════════
# STEP 3 — TABBUWindow class mein yeh naya method add karo
# ═══════════════════════════════════════════════════════════

STEP_3_METHOD = '''
    def _on_user_msg_webforge(self, text: str):
        """
        Har user message check karo — agar WebForge command hai
        to handle karo, warna ALIRA normal response degi.
        """
        if not _HAS_WEBFORGE or not _webforge:
            return
        if not _webforge.is_webforge_command(text):
            return

        # WebForge command detected!
        self._chat.add_sys(f"🌐 WebForge command detected: {text[:60]}...")
        self._topbar.set_status("thinking", "WEBFORGE ⚙")
        self._orb.set_state("thinking")

        import threading
        def _run():
            result = _webforge.handle_command(text, parent_widget=self)
            # UI update main thread pe karo
            from PyQt5.QtCore import QMetaObject, Q_ARG, Qt
            if result["success"]:
                msg = (
                    f"✅ Website ready!\\n"
                    f"🌐 Live: {result.get('live_url','—')}\\n"
                    f"🐙 GitHub: {result.get('github_url','—')}\\n"
                    f"👁 Preview: {result.get('preview_url','—')}"
                )
                self._worker.send_text(
                    f"Website successfully banaya aur deploy kiya! "
                    f"Live URL hai: {result.get('live_url','deploy ho rahi hai')}. "
                    f"User ko batao ki website ready hai aur QR code bhi show ho gaya hai."
                )
            else:
                msg = f"❌ WebForge error: {result['message']}"
                self._worker.send_text(
                    f"Website banane mein error aayi: {result['message'][:100]}. "
                    f"User ko batao aur solution suggest karo."
                )
            # Chat update
            from PyQt5.QtWidgets import QApplication
            QApplication.instance().postEvent(
                self, _WebForgeEvent(msg)
            )

        threading.Thread(target=_run, daemon=True).start()
'''


# ═══════════════════════════════════════════════════════════
# STEP 4 — Yeh helper event class bhi add karo (class ke bahar)
# ═══════════════════════════════════════════════════════════

STEP_4_EVENT = """
from PyQt5.QtCore import QEvent

class _WebForgeEvent(QEvent):
    TYPE = QEvent.Type(QEvent.registerEventType())
    def __init__(self, msg: str):
        super().__init__(self.TYPE)
        self.msg = msg
"""


# ═══════════════════════════════════════════════════════════
# STEP 5 — TABBUWindow.event() override karo ya customEvent:
# ═══════════════════════════════════════════════════════════

STEP_5_EVENT_HANDLER = """
    def customEvent(self, event):
        if isinstance(event, _WebForgeEvent):
            self._chat.add_sys(event.msg)
            self._topbar.set_status("standby", "STANDBY")
            self._orb.set_state("idle")
        else:
            super().customEvent(event)
"""


# ───────────────────────────────────────────────────────────
# QUICK INTEGRATION (Recommended):
# Sirf yeh ek function copy karo aur main.py mein paste karo
# ───────────────────────────────────────────────────────────

def apply_webforge_patch_to_window(window_class):
    """
    Decorator style patch — TABBUWindow class ko monkey-patch karta hai.
    main.py ke BOTTOM pe, agar __name__ == '__main__' se PEHLE, add karo:

        from webforge_integration import apply_webforge_patch_to_window
        apply_webforge_patch_to_window(TABBUWindow)
    """
    try:
        from .webforge_manager import WebForgeManager
        _wf = WebForgeManager()
    except ImportError as e:
        print(f"[WebForge] Not available: {e}")
        return window_class

    import threading
    from PyQt5.QtCore import QEvent

    class _WFEvent(QEvent):
        TYPE = QEvent.Type(QEvent.registerEventType())
        def __init__(self, msg, ok):
            super().__init__(self.TYPE)
            self.msg = msg
            self.ok  = ok

    original_start_worker = window_class._start_worker

    def _patched_start_worker(self):
        original_start_worker(self)
        # Connect WebForge interceptor AFTER worker is created
        self._worker.sig_user_msg.connect(
            lambda txt: _intercept(self, _wf, txt, _WFEvent)
        )

    def _intercept(win, wf, text, WFEvent):
        if not wf.is_webforge_command(text):
            return
        win._chat.add_sys(f"🌐 WebForge: {text[:50]}...")
        win._topbar.set_status("thinking", "WEBFORGE ⚙")
        win._orb.set_state("thinking")

        def _run():
            result = wf.handle_command(text, parent_widget=win)
            if result["success"]:
                win._worker.send_text(
                    f"Website banaya aur deploy kiya! "
                    f"Live URL: {result.get('live_url','deploy ho rahi hai')}. "
                    f"QR code bhi show ho gaya. User ko congratulate karo!"
                )
                msg = (f"✅ Deployed!\n"
                       f"Live: {result.get('live_url','—')}\n"
                       f"GitHub: {result.get('github_url','—')}")
            else:
                win._worker.send_text(
                    f"WebForge error: {result['message'][:80]}. Help karo."
                )
                msg = f"❌ {result['message']}"

            from PyQt5.QtWidgets import QApplication
            QApplication.instance().postEvent(win, WFEvent(msg, result["success"]))

        threading.Thread(target=_run, daemon=True).start()

    def _custom_event(self, event):
        if isinstance(event, _WFEvent):
            self._chat.add_sys(event.msg)
            self._topbar.set_status("standby", "STANDBY")
            self._orb.set_state("idle")
        else:
            super(window_class, self).customEvent(event)

    window_class._start_worker  = _patched_start_worker
    window_class.customEvent    = _custom_event
    print("[WebForge] ✅ Patch applied to TABBUWindow")
    return window_class


if __name__ == "__main__":
    print("WebForge Integration Patch — Documentation:")
    print(STEP_1_IMPORT)
    print("\n" + "="*60)
    print("STEP 2 — In _start_worker():")
    print(STEP_2_WORKER)
    print("\n" + "="*60)
    print("STEP 3 — New method:")
    print(STEP_3_METHOD)