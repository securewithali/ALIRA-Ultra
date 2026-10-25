# -*- coding: utf-8 -*-
"""
ALIRA Autostart + Background mode + Single instance
==================================================
  * Windows login/restart par ALIRA khud chalu (HKCU Run key — admin nahi chahiye, Task Manager ->
    Startup apps mein "ALIRA" dikhta hai; chalne par process Task Manager mein dikhta hai)
  * --background: window nahi, sirf mini orb (aur tray icon)
  * Single instance: dobara chalaane par nayi copy nahi banti — chalti hui ALIRA ka window khul jaata hai

Command line:
    alira install            # startup ON + abhi background mein chalu
    alira uninstall          # startup OFF
    alira --background       # sirf orb ke saath chalo
    alira.exe --install-startup / --uninstall-startup / --background
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
def _kill_stale(pid=0):
    """Atki hui purani ALIRA process hatao (pid pata ho to wahi, warna 'ALIRA' wali dusri python processes)."""
    try:
        import psutil
    except Exception:
        return
    me = os.getpid()
    mine = {me}
    try:
        mine |= {p.pid for p in psutil.Process(me).parents()}
    except Exception:
        pass
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if p.pid in mine:
                continue
            if pid and p.pid != pid:
                continue
            cl = " ".join(p.info.get("cmdline") or [])
            if not pid and not ("-m ALIRA" in cl or "Main_normal" in cl or "ALIRA_linux_boot" in cl or "ALIRA-linux" in cl):
                continue
            if "python" not in (p.info.get("name") or "").lower() and "ALIRA" not in (p.info.get("name") or "").lower():
                continue
            p.terminate()
            try:
                p.wait(3)
            except Exception:
                p.kill()
        except Exception:
            continue


def make_single_instance():
    import time
    from PyQt5.QtCore import QObject, pyqtSignal
    from PyQt5.QtNetwork import QLocalServer, QLocalSocket

    class SingleInstance(QObject):
        sig_show = pyqtSignal()

        def __init__(self):
            super().__init__()
            self._server = None
            self._ready = False
            self._busy = False
            self._t0 = time.time()

        def set_busy(self, on=True):
            """Setup dialog (API key/naam) khula hai — ise atka hua mat samjho."""
            self._busy = bool(on)

        def mark_ready(self):
            """Main window ban chuki hai — ab 'show' ka jawab READY milega."""
            self._ready = True

        def acquire(self) -> bool:
            """True = ye pehli copy hai. False = pehle se chal rahi hai (usse 'show' bhej diya).
            Purani copy atki hui (window nahi ban payi / jawab nahi deti) ho to use hata kar ye copy le leti hai."""
            sock = QLocalSocket()
            sock.connectToServer(SINGLE_KEY)
            if sock.waitForConnected(400):
                sock.write(b"show")
                sock.flush()
                sock.waitForBytesWritten(400)
                got = sock.waitForReadyRead(2500)
                reply = bytes(sock.readAll()).decode("utf-8", "ignore") if got else ""
                closed = sock.state() == QLocalSocket.UnconnectedState
                sock.disconnectFromServer()
                parts = reply.split("|")
                state = parts[0]
                pid = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                try:
                    age = float(parts[2]) if len(parts) > 2 else 0.0
                except ValueError:
                    age = 0.0
                limit = float(os.environ.get("ALIRA_ZOMBIE_SECS", "75"))
                if state in ("READY", "BUSY"):
                    return False
                if state == "LOADING" and age < limit:
                    print("[ALIRA] Pehli copy abhi start ho rahi hai — thoda ruko.")
                    return False
                if not got and closed:
                    return False                              # purana version (jawab nahi deta par theek chal raha hai)
                print(f"[ALIRA] Purani copy atki hui hai (state={state or 'no-reply'}) — hata kar nayi chala rahi hoon.")
                _kill_stale(pid)
                time.sleep(0.5)
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
                state = "READY" if self._ready else ("BUSY" if self._busy else "LOADING")
                c.write(f"{state}|{os.getpid()}|{time.time() - self._t0:.0f}".encode())
                c.flush()
                c.waitForBytesWritten(300)
                c.disconnectFromServer()
                if self._ready:
                    self.sig_show.emit()

    return SingleInstance()
