"""Allena il classificatore PERSONALE sui suoni di taratura (C:\\sonno_audio\\cal) e lo salva per il telefono.
   python cal_train.py   -> stampa accuratezza su dati mai visti + confronto con YAMNet, salva modello_personale.npz
"""
import os, sys
import numpy as np, onnxruntime as ort
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
sys.path.insert(0, r"C:\sonno_tex")
from sonno_audio import load, MODEL

CAL, OUT = r"C:\sonno_audio\cal", r"C:\sonno_tex\modello_personale.npz"
SR, HOP = 16000, 0.48
sess = ort.InferenceSession(MODEL)


def feat(path):
    w = load(path)
    sc, emb, _ = sess.run(None, {"waveform": w})
    n = int(HOP * SR)
    db = np.array([20 * np.log10(np.sqrt(np.mean(w[i * n:(i + 1) * n] ** 2)) + 1e-9) for i in range(len(emb))])
    return emb, sc, db


files = sorted(f for f in os.listdir(CAL) if f.endswith((".m4a", ".wav")))
data = {f: feat(os.path.join(CAL, f)) for f in files}
amb = [data[f][2] for f in files if f.startswith("ambiente")]
# frame piu' bassi del sottofondo+4dB = solo sottofondo: non li uso come esempi di russa/tosse/...
soglia = np.median(np.concatenate(amb)) + 4 if amb else -200.0
Xtr, ytr, Xte, yte, Ste = [], [], [], [], []
for f in files:
    lab = f.split("__")[0]
    emb, sc, db = data[f]
    keep = np.ones(len(emb), bool) if lab == "ambiente" else db > soglia
    cut = int(len(emb) * 0.7)  # primo 70% allena, ultimo 30% verifica (mai visto)
    for i in np.where(keep)[0]:
        (Xtr if i < cut else Xte).append(emb[i]); (ytr if i < cut else yte).append(lab)
        if i >= cut: Ste.append(sc[i])
    print(f"{f:45s} frame {len(emb):4d}  usati {keep.sum():4d}")
Xtr, Xte, ytr, yte, Ste = map(np.array, (Xtr, Xte, ytr, yte, Ste))
mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-6
clf = LogisticRegression(max_iter=3000, C=0.5, class_weight="balanced").fit((Xtr - mu) / sd, ytr)
pred = clf.predict((Xte - mu) / sd)
print("\n=== MODELLO PERSONALE su dati mai visti ===")
print(classification_report(yte, pred, digits=2, zero_division=0))
print("confusione (righe=vero, colonne=previsto):", list(clf.classes_))
print(confusion_matrix(yte, pred, labels=clf.classes_))
# confronto: YAMNet generico, solo russa si/no
vero = yte == "russa"
conf = {}
for nome, p in (("YAMNet (russa>0.2)", Ste[:, 38] > 0.2), ("personale", pred == "russa")):
    tp, fp = (p & vero).sum(), (p & ~vero).sum()
    conf[nome] = (tp - fp) / max(vero.sum(), 1)  # trovati meno falsi allarmi
    print(f"{nome:20s} russamento: trovati {tp}/{vero.sum()} ({tp / max(vero.sum(), 1):.0%}), falsi allarmi {fp}")
# mai installare un modello che non ha visto russamento nel test: il telefono smetterebbe di riconoscerlo
# ...e mai senza la classe "ambiente" (silenzio): di notte e' quasi tutto silenzio, lo chiamerebbe russa/respiro
MIGLIORA = ("ambiente" in set(ytr) and vero.sum() >= 5 and conf["personale"] > 0
            and conf["personale"] >= conf["YAMNet (russa>0.2)"])
if "ambiente" not in set(ytr):
    print("=> manca 'ambiente' (silenzio): NON installabile finche' non registri 20-30s di silenzio")
print("=> personale", "MIGLIORE: lo installo" if MIGLIORA else "NON migliore: resta YAMNet")
# modello finale su TUTTI i dati, salvato per il telefono (solo numpy: softmax(W x + b))
X, y = np.concatenate([Xtr, Xte]), np.concatenate([ytr, yte])
mu, sd = X.mean(0), X.std(0) + 1e-6
clf = LogisticRegression(max_iter=3000, C=0.5, class_weight="balanced").fit((X - mu) / sd, y)
np.savez(OUT, mu=mu, sd=sd, W=clf.coef_, b=clf.intercept_, classi=clf.classes_.astype(str), soglia_db=soglia)
print("salvato", OUT, list(clf.classes_))
