"""Attivita' Windows SonnoMappaRussare (ogni 15'): rifa' la mappa del russare della notte appena finita.
Parte solo se: sei sveglio certo (stato.json del telefono) + PC fermo da 10' (dopo le 18:00 basta sveglio certo) + la mappa di oggi non e' gia' stata fatta col calcolo pesante.
Lanciata da pythonw: log in C:\sonno_audio\mappe\_src\auto.log."""
import senza_finestre  # noqa: F401  (primo: niente finestre dei processi figli)
import json, os, sys, time
from datetime import datetime
sys.path.insert(0, r"C:\sonno_tex")
import mappa_russare as MR

os.makedirs(MR.SRC, exist_ok=True)
sys.stdout = sys.stderr = open(MR.SRC + r"\auto.log", "a", encoding="utf-8", buffering=1)
day = datetime.now().strftime("%Y%m%d")
J = MR.OUT + rf"\mappa_{day}.json"
nessuna = MR.SRC + rf"\nessuna_{day}.txt"  # "nessuna notte riconosciuta": non riprovare per 2 ore
if (os.path.exists(J) and json.load(open(J, encoding="utf-8"))["tempi_s"].get("pesante")) \
        or (os.path.exists(nessuna) and time.time() - os.path.getmtime(nessuna) < 7200):
    sys.exit()
if MR.puo_pesante(auto=True):
    print(datetime.now().isoformat(timespec="seconds"), "parto", day, flush=True)
    r = MR.main(["--auto", day])
    print("fatto:", None if not r else r["tempi_s"], flush=True)
    if not r:
        open(nessuna, "w").write("1")
