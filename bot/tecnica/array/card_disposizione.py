"""
Stile concept (carta e denim), quadrata come tutte le foto del bot (grafici.MAX_ALTEZZA). In alto la vista dall'alto,
sotto la vista 3D inclinata. Onestà (ux/ONESTA.md): ogni telefono ha il cerchio d'errore e "circa ±N cm".
   python card_disposizione.py [cartella]   -> ultima calibra_* VALIDA se non la dai
Punti: pc_tre_punti (PC = cassa SX, cassa DX, microfono). Errore: se la cartella ha vero.json {"tuo telefono": [x, y],
Misura NON valida (residuo > 30 cm, es. calibra_3: 76 m) = scartata: meglio nessuna mappa che una mappa falsa.
"""
import contextlib, glob, io, json, os, sys
import numpy as np
QUI = os.path.dirname(os.path.abspath(__file__))
sys.path[:0] = [os.path.join(QUI, "..", "..", "concept"), QUI]
import grafici as G
import pc_tre_punti as PC3
import turni as T
from matplotlib.patches import Circle, Rectangle
import mpl_toolkits.mplot3d  # noqa: F401  (registra la proiezione 3d)

P = G.P
OUT = r"C:\sonno_audio\array\grafici\disposizione_card.png"
PC_W, PC_D = 0.322, 0.218
ERR_MIN = {"tuo telefono": 0.17, "A21s": 0.37}
VALIDA_M = 0.30


def misura(nome):
    """{telefono: (x, y)}, residuo massimo (m). pc_tre_punti stampa: zitto."""
    with contextlib.redirect_stdout(io.StringIO()):
        a, c, r = PC3.main(nome)
    return {"tuo telefono": tuple(a), "A21s": tuple(c)}, float(np.max(np.abs(r.fun)))


def ultima_valida():
    for d in sorted(glob.glob(os.path.join(T.DISP, "calibra_*")), key=os.path.getmtime, reverse=True):
        try:
            pos, res = misura(os.path.basename(d))
        except Exception:
            continue
        if res < VALIDA_M:
            return os.path.basename(d), pos, res
    return None, None, None


def card(nome=None, out=OUT):
    if nome:
        pos, res = misura(nome)
        if res >= VALIDA_M:
            raise SystemExit(f"{nome}: misura non valida (residuo {res * 100:.0f} cm)")
    else:
        nome, pos, res = ultima_valida()
        if not nome:
            raise SystemExit("nessuna calibrazione valida")
    f_vero = os.path.join(T.DISP, nome, "vero.json")
    vero = json.load(open(f_vero, encoding="utf-8")) if os.path.exists(f_vero) else {}
    if nome == "calibra_1" and not vero:  # la L: posizioni vere dai quaderni (scena_L.py)
        import scena_L
        vero = scena_L.VERO
    err = {n: (np.hypot(p[0] - vero[n][0], p[1] - vero[n][1]) if n in vero else max(ERR_MIN[n], 3 * res))
           for n, p in pos.items()}
    json.dump({n: round(float(e), 3) for n, e in err.items()},  # per i bottoni del bot (📡 Dispositivi)
              open(os.path.splitext(out)[0] + "_err.json", "w", encoding="utf-8"))
    fig = G._fig(5.4)  # quadrata 1080x1080
    fig.text(0.06, 0.93, "Telefoni", family=G.SERIF, fontsize=26, va="top")

    ax = fig.add_axes([0.03, 0.47, 0.94, 0.37]); ax.set_aspect("equal"); ax.axis("off")
    ax.add_patch(Rectangle((-PC_W / 2, 0), PC_W, PC_D, color=P["inchiostro"], alpha=0.85))
    ax.text(0, PC_D + 0.03, "PC", ha="center", va="bottom", fontsize=13, color=P["inchiostro"])
    for n, (x, y) in pos.items():
        ax.add_patch(Circle((x, y), err[n], color=P["sonno_chiaro"], alpha=0.45, lw=0))
        ax.plot(x, y, "o", color=P["sonno"], ms=10)
        if n in vero:
            ax.plot(*vero[n], "o", mfc="none", mec=P["inchiostro"], ms=13, mew=2)
            ax.plot([x, vero[n][0]], [y, vero[n][1]], ls=":", color=P["grigio"], lw=1.5)
        ax.text(x, y - err[n] - 0.03, f"{n} ±{err[n] * 100:.0f} cm",
                ha="center", va="top", fontsize=12, color=P["sonno"], weight="semibold")
    xs = [p[0] for p in pos.values()] + [-PC_W / 2, PC_W / 2]
    ys = [p[1] for p in pos.values()] + [0, PC_D]
    m = max(err.values()) + 0.12
    ax.set_xlim(min(xs) - m, max(xs) + m); ax.set_ylim(min(ys) - m - 0.1, max(ys) + m)

    b3 = fig.add_axes([-0.1, 0.06, 1.2, 0.46], projection="3d")
    b3.set_facecolor(P["carta"]); b3.set_axis_off(); b3.view_init(elev=28, azim=-62)
    X = [-PC_W / 2, PC_W / 2, PC_W / 2, -PC_W / 2, -PC_W / 2]
    Y = [0, 0, PC_D, PC_D, 0]
    b3.plot(X, Y, [0] * 5, color=P["inchiostro"], lw=2)
    b3.plot([-PC_W / 2, PC_W / 2, PC_W / 2, -PC_W / 2, -PC_W / 2], [PC_D, PC_D, PC_D + .04, PC_D + .04, PC_D],
            [0, 0, .21, .21, 0], color=P["inchiostro"], lw=2)  # schermo aperto
    b3.scatter(*PC3.MIC, color=P["inchiostro"], marker="^", s=40)
    for i, (n, (x, y)) in enumerate(pos.items()):
        t = np.linspace(0, 2 * np.pi, 60)
        b3.plot(x + err[n] * np.cos(t), y + err[n] * np.sin(t), 0, color=P["sonno_chiaro"], lw=2)
        b3.plot([x, x], [y, y], [0, 0.06], color=P["sonno"], lw=2)
        b3.scatter(x, y, 0.06, color=P["sonno"], s=40)
    lim = max(max(abs(v) for v in xs + ys) + m, 0.5)
    b3.set_xlim(min(xs) - m, max(xs) + m); b3.set_ylim(min(ys) - m, max(ys) + m); b3.set_zlim(0, 0.4)
    b3.set_box_aspect((max(xs) - min(xs) + 2 * m, max(ys) - min(ys) + 2 * m, 0.4), zoom=1.25)

    peggiore = max(err.values())
    liv = "forse" if peggiore > 0.2 else "quasi sicuro" if peggiore > 0.05 else "sicuro"
    motivo = "eco della cassa del PC" if nome == "calibra_1" else "posizione vera non misurata" if not vero else "misura"
    fig.text(0.06, 0.045, f"{liv} · {motivo}", fontsize=16, weight="semibold",
             color=P["sveglio"] if liv == "forse" else P["grigio"])
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, facecolor=P["carta"]); G.plt.close(fig)
    return out, nome


if __name__ == "__main__":
    o, nome = card(sys.argv[1] if len(sys.argv) > 1 else None)
    from PIL import Image
    w, h = Image.open(o).size
    assert h <= w * G.MAX_ALTEZZA + 1, (w, h)
    try:
        card("calibra_3", os.devnull)
        raise AssertionError("calibra_3 (76 m) doveva essere scartata")
    except SystemExit:
        pass
    print(o, nome, w, h)
