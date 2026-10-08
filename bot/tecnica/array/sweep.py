"""MAPPA DEL CANALE con SWEEP ESPONENZIALE (metodo Farina, lo standard online: REW, acustica).
   python sweep.py [nome]          -> silenzio 3 s, poi A56, A21s, PC suonano lo sweep 80 Hz-16 kHz (4 s) a turno;
                                      ascoltano A56, A21s, PC Intel, webcam. Salva la mappa in
                                      C:\\sonno_audio\\array\\mappa_<nome>.npz (+ .png) e stampa la tabella
   python sweep.py analizza [nome] -> solo analisi
Deconvoluzione (registrazione * sweep inverso) = RISPOSTA ALL'IMPULSO X->Y:
  primo picco = ritardo (distanza), picchi dopo = ECHI, spettro = PERDITA per frequenza,
  picco ~0,5 s PRIMA = 2a armonica = DEFORMAZIONE (separata dal lineare), silenzio deconvoluto = RUMORE di fondo.
"""
import os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import beepbeep as b  # PRIMA di scipy: altrimenti onnxruntime "DLL load failed"
import canale
from scipy.signal import fftconvolve, hilbert, find_peaks

# (3 mappe con 4 s a volume max, SNR minimo per ottava): telefoni e PC-bocca 52-101 dB (margine 12-60 sopra i 40 dB
# 8 kHz = il piu' alto (53-101) = energia sprecata dove fa male. Quindi: T resta 4 s, AMPIEZZA -10 dB, F2 10 kHz
# (l'ultima ottava analizzata e' 8 kHz). Caso peggiore fra telefoni: 52 -> ~42 dB, ancora > 40.
F1, F2, T = 80.0, float(os.environ.get("SWEEP_F2", 10000)), 4.0
ALTI = (11000, 13000, 15000, 17000, 19000, 21000)  # bande +-1 kHz sopra 10 kHz: fin dove emette/sente (ultrasuoni)
AMPIEZZA = 0.9 * 10 ** (-10 / 20)  # -10 dB rispetto a prima
RUMORE = (0.5, 2.0)
TESTA, CODA = 0.1, 0.4  # s di zeri prima/dopo lo sweep (coda: la risposta dura ~120 ms; era 1,0 s = pausa inutile)
L = np.log(F2 / F1)
OTTAVE = (125, 250, 500, 1000, 2000, 4000, 8000)
ORECCHI = {"A56": "a56.m4a", "A21s": "a21s.m4a", "PCintel": "pc_intel.wav", "webcam": "pc_webcam.wav"}
BOCCHE = ("A56", "A21s", "PC")


def ess():
    t = np.arange(int(T * b.SR)) / b.SR
    x = np.sin(2 * np.pi * F1 * T / L * (np.exp(t * L / T) - 1))
    fade = np.minimum(1, np.minimum(t / 0.05, (T - t) / 0.01))  # rampe: niente click
    x = AMPIEZZA * x * fade
    inv = x[::-1] * np.exp(-t * L / T)  # sweep inverso: compensa l'energia maggiore sui bassi
    inv /= np.abs(fftconvolve(x, inv)).max()
    return x.astype(np.float32), inv


def segnale():
    x, _ = ess()
    return np.concatenate([np.zeros(int(TESTA * b.SR)), x, np.zeros(int(CODA * b.SR))]).astype(np.float32)


def bande(ir, centri=OTTAVE, mezza=None):
    F = np.abs(np.fft.rfft(ir, 1 << 14)) ** 2; fr = np.fft.rfftfreq(1 << 14, 1 / b.SR)
    lim = [(o - mezza, o + mezza) if mezza else (o / np.sqrt(2), o * np.sqrt(2)) for o in centri]
    return np.array([10 * np.log10(F[(fr >= lo) & (fr < hi)].mean() + 1e-20) for lo, hi in lim])


