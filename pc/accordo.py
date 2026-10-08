"""
   python accordo.py  -> righe clip,panns,efficientat e il riassunto dell'accordo (soglia 0,2)"""
import glob, os, subprocess
import numpy as np
import onnxruntime as ort

H = os.path.expanduser("~")
s = ort.InferenceSession(f"{H}/efficientat/mn10_as.onnx", providers=["CPUExecutionProvider"])
n = {"entrambi_si": 0, "entrambi_no": 0, "solo_panns": 0, "solo_eff": 0}
for c in sorted(glob.glob(f"{H}/rec/russa_*.m4a")):
    try:
        p = float(open(c[:-4] + ".panns").read().split(",")[0])
    except (OSError, ValueError):
        continue
    w = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", c, "-ac", "1", "-ar", "32000", "-f", "f32le", "-"],
                                     capture_output=True).stdout, np.float32)
    if len(w) < 160000:
        w = np.pad(w, (0, 160000 - len(w)))  # sotto 4 s si satura: sempre almeno 5 s
    e = max(s.run(None, {"waveform": w[i:i + 160000][None]})[0][0, 43] for i in range(0, len(w) - 160000 + 1, 32000))
    k = ("entrambi_si" if e > 0.2 else "solo_panns") if p > 0.2 else ("solo_eff" if e > 0.2 else "entrambi_no")
    n[k] += 1
    print(f"{os.path.basename(c)},{p:.2f},{e:.2f}", flush=True)
print("RIASSUNTO", n)
