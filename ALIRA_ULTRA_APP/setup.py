# -*- coding: utf-8 -*-
"""
Build customization for ALIRA AI Assistant.

All metadata/dependencies/package lists live in pyproject.toml - this file
only wires up a build step pyproject.toml can't express: shipping COMPILED
code instead of plain-text .py source in the wheel.

Two protection levels (wheel mein .py source KABHI nahi jaata):

  default            .py -> sourceless .pyc  (bytecode; decompile ho sakta hai)
  ALIRA_NATIVE=1      .py -> native machine code (.pyd) via Cython + MSVC
                     (bytecode nahi, source wapas banana bahut mushkil; jo module
                      compile na ho sake wo apne aap .pyc par fall back karta hai)

    # native build (Windows, MSVC Build Tools chahiye):
    set ALIRA_NATIVE=1
    python -m build --wheel --no-isolation

IMPORTANT: .pyc / .pyd dono us exact CPython build (3.11, win_amd64) se bandhe hain,
isliye wheel "cp311-win_amd64" tag ke saath banta hai (bdist_wheel_compiled below).
Do NOT upload the sdist to PyPI - it contains plain .py source (MANIFEST.in).
"""
import os
import py_compile
import re
from pathlib import Path

from setuptools import Extension, setup
from setuptools.command.build_ext import build_ext as _build_ext
from setuptools.command.build_py import build_py as _build_py

try:
    from wheel.bdist_wheel import bdist_wheel as _bdist_wheel
except ImportError:
    _bdist_wheel = None

ROOT = Path(__file__).resolve().parent
NATIVE = os.environ.get("ALIRA_NATIVE") == "1"
PACKAGES = ("ALIRA", "TABBU_modules", "website_builder")
# Ye modules native nahi banenge (-m / package-init ke liye .pyc hi chahiye)
_KEEP_PYC = {"ALIRA.__main__"}
_SKIP = {m.strip() for m in os.environ.get("ALIRA_NATIVE_SKIP", "").split(",") if m.strip()}


def _top_modules():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"py-modules\s*=\s*\[(.*?)\]", text, re.S)
    return re.findall(r'"([^"]+)"', block.group(1)) if block else []


def _native_candidates():
    """{dotted_module_name: relative .py path}"""
    out = {}
    for m in _top_modules():
        if (ROOT / f"{m}.py").exists():
            out[m] = f"{m}.py"
    for pkg in PACKAGES:
        for p in (ROOT / pkg).rglob("*.py"):
            if "__pycache__" in p.parts or p.name == "__init__.py":
                continue
            rel = p.relative_to(ROOT)
            out[".".join(rel.with_suffix("").parts)] = str(rel).replace("\\", "/")
    return {k: v for k, v in out.items() if k not in _KEEP_PYC and k not in _SKIP}


_NATIVE = _native_candidates() if NATIVE else {}


def _pyc_and_remove(py_path):
    py_compile.compile(py_path, cfile=py_path[:-3] + ".pyc", doraise=True)
    os.remove(py_path)


class build_py_compiled(_build_py):
    """Normal modules: .py -> .pyc (aur .py hata do). Native-candidates ko build_ext tak .py hi rehne do."""

    def run(self):
        super().run()
        for root, _dirs, files in os.walk(self.build_lib):
            for name in files:
                if not name.endswith(".py"):
                    continue
                py_path = os.path.join(root, name)
                rel = os.path.relpath(py_path, self.build_lib)
                mod = ".".join(Path(rel).with_suffix("").parts)
                if mod in _NATIVE:
                    continue                                   # build_ext ke baad decide hoga (.pyd mila ya pyc fallback)
                _pyc_and_remove(py_path)


class build_ext_native(_build_ext):
    def finalize_options(self):
        super().finalize_options()
        self.parallel = int(os.environ.get("ALIRA_NATIVE_JOBS", "4"))     # bade files memory khate hain — zyada parallel mat karo

    def run(self):
        super().run()
        # fix-up: jis module ka .pyd bana uska .py hata do; jiska nahi bana usko .pyc bana do (kabhi .py wheel mein nahi)
        built = 0
        fallback = []
        for mod in _NATIVE:
            parts = mod.split(".")
            pyd_dir = os.path.join(self.build_lib, *parts[:-1])
            has_pyd = os.path.isdir(pyd_dir) and any(
                f.startswith(parts[-1] + ".") and f.endswith(".pyd") for f in os.listdir(pyd_dir))
            py_path = os.path.join(self.build_lib, *parts) + ".py"
            if os.path.exists(py_path):
                if has_pyd:
                    os.remove(py_path)
                    built += 1
                else:
                    _pyc_and_remove(py_path)
                    fallback.append(mod)
            elif has_pyd:
                built += 1
        print(f"[native] {built} modules -> .pyd | {len(fallback)} fallback -> .pyc: {fallback}")


cmdclass = {"build_py": build_py_compiled}
ext_modules = []

if NATIVE:
    from Cython.Build import cythonize
    import Cython.Compiler.Options as _CyOpts

    _CyOpts.docstrings = False                              # docstrings binary mein nahi jaayenge
    exts = [Extension(name, [path], optional=True) for name, path in sorted(_NATIVE.items())]
    ext_modules = cythonize(
        exts,
        compiler_directives={"language_level": "3", "embedsignature": False, "emit_code_comments": False},
        build_dir="build/cython",
        nthreads=0,                                         # serial: Cython.Options.docstrings workers tak nahi pahunchta (Windows spawn)
        exclude_failures=True,                              # Cython jo module compile na kar paye usko pyc par chhod do
        quiet=True,
    )
    cmdclass["build_ext"] = build_ext_native
    _NATIVE = {k: v for k, v in _NATIVE.items() if k in {e.name for e in ext_modules}}   # sirf jo cythonize hue

if _bdist_wheel is not None:
    class bdist_wheel_compiled(_bdist_wheel):
        def finalize_options(self):
            super().finalize_options()
            self.root_is_pure = False

    cmdclass["bdist_wheel"] = bdist_wheel_compiled

setup(cmdclass=cmdclass, ext_modules=ext_modules)
