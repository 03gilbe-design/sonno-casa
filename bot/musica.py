"""
Dati (PC: stato_live.py ogni 2', copie in ~/sonno_bot):
  media_a56.csv     t,dev,si|no,app,uscita[,t_fine,tipo]  (righe A56/A21s MESCOLATE e fuori ordine; 7 colonne = intervalli esatti)
  musica_eventi.csv t,evento,volume_prima,volume_dopo,app,volume_max,uscita   evento = campione | abbassato | sveglio_volume
"""
import csv
from datetime import datetime, timedelta
from collections import Counter

BUCO = timedelta(minutes=6)       # pausa tra due brani (campioni ogni 2') che non spezza il tratto: come stato_live.BUCO_MIN
MIN_TRATTO = timedelta(minutes=10)  # ponytail: sotto 10' e' un video/vocale, non musica di sottofondo


def _righe(path):
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return list(csv.reader(f))
    except OSError:
        return []


def _t(s):
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def tratti(media_csv, inizio, fine):
    """[(t0, t1, uscita, app)] dell'A56 che suona, dai campioni (righe da 5 colonne), ordinati per tempo."""
    camp = sorted(((_t(r[0]), r) for r in _righe(media_csv) if 5 <= len(r) < 7 and r[1] == "a56" and r[2] == "si"),
                  key=lambda x: x[0] or datetime.min)
    out = []  # [t0, t1, uscita, Counter(app)]
    for t, r in camp:
        if t is None or not inizio <= t <= fine:
            continue
        if out and t - out[-1][1] <= BUCO and out[-1][2] == r[4]:
            out[-1][1] = max(out[-1][1], t)  # fine solo crescente
        else:
            out.append([t, t, r[4], Counter()])
        out[-1][3][r[3]] += 1
    return [(a, b, u, next((x for x, _ in c.most_common() if x not in ("", "?")), "?")) for a, b, u, c in out if b - a >= MIN_TRATTO]


def riassunto_notte(media_csv, eventi_csv, inizio, fine):
    righe = _righe(eventi_csv)
    ev = [dict(zip(righe[0], r)) for r in righe[1:]] if righe else []
    ev = sorted(((t, r) for r in ev if (t := _t(r.get("t"))) and inizio <= t <= fine), key=lambda x: x[0])
    pezzi = []
    for a, b, uscita, app in tratti(media_csv, inizio, fine):
        c = [r for t, r in ev if r["evento"] == "campione" and a - BUCO <= t <= b + BUCO]
        vol = f", volume {c[0]['volume_prima']}/{c[0]['volume_max']}" if c and c[0].get("volume_max") else ""
        pezzi.append(f"{a:%H:%M}-{b:%H:%M} ({app}{', in cuffia' if uscita == 'cuffie' else ''}{vol})")
    abb = [(t, r) for t, r in ev if r["evento"] == "abbassato"]
    sv = [t for t, r in ev if r["evento"] == "sveglio_volume"]
    if not pezzi and not abb and not sv:
        return ""
    testo = "Musica: " + ("; ".join(pezzi) or "?")
    if abb:
        testo += f", abbassata alle {abb[0][0]:%H:%M} (da {abb[0][1]['volume_prima']} a {abb[-1][1]['volume_dopo']})"
    elif pezzi:
        testo += ", non abbassata"
    return testo + "".join(f"; rialzata da te alle {t:%H:%M} (sveglio)" for t in sv)
