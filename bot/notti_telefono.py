"""Notti da A56/SAA: minuti supportati, fiducia bassa, nessun voto audio."""
import csv
from datetime import datetime, timedelta
from pathlib import Path

SONNO = {"deep_sleep", "light_sleep", "rem", "not_awake"}


def righe(p):
    try:
        with Path(p).open(encoding="utf-8") as f:
            return list(csv.reader(f))
    except OSError:
        return []


def giorni_fuori(note):
    out = set()
    for n in note:
        valore = n.get("valore", "")
        if n.get("tipo") == "notte" and valore.endswith((":fuori", ":altra_stanza")):
            out.add(valore.split(":")[0])
        elif n.get("tipo") == "altro" and valore.lower().strip() in (
                "altra stanza", "dormo in altra stanza", "ho dormito in altra stanza"):
            try:
                t = datetime.fromisoformat(n["ts"])
                out.add((t + timedelta(days=t.hour >= 18)).strftime("%Y%m%d"))
            except (ValueError, KeyError):
                pass
    return out


def ricostruisci(eventi_path, uso_path, ora=None):
    ora = ora or datetime.now()
    eventi, uso = set(), set()
    for r in righe(eventi_path):
        try:
            t = datetime.fromisoformat(r[0])
            if ora-timedelta(days=8) <= t <= ora:
                eventi.add((t, r[1]))
        except (ValueError, IndexError, TypeError):
            continue
    for r in righe(uso_path):
        try:
            if r[1] in ("a56", "pc"):
                uso.add(datetime.fromisoformat(r[0]).replace(second=0, microsecond=0))
        except (ValueError, IndexError):
            continue
    # Una sessione aperta o un singolo evento senza tracking non bastano.
    sessione, notti = None, {}
    ordine = {"sleep_tracking_started": 0, "awake": 2, "sleep_tracking_stopped": 3}
    for t, ev in sorted(eventi, key=lambda x: (x[0], ordine.get(x[1], 1), x[1])):
        if ev == "sleep_tracking_started":
            sessione = [(t, ev)]
        elif sessione is not None and ev in SONNO | {"awake", "sleep_tracking_stopped"}:
            sessione.append((t, ev))
            if ev != "sleep_tracking_stopped":
                continue
            sonno, noti = set(), set()
            for (a, stato), (z, _) in zip(sessione, sessione[1:]):
                if stato not in SONNO | {"awake"}:
                    continue
                # Nessuna propagazione oltre 10 minuti: buchi restano buchi.
                fine = min(z, a+timedelta(minutes=10))
                m = a.replace(second=0, microsecond=0)
                if m < a:
                    m += timedelta(minutes=1)
                while m+timedelta(minutes=1) <= fine:
                    noti.add(m)
                    if stato in SONNO and m not in uso:
                        sonno.add(m)
                    m += timedelta(minutes=1)
            a, z = sessione[0][0], t
            durata = (z-a).total_seconds()/60
            if len(sonno) >= 60 and durata <= 24*60 and len(noti) >= durata/2:
                day = (a + timedelta(days=a.hour >= 18)).strftime("%Y%m%d")
                accumulo = notti.setdefault(day, {"sonno":set(), "noti":set(), "totale":0})
                accumulo["sonno"].update(sonno)
                accumulo["noti"].update(noti)
                accumulo["totale"] += durata
            sessione = None
    out = {}
    for day, dati in notti.items():
        s = dati["sonno"]
        out[day] = dict(day=day, inizio=min(s).isoformat(),
                        fine=(max(s)+timedelta(minutes=1)).isoformat(), durata=str(round(len(s)/60, 2)),
                        eff="", risvegli="", russa_min="", punteggio="", fonte="A56/SAA/uso",
                        fiducia="bassa", copertura=round(len(dati["noti"])/dati["totale"], 3))
    return out
