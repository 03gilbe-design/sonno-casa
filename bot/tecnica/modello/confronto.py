"""
1) ESC-50: 40 russare + 40 respiro etichettati da persone -> quanti russare riconosce, quanti respiri scambia.
2) le SUE clip giudicate (❌): un'immagine a clip = spettrogramma + le due curve "quanto e' russare" + la soglia.
   cd ~/confronto && python confronto.py      (legge esc50/, sue/*.m4a, giudizi da ~/sonno_bot/giudizi.csv)
Scrive: riassunto.png, clip_*.png, risultati.txt
"""
import csv, glob, os, subprocess
import numpy as np, onnxruntime as ort

H = os.path.expanduser("~")
SOGLIA = 0.2  # quella usata oggi per YAMNet (sonno_tel.py): stessa per tutti e due, confronto onesto
Y = ort.InferenceSession(f"{H}/yamnet.onnx", providers=["CPUExecutionProvider"])
P = ort.InferenceSession(f"{H}/confronto/cnn14.onnx", providers=["CPUExecutionProvider"])
Y_RUSSA = next(i for i, r in enumerate(csv.DictReader(open(f"{H}/yamnet_class_map.csv"))) if r["display_name"] == "Snoring")
P_RUSSA = next(i for i, r in enumerate(csv.DictReader(open("class_labels_indices.csv"))) if r["display_name"] == "Snoring")


def audio(path, sr):
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(pcm, np.float32)


def curva_yamnet(path):
    """Un valore ogni 0,48 s."""
    w = audio(path, 16000)
    return Y.run(None, {"waveform": w})[0][:, Y_RUSSA], 0.48


def curva_panns(path, fin=2.0, passo=0.5):
    """Finestre da 2 s ogni 0,5 s (PANNs da' un valore per finestra, non per frame)."""
    w = audio(path, 32000)
    n, p = int(fin * 32000), int(passo * 32000)
    if len(w) < n:
        w = np.pad(w, (0, n - len(w)))
    F = np.stack([w[i:i + n] for i in range(0, len(w) - n + 1, p)])
    out = np.concatenate([P.run(None, {"waveform": F[i:i + 1]})[0] for i in range(len(F))])  # 1 alla volta: A21s 2,7 GB, a 8 Android lo uccideva
    return out[:, P_RUSSA], passo


def esc50():
    ris = {}
    for cat in ("snoring", "breathing"):
        fs = sorted(glob.glob(f"esc50/{cat}/*.wav"))
        ris[cat] = []
        for f in fs:
            ris[cat].append((curva_yamnet(f)[0].max(), curva_panns(f)[0].max()))
            print(cat, len(ris[cat]), f"{ris[cat][-1][0]:.2f} {ris[cat][-1][1]:.2f}", flush=True)
    return ris


def disegna_riassunto(ris, out):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 26, "font.family": "DejaVu Sans"})
    fig, ax = plt.subplots(figsize=(10, 10), dpi=100)
    n = len(ris["snoring"])
    for j, (nome, col) in enumerate((("YAMNet (oggi)", "#d9822b"), ("PANNs", "#2b6cb0"))):
        si = sum(x[j] > SOGLIA for x in ris["snoring"])
        no = sum(x[j] > SOGLIA for x in ris["breathing"])
        ax.barh(1 - j * 0.4, si, 0.3, color=col); ax.text(si + 0.5, 1 - j * 0.4, f"{nome}: {si}/{n}", va="center")
        ax.barh(-0.6 - j * 0.4, no, 0.3, color=col); ax.text(no + 0.5, -0.6 - j * 0.4, f"{nome}: {no}/{n}", va="center")
    ax.text(0, 1.45, "russare vero riconosciuto (meglio alto)", weight="bold")
    ax.text(0, -0.15, "respiro scambiato per russare (meglio basso)", weight="bold")
    ax.set_xlim(0, n * 1.9); ax.set_ylim(-1.3, 1.8); ax.axis("off")
    fig.suptitle(f"Prova su 80 clip etichettate da persone (ESC-50), soglia {SOGLIA}", fontsize=24)
    fig.savefig(out); plt.close(fig)


def disegna_clip(path, titolo, out):
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 24, "font.family": "DejaVu Sans"})
    w = audio(path, 16000)
    y, hy = curva_yamnet(path)
    p, hp = curva_panns(path)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(10, 10), dpi=100, sharex=True, gridspec_kw={"height_ratios": [1, 1]})
    a1.specgram(w, NFFT=512, Fs=16000, noverlap=256, cmap="magma"); a1.set_ylim(0, 4000)
    a1.set_ylabel("Hz"); a1.set_title(titolo, fontsize=24)
    a2.plot(np.arange(len(y)) * hy, y, lw=5, color="#d9822b", label="YAMNet (oggi)")
    a2.plot(np.arange(len(p)) * hp + 1.0, p, lw=5, color="#2b6cb0", label="PANNs")  # +1 s: centro della finestra
    a2.axhline(SOGLIA, lw=3, ls="--", color="#555"); a2.text(0.2, SOGLIA + 0.03, "soglia", color="#555")
    a2.set_ylim(0, 1); a2.set_ylabel("quanto e' russare"); a2.set_xlabel("secondi"); a2.legend(loc="upper right")
    fig.tight_layout(); fig.savefig(out); plt.close(fig)
    return y.max(), p.max()


if __name__ == "__main__":
    righe = []
    ris = esc50()
    disegna_riassunto(ris, "riassunto.png")
    for cat, xs in ris.items():
        righe.append(f"{cat}: YAMNet sopra soglia {sum(x[0] > SOGLIA for x in xs)}/{len(xs)}, "
                     f"PANNs {sum(x[1] > SOGLIA for x in xs)}/{len(xs)}")
    giud = {r["clip"]: r["giusto"] for r in csv.DictReader(open(f"{H}/sonno_bot/giudizi.csv"))}
    for f in sorted(glob.glob("sue/*.m4a")):
        b = os.path.basename(f)
        ora = f"{b[-8:-6]}:{b[-6:-4]}"
        tu = {"1": "tu: SI' russavo", "0": "tu: NO"}.get(giud.get(b), "tu: -")
        ym, pm = disegna_clip(f, f"{b[12:14]}/{b[10:12]} {ora} · {tu}", f"clip_{b[:-4]}.png")
        righe.append(f"{b}: {tu} · YAMNet max {ym:.2f} · PANNs max {pm:.2f}")
    open("risultati.txt", "w").write("\n".join(righe) + "\n")
    print("\n".join(righe))
