"""
Prima: termux-sensor scriveva JSON grezzo senza orario (14 MB in 2 h, orari solo stimati contando le letture).
Ora: legge lo stesso flusso e scrive ~/notte_sensori/<data>_minuti.csv:  t,mov,luce,n
   mov  = somma |variazione del modulo dell'accelerazione| nel minuto (fondo tranquillo ~5-20, telefono in mano 100+)
   luce = lux medi (0 = buio/coperto), n = letture nel minuto (10 Hz -> ~600; meno = sensore rallentato)
Regola (sua): movimenti CONTINUI = sveglio, POCHI ogni tanto = mosso ma dorme, telefono in uso = sveglio -> la applica il PC.
   python sensori_minuti.py            (di notte lo lancia sensori_notte.sh)
   python sensori_minuti.py prova FILE (legge un JSON vecchio da file invece che dal sensore)
"""
import json, os, subprocess, sys, time
from datetime import datetime

SENSORI = "ICM42632M Accelerometer,STK31610 Light"


def oggetti(flusso):
    """Il flusso di termux-sensor e' una fila di oggetti JSON su piu' righe: li ricompone uno per uno."""
    buf, prof = [], 0
    for riga in flusso:
        prof += riga.count("{") - riga.count("}")
        buf.append(riga)
        if prof == 0 and "".join(buf).strip():
            try:
                yield json.loads("".join(buf))
            except ValueError:
                pass
            buf = []


def minuti(flusso, adesso=datetime.now, scrivi=print):
    minuto, mov, luce, n, prec = None, 0.0, [], 0, None
    for o in oggetti(flusso):
        t = adesso().replace(second=0, microsecond=0)
        if minuto and t != minuto:
            scrivi(f"{minuto:%Y-%m-%dT%H:%M},{mov:.1f},{sum(luce) / max(len(luce), 1):.1f},{n}")
            mov, luce, n = 0.0, [], 0
        minuto = t
        a = o.get("ICM42632M Accelerometer", {}).get("values")
        if a:
            m = (a[0] ** 2 + a[1] ** 2 + a[2] ** 2) ** 0.5
            if prec is not None:
                mov += abs(m - prec)
            prec, n = m, n + 1
        lx = o.get("STK31610 Light", {}).get("values")
        if lx:
            luce.append(lx[0])
    if minuto:
        scrivi(f"{minuto:%Y-%m-%dT%H:%M},{mov:.1f},{sum(luce) / max(len(luce), 1):.1f},{n}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["prova"]:  # 600 letture = 1 minuto finto
        k = [0]

        def finto():
            k[0] += 1
            return datetime(2026, 9, 28, 23, 27) + (k[0] // 600) * (datetime(2026, 1, 1, 0, 1) - datetime(2026, 1, 1))
        righe = []
        minuti(open(sys.argv[2], encoding="utf-8"), finto, righe.append)
        assert len(righe) >= 100 and righe[0].startswith("2026-09-28T11:27,"), righe[:2]
        print(len(righe), "minuti; es.", righe[2], righe[8])
        sys.exit()
    d = os.path.expanduser("~/notte_sensori"); os.makedirs(d, exist_ok=True)
    out = open(os.path.join(d, f"{datetime.now():%Y%m%d_%H%M}_minuti.csv"), "a", buffering=1)
    out.write("t,mov,luce,n\n")
    p = subprocess.Popen(["termux-sensor", "-s", SENSORI, "-d", "100"], stdout=subprocess.PIPE, text=True)
    fine = time.time() + 10 * 3600
    try:
        minuti(iter(lambda: p.stdout.readline() if time.time() < fine else "", ""),
               scrivi=lambda r: out.write(r + "\n"))
    finally:
        p.terminate()
        subprocess.run(["termux-sensor", "-c"], capture_output=True)
