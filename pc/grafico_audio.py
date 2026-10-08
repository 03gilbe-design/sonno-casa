# Grafico di un pezzo audio: spettrogramma + cosa ha riconosciuto YAMNet (russamento, voce, rumori esterni) nel tempo.
#   python grafico_audio.py file.m4a out.png
import re, sys, csv
from datetime import datetime, timedelta
import numpy as np, onnxruntime as ort, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
sys.path.insert(0, r"C:\sonno_tex")
from sonno_audio import load, MODEL

src, out = sys.argv[1], sys.argv[2]
w = load(src)
sc = ort.InferenceSession(MODEL).run(None, {"waveform": w})[0]
nomi = [r["display_name"] for r in csv.DictReader(open(r"C:\sonno_tex\yamnet\yamnet_class_map.csv"))]
ext = [i for i, n in enumerate(nomi) if i > 0 and re.search(
    r"vehicle|^car|traffic|engine|television|radio|music|dog|bird|rain|wind|fan$|mechanical|door|alarm", n, re.I)]
t0 = datetime.strptime(src.replace("\\", "/").split("/")[-1][:15], "%Y%m%d_%H%M%S") if src[-19].isdigit() else datetime(2026, 1, 1)
tf = [t0 + timedelta(seconds=i * 0.48) for i in range(len(sc))]
righe = [("Russamento", sc[:, 38], "#c0392b"), ("Respiro", sc[:, 36], "#e67e22"),
         ("Voce", sc[:, 0], "#2980b9"), ("Tosse", sc[:, 42], "#8e44ad"), ("Esterni", sc[:, ext].max(1), "#7f8c8d")]

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 13})
fig, ax = plt.subplots(len(righe) + 1, 1, figsize=(13, 11), sharex=True,
                       gridspec_kw={"height_ratios": [3] + [1] * len(righe)})
t_end = mdates.date2num(t0 + timedelta(seconds=len(w) / 16000))
ax[0].specgram(w + 1e-7, NFFT=512, Fs=16000, noverlap=256, cmap="magma", xextent=(mdates.date2num(t0), t_end))
ax[0].set_ylim(0, 4000); ax[0].set_ylabel("frequenza (Hz)")
ax[0].set_title(sys.argv[3] if len(sys.argv) > 3 else "Cosa sente il telefono", loc="left", fontsize=16,
                fontweight="bold")
for a, (nome, y, col) in zip(ax[1:], righe):
    a.fill_between(tf, y, color=col, alpha=0.85, step="mid")
    a.set_ylim(0, 1); a.set_yticks([])
    a.text(0.005, 0.75, f"{nome}  (max {y.max():.2f})", transform=a.transAxes, fontsize=13, fontweight="bold", color=col,
           bbox=dict(facecolor="white", edgecolor="none", pad=1.5))
    a.spines[["top", "right", "left"]].set_visible(False)
ax[-1].xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
ax[-1].set_xlabel(f"ora — {t0:%d/%m/%Y}")
fig.tight_layout()
fig.savefig(out, dpi=110)
print(out)
