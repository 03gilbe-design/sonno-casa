"""Lanciatore per le attivita' pianificate (pythonw non ha console): esegue lo script dato e scrive in
senza una riga di log).   pythonw avvia_logga.py C:\\sonno_tex\\kaggle_mattino.py [argomenti...]"""
import os, runpy, sys, traceback
from datetime import datetime

LOG = r"C:\sonno_audio\avvii_errori.log"
script = sys.argv[1]
sys.argv = sys.argv[1:]
sys.path.insert(0, os.path.dirname(os.path.abspath(script)))
os.chdir(os.path.dirname(os.path.abspath(script)))
try:
    runpy.run_path(script, run_name="__main__")
except SystemExit as e:
    if e.code not in (None, 0):
        open(LOG, "a", encoding="utf-8").write(f"{datetime.now():%Y-%m-%dT%H:%M:%S} {script} SystemExit {e.code}\n")
    raise
except BaseException:  # noqa: BLE001
    open(LOG, "a", encoding="utf-8").write(f"{datetime.now():%Y-%m-%dT%H:%M:%S} {script}\n{traceback.format_exc()}\n")
    raise
