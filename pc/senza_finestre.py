# senza_finestre.py - importalo PER PRIMO negli script lanciati dalle attivita' pianificate (pythonw):
# ogni processo figlio (ssh, adb, ffmpeg, rclone...) parte senza aprire una finestra di console.
import subprocess, sys

if sys.platform == "win32" and not getattr(subprocess, "_senza_finestre", False):
    _init = subprocess.Popen.__init__

    def _senza(self, *a, **k):
        k["creationflags"] = k.get("creationflags", 0) | 0x08000000  # CREATE_NO_WINDOW
        _init(self, *a, **k)

    subprocess.Popen.__init__ = _senza
    subprocess._senza_finestre = True
