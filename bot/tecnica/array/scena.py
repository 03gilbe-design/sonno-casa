"""
Disposizione "telo": per terra su telo, in fila lungo il muro: PC (angolo, retro schermo al battiscopa) | foglio A4 |
A56 | foglio A4 | A21s. Telefoni sdraiati lungo il muro. Punti di casse/mic dal modello locale di geometria.py.
   python scena.py            -> previsioni per i 4 orientamenti + figura C:/sonno_audio/array/scena_telo.png
   python scena.py verifica   -> prova.py (suoni!) poi confronto previsto/misurato e orientamento dedotto
Coordinate globali cm: x lungo il muro (verso destra), y dal muro verso la stanza, z in su. Centro PC in x=0.
"""
import itertools, sys
import numpy as np
import geometria as g

A4 = 29.7                      # spazio fra un dispositivo e l'altro (foglio A4 per lungo, sua misura)
# A56 SM-A566B 162,2 x 77,5 x 7,4 mm (phonemore/gsmchoice); A21s SM-A217F 163,7 x 75,3 x 8,9 mm (gsmarena,
# manuale Samsung: cassa + mic in basso vicino alla USB-C, 2o mic in alto); PC 321,5 x 217,5 x 17,9 (PSREF Lenovo)
LUNGO = {"A56": 16.22, "A21s": 16.37}
LARGO = {"A56": 7.75, "A21s": 7.53}
SPESSO = {"A56": 0.74, "A21s": 0.89}
TELO = 1.5  # cm: telo da spiaggia 1-2 cm sotto tutti (sua misura)
MURO_Y = 0.0


def scena(o56, o21):
    """o = 'PC' / 'lontano': telefono sdraiato LUNGO il muro, bordo basso (USB, cassa, mic) verso il PC o dall'altra parte;
    schermo in alto"). Ritorna {disp: {bocca, orecchio}}."""
    pc_cx, pc_cy = 0.0, MURO_Y + g.PC_D / 2                         # PC col retro contro il muro
    loc = lambda d, n: np.array(g.PUNTI[d, n][:3])
    # PC locale: y+ = verso la cerniera = verso il muro -> globale y = pc_cy - y_locale
    pcg = lambda n: np.array([pc_cx + loc("PC", n)[0], pc_cy - loc("PC", n)[1], TELO + loc("PC", n)[2]])
    out = {"PC": {"bocca": pcg("cassa_dx"), "orecchio": (pcg("mic_sx") + pcg("mic_dx")) / 2}}
    x = g.PC_W / 2 + A4
    for nome, o in (("A56", o56), ("A21s", o21)):
        ingombro = LARGO[nome] if o == "stanza" else LUNGO[nome]  # quanto occupa LUNGO il muro
        xc = x + ingombro / 2; x += ingombro + A4
        if o == "stanza":   # asse lungo perpendicolare al muro, bordo basso (y locale negativo) verso la stanza
            glob = lambda n, xc=xc: np.array([xc + loc(nome, n)[0], MURO_Y + LUNGO[nome] / 2 - loc(nome, n)[1],
                                              TELO + SPESSO[nome] / 2])  # fori a meta' spessore del bordo
        else:               # sdraiato lungo il muro; bordo basso verso il PC = x minore
            v = 1 if o == "PC" else -1
            glob = lambda n, xc=xc, v=v: np.array([xc + v * loc(nome, n)[1], MURO_Y + LARGO[nome] / 2 - loc(nome, n)[0],
                                                   TELO + SPESSO[nome] / 2])
        out[nome] = {"bocca": glob("cassa_basso"), "orecchio": glob("mic_basso")}
    return out


def previsioni(s):
    bb = lambda A, B: (np.linalg.norm(A["bocca"] - B["orecchio"]) + np.linalg.norm(B["bocca"] - A["orecchio"])) / 200
    return {"A56-A21s": bb(s["A56"], s["A21s"]), "A56-PC": bb(s["A56"], s["PC"]), "A21s-PC": bb(s["A21s"], s["PC"]),
            "tdoa_PCintel": (np.linalg.norm(s["A21s"]["bocca"] - s["PC"]["orecchio"]) -
                             np.linalg.norm(s["A56"]["bocca"] - s["PC"]["orecchio"])) / 100}


NOMI_O = {"PC": "USB verso PC", "lontano": "USB lontano PC", "stanza": "USB verso stanza"}
ORIENT = {(a, c): f"A56 {NOMI_O[a]}, A21s {NOMI_O[c]}" for a, c in itertools.product(NOMI_O, NOMI_O)}


def confronta(misure):
    print(f"{'orientamento':40s}" + "".join(f"{k:>14s}" for k in ("A56-A21s", "A56-PC", "A21s-PC", "tdoa_PCintel")) + "   errore")
    if misure:
        print(f"{'MISURATO':40s}" + "".join(f"{misure[k][0]:14.3f}" if k in misure else f"{'-':>14s}"
                                           for k in ("A56-A21s", "A56-PC", "A21s-PC", "tdoa_PCintel")))
    migliore = None
    for v, nome in ORIENT.items():
        p = previsioni(scena(*v))
        # errore solo sulle misure affidabili (dispersione < 5 cm)
        usa = [k for k in p if k in misure and misure[k][1] < 0.05] if misure else []
        err = np.sqrt(np.mean([(p[k] - misure[k][0]) ** 2 for k in usa])) * 100 if usa else np.nan
        print(f"{nome:40s}" + "".join(f"{p[k]:14.3f}" for k in p) + (f"   {err:5.1f} cm" if usa else ""))
        if usa and (migliore is None or err < migliore[0]):
            migliore = (err, nome)
    if migliore:
        print(f"\nORIENTAMENTO DEDOTTO dai suoni: {migliore[1]}  (errore medio {migliore[0]:.1f} cm)")
    return migliore


def figura(v=("stanza", "stanza"), path="C:/sonno_audio/array/scena_telo.png"):
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    s = scena(*v); ax = plt.figure(figsize=(9, 5)).add_subplot(projection="3d")
    for d, pts in s.items():
        for tipo, p in pts.items():
            ax.scatter(*p, c="tab:red" if tipo == "bocca" else "tab:blue", s=50); ax.text(*p, f"{d} {tipo}", fontsize=7)
    ax.plot([-20, 130], [MURO_Y, MURO_Y], [0, 0], "k-", lw=2); ax.text(-20, MURO_Y, 0, "muro", fontsize=8)
    ax.set_xlabel("x cm (lungo il muro)"); ax.set_ylabel("y cm (verso la stanza)"); ax.set_zlabel("z cm")
    ax.set_title(ORIENT[v] + "  (rosso = cassa, blu = mic)")
    plt.savefig(path, dpi=110); print("figura:", path)


if __name__ == "__main__":
    misure = {}
    if sys.argv[1:] == ["verifica"]:
        import prova, ripetuti
        prova.registra(); prova.analizza("telo_verifica"); prova.RIPRISTINO.join()
        misure = dict(ripetuti.RIS)
    migliore = confronta(misure)
    figura(next(v for v, n in ORIENT.items() if n == migliore[1]) if migliore else ("stanza", "stanza"))
