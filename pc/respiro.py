"""
ed espiro!"). Solo numpy (sul telefono niente scipy).
  inviluppo(w)  -> energia 100-1500 Hz ogni 50 ms (log), lisciata
  ritmo(env)    -> respiri al minuto per ogni minuto (autocorrelazione: periodo 2-10 s; regge anche se inspiro ed
                   espiro fanno due rumori, conta il ciclo intero)
  picchi(env)   -> istanti dei respiri rumorosi (russate / sbuffi)
  pause(...)    -> buchi >= 10 s senza respiri DENTRO un tratto regolare = "pausa del respiro" (NON diagnosi di apnea)
  python respiro.py blocco.m4a [out.png]
"""
import subprocess, sys
import numpy as np

SR, PASSO = 8000, 0.05  # 8 kHz bastano (respiro/russare < 2 kHz); una misura ogni 50 ms


def leggi(path):
    return np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                                        capture_output=True, check=True).stdout, dtype="<f4")


def inviluppo(w, liscia=0.4):
    n = int(SR * PASSO)
    fr = w[:len(w) // n * n].reshape(-1, n) * np.hanning(n)
    sp = np.abs(np.fft.rfft(fr, axis=1)) ** 2
    f = np.fft.rfftfreq(n, 1 / SR)
    e = np.log10(sp[:, (f >= 100) & (f <= 1500)].sum(1) + 1e-10)
    k = max(1, int(liscia / PASSO))
    return np.convolve(e, np.ones(k) / k, mode="same")


def ritmo(env, finestra=60, min_s=2.0, max_s=10.0):
    """[(minuto, respiri_al_minuto o None, forza)] — forza = quanto il ritmo e' netto (0-1): sotto 0.3 non si dice."""
    n, out = int(finestra / PASSO), []
    for i in range(0, len(env) - n + 1, n):
        x = env[i:i + n] - env[i:i + n].mean()
        ac = np.correlate(x, x, "full")[n - 1:]
        ac = ac / (ac[0] + 1e-12)
        a, b = int(min_s / PASSO), int(max_s / PASSO)
        k = a + int(np.argmax(ac[a:b]))
        forza = float(ac[k])
        out.append((i * PASSO / 60, 60 / (k * PASSO) if forza >= 0.3 else None, forza))
    return out


def picchi(env, distanza=1.8, soglia=None):
    """Istanti (s) dei massimi locali alti sopra la mediana di 30 s di almeno `soglia` (default: 1.5 x MAD globale)."""
    k = int(30 / PASSO)
    base = np.array([np.median(env[max(0, i - k // 2):i + k // 2 + 1:10]) for i in range(len(env))])
    alto = env - base
    s = soglia if soglia is not None else 1.5 * np.median(np.abs(alto - np.median(alto))) + 0.05
    d, out = int(distanza / PASSO), []
    for i in range(1, len(env) - 1):
        if alto[i] > s and env[i] >= env[i - 1] and env[i] > env[i + 1] and (not out or i - out[-1] >= d):
            out.append(i)
        elif out and i - out[-1] < d and alto[i] > s and env[i] > env[out[-1]]:
            out[-1] = i  # nella stessa finestra tengo il massimo piu' alto
    return np.array(out) * PASSO


def pause(tp, minimo=10.0, regolari=6, cv=0.3, volte=2.5):
    """
    (voce, musica = picchi a caso) -> vale solo se i `regolari` intervalli prima erano REGOLARI (variazione < `cv`) e il
    buco e' >= `volte` il respiro normale e >= `minimo` s."""
    out = []
    iv = np.diff(tp)
    for i in range(regolari, len(iv)):
        prima = iv[i - regolari:i]
        norm = float(np.median(prima))
        if iv[i] >= max(minimo, volte * norm) and prima.std() / prima.mean() < cv:
            out.append((float(tp[i]), float(iv[i])))
    return out


def blocco(path):
    """Risultato di un blocco da 30' (rec/interi/<nome>.m4a), calcolato UNA volta e salvato accanto al dataset:
    rec/dataset/<nome>.resp.npz = picchi (s dall'inizio), ritmo (minuto, respiri/min o nan, forza)."""
    import os
    sys.path.insert(0, os.path.expanduser("~"))
    import conferma
    f = os.path.join(conferma.D, "dataset", os.path.basename(path)[:-4] + ".resp.npz")
    if not os.path.exists(f):
        e = inviluppo(leggi(path))
        r = np.array([(m, np.nan if b is None else b, fz) for m, b, fz in ritmo(e)], dtype=float).reshape(-1, 3)
        os.makedirs(os.path.dirname(f), exist_ok=True)
        np.savez_compressed(f, picchi=picchi(e), ritmo=r)
    z = np.load(f)
    return z["picchi"], z["ritmo"]


def pause_tra(da, a):
    """[(inizio datetime, durata s)] delle pause del respiro rumoroso tra da e a (tutti i blocchi dell'intervallo)."""
    from datetime import timedelta
    import categorie
    out = []
    for t0, p in categorie.blocchi(da, a):
        tp, _ = blocco(p)
        out += [(t0 + timedelta(seconds=x), d) for x, d in pause(tp) if da <= t0 + timedelta(seconds=x) <= a]
    return out


if __name__ == "__main__":
    if sys.argv[1:] == ["prova"]:
        t = np.arange(0, 120, 1 / SR)
        r = 0.2 * np.sin(2 * np.pi * 300 * t) * (np.sin(2 * np.pi * t / 4) > 0.6)  # un respiro ogni 4 s = 15/min
        r[(t > 60) & (t < 75)] = 0  # pausa di 15 s
        r = (r + 0.002 * np.random.default_rng(1).standard_normal(len(t))).astype(np.float32)
        e = inviluppo(r)
        rr = ritmo(e)
        assert abs(rr[0][1] - 15) < 1, rr
        tp = picchi(e)
        p = pause(tp)
        assert len(p) == 1 and 58 < p[0][0] + p[0][1] / 2 < 77 and 13 < p[0][1] < 20, p
        print("ok", rr[0], p)
    else:
        w = leggi(sys.argv[1]); e = inviluppo(w); tp = picchi(e)
        for m, bpm, f in ritmo(e):
            print(f"{int(m):3d}' {'' if bpm is None else f'{bpm:4.1f}/min'} forza {f:.2f} respiri rumorosi {((tp >= m*60) & (tp < m*60+60)).sum()}")
        print("pause:", [(f"{int(a // 60)}'{int(a % 60):02d}", f"{d:.0f} s") for a, d in pause(tp)])
        if len(sys.argv) > 2:  # 2 minuti di inviluppo con i picchi, per controllare a occhio
            import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
            da = int(float(sys.argv[3]) * 60 / PASSO) if len(sys.argv) > 3 else 0
            x = np.arange(da, da + int(120 / PASSO)) * PASSO
            plt.figure(figsize=(16, 3)); plt.plot(x, e[da:da + len(x)], lw=0.8)
            q = tp[(tp >= x[0]) & (tp <= x[-1])]; plt.plot(q, e[(q / PASSO).astype(int)], "rv")
            plt.tight_layout(); plt.savefig(sys.argv[2])
