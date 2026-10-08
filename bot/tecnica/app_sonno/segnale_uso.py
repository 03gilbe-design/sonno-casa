"""Solo Termux A56, ogni minuto dal watchdog. Nessun lavoro sul PC.
ADB locale autorizzato: A56_ADB_SERIAL, default 127.0.0.1:5555.
Errore di accesso: heartbeat non aggiornato, musica resta protetta.
"""
import csv
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

OUT = Path.home() / "storage/shared/Documents/sonno"


def raccogli():
    serial = os.environ.get("A56_ADB_SERIAL", "127.0.0.1:5555")
    subprocess.run(["adb", "connect", serial], capture_output=True, timeout=5, check=True)
    r = subprocess.run(["adb", "-s", serial, "shell",
        "dumpsys power | grep mWakefulness=; "
        "dumpsys usagestats | grep -E 'type=(SCREEN_INTERACTIVE|SCREEN_NON_INTERACTIVE|KEYGUARD_HIDDEN) package=android'"],
        capture_output=True, text=True, timeout=15)
    if r.returncode or "Permission Denial" in r.stdout or r.stderr.strip():
        raise RuntimeError("lettura schermo A56 non riuscita")
    return r.stdout


def snapshot(testo, ora):
    power = re.search(r"mWakefulness=(Awake|Asleep|Dozing|Dreaming)\b", testo)
    if not power:
        raise ValueError("stato schermo assente")
    eventi = []
    for t, ev in re.findall(r'time="([^"]+)" type=(SCREEN_INTERACTIVE|SCREEN_NON_INTERACTIVE|KEYGUARD_HIDDEN) package=android', testo):
        dt = datetime.fromisoformat(t)
        if dt > ora:
            raise ValueError("evento schermo futuro")
        eventi.append((dt, ev))
    if not eventi:
        raise ValueError("eventi schermo assenti")
    # Sessione ancora aperta conta adesso anche senza nuovi sblocchi.
    ultimo = ora if power[1] in ("Awake", "Dreaming") else max(t for t, ev in eventi)
    return dict(fonte="a56_locale", raccolto=ora.isoformat(), a56=ultimo.isoformat(), schermo=power[1])


def invia(percorso=None, adesso=None):
    """Nome storico: ora scrive localmente, non invia dal PC."""
    p = Path(percorso or OUT)
    d = snapshot(raccogli(), adesso or datetime.now())
    ora = datetime.fromisoformat(d["raccolto"])
    p.mkdir(parents=True, exist_ok=True)
    righe = set()
    try:
        with (p / "uso.csv").open(encoding="utf-8") as f:
            for r in csv.reader(f):
                if len(r) == 2 and r[1] == "a56" and ora-timedelta(days=8) <= datetime.fromisoformat(r[0]) <= ora:
                    righe.add(tuple(r))
    except FileNotFoundError:
        pass
    ultimo = datetime.fromisoformat(d["a56"])
    if ora-timedelta(days=8) <= ultimo <= ora:
        righe.add((ultimo.isoformat(timespec="minutes"), "a56"))
    tmp = p / "uso.csv.tmp"
    tmp.write_text("".join(",".join(r)+"\n" for r in sorted(righe)), encoding="utf-8")
    tmp.replace(p / "uso.csv")
    # Pubblicato per ultimo, dopo archivio uso riuscito.
    tmp = p / "uso_recente.json.tmp"
    tmp.write_text(json.dumps(d), encoding="utf-8")
    tmp.replace(p / "uso_recente.json")
    return d


if __name__ == "__main__":
    if sys.argv[1:] == ["--loop"]:
        import fcntl
        # Impedisce doppie raccolte anche se il watchdog riparte contemporaneamente.
        with (Path.home()/".segnale_uso.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            while True:
                inizio = time.monotonic()
                try:
                    invia()
                except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as e:
                    print(type(e).__name__ + ": " + str(e)[:120], flush=True)
                time.sleep(max(1, 60-(time.monotonic()-inizio)))
    else:
        invia()
