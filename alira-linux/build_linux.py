# -*- coding: utf-8 -*-
"""Linux package (ALIRA-linux) ka staging folder banao aur wheel build karo.

    python build_linux.py 0.1.0
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
APP = HERE.parent / "ALIRA_ULTRA_APP"
STAGE = HERE / "stage"
VERSION = sys.argv[1] if len(sys.argv) > 1 else "0.1.0"

SKIP_DIRS = {"dist", "dist_native", "build", "__pycache__", "admin_and_build_tools", "backend", "Projects", ".git", "node_modules",
             "tests", "stage"}
SKIP_FILES = {"TABBU_login.py", "firebase_connection.py", "face_auth.py", "TABBU_daemon.py", "TABBU_startup.py", "main_hotkey.py", ".env", ".env.example", "setup.py", "ALIRA_ULTRA.spec", "install_ALIRA.cmd"}
WIN_DEPS = ("pywin32", "pywinauto", "pyaudio", "pygetwindow", "wmi", "comtypes", "pycaw", "pyttsx3", "pynput", "pywhatkit",
            "pyinstaller", "opencv-python>")

if STAGE.exists():
    shutil.rmtree(STAGE)
STAGE.mkdir()


def copy_tree(src: Path, dst: Path):
    for p in src.iterdir():
        if p.name in SKIP_DIRS or p.name.startswith("TITAN_") or p.name.startswith("TABBU_") or p.name.endswith(".egg-info") or p.name.endswith(".pyc"):
            continue
        if p.is_dir():
            if p.name == "ALIRA_coder":                       # sirf compiled engine (dist/) — Linux par bhi node chahiye
                continue
            copy_tree(p, dst / p.name)
        elif p.name not in SKIP_FILES:
            dst.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst / p.name)


copy_tree(APP, STAGE)
for f in ("ALIRA_linux_boot.py", "ALIRA_linux_tools.py", "linux_extra.py"):
    shutil.copy2(HERE / "src" / f, STAGE / f)

pp = (APP / "pyproject.toml").read_text(encoding="utf-8")
pp = re.sub(r'^name = ".*"$', 'name = "ALIRA-linux"', pp, flags=re.M)
pp = re.sub(r'^version = ".*"$', f'version = "{VERSION}"', pp, flags=re.M)
pp = pp.replace('description = "ALIRA AI Assistant — intelligent desktop companion with voice, vision, automation, and productivity tools."',
                'description = "ALIRA AI Assistant for Linux — same desktop UI, Gemini Live voice, 148+ languages and Linux system control."')
pp = pp.replace('"Operating System :: Microsoft :: Windows"', '"Operating System :: POSIX :: Linux"')
pp = pp.replace('"Programming Language :: Python :: 3.10",', '"Programming Language :: Python :: 3.10",\n  "Environment :: X11 Applications :: Qt",')
deps_i = pp.index("dependencies = [")
deps_j = pp.index("]", deps_i)
deps = [l for l in pp[deps_i:deps_j].splitlines()[1:] if l.strip().startswith('"')]
deps = [d for d in deps if not any(w in d.lower() for w in WIN_DEPS)]
deps += ['  "opencv-python-headless>=4.5.0",', '  "python-xlib>=0.33",', '  "pytesseract>=0.3.8",'] + ([] if any("rapidfuzz" in d for d in deps) else ['  "rapidfuzz>=3.0.0",'])
pp = pp[:deps_i] + "dependencies = [\n" + "\n".join(deps) + "\n" + pp[deps_j:]
pp = re.sub(r"\[project\.scripts\].*?\n\n", '[project.scripts]\nALIRA-linux = "ALIRA_linux_boot:main"\nALIRA-linux-gui = "ALIRA_linux_boot:main"\n\n', pp, flags=re.S)
pp = pp.replace('py-modules = [', 'py-modules = [\n  "ALIRA_linux_boot", "ALIRA_linux_tools", "linux_extra",', 1)
pp = pp.replace('  "ALIRA_coder", "ALIRA_coder.*",\n', "")
pp = re.sub(r'"ALIRA_coder"\s*=\s*\[.*?\]\n', "", pp, flags=re.S)
(STAGE / "pyproject.toml").write_text(pp, encoding="utf-8")

(STAGE / "MANIFEST.in").write_text("include README.md\ninclude LICENSE*\nrecursive-include TABBU_modules *.png *.jpg *.xml\n"
                                   "recursive-include assets *\nrecursive-include fonts *\n", encoding="utf-8")
# py-modules mein jo file stage mein nahi (Windows-only skip) wo setuptools ko dikhaye na — missing ho to hata do
mods = re.search(r"py-modules = \[(.*?)\]", pp, flags=re.S).group(1)
missing = [m for m in re.findall(r'"([\w]+)"', mods) if not (STAGE / f"{m}.py").exists()]
if missing:
    pp2 = pp
    for m in missing:
        pp2 = pp2.replace(f'"{m}", ', "").replace(f'"{m}",', "").replace(f', "{m}"', "")
    (STAGE / "pyproject.toml").write_text(pp2, encoding="utf-8")
    print("py-modules mein se hataye (stage mein nahi the):", missing)

if not (STAGE / "README.md").exists():
    (STAGE / "README.md").write_text("# ALIRA for Linux\n", encoding="utf-8")
(STAGE / "README.md").write_text((HERE / "README.md").read_text(encoding="utf-8"), encoding="utf-8")

out = HERE / "dist"
if out.exists():
    shutil.rmtree(out)
r = subprocess.run([sys.executable, "-m", "build", "--outdir", str(out)], cwd=STAGE)
print("exit", r.returncode, sorted(p.name for p in out.glob("*")) if out.exists() else "")
sys.exit(r.returncode)
