"""
distanza da un punto: d_mis = (|cassa-X| + |X-mic| - |cassa-mic|) / 2. Con cassa SX e DX ogni telefono da' 2 equazioni,
+ distanza fra i telefoni = 5 equazioni, 4 incognite (x,y dei telefoni sul tavolo) -> minimi quadrati, 1 di controllo.
   python pc_tre_punti.py <cartella calibra_n>
Geometria PC (HMM Lenovo, HARDWARE.md): casse ai lati della tastiera ~1,5 cm dai bordi, ~10 cm dal bordo polsi;
mic al centro sopra lo schermo (schermo ~21 cm, aperto ~100-110 gradi). Origine: centro del bordo polsi, x a destra,
y verso lo schermo, z in alto. ponytail: geometria stimata, non misurata sul pezzo: +-2 cm.
"""
import os, sys, contextlib, io
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import turni as T  # PRIMA di scipy.optimize: altrimenti onnxruntime 'DLL load failed'
from scipy.optimize import least_squares
b = T.b

CASSA_SX, CASSA_DX = np.array([-0.145, 0.10, 0.0]), np.array([0.145, 0.10, 0.0])
MIC = np.array([0.0, 0.25, 0.21])


def misure(cartella):
    x = T.chirp("udibile")
    t = {}
    for o, f in T.FILE.items():
        tt = T.bip_in(b.decodifica(os.path.join(cartella, f)), x, len(T.GIRO))
        for chi in set(T.GIRO):
            t[o, chi] = tt[[i for i, c in enumerate(T.GIRO) if c == chi]]
    orecchio = {"A56": "A56", "A21s": "A21s", "PC": "PCintel", "PCdx": "PCintel"}
    m = {}
    for X, Y in (("A56", "A21s"), ("A56", "PC"), ("A21s", "PC"), ("A56", "PCdx"), ("A21s", "PCdx")):
        oX, oY = orecchio[X], orecchio[Y]
        dd = [b.C / 2 * ((ty - tx) - (ty2 - tx2)) for tx, tx2 in zip(t[oX, X], t[oY, X]) for ty, ty2 in zip(t[oX, Y], t[oY, Y])]
        m[X, Y] = float(np.median(dd))
    return m


def risolvi(m):
    def mis_pc(p, cassa):
        X = np.array([p[0], p[1], 0.0])
        return (np.linalg.norm(cassa - X) + np.linalg.norm(X - MIC) - np.linalg.norm(cassa - MIC)) / 2

    def res(v):
        a, c = v[:2], v[2:]
        return [mis_pc(a, CASSA_SX) - m["A56", "PC"], mis_pc(a, CASSA_DX) - m["A56", "PCdx"],
                mis_pc(c, CASSA_SX) - m["A21s", "PC"], mis_pc(c, CASSA_DX) - m["A21s", "PCdx"],
                np.linalg.norm(a - c) - m["A56", "A21s"]]
    migliore = None
    for s1 in (-1, 1):  # davanti o dietro la linea delle casse: provo tutte e 4 le combinazioni
        for s2 in (-1, 1):
            v0 = [0.4, 0.3 * s1, 1.0, 0.3 * s2]
            r = least_squares(res, v0)
            if migliore is None or r.cost < migliore.cost:
                migliore = r
    return migliore


def main(nome):
    d = os.path.join(T.DISP, nome)
    m = misure(d)
    print("misure grezze (m):", {f"{k[0]}-{k[1]}": round(v, 3) for k, v in m.items()})
    r = risolvi(m)
    a, c = r.x[:2], r.x[2:]
    print(f"tuo telefono: x {a[0]:+.3f}  y {a[1]:+.3f} m   (dal centro del bordo polsi del PC)")
    print(f"A21s:         x {c[0]:+.3f}  y {c[1]:+.3f} m")
    print(f"distanza telefoni {np.linalg.norm(a - c):.3f} m;  residui (cm) {np.round(np.array(r.fun) * 100, 1)}")
    for nomep, p in (("tuo telefono", a), ("A21s", c)):
        print(f"  {nomep}: da cassa SX {np.linalg.norm(CASSA_SX - [p[0], p[1], 0]):.3f} m, dal mic {np.linalg.norm(MIC - [p[0], p[1], 0]):.3f} m")
    return a, c, r


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "calibra_1")
