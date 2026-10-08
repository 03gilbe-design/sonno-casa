"""Triangolo dei dispositivi dalle distanze misurate + MAPPA DELLA PRECISIONE (GDOP) di un suono sconosciuto
(es. russare) localizzato con le differenze di arrivo (TDOA) fra i 3 microfoni. Vista dall'alto, 2D.
   python mappa_precisione.py [manda]
Errore in un punto: sigma * sqrt(traccia((J^T J)^-1)), J = gradienti delle differenze di distanza rispetto al PC.
ponytail: 2D (tutti circa alla stessa altezza); lo specchio (y -> -y) non si decide dalle sole distanze.
"""
import sys
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "C:/sonno_audio/array/grafici/mappa_precisione.png"
BG, ROSSO, BIANCO, GRIGIO = "#141416", "#e63946", "#d4d4d8", "#3a3a40"
D = {("PC", "A56"): 1.063, ("A56", "A21s"): 2.855, ("PC", "A21s"): 3.724}
SIGMA = 0.01  # m: precisione di una differenza di distanza (1 cm)


def posizioni():
    a, b, c = D["PC", "A56"], D["A56", "A21s"], D["PC", "A21s"]
    x = (a ** 2 - b ** 2 + c ** 2) / (2 * c)
    return {"PC": np.array([0.0, 0.0]), "A21s": np.array([c, 0.0]), "A56": np.array([x, np.sqrt(max(a ** 2 - x ** 2, 0))])}


def errore(P, p):
    """errore di posizione (m) di un suono in p con TDOA rispetto al PC."""
    u = {k: (p - v) / (np.linalg.norm(p - v) + 1e-9) for k, v in P.items()}
    J = np.array([u["A56"] - u["PC"], u["A21s"] - u["PC"]])
    try:
        return SIGMA * np.sqrt(np.trace(np.linalg.inv(J.T @ J)))
    except np.linalg.LinAlgError:
        return np.inf


def main(manda=False):
    P = posizioni()
    xs, ys = np.linspace(-1.0, 4.7, 240), np.linspace(-2.2, 2.6, 200)
    E = np.array([[errore(P, np.array([x, y])) for x in xs] for y in ys]) * 100
    fig, ax = plt.subplots(figsize=(8, 10), facecolor=BG); ax.set_facecolor(BG)
    im = ax.imshow(np.clip(E, 0, 30), extent=[xs[0], xs[-1], ys[0], ys[-1]], origin="lower", cmap="magma_r", vmin=0, vmax=30)
    cs = ax.contour(xs, ys, E, levels=[2, 5, 10], colors=BIANCO, linewidths=0.8, alpha=0.6)
    ax.clabel(cs, fmt="%d cm", fontsize=8, colors=BIANCO)
    nomi = list(P)
    for i in range(3):
        for j in range(i + 1, 3):
            a, b2 = P[nomi[i]], P[nomi[j]]
            ax.plot(*zip(a, b2), color=ROSSO, lw=1.5, alpha=0.8)
            k = D.get((nomi[i], nomi[j])) or D.get((nomi[j], nomi[i]))
            ax.text(*(a + b2) / 2 + [0, 0.08], f"{k:.2f} m", color=ROSSO, ha="center", fontsize=10)
    for k, v in P.items():
        ax.plot(*v, "o", color=BIANCO, ms=10); ax.text(v[0], v[1] - 0.22, k, color=BIANCO, ha="center", fontsize=12)
    ax.set_aspect("equal"); ax.tick_params(colors=BIANCO); [s.set_visible(False) for s in ax.spines.values()]
    ax.set_xlabel("m (asse PC -> A21s)", color=BIANCO); ax.set_ylabel("m", color=BIANCO)
    cb = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02); cb.set_label("errore di posizione di un suono (cm)", color=BIANCO)
    cb.ax.tick_params(colors=BIANCO)
    ax.set_title("Dove localizzo bene un suono (russare)\nchiaro = preciso, scuro = incerto", color=BIANCO, fontsize=13)
    fig.savefig(OUT, facecolor=BG, dpi=120, bbox_inches="tight")
    print("salvato", OUT, {k: np.round(v, 2).tolist() for k, v in P.items()})
    for nome, p in (("meta PC-A21s", (P["PC"] + P["A21s"]) / 2), ("vicino A21s", P["A21s"] + [-0.3, 0.3])):
        print(nome, f"errore {errore(P, p) * 100:.1f} cm")
    if manda:
        sys.path.insert(0, "C:/sonno_bot")
        import manda_valutazione as m
        m.file("sendPhoto", "photo", OUT, "🗺️ <b>Triangolo misurato</b> (ping-pong, errore &lt;1 cm) e <b>mappa della precisione</b>: "
               "per ogni punto, con quanti cm di errore localizzo un suono (es. russare). Chiaro = preciso, scuro = incerto (fuori dal triangolo e dietro ai dispositivi).")
        print("inviato")


if __name__ == "__main__":
    main(sys.argv[1:] == ["manda"])
