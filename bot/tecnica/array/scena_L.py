"""
verticale; telefoni VERI (dalla L) contro MISURATI (pc_tre_punti su calibra_1). Unita' m, origine centro bordo polsi PC.
   python scena_L.py [manda]
"""
import sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

OUT = "C:/sonno_audio/array/grafici/scena_L.png"
BG, ROSSO, BIANCO, GRIGIO, AZZ = "#141416", "#e63946", "#d4d4d8", "#55555c", "#4ea8de"
PC_W, PC_D = 0.322, 0.218
FOGLI = [("foglio 1", 0.161, 0.0, 0.297, 0.21), ("quaderno 2", 0.458, 0.0, 0.297, 0.21), ("quaderno 3", 0.755, 0.0, 0.21, 0.297)]
VERO = {"tuo telefono": (0.34, -0.12), "A21s": (0.87, 0.34)}
MISURATO = {"tuo telefono": (0.463, -0.002), "A21s": (1.165, 0.118)}


def rett(ax, x, y, w, h, z=0.0, col=GRIGIO, a=0.5):
    ax.add_collection3d(Poly3DCollection([[(x, y, z), (x + w, y, z), (x + w, y + h, z), (x, y + h, z)]], facecolor=col, edgecolor=BIANCO, alpha=a, lw=0.6))


def main(manda=False):
    fig = plt.figure(figsize=(8, 10), facecolor=BG); ax = fig.add_subplot(111, projection="3d"); ax.set_facecolor(BG)
    rett(ax, -PC_W / 2, 0, PC_W, PC_D, col="#2a2a30", a=0.9)  # base PC
    ax.add_collection3d(Poly3DCollection([[(-PC_W / 2, PC_D, 0), (PC_W / 2, PC_D, 0), (PC_W / 2, PC_D + 0.04, 0.21), (-PC_W / 2, PC_D + 0.04, 0.21)]],
                                         facecolor="#1d1d22", edgecolor=BIANCO, alpha=0.9, lw=0.6))  # schermo
    ax.scatter([-0.145, 0.145], [0.10, 0.10], [0.005, 0.005], c=AZZ, s=40); ax.scatter([0], [0.25], [0.21], c=AZZ, s=50, marker="^")
    ax.text(0, 0.27, 0.25, "mic PC", color=AZZ, fontsize=9); ax.text(-0.3, 0.1, 0.02, "casse", color=AZZ, fontsize=9)
    for nome, x, y, w, h in FOGLI:
        rett(ax, x, y, w, h); ax.text(x + w / 2, y + h / 2, 0.01, nome, color=BIANCO, fontsize=8, ha="center")
    for nome in VERO:
        (xv, yv), (xm, ym) = VERO[nome], MISURATO[nome]
        ax.scatter([xv], [yv], [0.0], s=160, facecolors="none", edgecolors=BIANCO, linewidths=2)
        ax.scatter([xm], [ym], [0.0], s=120, c=ROSSO, marker="x", linewidths=3)
        ax.plot([xv, xm], [yv, ym], [0, 0], color=ROSSO, lw=1, ls="--")
        err = np.hypot(xm - xv, ym - yv) * 100
        ax.text(xv, yv - 0.08, 0.02, f"{nome}\nerrore {err:.0f} cm", color=BIANCO, fontsize=10, ha="center")
    ax.set_xlim(-0.3, 1.25); ax.set_ylim(-0.45, 0.6); ax.set_zlim(0, 0.4); ax.set_box_aspect((1.55, 1.05, 0.4))
    ax.view_init(elev=35, azim=-70); ax.set_axis_off()
    fig.text(0.5, 0.93, "La tua L ricreata in 3D", ha="center", color=BIANCO, fontsize=20)
    fig.text(0.5, 0.89, "cerchio = dove sono davvero (dai quaderni)   ×  = dove li ho misurati", ha="center", color=BIANCO, fontsize=11)
    fig.text(0.5, 0.06, "A21s: la sua misura con la cassa sinistra del PC e' sbagliata (eco) -> errore grande", ha="center", color=BIANCO, fontsize=10, alpha=0.8)
    fig.savefig(OUT, facecolor=BG, dpi=110); print("salvato", OUT)
    if manda:
        sys.path.insert(0, "C:/sonno_bot")
        import manda_valutazione as m
        m.file("sendPhoto", "photo", OUT, "🧊 La L ricreata in 3D: cerchi = posizioni vere dai quaderni, × = misurate. Tuo telefono ~15 cm di errore, A21s ~40 cm (misura col PC falsata da eco)")
        print("inviato")


if __name__ == "__main__":
    main(sys.argv[1:] == ["manda"])
