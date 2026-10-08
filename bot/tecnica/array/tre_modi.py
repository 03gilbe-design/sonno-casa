"""
  normale    = chirp 1-6,5 kHz in bande separate (come sempre)
  ultrasuoni = chirp 17-21 kHz in bande separate (quasi non udibili)
  fruscio    = rumore 1-7 kHz, -30 dB, un seme diverso per dispositivo (stessa banda, codici diversi)
   python tre_modi.py [modo ...]   -> risultati in C:/sonno_audio/array/disposizioni/tre_modi/<modo>
Usa la versione di ripetuti.py che misura giusto (555a082, in RIP_OK) finche' quella nuova non e' riparata.
"""
import os, shutil, sys
import numpy as np
RIP_OK = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vecchio")  # ripetuti 555a082 + voce dopo la preparazione
sys.path.insert(0, RIP_OK); sys.path.insert(1, os.path.dirname(os.path.abspath(__file__)))
import ripetuti as r
import prova
from scipy.signal import butter, sosfiltfilt

b = r.b
DUR = len(r.BOCCHE["A56"]) / b.SR


def fruscio(seme, f0=1000, f1=7000, rms=0.012):  # chirp ~0,39 rms -> -30 dB
    x = np.random.default_rng(seme).standard_normal(len(r.BOCCHE["A56"]))
    x = sosfiltfilt(butter(6, [f0, f1], "bandpass", fs=b.SR, output="sos"), x) * np.hanning(len(x))
    return (x / np.sqrt(np.mean(x ** 2)) * rms).astype(np.float32)


MODI = {"normale": dict(r.BOCCHE),
        "ultrasuoni": {"A56": b.chirp(17000, 18200, DUR), "A21s": b.chirp(18400, 19600, DUR), "PC": b.chirp(19800, 21000, DUR)},
        "fruscio": {"A56": fruscio(1), "A21s": fruscio(2), "PC": fruscio(3)}}


def main(modi):
    for m in modi:
        prova.parla(m)
        r.BOCCHE.clear(); r.BOCCHE.update(MODI[m])
        try:
            r.registra(); r.analizza()
        except Exception as e:
            print(m, "ERRORE", e)
        d = f"C:/sonno_audio/array/disposizioni/tre_modi/{m}"
        os.makedirs(d, exist_ok=True)
        for f in os.listdir(b.OUT):
            if f.startswith("rip_") and not f.endswith(".caricato"):
                shutil.copy(os.path.join(b.OUT, f), d)
        print("=====", m, "fatto")


if __name__ == "__main__":
    main(sys.argv[1:] or list(MODI))
