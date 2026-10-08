"""
   python finestre_candidate.py 20261002 [N=15] [--panns]   -> ritaglia dai blocchi interi, copia in ~/rec/ del telefono come finestra_AAAAMMGG_HHMMSS.m4a
--panns: invece dei periodi candidati, le serie di minuti dove PANNs (PRECISO) dice russare e che NON hanno ancora nessuna clip sul
telefono (una finestra al centro di ogni serie, le piu' lunghe prima): il bot le mette in cima alla coda (ordine per valore).
Distribuite sui periodi (almeno una per periodo finche' ci stanno, il resto in proporzione ai minuti)."""
import json, os, subprocess, sys
from datetime import datetime, timedelta
import mappa_russare as MR

def periodi_panns(J, N):
    """Serie di minuti consecutivi (buco <= 1') con PANNs russa e senza clip: [{da, a, minuti, certezza}], le piu' lunghe prima."""
    cel = next(c["celle"] for c in J["corsie"] if c["nome"] == "PANNs")
    con_clip = {n.split("_", 1)[1][:13] for n in MR.ssh("ls ~/rec").split() if "_" in n and n.endswith(".m4a")}
    mm = [m for m in sorted(datetime.fromisoformat(k) for k, v in cel.items() if "russa" in v) if f"{m:%Y%m%d_%H%M}" not in con_clip]
    serie = []
    for m in mm:
        if serie and m - serie[-1][-1] <= timedelta(minutes=2):
            serie[-1].append(m)
        else:
            serie.append([m])
    serie.sort(key=len, reverse=True)
    return [dict(da=x[0].isoformat(timespec="minutes"), a=(x[-1] + timedelta(minutes=1)).isoformat(timespec="minutes"), minuti=len(x), certezza=0)
            for x in serie[:N]]


args = [x for x in sys.argv[1:] if not x.startswith("--")]
day, N = args[0], int(args[1]) if len(args) > 1 else 15
J = json.load(open(f"{MR.OUT}\mappa_{day}.json", encoding="utf-8"))
per = periodi_panns(J, N) if "--panns" in sys.argv else [p for p in J["periodi"] if p["certezza"] <= 2]
if not per:
    sys.exit("nessun periodo candidato")
q = [1 if len(per) <= N else 0] * len(per)
for _ in range(N - sum(q)):  # il prossimo va dove i minuti per finestra sono di piu'
    i = max(range(len(per)), key=lambda i: per[i]["minuti"] / (q[i] + 1))
    q[i] += 1
a, z = datetime.fromisoformat(J["inizio"]), datetime.fromisoformat(J["fine"])
blocchi = MR.blocchi_interi(a, z)
fatte = 0
for p, k in zip(per, q):
    da = datetime.fromisoformat(p["da"])
    for i in range(k):
        t = da + timedelta(seconds=(i + .5) / k * p["minuti"] * 60 - 10)  # centro della i-esima fetta, 20 s attorno
        t = t.replace(microsecond=0)
        b = next((x for x in blocchi if x[0] <= t and t + timedelta(seconds=20) <= x[1]), None)
        if not b:
            continue
        nome = f"finestra_{t:%Y%m%d_%H%M%S}.m4a"
        loc = MR.SRC + "\\" + nome
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{(t - b[0]).total_seconds():.2f}", "-t", "20", "-i", b[2], "-c:a", "aac", "-b:a", "64k", loc], check=True)
        if MR.scp(loc, f"{MR.PHONE}:rec/{nome}", 120):
            fatte += 1
            print(nome, f"periodo {p['da'][11:]}-{p['a'][11:]}")
print("finestre in coda:", fatte)
