"""
MINUTO per minuto, se un blocco audio va tenuto: ~/stato.json e' un solo istante e si aggiorna una volta a blocco (30').
   python stato_storia.py         -> campiona adesso
   python stato_storia.py prova   -> self-check
Il microfono NON si tocca mai: registra=0 vuol dire solo "scarta l'audio di quei minuti" (vedi sonno_tel.analizza)."""
import csv, os, sys
from datetime import datetime, timedelta

HOME = os.path.expanduser("~")
STORIA = os.path.join(HOME, "stato_storia.csv")
VALIDITA = 5  # minuti: un campione vale fino al successivo, al massimo 5' (cron ogni 2'); dopo, nel dubbio si registra


def registra_di(j):
    """(nota rimossa)"""
    return not (j.get("stato") == "sveglio" and (j.get("albero") or {}).get("registra") is False)


def leggi_storia(path=STORIA):
    """[(datetime, bool)] ordinata; righe rotte ignorate; file mancante -> []."""
    out = []
    try:
        with open(path, encoding="utf-8") as f:
            for r in csv.reader(f):
                try:
                    out.append((datetime.fromisoformat(r[0]), r[1].strip() != "0"))
                except (ValueError, IndexError):
                    pass
    except OSError:
        pass
    return sorted(out)


def registra_a(t, storia, validita=VALIDITA):
    """False solo se l'ultimo campione <= t dice False ed e' fresco (<= validita'). Senza dati: True."""
    prima = [(ts, r) for ts, r in storia if ts <= t]
    if not prima or t - prima[-1][0] > timedelta(minutes=validita):
        return True
    return prima[-1][1]


def campiona(adesso=None, path=STORIA, **kw):
    import stato
    adesso = adesso or datetime.now()
    reg = registra_di(stato.utente(adesso, **kw))
    with open(path, "a", newline="") as f:
        csv.writer(f).writerow([adesso.isoformat(timespec="seconds"), int(reg)])
    try:  # file piccolo: sopra 100 KB tengo le ultime 1500 righe (~2 giorni a 1 ogni 2')
        if os.path.getsize(path) > 100_000:
            righe = open(path, encoding="utf-8").read().splitlines()[-1500:]
            open(path + ".tmp", "w", encoding="utf-8").write("\n".join(righe) + "\n")
            os.replace(path + ".tmp", path)
    except OSError:
        pass
    return reg


if __name__ == "__main__":
    if sys.argv[1:] == ["prova"]:
        t = datetime(2026, 10, 2, 23, 0)
        s = [(t, False), (t + timedelta(minutes=2), True)]
        assert registra_a(t + timedelta(minutes=1), s) is False
        assert registra_a(t + timedelta(minutes=3), s) is True
        assert registra_a(t - timedelta(minutes=1), s) is True          # prima di ogni campione
        assert registra_a(t + timedelta(minutes=9), s[:1]) is True      # campione vecchio: nel dubbio si registra
        assert registra_a(t, []) is True
        assert registra_di(dict(stato="sveglio", albero=dict(registra=False))) is False
        assert registra_di(dict(stato="sveglio", albero=dict(registra=True))) is True
        assert registra_di(dict(stato="sveglio", albero=dict(errore="x"))) is True   # albero vecchio/assente
        assert registra_di(dict(stato="?", albero=dict(registra=False))) is True     # stato.py non e' sicuro
        print("ok")
    else:
        try:
            campiona()
        except Exception as e:  # il cron non deve mai rompere altro: senza storia si registra tutto
            print(f"stato_storia: {e}", file=sys.stderr)
