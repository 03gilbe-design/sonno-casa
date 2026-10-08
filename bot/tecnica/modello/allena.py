"""Modello PERSONALE russa / respiro / movimento / ambiente: embedding YAMNet (1024) + regressione logistica.
   python allena.py   -> stampa verifica, e se batte YAMNet sulle SUE clip giudicate salva modello_personale.npz
Dati (vedi RISULTATI.md): suoi file Sleep as Android (A56, Drive "dormire"), ESC-50 snoring/breathing, suoi suoni
"""
import glob, os, sys
import numpy as np
sys.path.insert(0, r"C:\sonno_tex")
from sonno_audio import load, MODEL  # load = ffmpeg -> float32 16 kHz mono
import onnxruntime as ort
from sklearn.linear_model import LogisticRegression

A = r"C:\sonno_audio"
OUT = r"C:\sonno_tex\modello_candidato.npz"  # NON il nome che cerca il telefono: solo candidato (vedi sotto)
RUSSA, RESPIRO, VOCE = 38, 36, 0
sess = ort.InferenceSession(MODEL)


def feat(path):
    w = load(path)
    if len(w) < 16000:
        return None
    outs = [sess.run(None, {"waveform": w[i:i + 16000 * 60]}) for i in range(0, len(w) - 8000, 16000 * 60)]
    sc, emb = np.concatenate([o[0] for o in outs]), np.concatenate([o[1] for o in outs])
    n = int(0.48 * 16000)
    db = np.array([20 * np.log10(np.sqrt(np.mean(w[i * n:(i + 1) * n] ** 2)) + 1e-9) for i in range(len(sc))])
    return emb, sc, db


def frame(path, regola):
    """-> [(emb, etichetta)] per i frame sopra il fondo del file (percentile 20 + 6 dB), etichetta da regola(sc_i)."""
    r = feat(path)
    if r is None:
        return []
    emb, sc, db = r
    soglia = np.percentile(db, 20) + 6
    return [(emb[i], regola(sc[i])) for i in range(len(emb)) if db[i] > soglia and regola(sc[i])]


dati = []
# suo russare (A56): colpo sentito da YAMNet = russa; pausa senza russa ne' voce = respiro fra un colpo e l'altro
for f in glob.glob(A + r"\dormire_a56\Russare\*.m4a"):
    dati += frame(f, lambda s: "russa" if s[RUSSA] > 0.2 else ("respiro" if s[RUSSA] < 0.05 and s[VOCE] < 0.3 else None))
# MA sull'A21s vede movimento anche nel silenzio (14-25 frame su 41) -> NON usarla per i risvegli: in sonno_tel
# il movimento deve restare la regola a energia (db > base + 12). Per questo il modello e' solo CANDIDATO.
# movimento = solo i picchi forti (fondo + 15 dB), respiro dove YAMNet lo sente, il resto non si usa.
for f in glob.glob(A + r"\dormire_a56\Muoversi\*.m4a"):
    r = feat(f)
    if r:
        emb, sc, db = r
        base = np.percentile(db, 20)
        for i in range(len(emb)):
            lab = ("respiro" if sc[i, RESPIRO] > 0.3 else
                   "movimento" if db[i] > base + 15 and sc[i, VOCE] < 0.3 else None)
            if lab:
                dati.append((emb[i], lab))
for f in glob.glob(A + r"\esc50\snoring\*.wav"):
    dati += frame(f, lambda s: "russa")
for f in glob.glob(A + r"\esc50\breathing\*.wav"):
    dati += frame(f, lambda s: "respiro")
for f in glob.glob(A + r"\cal\respiro__voce__*.wav"):
    dati += frame(f, lambda s: "respiro" if s[VOCE] < 0.3 else None)
for f in glob.glob(A + r"\cal\ambiente__calibra_*.wav"):  # silenzio VERO della stanza, dall'A21s
    r = feat(f)
    if r:
        dati += [(e, "ambiente") for e in r[0]]

X = np.array([d[0] for d in dati]); y = np.array([d[1] for d in dati])
print("esempi:", {k: int((y == k).sum()) for k in sorted(set(y))})
mu, sd = X.mean(0), X.std(0) + 1e-6
clf = LogisticRegression(max_iter=3000, C=0.5, class_weight="balanced").fit((X - mu) / sd, y)

giudicate = {"0413": "respiro+movimento", "0938": "respiro", "0644": "musica+respiro", "0710": "respiro+musica",
             "0907": "silenzio", "0910": "silenzio", "0916": "silenzio"}
tot_y = tot_p = tot = 0
print("\nclip A21s giudicata da lui (NON russa) | frame russa: YAMNet vs personale | cosa vede il personale")
for c, g in giudicate.items():
    p = rf"{A}\raw\russa_20260928_{c}.m4a"
    if not os.path.exists(p):
        continue
    emb, sc, db = feat(p)
    pr = clf.predict((emb - mu) / sd)
    ny, npers = int((sc[:, RUSSA] > 0.2).sum()), int((pr == "russa").sum())
    tot_y += ny; tot_p += npers; tot += len(pr)
    vals, cnt = np.unique(pr, return_counts=True)
    print(f"  {c} {g:18s} | {ny:3d} vs {npers:3d} su {len(pr)} | " + ", ".join(f"{v} {n}" for v, n in zip(vals, cnt)))
print(f"TOTALE falsi russa: YAMNet {tot_y}, personale {tot_p} (su {tot} frame)")

# e il russare vero lo trova ancora? file misti "muoversi e russare" (mai visti) + frame russa noti
for f in glob.glob(A + r"\dormire_a56\Muoversi e russare\*.m4a"):
    emb, sc, db = feat(f)
    pr = clf.predict((emb - mu) / sd)
    print(f"misto '{os.path.basename(f)}': YAMNet russa {(sc[:, RUSSA] > 0.2).sum()}, personale russa "
          f"{(pr == 'russa').sum()}, movimento {(pr == 'movimento').sum()} su {len(pr)}")

amb_db = np.concatenate([feat(f)[2] for f in glob.glob(A + r"\cal\ambiente__calibra_*.wav")])
MEGLIO = tot_p < tot_y
if MEGLIO:
    np.savez(OUT, mu=mu, sd=sd, W=clf.coef_, b=clf.intercept_, classi=clf.classes_.astype(str),
             soglia_db=np.median(amb_db) + 4)
print("=>", f"MIGLIORE di YAMNet: salvato {OUT}" if MEGLIO else "NON migliore: resta YAMNet")
