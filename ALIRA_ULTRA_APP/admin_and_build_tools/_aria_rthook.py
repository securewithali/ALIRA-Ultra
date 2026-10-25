# -*- coding: utf-8 -*-
"""
TABBU/ALIRA — PyInstaller Runtime Hook  v5  [SECURE]
===================================================
- Firebase JSON path setup REMOVED (backend API use hoti hai)
- TITAN_Notes + required user directories create karta hai
- Backend URL env vTABBUble set karta hai (EXE mein)
"""
import sys, os

if getattr(sys, 'frozen', False):
    _base = sys._MEIPASS

    # 1. _MEIPASS ko sys.path mein daalo
    for _p in [_base, os.path.join(_base,'TABBU_modules'), os.path.join(_base,'ALIRA')]:
        if os.path.isdir(_p) and _p not in sys.path:
            sys.path.insert(0, _p)

    # 2. pyttsx3 SAPI5
    os.environ.setdefault('PYTTSX3_DRIVER', 'sapi5')

    # 3. Backend URL — EXE mein bhi same API use hogi
    os.environ.setdefault('ALIRA_BACKEND_URL', 'https://api.SecureWithAli.in')

    # 4. Required directories create karo (TITAN_Notes error fix)
    _home = os.path.expanduser('~')
    _docs = os.path.join(_home, 'Documents')
    for _d in [
        os.path.join(_docs, 'TITAN_Notes'),
        os.path.join(_docs, 'TITAN_Recordings'),
        os.path.join(_docs, 'TITAN_Wallpapers'),
        os.path.join(_docs, 'TITAN_PDFs'),
        os.path.join(_home, 'TITAN_Codes'),
        os.path.join(_home, 'TABBU_Downloads'),
        os.path.join(os.environ.get('APPDATA', _home), 'ALIRA'),
    ]:
        try: os.makedirs(_d, exist_ok=True)
        except Exception: pass

# Block onnxruntime
class _OnnxBlocker:
    def find_module(self, name, path=None):
        if name and ('onnxruntime' in name or name == 'onnx'): return self
    def load_module(self, name): raise ImportError(f'Blocked: {name}')

sys.meta_path.insert(0, _OnnxBlocker())
