"""
hai cerchi attaccati ma non fissi, tipo catena; poi il terzo punto fa suono e crea altri due cerchi"; "immaginiamo
che li disponga sul pavimento a caso").
   python animazione.py [manda]  -> C:/sonno_audio/array/grafici/5_animazione.mp4 (1080x1350, 4:5)
Fasi: 1) suona PC -> A56 e A21s stanno ciascuno su un ANELLO attorno al PC (posizione ignota sull'anello)
      2) suona A56 -> A21s sta anche su un anello attorno ad A56: CATENA PC-A56-A21s, ancora snodata (oscilla)
      3) suona A21s -> il triangolo si chiude: RIGIDO, ma puo' ancora ruotare tutto attorno al PC
      4) un riferimento (una direzione nota) blocca la rotazione -> posizioni vere.
Distanze = teoria (dispositivi a caso sul pavimento); il metodo e' quello misurato stasera (BeepBeep, mm).
"""
import os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter

OUT = "C:/sonno_audio/array/grafici/5_animazione.mp4"
FONDO, TESTO = "#101820", "#E8E6E3"
COL = {"PC": "#F2AA4C", "A56": "#4CC9F0", "A21s": "#7BD389"}
VERI = {"PC": np.array([0.0, 0.0]), "A56": np.array([62.0, 18.0]), "A21s": np.array([22.0, 58.0])}  # a caso, cm
D = {("PC", "A56"): 64.6, ("PC", "A21s"): 62.0, ("A56", "A21s"): 56.6}
FPS, F = 20, 50  # fotogrammi per fase


def rot(v, a):
    return np.array([np.cos(a) * v[0] - np.sin(a) * v[1], np.sin(a) * v[0] + np.cos(a) * v[1]])


