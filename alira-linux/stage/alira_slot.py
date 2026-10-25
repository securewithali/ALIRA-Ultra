# -*- coding: utf-8 -*-
"""
ALIRA_slot.slot(fn) — PyQt slot wrapper jo compiled (Cython) build mein bhi chalta hai.

PyQt, pure-Python slot ko signal ke jitne arguments le sake utne hi deta hai (clicked(bool) -> fn() bhi chalta hai).
Cython-compiled function par ye "kam args ke saath dobara try" kaam nahi karta: `_kill() takes exactly 1 positional
argument (2 given)` aur PyQt process abort kar deta hai. slot() wahi retry khud kar deta hai.

    btn.clicked.connect(slot(self._save))
"""
import re

try:
    from PyQt5.QtCore import pyqtBoundSignal
except Exception:                                   # pragma: no cover
    pyqtBoundSignal = ()

_ARGERR = re.compile(r"positional argument|takes (exactly|at most|no) |were given|was given|\d+ given|too many arguments|too few arguments|expected \d+ argument|takes no arguments")


def slot(fn):
    if isinstance(fn, pyqtBoundSignal) or not callable(fn):
        return fn                                   # signal -> signal connect, ya already sahi cheez
    try:
        from PyQt5 import sip
        if isinstance(getattr(fn, "__self__", None), sip.simplewrapper) and type(fn).__name__ == "builtin_function_or_method":
            return fn                               # Qt ka apna method (accept/reject/close...) — PyQt khud sambhalta hai
    except Exception:
        pass

    name = getattr(fn, "__name__", "")

    def _call(*args):
        n = len(args)
        while True:
            try:
                return fn(*args[:n])
            except TypeError as e:
                msg = str(e)
                if n > 0 and name in msg and _ARGERR.search(msg):
                    n -= 1                          # signature mismatch (arg-count) — ek kam arg se phir try
                    continue
                raise

    return _call
