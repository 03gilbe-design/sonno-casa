import ctypes, subprocess, time, sys, json
import numpy as np, onnxruntime as ort
ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL
H = r"C:\sonno_tex"
def pcm(p, sr):
    return np.frombuffer(subprocess.run(["ffmpeg","-v","error","-i",p,"-ac","1","-ar",str(sr),"-f","f32le","-"],capture_output=True).stdout, np.float32)
def T(f):
    c0, w0 = time.process_time(), time.time(); r = f(); return time.time()-w0, time.process_time()-c0
res = {}
for nome, f in (("A56", "a56_10min.m4a"), ("PC", "pc_10min.flac")):
    dur = 600.0
    w, c = T(lambda: pcm(f, 16000)); res[(nome,"decodifica ffmpeg")] = (w, c)
    w16 = pcm(f, 16000); w32 = pcm(f, 32000)
    s = ort.InferenceSession(H+r"\yamnet\yamnet.onnx", providers=["CPUExecutionProvider"])
    res[(nome,"YAMNet")] = T(lambda: [s.run(None, {"waveform": w16[i:i+16000*60]}) for i in range(0, len(w16)-16000, 16000*60)])
    s = ort.InferenceSession(H+r"\efficientat\mn10_as.onnx", providers=["CPUExecutionProvider"])
    res[(nome,"EfficientAT passo 1 s")] = T(lambda: [s.run(None, {"waveform": w32[i:i+160000][None]}) for i in range(0, len(w32)-160000+1, 32000)])
    res[(nome,"EfficientAT passo 5 s")] = T(lambda: [s.run(None, {"waveform": w32[i:i+160000][None]}) for i in range(0, len(w32)-160000+1, 160000)])
    s = ort.InferenceSession(H+r"\panns\cnn14.onnx", providers=["CPUExecutionProvider"])
    res[(nome,"PANNs passo 1 s")] = T(lambda: [s.run(None, {"waveform": w32[i:i+64000][None]}) for i in range(0, len(w32)-64000+1, 32000)])
    print(nome, "ok", flush=True)
out = {f"{k[0]}|{k[1]}": v for k, v in res.items()}
json.dump(out, open("bench.json","w"))
for k, (w, c) in out.items(): print(f"{k:35s} wall {w:6.1f}s cpu {c:6.1f}s  -> {w/10:5.2f} s/min wall, CPU util {c/w*100:4.0f}%")
