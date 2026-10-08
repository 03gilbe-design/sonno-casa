"""
   python schema_disposizione.py [manda]
Origine = centro del bordo polsi del PC (linea zero); x verso destra, y verso il muro (cm).
"""
import sys
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

OUT = "C:/sonno_audio/array/grafici/schema_disposizione.png"
BG, BIANCO, GRIGIO, ROSSO = "#141416", "#d4d4d8", "#3a3a40", "#e63946"
PC_W, PC_D = 32.2, 21.8
A56_L, A56_W = 16.2, 7.8
A21_L, A21_W = 16.4, 7.5
A56_X = PC_W / 2 + 29.7      # bordo USB dell'A56 a 1 A4 (lungo) dal fianco destro del PC
A21_Y = -10.5                # lato lungo dell'A21s a mezzo A4 (corto piegato) dalla linea zero


def main(manda=False):
    fig, ax = plt.subplots(figsize=(8, 10), facecolor=BG)
    ax.set_facecolor(BG); ax.set_aspect("equal")
    ax.set_xlim(-25, 65); ax.set_ylim(-35, 75)
    ax.set_xticks(range(-20, 61, 10)); ax.set_yticks(range(-30, 71, 10))
    ax.grid(color=GRIGIO, lw=0.8); ax.tick_params(colors=BIANCO, labelsize=9)
    for s in ax.spines.values():
        s.set_visible(False)
    rett = lambda x, y, w, h, **k: ax.add_patch(Rectangle((x, y), w, h, fill=False, lw=2.5, **k))
    rett(-PC_W / 2, 0, PC_W, PC_D, ec=BIANCO)
    ax.plot([-PC_W / 2, PC_W / 2], [PC_D, PC_D], color=BIANCO, lw=7)  # schermo in piedi
    ax.text(0, PC_D + 3, "SCHERMO (in piedi, guarda verso di te)", color=BIANCO, ha="center", fontsize=10)
    ax.text(0, PC_D / 2, "PC\ntastiera", color=BIANCO, ha="center", va="center", fontsize=12)
    rett(-5, 1.5, 10, 6, ec=GRIGIO); ax.text(0, 4.5, "touchpad", color=BIANCO, ha="center", va="center", fontsize=8)
    # A56: sdraiato orizzontale, USB a sinistra (verso il PC), bordo davanti sulla linea zero
    rett(A56_X, 0, A56_L, A56_W, ec=BIANCO)
    ax.plot([A56_X, A56_X], [0, A56_W], color=ROSSO, lw=5); ax.text(A56_X + 1, A56_W / 2, "USB", color=ROSSO, va="center", fontsize=9)
    ax.text(A56_X + A56_L / 2, A56_W + 2.5, "A56 (schermo al soffitto)", color=BIANCO, ha="center", fontsize=10)
    # dalla linea zero, bordo USB a destra allineato al fianco destro del PC
    x0 = PC_W / 2 - A21_L
    rett(x0, A21_Y - A21_W, A21_L, A21_W, ec=BIANCO)
    ax.plot([PC_W / 2, PC_W / 2], [A21_Y - A21_W, A21_Y], color=ROSSO, lw=5)
    ax.text(PC_W / 2 - 1, A21_Y - A21_W / 2, "USB", color=ROSSO, ha="right", va="center", fontsize=9)
    ax.text(x0 + A21_L / 2, A21_Y - A21_W - 3.5, "A21s (schermo al soffitto)", color=BIANCO, ha="center", fontsize=10)
    ax.plot([PC_W / 2, PC_W / 2], [A21_Y, 0], color=GRIGIO, lw=1.5, ls=":")
    ax.text(PC_W / 2 + 1.5, A21_Y - A21_W / 2, "← USB allineata al\n   fianco destro del PC", color=BIANCO, va="center", fontsize=8)
    ax.axhline(0, color=BIANCO, lw=1, ls="--"); ax.text(-24, -9, "linea zero\n(bordo polsi)", color=BIANCO, ha="left", fontsize=9)
    frecce = dict(arrowstyle="<->", color=ROSSO, lw=1.8)
    ax.annotate("", (PC_W / 2, 10), (A56_X, 10), arrowprops=frecce)
    ax.text((PC_W / 2 + A56_X) / 2, 11.5, "29,7 cm\n1 A4 lungo", color=ROSSO, ha="center", fontsize=9)
    ax.annotate("", (5, 0), (5, A21_Y), arrowprops=frecce)
    ax.text(6, A21_Y / 2, "10,5 cm = mezzo A4\n(lato corto piegato)", color=ROSSO, ha="left", va="center", fontsize=9)
    ax.text(20, 50,"WEBCAM: dove vuoi,\nalta >= 10 cm,\nNON dirmelo", color=BIANCO, ha="center", fontsize=11)
    ax.set_title("Disposizione prova 3D (vista dall'alto, griglia 10 cm)", color=BIANCO, fontsize=13)
    ax.plot(0, 0, "o", color=ROSSO, ms=9); ax.text(-2, -3, "0,0 = centro\nbordo polsi PC", color=ROSSO, fontsize=8, ha="right", va="top")
    ax.set_xlabel("cm verso DESTRA dal centro del PC  →", color=BIANCO, fontsize=10)
    ax.set_ylabel("cm verso il MURO dal bordo polsi  →", color=BIANCO, fontsize=10)
    fig.savefig(OUT, facecolor=BG, dpi=130, bbox_inches="tight")
    print("salvato", OUT)
    if manda:
        sys.path.insert(0, "C:/sonno_bot")
        import manda_valutazione as m
        m.file("sendPhoto", "photo", OUT, "📐 Disposizione prova 3D, in scala (griglia 10 cm). Rosso = bordo USB.")
        print("inviato")


if __name__ == "__main__":
    main(sys.argv[1:] == ["manda"])