def main(manda=False):
    fig = plt.figure(figsize=(10.8, 13.5), dpi=100, facecolor=FONDO)
    ax = fig.add_axes([0.03, 0.14, 0.94, 0.72]); ax.set_facecolor(FONDO)
    ax.set_xlim(-85, 135); ax.set_ylim(-95, 140); ax.set_aspect("equal"); ax.axis("off")
    tit = fig.text(0.5, 0.935, "", ha="center", color=TESTO, fontsize=26, weight="bold")
    sot = fig.text(0.5, 0.89, "", ha="center", color="#aab", fontsize=16)
    bas = fig.text(0.5, 0.07, "", ha="center", color=TESTO, fontsize=19)
    for n, v in VERI.items():  # posizioni vere (fantasmi)
        ax.scatter(*v, s=700, facecolors="none", edgecolors=COL[n], linewidths=1, alpha=0.3)
    anelli = []
    punti = {n: ax.scatter([0], [0], s=420, c=COL[n], edgecolors="white", linewidths=1.5, zorder=5) for n in VERI}
    nomi = {n: ax.text(0, 0, n, color=COL[n], fontsize=16, ha="center", weight="bold", zorder=6) for n in VERI}
    onda = plt.Circle((0, 0), 0, fill=False, lw=3, alpha=0.9); ax.add_patch(onda)
    tot = 5 * F

    def anello(c, r, col, ls="-", a=0.8):
        anelli.append(ax.add_patch(plt.Circle(tuple(c), r, fill=False, color=col, lw=2.2, ls=ls, alpha=a)))

    def frame(i):
        for p in anelli:
            p.remove()
        anelli.clear()
        fase, k = divmod(i, F); t = k / F
        a56 = VERI["A56"]; a21 = VERI["A21s"]; ang_vero = np.arctan2(a56[1], a56[0])
        pos = {"PC": np.zeros(2)}
        onda.set_radius(0)
        if fase == 0:
            tit.set_text("1 · Suona il PC"); sot.set_text("due cerchi attorno al PC: ognuno sta sul suo, ma come stanno tra loro non si sa")
            onda.center = (0, 0); onda.set_radius(t * 80); onda.set_edgecolor(COL["PC"])
            if t > 0.8:
                anello((0, 0), D["PC", "A56"], COL["A56"]); anello((0, 0), D["PC", "A21s"], COL["A21s"])
            pos["A56"] = rot(np.array([D["PC", "A56"], 0]), 2.0 + 3 * t); pos["A21s"] = rot(np.array([D["PC", "A21s"], 0]), 4.0 - 2 * t)
            bas.set_text("A56 su un anello da 64,6 cm · A21s su uno da 62,0 cm")
        elif fase == 1:
            tit.set_text("2 · Suona l'A56"); sot.set_text("A21s e' anche su un anello attorno all'A56: con 3 distanze il triangolo e' GIA' fisso")
            osc = 0.9 * np.sin(2 * np.pi * t)  # la catena ruota: tutto e' ancora possibile
            pos["A56"] = rot(a56, osc)
            # A21s: sui due anelli (PC e A56) -> intersezione, che si muove con la catena
            pos["A21s"] = rot(a21, osc)
            onda.center = tuple(pos["A56"]); onda.set_radius((t % 0.5) * 2 * 60); onda.set_edgecolor(COL["A56"])
            anello((0, 0), D["PC", "A56"], COL["A56"], a=0.4); anello((0, 0), D["PC", "A21s"], COL["A21s"], a=0.4)
            anello(pos["A56"], D["A56", "A21s"], COL["A21s"])
            bas.set_text("forma fissa, ma puo' ancora ruotare tutto (o ribaltarsi a specchio)")
        elif fase == 2:
            tit.set_text("3 · Suona l'A21s"); sot.set_text("altri due anelli: rimisurano le stesse distanze = CONTROLLO (stasera: 2 mm)")
            osc = 0.9 * (1 - t) * np.sin(2 * np.pi * t)
            pos["A56"] = rot(a56, osc); pos["A21s"] = rot(a21, osc)
            onda.center = tuple(pos["A21s"]); onda.set_radius(t * 70); onda.set_edgecolor(COL["A21s"])
            anello(pos["A21s"], D["PC", "A21s"], COL["PC"], ls="--"); anello(pos["A21s"], D["A56", "A21s"], COL["A56"], ls="--")
            bas.set_text("la catena snodata vera arriva con 4+ dispositivi che non si sentono tutti")
        elif fase == 3:
            tit.set_text("4 · Un riferimento blocca la rotazione"); sot.set_text("es. il muro, o una direzione nota")
            giro = (1 - t) * 1.2
            pos["A56"] = rot(a56, giro); pos["A21s"] = rot(a21, giro)
            bas.set_text("il triangolo ruota fino a combaciare")
        else:
            tit.set_text("Posizioni trovate solo col suono"); sot.set_text("anelli → catena → triangolo → riferimento")
            pos["A56"] = a56; pos["A21s"] = a21
            bas.set_text("PC–A56 64,6 cm · PC–A21s 62,0 cm · A56–A21s 56,6 cm")
        for n, p in pos.items():
            punti[n].set_offsets([p]); nomi[n].set_position(p + [0, 8])
        if fase >= 1:
            for a, c in (("PC", "A56"), ("A56", "A21s")) + ((("PC", "A21s"),) if fase >= 2 else ()):
                anelli.append(ax.plot(*zip(pos[a], pos[c]), color="white", ls="--", lw=1.5, alpha=0.7)[0])
        return []

    anim = FuncAnimation(fig, frame, frames=tot, interval=1000 / FPS)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    anim.save(OUT, writer=FFMpegWriter(fps=FPS, bitrate=2500, extra_args=["-pix_fmt", "yuv420p"]), savefig_kwargs={"facecolor": FONDO})
    for t in (0.9, 1.5, 2.5):
        frame(int(t * F)); fig.savefig(OUT.replace(".mp4", f"_f{t}.png"), facecolor=FONDO)
    print("salvato", OUT)
    if manda:
        sys.path.insert(0, "C:/sonno_bot")
        import manda_valutazione as m
        m.file("sendAnimation", "animation", OUT,
               "🎬 <b>Anelli → catena → triangolo</b>: 1 suono = anello, 2 = catena snodata, 3 = triangolo rigido, "
               "un riferimento blocca la rotazione. Dispositivi a caso sul pavimento.")
        print("inviato")


if __name__ == "__main__":
    main(sys.argv[1:] == ["manda"])
