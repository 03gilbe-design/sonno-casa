"""
   python super_mic.py [bocca]   -> prende lo sweep di <bocca> (PC default) sentito da tutti gli orecchi dell'ultima
       prova.py, deconvolve (risposta all'impulso), allinea i picchi e somma pesando ogni orecchio per il suo rumore
       (maximum ratio combining). Stampa SNR di ogni orecchio e del super microfono.
Teoria: sommando N orecchi allineati il segnale si somma in fase, il rumore (indipendente) no -> guadagno fino a
10*log10(N) dB se uguali; con pesi ottimi SNR_super = somma degli SNR lineari.
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import beepbeep as b
import sweep as sw
from scipy.signal import fftconvolve, hilbert

FILE = {"A56": "sweep_a56.m4a", "A21s": "sweep_a21s.m4a", "PCintel": "sweep_pc_intel.wav"}


def main(bocca="PC"):
    x, inv = sw.ess(); k = sw.BOCCHE.index(bocca)
    pre, post = int(0.005 * b.SR), int(0.12 * b.SR)
    ir, rum = {}, {}
    for o, f in FILE.items():
        if o.startswith(bocca):  # la bocca non ascolta se stessa per il super microfono
            continue
        p = os.path.join(b.OUT, f)
        if not os.path.exists(p):
            continue
        r = b.decodifica(p); h = fftconvolve(r, inv, "full")[len(inv) - 1:]; env = np.abs(hilbert(h))
        pk, c2 = [], env.copy()
        for _ in sw.BOCCHE:
            i = int(np.argmax(c2)); pk.append(i); c2[max(0, i - int((sw.T + 0.5) * b.SR)): i + int((sw.T + 0.5) * b.SR)] = 0
        i = sorted(pk)[k]
        ir[o] = h[i - pre: i + post]
        n = fftconvolve(r[int(sw.RUMORE[0] * b.SR): int(sw.RUMORE[1] * b.SR)], inv, "full")
        rum[o] = float(np.var(n[len(n) // 2 - pre: len(n) // 2 + post]))
    snr = {o: 10 * np.log10(np.max(ir[o] ** 2) / rum[o]) for o in ir}
    # allineo sul picco (i ritardi fra orecchi = le distanze, gia' misurate) e sommo con pesi a/sigma^2
    pesi = {o: np.max(np.abs(ir[o])) / rum[o] for o in ir}
    somma = sum(pesi[o] * ir[o] * np.sign(ir[o][pre]) for o in ir)
    rum_somma = sum(pesi[o] ** 2 * rum[o] for o in ir)
    snr_super = 10 * np.log10(np.max(somma ** 2) / rum_somma)
    print(f"bocca {bocca}: SNR per orecchio (dB):", {o: round(v, 1) for o, v in snr.items()})
    print(f"SUPER MICROFONO ({len(ir)} orecchi): {snr_super:.1f} dB  -> +{snr_super - max(snr.values()):.1f} dB sul "
          f"migliore; teorico MRC {10 * np.log10(sum(10 ** (v / 10) for v in snr.values())):.1f} dB")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "PC")
