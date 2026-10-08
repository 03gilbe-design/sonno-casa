# Conferma le clip YAMNet con PANNs: non e' una verita' assoluta.
import csv, glob, os, subprocess, sys
import numpy as np

HOME = os.path.expanduser("~")
D = os.environ.get("SONNO_DIR", os.path.join(HOME, "rec"))
P = os.path.join(HOME, "panns")
SR = 32000


def finestre(w):
    # Solo finestre complete: 2 secondi, passo 1 secondo, senza copie.
    for i in range(0, len(w) - 2 * SR + 1, SR):
        yield w[i:i + 2 * SR]


def classifica(path, sess, indice):
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1",
                          "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    w = np.frombuffer(pcm, dtype="<f4")
    if len(w) < 2 * SR:
        return "-1,0"
    massimo, secondi = 0.0, 0
    for finestra in finestre(w):
        # Una sola finestra per chiamata: limita la RAM su Android.
        p = float(sess.run(None, {"waveform": finestra.reshape(1, -1)})[0][0, indice])
        if not np.isfinite(p):
            raise ValueError("Probabilita' non finita")
        massimo = max(massimo, p)
        # Ogni finestra positiva conta un passo da 1 s, non 2 s.
        secondi += int(p > 0.2)
    return f"{massimo:.2f},{secondi}"


def efficientat():
    """
    'max,secondi_sopra_0.2'. Non decide niente: raccoglie il confronto notte per notte (sulle 84 clip: accordo 72,
    scatta piu' di PANNs). Finestre da 5 s: sotto ~4 s il modello si satura. Classe Snoring = 43 (non 38)."""
    m = os.path.join(HOME, "efficientat", "mn10_as.onnx")
    clip = [p for p in sorted(glob.glob(os.path.join(D, "russa_*.m4a")))
            if not os.path.exists(os.path.splitext(p)[0] + ".eff")]
    if not clip or not os.path.exists(m):
        return
    import onnxruntime as ort
    sess = ort.InferenceSession(m, providers=["CPUExecutionProvider"])
    for path in clip:
        try:
            pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                                 capture_output=True, check=True).stdout
            w = np.frombuffer(pcm, dtype="<f4")
            w = np.pad(w, (0, max(0, 5 * SR - len(w))))
            v = [float(sess.run(None, {"waveform": w[i:i + 5 * SR].reshape(1, -1)})[0][0, 43])
                 for i in range(0, len(w) - 5 * SR + 1, SR)]
            r = f"{max(v):.2f},{sum(x > 0.2 for x in v)}"
        except Exception as e:
            print(f"{path}: EfficientAT {e}", file=sys.stderr)
            r = "-1,0"
        with open(os.path.splitext(path)[0] + ".eff", "w", encoding="utf-8") as f:
            f.write(r + "\n")


def main():
    if os.path.exists(os.path.join(P, "SPENTO")):
        return
    clip = [p for p in sorted(glob.glob(os.path.join(D, "russa_*.m4a")))
            if not os.path.exists(os.path.splitext(p)[0] + ".panns")]
    if not clip:
        return
    try:
        import onnxruntime as ort
        with open(os.path.join(P, "class_labels_indices.csv"), encoding="utf-8-sig", newline="") as f:
            indice = next(int(r["index"]) for r in csv.DictReader(f)
                          if r["display_name"] == "Snoring")
        sess = ort.InferenceSession(os.path.join(P, "cnn14.onnx"),
                                    providers=["CPUExecutionProvider"])
    except Exception as e:
        # Configurazione assente: lascia le clip disponibili per il prossimo giro.
        print(f"PANNs: {e}", file=sys.stderr)
        return
    for path in clip:
        try:
            risultato = classifica(path, sess, indice)
        except Exception as e:
            print(f"{path}: {e}", file=sys.stderr)
            risultato = "-1,0"
        try:
            with open(os.path.splitext(path)[0] + ".panns", "w", encoding="utf-8") as f:
                f.write(risultato + "\n")
        except Exception as e:
            print(f"{path}: scrittura .panns: {e}", file=sys.stderr)


