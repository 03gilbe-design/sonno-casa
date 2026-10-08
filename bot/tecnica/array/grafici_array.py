"""
   python grafici_array.py        -> 4 PNG 1080x1350 (4:5) in C:/sonno_audio/array/grafici/
   python grafici_array.py manda  -> li genera e li manda su @IlTuoBot
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import beepbeep as b  # prima di scipy
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import hilbert, find_peaks
import scena as sc

OUT = "C:/sonno_audio/array/grafici"
FONDO, TESTO, ACC1, ACC2, ACC3 = "#101820", "#E8E6E3", "#F2AA4C", "#4CC9F0", "#3E7C6B"
plt.rcParams.update({"figure.facecolor": FONDO, "axes.facecolor": FONDO, "text.color": TESTO, "axes.labelcolor": TESTO,
                     "xtick.color": TESTO, "ytick.color": TESTO, "axes.edgecolor": "#445", "font.size": 13})


def fig45():
    return plt.figure(figsize=(10.8, 13.5), dpi=100)


def scena_3d():
    s = sc.scena("stanza", "stanza"); f = fig45()
    ax = f.add_axes([0.0, 0.08, 1.0, 0.8], projection="3d"); ax.set_facecolor(FONDO)  # niente vuoto intorno
    for a in (ax.xaxis, ax.yaxis, ax.zaxis):
        a.set_pane_color((0.06, 0.09, 0.12, 1)); a._axinfo["grid"]["color"] = (0.3, 0.33, 0.38, 1)
    col = {"PC": ACC1, "A56": ACC2, "A21s": ACC3}
    ax.plot([-20, 110], [0, 0], [0, 0], color="#888", lw=4); ax.text(100, -1, 0.5, "muro", color="#aaa")

    def scatola(x0, x1, y0, y1, z0, z1, c):
        for zz in (z0, z1):
            ax.plot([x0, x1, x1, x0, x0], [y0, y0, y1, y1, y0], [zz] * 5, color=c, lw=1.2, alpha=0.8)
        for xx, yy in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            ax.plot([xx, xx], [yy, yy], [z0, z1], color=c, lw=1.2, alpha=0.8)
    import geometria as g
    t = sc.TELO
    scatola(-g.PC_W / 2, g.PC_W / 2, 0, g.PC_D, t, t + g.PC_H, ACC1)           # base del PC
    # schermo: cerniera CONTRO IL MURO (y=0), bordo alto dove stanno i mic (stesse coordinate di scena.py)
    ytop = g.PC_D / 2 - g.alto[1]; ztop = t + g.alto[2]
    ax.plot([-g.PC_W / 2, g.PC_W / 2, g.PC_W / 2, -g.PC_W / 2, -g.PC_W / 2], [0, 0, ytop, ytop, 0],
            [t + g.PC_H, t + g.PC_H, ztop, ztop, t + g.PC_H], color=ACC1, lw=1.2)
    x = g.PC_W / 2 + sc.A4
    for nome in ("A56", "A21s"):
        scatola(x, x + sc.LARGO[nome], 0, sc.LUNGO[nome], t, t + sc.SPESSO[nome], col[nome]); x += sc.LARGO[nome] + sc.A4
    for d, p in s.items():
        for tipo, q in p.items():
            ax.scatter(*q, s=180 if tipo == "bocca" else 90, c=col[d], marker="o" if tipo == "bocca" else "^",
                       edgecolors="white", linewidths=0.8)
        ax.text(*(p["bocca"] + [0, 3, 3]), d, color=col[d], fontsize=15, weight="bold")
    mis = {("PC", "A56"): 0.312, ("A56", "A21s"): 0.405}  # prova delle 20:44 (telo, verifica)
    for (a, c), m in mis.items():
        pa, pc_ = s[a]["bocca"], s[c]["bocca"]
        ax.plot(*zip(pa, pc_), color="white", lw=1.5, ls="--")
        ax.text(*((pa + pc_) / 2 + [0, 6, 2]), f"{m * 100:.1f} cm", color="white", fontsize=14)
    ax.set_xlabel("lungo il muro (cm)"); ax.set_ylabel("verso la stanza (cm)"); ax.set_zlabel("altezza (cm)")
    ax.view_init(elev=26, azim=108)
    ax.set_box_aspect((3, 1.2, 0.8), zoom=1.08); ax.set_xlim(-22, 112); ax.set_ylim(-5, 25); ax.set_zlim(0, 25)
    f.suptitle("La scena in 3D\n● cassa   ▲ microfono   -- distanza misurata col suono", fontsize=20, color=TESTO)
    return f


def pettine():
    z = np.load("C:/sonno_audio/array/mappa_telo.npz"); ir = z["A21s__A56__ir"]; pre = int(0.005 * b.SR)
    e = np.abs(hilbert(ir)); d = pre + int(np.argmax(e[pre:pre + 48])); q = d + 24 + int(np.argmax(e[d + 24:d + 144]))
    dt = (q - d) / b.SR
    f = fig45(); a1, a2 = f.subplots(2, 1, gridspec_kw={"height_ratios": [1, 1.4]})
    t = (np.arange(len(ir)) - d) / b.SR * 1000
    a1.plot(t, 20 * np.log10(e / e.max() + 1e-6), color=ACC2); a1.set_xlim(-1, 8); a1.set_ylim(-40, 2)
    a1.axvline(0, color=ACC1, lw=2); a1.axvline(dt * 1000, color=ACC3, lw=2)
    a1.text(0.1, -5, "diretto", color=ACC1); a1.text(dt * 1000 + 0.1, -12, f"eco +{dt * 1000:.2f} ms\n= {dt * 343 * 100:.0f} cm in più",
                                                        color=ACC3)
    a1.set_xlabel("ms"); a1.set_ylabel("dB"); a1.set_title("Il suono dell'A21s arriva all'A56 due volte")
    F = np.abs(np.fft.rfft(ir[d - 24:d + int(0.004 * b.SR)], 8192)); fr = np.fft.rfftfreq(8192, 1 / b.SR)
    sel = (fr > 300) & (fr < 8000)
    a2.plot(fr[sel] / 1000, 20 * np.log10(F[sel] / F[sel].max()), color=ACC2, lw=2, label="misurato")
    for n in range(4):
        p = (2 * n + 1) / (2 * dt) / 1000
        if p < 8:
            a2.axvline(p, color=ACC1, ls="--", lw=2, label="buco previsto" if n == 0 else None)
    a2.set_xlabel("kHz"); a2.set_ylabel("dB"); a2.legend(facecolor=FONDO, labelcolor=TESTO)
    a2.set_title("Onde distruttive: la fisica prevede i buchi, i dati li trovano (1-7 %)")
    f.tight_layout(rect=(0, 0, 1, 0.97)); return f


def distanze():
    prove = [("tavolo\nPC-A56", 0.297, 0.010), ("tavolo\nA56-A21s", 0.413, 0.010), ("scambio\nA56-A21s", 0.379, 0.001),
             ("scambio\nA56-PC", 0.831, 0.002), ("telo\nA56-PC", 0.362, 0.005), ("telo\nA56-A21s", 0.464, 0.003),
             ("20:44\nA56-PC", 0.312, 0.005), ("20:44\nA56-A21s", 0.405, 0.002), ("PC al centro\nA56-PC", 0.426, 0.004)]
    f = fig45(); ax = f.add_subplot()
    y = np.arange(len(prove))[::-1]
    ax.barh(y, [p[1] * 100 for p in prove], xerr=[p[2] * 100 for p in prove], color=ACC2, ecolor=ACC1, capsize=6)
    for yi, p in zip(y, prove):
        ax.text(p[1] * 100 + 2, yi, f"{p[1] * 100:.1f} cm  ±{p[2] * 1000:.0f} mm", va="center", color=TESTO)
    ax.set_yticks(y, [p[0] for p in prove]); ax.set_xlabel("distanza misurata col suono (cm)"); ax.set_xlim(0, 110)
    ax.set_title("Tutte le distanze della serata\nbarra arancio = dispersione fra i bip (millimetri)", fontsize=18)
    f.tight_layout(); return f


def progressi():
    f = fig45(); a1, a2 = f.subplots(2, 1)
    tappe = ["inizio", "compensaz.", "telo", "verifica"]
    a1.plot(tappe, [284, 31, 85, 46], "o-", color=ACC1, lw=3, ms=10, label="telefono personale")
    a1.plot(tappe, [213, 142, 0, 33], "o-", color=ACC3, lw=3, ms=10, label="A21s")
    a1.set_ylabel("ms di sfasamento"); a1.set_title("Sincronia dei bip"); a1.legend(facecolor=FONDO, labelcolor=TESTO)
    a2.bar(["prima", "adesso"], [45, 22], color=[ACC1, ACC2]); a2.set_ylabel("secondi")
    a2.bar(["risultato\nprima", "risultato\nadesso"], [120, 10], color=[ACC1, ACC2])
    a2.set_title("Durata della prova e attesa del risultato")
    f.suptitle("Com'e' migliorata la serata", fontsize=20); f.tight_layout(rect=(0, 0, 1, 0.96)); return f


def tutti():
    os.makedirs(OUT, exist_ok=True); out = []
    for nome, fn in (("1_scena_3d", scena_3d), ("2_onde_distruttive", pettine), ("3_distanze", distanze),
                     ("4_progressi", progressi)):
        p = f"{OUT}/{nome}.png"; fig = fn(); fig.savefig(p, facecolor=FONDO); plt.close(fig); out.append(p)
    return out


if __name__ == "__main__":
    files = tutti(); print("\n".join(files))
    if sys.argv[1:] == ["manda"]:
        sys.path.insert(0, "C:/sonno_bot")
        import manda_valutazione as m
        didasc = ["🧊 <b>La scena in 3D</b>: casse ● e microfoni ▲, distanze misurate col suono",
                  "〰️ <b>Onde distruttive</b>: l'eco del muro cancella frequenze precise — previste e ritrovate nei dati",
                  "📏 <b>Tutte le distanze</b> della serata, al millimetro",
                  "📈 <b>Progressi</b>: sincronia bip 284 → 33 ms, prova 45 → 22 s"]
        for p, d in zip(files, didasc):
            m.file("sendPhoto", "photo", p, d)
        print("inviati")
