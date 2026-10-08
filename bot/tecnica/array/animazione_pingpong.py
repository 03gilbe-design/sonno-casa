"""
   python animazione_pingpong.py [manda]  -> C:/sonno_audio/array/grafici/7_pingpong.mp4 (1080x1350)
"""
import sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter
from mappa_precisione import posizioni, D
from animazione2 import BG, ROSSO, BIANCO, ease

OUT = "C:/sonno_audio/array/grafici/7_pingpong.mp4"
FPS, SLOT, V = 30, 1.3, 2.2          # s per turno, velocita' onda rallentata (m/s nel video)
P = posizioni()
P["PCdx"] = P["PC"] + np.array([0.0, -0.16])  # cassa destra ~16 cm (tastiera 32 cm)
P["PC"] = P["PC"] + np.array([0.0, 0.16])
GIRO = ("A56", "A21s", "PC", "PCdx", "A21s", "A56") * 2
NOME = {"A56": "telefono tuo", "A21s": "A21s", "PC": "PC sx", "PCdx": "PC dx"}


def main(manda=False):
    fig = plt.figure(figsize=(10.8, 13.5), dpi=100, facecolor=BG)
    ax = fig.add_axes([0.05, 0.12, 0.9, 0.72]); ax.set_facecolor(BG); ax.set_aspect("equal"); ax.axis("off")
    ax.set_xlim(-0.8, 4.5); ax.set_ylim(-1.6, 2.0)
    titolo = fig.text(0.5, 0.92, "il suono viaggia: 1-2-3-3-2-1", ha="center", color=BIANCO, fontsize=30)
    sotto = fig.text(0.5, 0.07, "", ha="center", color=BIANCO, fontsize=22)
    for (a, b), d in D.items():
        pa, pb = P[a], P[b]
        ax.plot(*zip(pa, pb), color=BIANCO, lw=1, alpha=0.18)
        ax.text(*(pa + pb) / 2 + [0, 0.07], f"{d:.2f} m", color=BIANCO, alpha=0.5, ha="center", fontsize=15)
    punti = {k: [ax.scatter(*v, s=s, c=BIANCO, alpha=al, linewidths=0, zorder=5) for s, al in ((2200, 0.05), (900, 0.1), (260, 1))]
             for k, v in P.items()}
    for k, v in P.items():
        ax.text(v[0], v[1] - 0.2 if k != "PC" else v[1] + 0.13, NOME[k], color=BIANCO, ha="center", fontsize=15)
    onde = [ax.add_patch(plt.Circle((0, 0), 0.01, fill=False, color=ROSSO, lw=w, alpha=0)) for w in (10, 4, 1.8)]
    n = int((len(GIRO) * SLOT + 1.5) * FPS)

    def frame(i):
        t = i / FPS; k = min(int(t / SLOT), len(GIRO) - 1); chi = GIRO[k]; ts = t - k * SLOT
        r = ts * V
        for c, al in zip(onde, (0.08, 0.2, 0.9)):
            c.center = tuple(P[chi]); c.set_radius(max(r, 0.01)); c.set_alpha(al * max(0, 1 - r / 4.2))
        for q, strati in punti.items():
            if q == chi:
                col, luce = ROSSO, ease(1 - ts / 0.5) * 0.6 + 0.4
            else:
                arriva = np.linalg.norm(P[q] - P[chi]) / V
                luce = ease(1 - abs(ts - arriva) / 0.25) if ts >= arriva - 0.25 else 0
                col = (1 - luce) * np.array(matplotlib.colors.to_rgb(BIANCO)) + luce * np.array(matplotlib.colors.to_rgb("#f4a261"))
            for sc, (s, al) in zip(strati, ((2200, 0.05), (900, 0.1), (260, 1))):
                sc.set_color([col]); sc.set_sizes([s * (1 + 0.8 * luce if q != chi else 1.3)])
        ascolto = ", ".join(NOME[q] for q in P if q != chi and np.linalg.norm(P[q] - P[chi]) / V <= ts)
        sotto.set_text(f"suona {NOME[chi]}" + (f"  ->  lo sente {ascolto}" if ascolto else ""))
        return []

    FuncAnimation(fig, frame, frames=n).save(OUT, writer=FFMpegWriter(fps=FPS, bitrate=5000, extra_args=["-pix_fmt", "yuv420p"]),
                                              savefig_kwargs={"facecolor": BG})
    frame(int(2.6 * SLOT * FPS)); fig.savefig(OUT.replace(".mp4", ".png"), facecolor=BG)
    print("salvato", OUT)
    if manda:
        sys.path.insert(0, "C:/sonno_bot")
        import manda_valutazione as m
        m.file("sendAnimation", "animation", OUT, "🔴 <b>Il suono che viaggia</b> (1-2-3-3-2-1, posizioni misurate stanotte, "
               "rallentato ~650 volte): chi suona diventa rosso, l'onda accende chi la sente")
        print("inviato")


if __name__ == "__main__":
    main(sys.argv[1:] == ["manda"])
