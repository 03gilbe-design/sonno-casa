"""Notti passate dai dati storici (PC + App Usage + TikTok) e previsione dell'ora in cui va a letto.
   python storico.py  -> notti_storiche.csv (day,inizio,fine,durata,fonti) + accuratezza della previsione
Sonno = pausa di attivita' piu' lunga (>=3h) nella finestra 18:00 -> 16:00 del giorno dopo (come notte.py).
Limite: e' "nessuna attivita' su PC/telefono", non sonno misurato: sovrastima se resta sveglio senza schermi.
"""
import csv, glob, os, re
from datetime import datetime, timedelta, timezone
import numpy as np

DL = os.path.expanduser(r"~\Downloads")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notti_storiche.csv")


def locale(utc):
    """(nota rimossa)"""
    def ult_dom(y, m):
        d = datetime(y, m + 1, 1) - timedelta(days=1) if m < 12 else datetime(y, 12, 31)
        return d - timedelta(days=(d.weekday() + 1) % 7)
    y = utc.year
    estate = ult_dom(y, 3).replace(hour=1) <= utc < ult_dom(y, 10).replace(hour=1)
    return utc + timedelta(hours=2 if estate else 1)


def eventi():
    ev = []  # (datetime locale, fonte)
    # TikTok: ogni video visto
    for f in glob.glob(os.path.join(DL, "TikTok_Data_*", "TikTok", "La tua attivit*", "Cronologia visualizzazioni.txt")):
        for m in re.finditer(r"Data: (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) UTC", open(f, encoding="utf-8").read()):
            ev.append((locale(datetime.fromisoformat(m.group(1))), "tiktok"))
    # PC: tastiera/mouse veri (ACTIVE = attivo da li' fino al prossimo IDLE)
    righe = list(csv.DictReader(open(r"C:\activity_log\activity.csv")))
    for a, b in zip(righe, righe[1:]):
        if a["event"] == "ACTIVE":
            t, fine = datetime.fromisoformat(a["timestamp"]), datetime.fromisoformat(b["timestamp"])
            while t <= fine:
                ev.append((t, "pc")); t += timedelta(minutes=10)
    # App Usage (telefono): sessioni app, escluso "schermo spento"
    for f in glob.glob(os.path.join(DL, "aum_2026-09-26", "AUM_V4_Activity_*.csv")):
        for r in csv.DictReader(open(f, encoding="utf-8-sig")):
            if not r.get("Time") or r["App name"].startswith("Schermo"):
                continue
            t = datetime.strptime(r["Date"] + " " + r["Time"], "%d/%m/%y %H:%M:%S")
            h, m, s = map(int, r["Duration"].split(":"))
            ev += [(t, "telefono"), (t + timedelta(hours=h, minutes=m, seconds=s), "telefono")]
    return sorted(ev)


def notti(ev):
    ts = np.array([e[0].timestamp() for e in ev])
    out = []
    d = ev[0][0].date() + timedelta(days=1)
    while d <= ev[-1][0].date():
        a = datetime.combine(d - timedelta(days=1), datetime.min.time()).replace(hour=18).timestamp()
        z = a + 22 * 3600
        dentro = ts[(ts >= a) & (ts < z)]
        if len(dentro) >= 5:  # ponytail: finestre con pochi eventi = dati mancanti, non notti
            gap = np.diff(dentro)
            i = int(np.argmax(gap))
            if gap[i] >= 3 * 3600:
                ini, fin = datetime.fromtimestamp(dentro[i]), datetime.fromtimestamp(dentro[i + 1])
                fonti = sorted({f for t, f in ev if ini - timedelta(hours=1) <= t <= ini})
                out.append(dict(day=d.strftime("%Y%m%d"), inizio=ini.isoformat(timespec="minutes"),
                                fine=fin.isoformat(timespec="minutes"), durata=round((fin - ini).total_seconds() / 3600, 2),
                                fonti="+".join(fonti)))
        d += timedelta(days=1)
    return out


def ora(iso):
    t = datetime.fromisoformat(iso)
    return t.hour + t.minute / 60


def media_circ(h):
    a = np.array(h) * 2 * np.pi / 24
    return (np.angle(np.mean(np.exp(1j * a))) * 24 / (2 * np.pi)) % 24


def diff_circ(a, b):
    return abs(((a - b + 12) % 24) - 12)


def previsione(N, k=7):
    """Walk-forward: ogni notte prevista SOLO con le k precedenti (mai vista). Confronto con 'come ieri'."""
    err_m, err_ieri, dentro1h = [], [], 0
    for i in range(k, len(N)):
        vero = ora(N[i]["inizio"])
        prev = media_circ([ora(x["inizio"]) for x in N[i - k:i]])
        err_m.append(diff_circ(prev, vero)); err_ieri.append(diff_circ(ora(N[i - 1]["inizio"]), vero))
        dentro1h += diff_circ(prev, vero) <= 1.5
    return np.median(err_m), np.median(err_ieri), dentro1h / max(len(err_m), 1), len(err_m)


if __name__ == "__main__":
    ev = eventi()
    N = notti(ev)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(N[0])); w.writeheader(); w.writerows(N)
    print(f"{len(ev)} eventi {ev[0][0]:%d/%m/%Y}-{ev[-1][0]:%d/%m/%Y} -> {len(N)} notti -> {OUT}")
    h = [ora(x["inizio"]) for x in N]
    print(f"addormentamento medio (circolare) {media_circ(h):.1f}h · durata mediana {np.median([x['durata'] for x in N]):.1f}h")
    em, ei, p, n = previsione(N)
    print(f"PREVISIONE ora di letto (media 7 notti prima, {n} notti mai viste): errore mediano {em:.1f}h "
          f"vs 'come ieri' {ei:.1f}h · entro ±1,5h nel {p:.0%} dei casi")
