"""
due punti bianchi vagano; dal nulla compare un triangolo rosso; il triangolo suona -> ogni punto ha un cerchio
(centrato su di se', raggio = distanza) che passa SEMPRE per il triangolo: i punti possono ancora muoversi (i cerchi
si incrociano, si separano) ma a distanza fissa. Poi suona un punto: nasce un cerchio e l'altro ci si INCASTRA piano;
poi suona il secondo (conferma); un riferimento ferma la rotazione.
   python animazione2.py [manda]  -> C:/sonno_audio/array/grafici/6_incastro.mp4 (1080x1350, 30 fps)
"""
import os, sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, FFMpegWriter

OUT = "C:/sonno_audio/array/grafici/6_incastro.mp4"
BG, ROSSO, BIANCO = "#141416", "#e63946", "#d4d4d8"
FPS = 60
R1, A1, R2, A2 = 62.0, 0.35, 46.0, 1.75          # posizioni vere dei due punti rispetto al triangolo (cm, rad)
D12 = float(np.hypot(R1 * np.cos(A1) - R2 * np.cos(A2), R1 * np.sin(A1) - R2 * np.sin(A2)))
T = dict(vaga=2.5, appare=1.0, suona=1.0, liberi=5.0, suona1=1.0, incastro=2.5, suona2=1.5, rif=2.5, fine=3.0)
INIZIO = {}; _t = 0
for k, v in T.items():
    INIZIO[k] = _t; _t += v
DUR = _t


def ease(x):
    x = np.clip(x, 0, 1); return 0.5 - 0.5 * np.cos(np.pi * x)


def fase(t, k):
    return (t - INIZIO[k]) / T[k]


def pol(r, a):
    return np.array([r * np.cos(a), r * np.sin(a)])


def angoli_liberi(t):
    """Angoli dei due punti attorno al triangolo: moto lento e morbido (somma di sinusoidi)."""
    return (A1 + 1.1 * np.sin(0.8 * t) + 0.45 * np.sin(1.9 * t + 1.0),
            A2 + 0.9 * np.sin(1.0 * t + 2.0) + 0.5 * np.sin(1.6 * t))


def stato(t):
    """Posizioni dei due punti, raggi dei cerchi visibili, alpha del triangolo, impulsi."""
    s = {"tri": ease(fase(t, "appare")), "cerchi": ease(fase(t, "suona")), "c12": 0.0, "c21": 0.0, "imp": []}
    if 0 < fase(t, "suona") <= 1:
        s["imp"].append(((0, 0), fase(t, "suona") * 90, ROSSO))
    # la distanza dal triangolo vaga e poi scivola dolcemente su quella vera): niente salti fra le fasi
    e = ease(fase(t, "suona"))
    rw1 = R1 + 28 * np.sin(0.7 * t + 0.5) + 10 * np.sin(1.3 * t)
    rw2 = R2 + 22 * np.sin(0.6 * t + 2.2) + 9 * np.sin(1.1 * t + 1)
    r1, r2 = (1 - e) * rw1 + e * R1, (1 - e) * rw2 + e * R2
    a1, a2 = angoli_liberi(t)
    # incastro: dopo che suona il punto 1, il punto 2 va verso l'angolo che rispetta la distanza D12 (stessa forma vera)
    e_inc = ease(fase(t, "incastro"))
    a2 = (1 - e_inc) * a2 + e_inc * (a1 + (A2 - A1))
    # riferimento: tutto ruota in blocco verso l'orientamento vero
    e_rif = ease(fase(t, "rif"))
    a1r = (1 - e_rif) * a1 + e_rif * A1
    a2 = (1 - e_rif) * a2 + e_rif * A2 if e_inc >= 1 else a2
    a1 = a1r
    s["p1"], s["p2"] = pol(r1, a1), pol(r2, a2)
    # gli altri due ASCOLTANO: ognuno ha un cerchio centrato su di se', raggio = distanza da chi suona
    o = np.zeros(2)
    if t < INIZIO["suona1"]:
        s["E"], ascolto, t_em = o, [("p1", s["p1"]), ("p2", s["p2"])], INIZIO["suona"]
    elif t < INIZIO["suona2"]:
        g = ease(fase(t, "suona1") * 2.5)
        s["E"], ascolto, t_em = (1 - g) * o + g * s["p1"], [("o", o), ("p2", s["p2"])], INIZIO["suona1"]
    else:
        g = ease(fase(t, "suona2") * 2.5)
        s["E"], ascolto, t_em = (1 - g) * s["p1"] + g * s["p2"], [("o", o), ("p1", s["p1"])], INIZIO["suona2"]
    s["emette"] = "o" if t < INIZIO["suona1"] else ("p1" if t < INIZIO["suona2"] else "p2")
    s["origine"] = ease(fase(t, "suona1") * 2)  # dove c'era il triangolo resta un puntino
    fresco = ease((t - t_em - 0.35) / 0.6)  # i cerchi nascono quando l'onda arriva
    s["ascolto"] = [(c, float(np.linalg.norm(c - s["E"])), fresco * s["cerchi"]) for _, c in ascolto]
    for k in ("suona1", "suona2"):
        if 0 < fase(t, k) <= 1:
            s["imp"].append((tuple(s["E"]), fase(t, k) * 80, ROSSO))
    return s


TESTI = [("vaga", "due punti, posizione ignota"), ("appare", "compare una sorgente"),
         ("suona", "suona: ognuno ora sa la SUA distanza"), ("liberi", "si muovono ancora, ma il cerchio tocca sempre il triangolo"),
         ("suona1", "ora suona lui: gli altri due ascoltano, nuovi cerchi"), ("incastro", "l'altro si incastra"),
         ("suona2", "suona il terzo: altri due cerchi, conferma"), ("rif", "un riferimento ferma la rotazione"), ("fine", "posizioni trovate")]


