# -*- coding: utf-8 -*-
"""
ALIRA Autostart + Background mode + Single instance
==================================================
  * Windows login/restart par ALIRA khud chalu (HKCU Run key — admin nahi chahiye, Task Manager ->
    Startup apps mein "ALIRA" dikhta hai; chalne par process Task Manager mein dikhta hai)
  * --background: window nahi, sirf mini orb (aur tray icon)
  * Single instance: dobara chalaane par nayi copy nahi banti — chalti hui ALIRA ka window khul jaata hai

Command line:
    ALIRA install            # startup ON + abhi background mein chalu
    ALIRA uninstall          # startup OFF
    ALIRA --background       # sirf orb ke saath chalo
    ALIRA_ULTRA.exe --install-startup / --uninstall-startup / --background
"""

import os
import sys
from pathlib import Path

APP_NAME = "ALIRA"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
SINGLE_KEY = "ALIRA_ULTRA_SINGLE_INSTANCE_V1"


def is_background_launch(argv=None) -> bool:
    argv = sys.argv if argv is None else argv
    return "--background" in argv or os.environ.get("ALIRA_BACKGROUND") == "1"


# ══════════════════════════════════════════════════════════════════
# STARTUP COMMAND
# ══════════════════════════════════════════════════════════════════
def _pythonw() -> str:
    exe = Path(sys.executable)
    w = exe.with_name("pythonw.exe")
    return str(w if w.exists() else exe)


def launch_command(background: bool = True) -> str:
    """Registry mein jo command jayegi (EXE / pip install / source — teeno ke liye)."""
    flag = " --background" if background else ""
    if getattr(sys, "frozen", False):                               # PyInstaller EXE
        return f'"{sys.executable}"{flag}'
    here = Path(__file__).resolve().parent
    if "site-packages" in str(here).lower():                        # pip install
        return f'"{_pythonw()}" -m ALIRA{flag}'
    return f'"{_pythonw()}" "{here / "Main_normal.py"}"{flag}'      # source tree


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except Exception:
        return False


def registered_command():
    """Registry mein ABHI jo startup command saved hai (ya None)."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as k:
            return winreg.QueryValueEx(k, APP_NAME)[0]
    except Exception:
        return None


def enable(background: bool = True) -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, launch_command(background))
        return True
    except Exception as e:
        print(f"[Autostart] enable: {e}")
        return False


def disable() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            winreg.DeleteValue(k, APP_NAME)
        return True
    except FileNotFoundError:
        return True
    except Exception as e:
        print(f"[Autostart] disable: {e}")
        return False


def spawn_background() -> bool:
    """Ek naya detached background ALIRA process shuru karo (install ke turant baad)."""
    import subprocess
    try:
        cmd = launch_command(True)
        flags = 0x00000008 | 0x00000200 | 0x08000000      # DETACHED | NEW_PROCESS_GROUP | NO_WINDOW
        subprocess.Popen(cmd, shell=False, creationflags=flags, close_fds=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        print(f"[Autostart] spawn: {e}")
        return False


def handle_cli_flags(argv=None) -> bool:
    """--install-startup / --uninstall-startup. True = flag handle ho gaya (app mat chalao)."""
    argv = sys.argv if argv is None else argv
    if "--install-startup" in argv:
        ok = enable(True)
        print("[ALIRA] Windows startup ON" if ok else "[ALIRA] startup ON nahi ho paya")
        return True
    if "--uninstall-startup" in argv:
        ok = disable()
        print("[ALIRA] Windows startup OFF" if ok else "[ALIRA] startup OFF nahi ho paya")
        return True
    return False


# ══════════════════════════════════════════════════════════════════
# SINGLE INSTANCE  (QLocalServer — pehli copy server, baaki client)
# ══════════════════════════════════════════════════════════════════
def make_single_instance():
    from PyQt5.QtCore import QObject, pyqtSignal
    from PyQt5.QtNetwork import QLocalServer, QLocalSocket

    class SingleInstance(QObject):
        sig_show = pyqtSignal()

        def __init__(self):
            super().__init__()
            self._server = None

        def acquire(self) -> bool:
            """True = ye pehli copy hai. False = pehle se chal rahi hai (usse 'show' bhej diya)."""
            sock = QLocalSocket()
            sock.connectToServer(SINGLE_KEY)
            if sock.waitForConnected(400):
                sock.write(b"show")
                sock.flush()
                sock.waitForBytesWritten(400)
                sock.disconnectFromServer()
                return False
            QLocalServer.removeServer(SINGLE_KEY)          # purani crash ka bacha hua socket
            self._server = QLocalServer(self)
            ok = self._server.listen(SINGLE_KEY)
            if ok:
                self._server.newConnection.connect(self._on_conn)
            return True

        def _on_conn(self):
            while self._server and self._server.hasPendingConnections():
                c = self._server.nextPendingConnection()
                c.waitForReadyRead(200)
                c.readAll()
                c.disconnectFromServer()
                self.sig_show.emit()

    return SingleInstance()
