"""
il riepilogo del mattino e' gia' partito oggi, il PC e' libero (nessun input da >=10', CPU<40%), e c'e' qualcosa di nuovo
(>=1 giudizio nuovo e non gia' allenato oggi, oppure >=20 giudizi nuovi). Nel dubbio (errore/dato mancante) rimanda.
   python personale_attivita.py [--forza]"""
import senza_finestre  # noqa: F401  (niente finestre dei processi figli: va importato per primo)
import csv, json, os, subprocess, sys
from datetime import datetime, timedelta
import psutil
sys.path.insert(0, r"C:\sonno_tex")
import personale_train as T

LOG = T.P + r"\attivita.log"


def log(s):
    open(LOG, "a", encoding="utf-8").write(f"{datetime.now():%Y-%m-%d %H:%M} {s}\n")


def rimanda():
    """None se si puo' allenare, altrimenti il motivo."""
    try:
        r = subprocess.run(T.SSH + ["cat ~/stato.json"], capture_output=True, timeout=30)
        s = json.loads(r.stdout)
        if s.get("utente") != "sveglio" or float(s.get("fiducia", 0)) < 0.95:
            return f"stato {s.get('utente')} fiducia {s.get('fiducia')}"
    except Exception as e:
        return f"stato illeggibile ({type(e).__name__})"
    # riepilogo di oggi mandato: dal bot (mandati.json ha la chiave AAAAMMGG di oggi) o da notte_check recap
    oggi = datetime.now().strftime("%Y%m%d")
    rec = r"C:\sonno_audio" + "\\notte_check_recap.txt"
    fatto = os.path.exists(rec) and datetime.fromtimestamp(os.path.getmtime(rec)).strftime("%Y%m%d") == oggi
    if not fatto:
        try:
            fatto = oggi in json.loads(subprocess.run(T.SSH + ["cat ~/sonno_bot/mandati.json"], capture_output=True, timeout=30).stdout)
        except Exception:
            pass
    if not fatto:
        return "riepilogo di oggi non ancora mandato"
    try:
        ev = list(csv.reader(open(r"C:\activity_log\activity.csv")))[-1]
        t = datetime.strptime(ev[0], "%Y-%m-%d %H:%M:%S")
        if ev[1] != "IDLE" or datetime.now() - t < timedelta(minutes=10):
            return "PC in uso"
    except Exception as e:
        return f"activity illeggibile ({type(e).__name__})"
    if psutil.cpu_percent(interval=3) > 40:
        return "CPU occupata"
    return None


def main():
    if "--forza" not in sys.argv:
        m = rimanda()
        if m:
            return log("rimando: " + m)
        T.pull_giudizi()
        st = json.load(open(T.STATO)) if os.path.exists(T.STATO) else {"data": "", "n_giudizi": 0}
        n = sum(1 for _ in open(T.P + r"\giudizi.csv", encoding="utf-8-sig")) - 1 - st["n_giudizi"]
        oggi = datetime.now().strftime("%Y-%m-%d")
        if not (n >= 20 or (n >= 1 and st["data"] != oggi)):
            return log(f"niente da fare ({n} giudizi nuovi, ultimo allenamento {st['data']})")
    psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
    sys.argv = [a for a in sys.argv if a != "--forza"] + ["--no-pull"] if "--forza" not in sys.argv else sys.argv[:1]
    T.main()
    log("allenato: " + open(T.REPORT, encoding="utf-8").read().splitlines()[-1])


if __name__ == "__main__":
    main()
