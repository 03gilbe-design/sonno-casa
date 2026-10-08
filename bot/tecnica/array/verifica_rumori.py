"""Verifica del metodo 'rumori' (ascolta.py) su sorgenti a posizione NOTA: nel ping-pong di una prova calibra_<n>,
il 1o giro allinea gli orologi (bip propri + testimone PC), i bip del 2o giro sono trattati come rumori sconosciuti:
TDOA con finestre 0,5 s + correlazione (come ascolta.py) contro il TDOA atteso dalla posizione del dispositivo.
   python verifica_rumori.py calibra_2
"""
import os, sys, contextlib, io
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import turni as T
from scipy.signal import butter, sosfiltfilt, correlate
b = T.b


def phat(a, c, L):
    """GCC-PHAT su finestre uguali (niente zeri ai bordi): sbianca -> conta la fase, non il filtro di ogni microfono."""
    N = 2 * len(a); A, C = np.fft.rfft(a, N), np.fft.rfft(c, N); R = A * np.conj(C); R /= np.abs(R) + 1e-9
    cc = np.fft.irfft(R, N); cc = np.concatenate([cc[-L:], cc[:L + 1]]); j = int(np.argmax(cc))
    y0, y1, y2 = cc[max(j - 1, 0)], cc[j], cc[min(j + 1, len(cc) - 1)]
    return (j - L + 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2 + 1e-12)) / b.SR


def main(nome):
    d = os.path.join(T.DISP, nome)
    with contextlib.redirect_stdout(io.StringIO()):
        ris, _ = T.analizza_pp(d)
    x = T.chirp("udibile"); rec = {o: b.decodifica(os.path.join(d, f)) for o, f in T.FILE.items()}
    tt = {o: T.bip_in(r, x, len(T.GIRO)) for o, r in rec.items()}
    n4 = len(T.GIRO) // 2
    dist = {("A56", "PC"): ris["A56", "PC"], ("A21s", "PC"): ris["A21s", "PC"], ("A56", "A21s"): ris["A56", "A21s"],
            ("PC", "PC"): 0.0, ("A56", "A56"): 0.0, ("A21s", "A21s"): 0.0}
    dd = lambda a, c: dist.get((a, c), dist.get((c, a)))
    # orologi dal 1o giro: bip PROPRIO di k (nel file di k) e lo stesso bip nel file del PC
    off = {}
    for k in ("A56", "A21s"):
        i = T.GIRO.index(k)
        off[k] = tt[k][i] - (tt["PCintel"][i] - dd(k, "PC") / b.C)
    sos = butter(4, [150, 6000], "bandpass", fs=b.SR, output="sos"); n = int(0.5 * b.SR); han = np.hanning(n); L = int(0.025 * b.SR)
    print("sorgente   tdoa A56 misurato/atteso (ms)   tdoa A21s misurato/atteso (ms)")
    for i in range(n4, len(T.GIRO)):
        chi = "PC" if T.GIRO[i] == "PCdx" else T.GIRO[i]
        te = tt["PCintel"][i]  # istante di arrivo al PC (il 'rumore' e' visto dal PC)
        seg_pc = sosfiltfilt(sos, rec["PCintel"][int((te - 0.1) * b.SR):int((te - 0.1) * b.SR) + n]) * han
        riga = f"{T.GIRO[i]:8s}"
        for k in ("A56", "A21s"):
            k0 = int(round((te - 0.1 + off[k]) * b.SR))
            seg = sosfiltfilt(sos, rec[k][k0:k0 + n]) * han
            cc = np.abs(correlate(seg, seg_pc, "full", method="fft")); m = n - 1; w = cc[m - L:m + L + 1]; j = int(np.argmax(w))
            mis = (j - L) / b.SR * 1000; att = (dd(k, chi) - dd("PC", chi)) / b.C * 1000
            mp = phat(seg, seg_pc, L) * 1000
            riga += f"   {mis:6.2f} | PHAT {mp:6.2f} / {att:6.2f}"

        print(riga)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "calibra_2")