def analizza(nome="tavolo"):
    x, inv = ess(); pre, post = int(0.005 * b.SR), int(0.12 * b.SR)
    d2 = int(T * np.log(2) / L * b.SR)  # la 2a armonica arriva d2 campioni PRIMA del lineare
    mappa, righe = {}, []
    for o, f in ORECCHI.items():
        p = os.path.join(b.OUT, f"sweep_{f}")
        if not os.path.exists(p):
            continue
        r = b.decodifica(p)
        h = fftconvolve(r, inv, "full")[len(inv) - 1:]  # h[i] = risposta per uno sweep iniziato in i
        env = np.abs(hilbert(h))
        pk, c2 = [], env.copy()
        for _ in BOCCHE:
            i = int(np.argmax(c2)); pk.append(i); c2[max(0, i - int((T + 0.5) * b.SR)): i + int((T + 0.5) * b.SR)] = 0
        pk.sort()
        rum = fftconvolve(r[int(RUMORE[0] * b.SR): int(RUMORE[1] * b.SR)], inv, "full")  # SILENZIO deconvoluto = rumore
        rum_ir = rum[len(rum) // 2: len(rum) // 2 + pre + post]
        rb = bande(rum_ir)
        for chi, i in zip(BOCCHE, pk):
            w = env[i - pre: i + post]
            fp, _ = find_peaks(w, height=0.5 * w.max()); i0 = i - pre + (int(fp[0]) if len(fp) else pre)  # PRIMO arrivo
            ir = h[i0 - pre: i0 + post]
            echi = [(round((q - pre) / b.SR * 1000, 1), round(20 * np.log10(e[q] / e[pre] + 1e-12), 1))
                    for e in [np.abs(hilbert(ir))] for q in find_peaks(e, height=0.1 * e[pre], distance=int(0.001 * b.SR))[0]
                    if q > pre + int(0.0005 * b.SR)][:4]
            arm = np.abs(h[i0 - d2 - pre: i0 - d2 + pre]).max() if i0 - d2 - pre > 0 else np.nan
            dist = 20 * np.log10(arm / (np.abs(h[i0 - pre: i0 + pre]).max() + 1e-12) + 1e-12)
            sb = bande(ir)
            mappa[chi, o] = dict(ir=ir, bande=sb, rumore=rb, echi=echi, dist2=dist)
            alti = bande(ir, ALTI, 1000) - bande(rum_ir, ALTI, 1000) if F2 > 10000 else None
            righe.append((chi, o, sb - sb.max(), sb - rb, echi, dist, alti))
    np.savez(os.path.join(b.OUT, f"mappa_{nome}.npz"),
             **{f"{c}__{o}__ir": v["ir"] for (c, o), v in mappa.items()},
             **{f"{c}__{o}__rumore": v["rumore"] for (c, o), v in mappa.items()})
    print("PERDITA = dB rispetto alla banda migliore;  SNR = dB sopra il rumore di fondo;  2a arm = deformazione (dB)")
    print(f"{'bocca->orecchio':17s}" + "".join(f"{o:>7d}" for o in OTTAVE) + "   2a arm   echi (ms dopo il diretto, dB)")
    if F2 > 10000:
        print("SNR alti (bande +-1 kHz):", "".join(f"{a // 1000:>6d}k" for a in ALTI))
    for chi, o, perd, snr, echi, dist, alti in righe:
        print(f"{chi + '->' + o:17s}" + "".join(f"{v:7.1f}" for v in perd) + f"   {dist:6.1f}   {echi}")
        print(f"{'   SNR':17s}" + "".join(f"{v:7.1f}" for v in snr))
        if alti is not None:
            print(f"{'   SNR alti':17s}" + "".join(f"{v:7.1f}" for v in alti))
    figura(mappa, nome)
    return mappa


def figura(mappa, nome):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(len(BOCCHE), len(ORECCHI), figsize=(14, 8), sharex=True)
    for i, c in enumerate(BOCCHE):
        for j, o in enumerate(ORECCHI):
            a = ax[i][j]
            if (c, o) in mappa:
                ir = mappa[c, o]["ir"]; tt = (np.arange(len(ir)) / b.SR - 0.005) * 1000
                a.plot(tt, 20 * np.log10(np.abs(hilbert(ir)) / np.abs(ir).max() + 1e-6), lw=0.7)
                a.set_ylim(-50, 3)
            a.set_title(f"{c} -> {o}", fontsize=8)
    for a in ax[-1]:
        a.set_xlabel("ms dal diretto")
    fig.suptitle("risposta all'impulso (dB): primo picco = diretto, dopo = echi")
    fig.tight_layout(); fig.savefig(os.path.join(b.OUT, f"mappa_{nome}.png"), dpi=100)
    print("figura:", os.path.join(b.OUT, f"mappa_{nome}.png"))


if __name__ == "__main__":
    a = sys.argv[1:]
    nome = (a[1] if a[:1] == ["analizza"] and len(a) > 1 else (a[0] if a and a[0] != "analizza" else "tavolo"))
    if a[:1] != ["analizza"]:
        canale.registra(segnale(), nome="sweep", pref="sweep")
    analizza(nome)