def main(manda=False):
    fig = plt.figure(figsize=(10.8, 13.5), dpi=100, facecolor=BG)
    ax = fig.add_axes([0, 0.1, 1, 0.8]); ax.set_facecolor(BG); ax.set_xlim(-75, 145); ax.set_ylim(-95, 125)  # quadrato: cerchi interi
    ax.set_aspect("equal"); ax.axis("off")
    testo = fig.text(0.5, 0.93, "", ha="center", color=BIANCO, fontsize=26)
    ALONI = ((7.0, 0.04), (4.0, 0.08), (2.2, 0.16), (1.0, 1.0))

    def punto_luce(col, s0, marker="o", z=7):
        return [ax.scatter([0], [0], s=s0 * k, c=col, marker=marker, linewidths=0, alpha=a, zorder=z) for k, a in ALONI]

    def sposta(strati, p, alpha=1.0):
        for (k, a), sc in zip(ALONI, strati):
            sc.set_offsets([p]); sc.set_alpha(a * alpha)

    tri = punto_luce(ROSSO, 260, "^", 6)  # piu' piccolo, sempre uguale
    p0, p1, p2 = punto_luce(BIANCO, 170), punto_luce(BIANCO, 170), punto_luce(BIANCO, 170)

    def cerchio_luce(r, ls="-"):
        return [ax.add_patch(plt.Circle((0, 0), r, fill=False, color=BIANCO, lw=w, ls=ls, alpha=0)) for w in (9, 4.5, 1.6)]

    def muovi_cerchio(strati, ctr, alpha, r=None, col=None):
        for w_a, c in zip((0.07, 0.15, 1.0), strati):
            c.center = ctr; c.set_alpha(w_a * alpha)
            if r is not None:
                c.set_radius(r)
            if col is not None:
                c.set_edgecolor(col)
    c1, c2 = cerchio_luce(R1), cerchio_luce(R2)
    impulsi = [cerchio_luce(0) for _ in range(2)]
    lati = [[ax.plot([], [], color=BIANCO, lw=w, alpha=0, solid_capstyle="round", zorder=4)[0] for w in (8, 3.5, 1.4)]
            for _ in range(3)]
    etich = [ax.text(0, 0, "", color=BIANCO, fontsize=17, ha="center", va="center", alpha=0, zorder=8) for _ in range(3)]
    n = int(DUR * FPS)

    def frame(i):
        t = i / FPS; s = stato(t)
        f = ease(fase(t, "fine") * 2)  # alla fine si accendono i lati del triangolo
        sposta(tri, (0, 0), 0)
        turni = (("o", "suona", "suona1"), ("p1", "suona1", "suona2"), ("p2", "suona2", "fine"))
        for nome, strati, pos in (("o", p0, (0, 0)), ("p1", p1, s["p1"]), ("p2", p2, s["p2"])):
            _, da, a = next(x for x in turni if x[0] == nome)
            rosso = min(ease((t - INIZIO[da]) / 0.3), ease((INIZIO[a] - t) / 0.3))
            col = (1 - rosso) * np.array(matplotlib.colors.to_rgb(BIANCO)) + rosso * np.array(matplotlib.colors.to_rgb(ROSSO))
            for sc in strati:
                sc.set_color([col])
            sposta(strati, pos, s["tri"] if nome == "o" else 1)
        vertici = [np.zeros(2), s["p1"], s["p2"]]
        for (a, c), strati, et in zip(((0, 1), (1, 2), (0, 2)), lati, etich):
            for w_a, ln in zip((0.08, 0.2, 0.9), strati):
                ln.set_data(*zip(vertici[a], vertici[c])); ln.set_alpha(w_a * f)
            m = (vertici[a] + vertici[c]) / 2; et.set_position(m + [0, 6]); et.set_alpha(f)
            et.set_text(f"{np.linalg.norm(vertici[a] - vertici[c]):.0f} cm")
        for cer, (ctr, r, a) in zip((c1, c2), s["ascolto"]):
            muovi_cerchio(cer, tuple(ctr), 0.65 * a, r=r)
        for j, im in enumerate(impulsi):
            if j < len(s["imp"]):
                ctr, r, col = s["imp"][j]; muovi_cerchio(im, ctr, max(0, 1 - r / 90), r=r, col=col)
            else:
                muovi_cerchio(im, (0, 0), 0)
        k = max((kk for kk, _ in TESTI if t >= INIZIO[kk]), key=lambda kk: INIZIO[kk])
        testo.set_text(dict(TESTI)[k]); testo.set_alpha(min(1, (t - INIZIO[k]) / 0.4))
        return []

    anim = FuncAnimation(fig, frame, frames=n, interval=1000 / FPS)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    anim.save(OUT, writer=FFMpegWriter(fps=FPS, bitrate=6000, extra_args=["-pix_fmt", "yuv420p"]), savefig_kwargs={"facecolor": BG})
    for k in ("liberi", "incastro", "fine"):
        frame(int((INIZIO[k] + T[k] * 0.6) * FPS)); fig.savefig(OUT.replace(".mp4", f"_{k}.png"), facecolor=BG)
    print("salvato", OUT, f"{DUR:.1f} s")
    if manda:
        sys.path.insert(0, "C:/sonno_bot")
        import manda_valutazione as m
        m.file("sendAnimation", "animation", OUT, "🔺 <b>Cerchi che si incastrano</b> (versione tua, fluida): il suono dà la distanza, "
               "i cerchi toccano sempre il triangolo, poi si incastrano uno nell'altro")
        print("inviato")


if __name__ == "__main__":
    main(sys.argv[1:] == ["manda"])