def dataset(max_blocchi=4, solo=None):
    """
    analizzato (rec/interi/*.m4a) -> rec/dataset/<blocco>.csv: una riga ogni 5 s = ora, russare (classe 43) e le 3
    categorie piu' forti (es. White noise, Breathing, Music). Pochi KB a notte: si tengono sempre (dati DI VALORE).
    ponytail: al massimo `max_blocchi` per giro (~4 x 30' = ~6' di calcolo), cosi' il loop non resta bloccato."""
    m, nomi = os.path.join(HOME, "efficientat", "mn10_as.onnx"), os.path.join(HOME, "efficientat", "labels.txt")
    if not (os.path.exists(m) and os.path.exists(nomi)):
        return
    out = os.path.join(D, "dataset"); os.makedirs(out, exist_ok=True)
    blocchi = [p for p in sorted(glob.glob(os.path.join(D, "interi", "*.m4a")), reverse=True)  # prima i piu' recenti
               if not os.path.exists(os.path.join(out, os.path.basename(p)[:-4] + ".csv"))][:max_blocchi]
    if solo:  # categorie.py: questi blocchi e basta (anche se gia' fatti senza tutte le classi)
        blocchi = list(solo)
    if not blocchi:
        return
    import onnxruntime as ort
    from datetime import datetime, timedelta
    lab = open(nomi, encoding="utf-8").read().split("\n")
    sess = ort.InferenceSession(m, providers=["CPUExecutionProvider"])
    for path in blocchi:
        n = os.path.basename(path)[:-4]
        try:
            t0 = datetime.strptime(n[:15], "%Y%m%d_%H%M%S")
            w = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f",
                                              "f32le", "-"], capture_output=True, check=True).stdout, dtype="<f4")
            righe, tutte = [], []
            for i in range(0, len(w) - 5 * SR + 1, 5 * SR):
                p = sess.run(None, {"waveform": w[i:i + 5 * SR].reshape(1, -1)})[0][0]
                tutte.append(p.astype(np.float16))
                top = np.argsort(p)[::-1][:3]
                righe.append([f"{t0 + timedelta(seconds=i / SR):%Y-%m-%dT%H:%M:%S}", f"{p[43]:.2f}"] +
                             [x for k in top for x in (lab[k], f"{p[k]:.2f}")])
            tmp = os.path.join(out, "." + n + ".csv")
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                csv.writer(f).writerows([["t", "russare", "c1", "p1", "c2", "p2", "c3", "p3"]] + righe)
            if tutte:  # ~3-5 MB a notte compresso: ogni 5 s tutte le classi (nomi in efficientat/labels.txt)
                np.savez_compressed(os.path.join(out, "." + n + ".npz"), p=np.stack(tutte), t0=n)
                os.replace(os.path.join(out, "." + n + ".npz"), os.path.join(out, n + ".npz"))
            os.replace(tmp, os.path.join(out, n + ".csv"))  # atomico: un csv c'e' solo se completo
            try:
                import respiro
                respiro.blocco(path)
            except Exception as e:
                print(f"{path}: respiro {e}", file=sys.stderr)
        except Exception as e:
            print(f"{path}: dataset {e}", file=sys.stderr)


def prova():
    w = np.arange(5 * SR + SR // 2, dtype=np.float32)
    ff = list(finestre(w))
    assert len(ff) == 4
    for i, f in enumerate(ff):
        assert f.shape == (2 * SR,) and f.dtype == np.float32
        assert np.array_equal(f, w[i * SR:i * SR + 2 * SR])
        assert np.shares_memory(f, w)
    assert len(list(finestre(w[:2 * SR]))) == 1
    assert list(finestre(w[:2 * SR - 1])) == []
    assert list(finestre(w[:0])) == []
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["prova"]:
        prova()
    else:
        try:
            main()
        except Exception as e:
            print(f"PANNs: {e}", file=sys.stderr)
        try:  # dopo PANNs, mai insieme (RAM); un modello per volta
            efficientat()
        except Exception as e:
            print(f"EfficientAT: {e}", file=sys.stderr)
        try:  # ultimo: EfficientAT su tutto l'audio gia' analizzato -> dataset, quanto lo decide lo stato
            import stato
            dataset(stato.aggiorna()["blocchi"])
        except Exception as e:
            print(f"dataset: {e}", file=sys.stderr)
