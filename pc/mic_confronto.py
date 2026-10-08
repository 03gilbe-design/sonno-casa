"""Classifica dei microfoni dai pezzi del telecomando (C:\\sonno_audio\\cal\\<suono>__<mic>__<ora>.m4a).
Per mic: fondo (dB, piu' basso = meno fruscio), SNR russamento (dB sopra il fondo), russamento riconosciuto
da YAMNet (% dei colpi), respiro riconosciuto (%), falsi allarmi nel silenzio (%).
Servono per ogni mic almeno un pezzo di: ambiente, russa, respiro.
"""
import glob, os, sys
import numpy as np, onnxruntime as ort
sys.path.insert(0, r"C:\sonno_tex")
from sonno_audio import load, MODEL

CAL = r"C:\sonno_audio\cal"
HOP, SR = 0.48, 16000


def misura(mic, sess):
    def f(lab):
        sc, db = [], []
        for p in glob.glob(os.path.join(CAL, f"{lab}__{mic}__*.m4a")):
            w = load(p)
            if len(w) < SR:
                continue
            sc.append(sess.run(None, {"waveform": w})[0])
            n = int(HOP * SR)
            db.append([20 * np.log10(np.sqrt(np.mean(w[i * n:(i + 1) * n] ** 2)) + 1e-9) for i in range(len(sc[-1]))])
        return (np.concatenate(sc), np.concatenate(db)) if sc else None
    a, r, b = f("ambiente"), f("russa"), f("respiro")
    manca = [n for n, x in (("ambiente", a), ("russa", r), ("respiro", b)) if x is None]
    if manca:
        return manca
    fondo = float(np.median(a[1]))
    forti = r[1] > np.percentile(r[1], 50)  # meta' piu' forte = dove ci sono i colpi
    return dict(fondo=fondo, snr=float(np.percentile(r[1], 90) - fondo),
                russa=float((r[0][forti, 38] > 0.2).mean()), respiro=float((b[0][:, 36] > 0.3).mean()),
                falsi=float((a[0][:, 38] > 0.2).mean()))


def classifica():
    sess = ort.InferenceSession(MODEL)
    mics = sorted({os.path.basename(p).split("__")[1] for p in glob.glob(os.path.join(CAL, "*__*__*.m4a"))})
    R = {m: misura(m, sess) for m in mics}
    ok = {m: x for m, x in R.items() if isinstance(x, dict)}
    # ponytail: pesi a buon senso (riconoscere russa conta di piu'), da rivedere se due mic sono vicini
    punt = {m: 50 * x["russa"] + 25 * x["respiro"] + 25 * min(max(x["snr"], 0) / 30, 1) - 50 * x["falsi"] for m, x in ok.items()}
    righe = ["📊 <b>Microfoni</b>"]
    for i, m in enumerate(sorted(punt, key=punt.get, reverse=True), 1):
        x = ok[m]
        righe.append(f"{i}. <b>{m}</b> {punt[m]:.0f} · russa {x['russa']:.0%} · respiro {x['respiro']:.0%} · SNR {x['snr']:.0f}dB")
    righe += [f"– {m}: manca {', '.join(x)}" for m, x in R.items() if not isinstance(x, dict)]
    return "\n".join(righe) if len(righe) > 1 else "📊 nessun dato: per ogni mic registra ambiente, russa, respiro"


if __name__ == "__main__":
    print(classifica())
