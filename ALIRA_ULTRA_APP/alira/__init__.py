# -*- coding: utf-8 -*-
"""ALIRA AI Assistant"""
import sys
from pathlib import Path
_here = Path(__file__).resolve().parent
_root = _here.parent
for _p in [str(_root), str(_here)]:
    if _p not in sys.path: sys.path.insert(0, _p)
__version__ = "0.3.3"
__author__  = "Md Ali"
