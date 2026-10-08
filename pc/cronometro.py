# 1 minuto vero cronometrato sull'A21s: YAMNet, EfficientAT (passo 1 s e 5 s), PANNs. Solo lettura (file in /tmp di Termux).
import glob, os, subprocess, time, resource
import numpy as np, onnxruntime as ort
import sonno_tel, conferma
H = os.path.expanduser("~"); T = os.environ.get("TMPDIR", H) + "/minuto.m4a"
b = sorted(glob.glob(H + "/rec/interi/2026092*.m4a"))[-1]
subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "300", "-t", "60", "-i", b, "-c", "copy", T], check=True)
t = time.time(); r = sonno_tel.classifica(T); y = time.time() - t
print(f"YAMNet      1 min: {y:5.1f} s (incl. carica modello)  frame={len(r[0]) if r else 0}")
pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", T, "-ac", "1", "-ar", "32000", "-f", "f32le", "-"], capture_output=True).stdout
w = np.frombuffer(pcm, "<f4")
t = time.time(); s = ort.InferenceSession(H + "/efficientat/mn10_as.onnx", providers=["CPUExecutionProvider"]); c = time.time() - t
for passo in (32000, 5 * 32000):
    t = time.time(); n = 0
    for i in range(0, len(w) - 5 * 32000 + 1, passo):
        s.run(None, {"waveform": w[i:i + 5 * 32000].reshape(1, -1)}); n += 1
    print(f"EfficientAT 1 min passo {passo // 32000} s: {time.time() - t:5.1f} s + carica {c:.1f} s  finestre={n}")
p = [x for x in glob.glob(H + "/panns/*.onnx")][0]
t = time.time(); sp = ort.InferenceSession(p, providers=["CPUExecutionProvider"]); c = time.time() - t
t = time.time(); conferma.classifica(T, sp, 38); print(f"PANNs       1 min: {time.time() - t:5.1f} s + carica {c:.1f} s")
print(f"RAM picco: {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024} MB")
