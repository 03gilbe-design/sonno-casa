"""Misura sull'A21s: EfficientAT (19 MB) vs PANNs (312 MB), motori CPU / XNNPACK / NNAPI, su clip vere.
   python misura_motori.py   (sotto il lucchetto ~/.analisi.lock, come la catena di rec.sh)
Per ogni modello e motore: provider davvero usati, tempo di carica, tempo per clip, RAM di picco (VmHWM), Snoring max."""
import glob, os, subprocess, time
import numpy as np
import onnxruntime as ort

H = os.path.expanduser("~")
MODELLI = {"EfficientAT": (f"{H}/efficientat/mn10_as.onnx", 43, 160000, 32000),  # finestre 5 s ogni 1 s
           "PANNs": (f"{H}/panns/cnn14.onnx", 38, 64000, 32000)}  # 2 s ogni 1 s (come conferma.py)
MOTORI = {"CPU": ["CPUExecutionProvider"], "XNNPACK": ["XnnpackExecutionProvider", "CPUExecutionProvider"],
          "NNAPI": ["NnapiExecutionProvider", "CPUExecutionProvider"]}


def picco():
    return int(next(l for l in open("/proc/self/status") if l.startswith("VmHWM")).split()[1]) // 1024


def audio(p):
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", p, "-ac", "1", "-ar", "32000", "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(pcm, np.float32)


clip = sorted(glob.glob(f"{H}/rec/russa_*.m4a"))[-3:]
wav = [audio(c) for c in clip]
for nome, (path, idx, fin, passo) in MODELLI.items():
    for mot, prov in MOTORI.items():
        try:
            t0 = time.time()
            s = ort.InferenceSession(path, providers=prov)
            carica = time.time() - t0
            tt, mx = [], []
            for w in wav:
                t0 = time.time()
                w = w if len(w) >= fin else np.pad(w, (0, fin - len(w)))
                v = [s.run(None, {"waveform": w[i:i + fin][None]})[0][0, idx] for i in range(0, len(w) - fin + 1, passo)]
                tt.append(time.time() - t0); mx.append(max(v))
            print(f"{nome:11s} {mot:7s} usa {s.get_providers()[0][:-17]:8s} carica {carica:4.1f}s  "
                  f"{np.mean(tt):5.1f} s/clip  picco RAM {picco()} MB  russa max {[round(float(x), 2) for x in mx]}",
                  flush=True)
            del s
        except Exception as e:
            print(f"{nome} {mot}: ERRORE {str(e)[:120]}", flush=True)
