"""Frequenza respiratoria minuto per minuto da un blocco audio intero.
Uso: python respiro_freq.py FILE.m4a [out.csv]    (senza argomenti: self-check)
Metodo: ffmpeg -> 16 kHz mono, banda 100-1000 Hz; inviluppo RMS 50 ms (20 Hz);
per ogni minuto autocorrelazione dell'inviluppo, lag 2-10 s (6-30 resp/min);
affidabilita' = altezza del picco (0..1). Minuti con voce/esterni nel
minuti_AAAAMMGG.csv -> incerto. Onesto: senza picco chiaro dice "nessun respiro udibile"."""
import sys, subprocess, os, re, csv
from datetime import datetime, timedelta
import numpy as np

SR, FPS = 16000, 20
OK, INC = 0.30, 0.15          # soglie picco autocorrelazione (calibrare con dati veri)
SILENZIO = 3e-4               # rms banda sotto cui e' silenzio (full scale = 1)
MINUTI_DIR = r"C:\sonno_audio\minuti"

def decodifica(path):
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR),
        "-af", "highpass=f=100,lowpass=f=1000", "-f", "s16le", "-"], capture_output=True, check=True)
    return np.frombuffer(r.stdout, np.int16).astype(np.float32) / 32768

def inviluppo(x):
    n = SR // FPS
    k = len(x) // n
    return np.sqrt((x[:k * n].reshape(k, n) ** 2).mean(1))

def minuto(env):
    """env: 60 s di inviluppo -> (resp/min, picco, rms)"""
    rms = float(np.sqrt((env ** 2).mean()))
    if rms < SILENZIO:
        return None, 0.0, rms
    e = np.convolve(env, np.ones(10) / 10, "same")       # smoothing 0.5 s
    e = e - e.mean()
    v = float(e @ e)
    if v <= 0:
        return None, 0.0, rms
    ac = np.correlate(e, e, "full")[len(e) - 1:] / v
    lo, hi = 2 * FPS, 10 * FPS
    seg = ac[lo:hi + 1]
    # picchi locali; il primo vicino al massimo (evita le armoniche a 2x lag)
    pk = [i for i in range(1, len(seg) - 1) if seg[i] > seg[i - 1] and seg[i] >= seg[i + 1]]
    if not pk:
        return None, 0.0, rms
    m = max(seg[i] for i in pk)
    if m <= 0:
        return None, 0.0, rms
    i = next(i for i in pk if seg[i] >= 0.85 * m)
    a, b, c = seg[i - 1], seg[i], seg[i + 1]
    d = a - 2 * b + c
    off = 0.5 * (a - c) / d if d else 0.0                  # interpolazione parabolica
    lag = (lo + i + off) / FPS
    return 60 / lag, float(b), rms

def esterni(path, t0, n):
    """set di indici-minuto con voce/esterni dal minuti_AAAAMMGG.csv (se c'e')"""
    bad, trovati = set(), False
    for g in {t0.date(), (t0 + timedelta(minutes=n)).date()}:
        f = os.path.join(MINUTI_DIR, f"minuti_{g:%Y%m%d}.csv")
        if not os.path.exists(f):
            continue
        trovati = True
        for r in csv.DictReader(open(f)):
            try:
                t = datetime.strptime(r["t"], "%Y-%m-%dT%H:%M")
                if 0 <= (t - t0).total_seconds() < n * 60 and (int(r["voce"]) or int(r["esterni"])):
                    bad.add(int((t - t0).total_seconds() // 60))
            except (ValueError, KeyError):
                pass
    return bad, trovati

def analizza(x, t0=None, path=""):
    env = inviluppo(x)
    n = len(env) // (60 * FPS)
    bad, _ = esterni(path, t0, n) if t0 else (set(), False)
    righe = []
    for m in range(n):
        rate, picco, rms = minuto(env[m * 60 * FPS:(m + 1) * 60 * FPS])
        if rate is None or picco < INC:
            stato, rate = "nessun respiro udibile", ""
        elif m in bad:
            stato, rate = "incerto (voce/rumori esterni)", f"{rate:.1f}"
        else:
            stato, rate = ("ok" if picco >= OK else "incerto"), f"{rate:.1f}"
        righe.append((m, rate, f"{picco:.2f}", f"{rms:.5f}", stato))
    return righe

def self_check():
    rng = np.random.default_rng(1)
    t = np.arange(60 * 30 * SR) / SR
    mod = 0.5 * (1 + np.sin(2 * np.pi * 15 / 60 * t))      # 15 resp/min
    res = analizza((0.02 * rng.standard_normal(len(t)) * (0.1 + mod)).astype(np.float32))
    ok = [float(r[1]) for r in res if r[4] == "ok"]
    assert len(ok) >= 28 and abs(np.median(ok) - 15) < 1, res[:3]
    res = analizza((0.02 * rng.standard_normal(len(t))).astype(np.float32))
    assert sum(r[4] == "nessun respiro udibile" for r in res) >= 27, [r[2] for r in res[:5]]
    print("self-check OK")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        self_check(); sys.exit()
    p = sys.argv[1]
    mt = re.search(r"(\d{8})_(\d{6})", os.path.basename(p))
    t0 = datetime.strptime(mt.group(1) + mt.group(2), "%Y%m%d%H%M%S").replace(second=0) if mt else None
    res = analizza(decodifica(p), t0, p)
    out = open(sys.argv[2], "w", newline="") if len(sys.argv) > 2 else sys.stdout
    w = csv.writer(out)
    w.writerow(["minuto", "resp_min", "picco_ac", "rms_banda", "affidabilita"])
    w.writerows(res)
