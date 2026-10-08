"""
Webcam appoggiata SULLA griglia sx della tastiera (cassa, distanza ~0): il PC fa 3 bip corti; un solo ffmpeg
registra i due mic insieme. ritardo = t_webcam - t_intel + (d_intel - d_webcam)/c  -> ritardo_webcam.json
   python calibra_webcam.py
"""
import json, subprocess, sys, time, wave, winsound
import numpy as np
from scipy.signal import hilbert

SR, C = 48000, 343.0
OUT = "C:/sonno_audio/array"
D_INTEL = 0.27  # cassa sx -> mic sopra lo schermo (HARDWARE.md: ~25-30 cm)
OFFSET = (0.0, 0.4, 1.2)


def mic(parte):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    return next(l.split('"')[1] for l in out.splitlines() if "(audio)" in l and parte in l)


def chirp(dur=0.1):
    t = np.arange(int(dur * SR)) / SR
    return np.sin(2 * np.pi * (2000 * t + 4000 / (2 * dur) * t ** 2)) * np.hanning(len(t))


def primo(rec, bip, da, a):
    """PRIMO arrivo (eco puo' essere piu' forte): inviluppo del filtro adattato, primo punto >= 50% del max."""
    env = np.abs(hilbert(np.correlate(rec[da:a], bip, "valid")))
    return da + int(np.argmax(env >= 0.5 * env.max()))


def leggi(path):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def main():
    bip = chirp()
    x = np.zeros(int(1.6 * SR))
    for o in OFFSET:
        x[int(o * SR):int(o * SR) + len(bip)] += 0.9 * bip
    wav = f"{OUT}/cal_webcam_bip.wav"
    with wave.open(wav, "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR); f.writeframes((x * 32767).astype("<i2").tobytes())
    st = f"{OUT}/cal_webcam_intel.wav"
    # diverse di ~180 ms, scarto casuale). -t PRIMA di ogni -i (dopo valeva solo per la 1a uscita -> infinito)
    if "analizza" not in sys.argv:  # "analizza" = rianalizza l'ultimo file, niente bip
        rec = subprocess.Popen(["ffmpeg", "-v", "quiet", "-y", "-t", "4", "-f", "dshow", "-i", f"audio={mic('USB')}",
                                "-t", "4", "-f", "dshow", "-i", f"audio={mic('Microphone Array')}",
                                "-filter_complex", f"[0:a]aresample={SR},pan=mono|c0=c0[w];[1:a]aresample={SR},pan=mono|c0=c0[i];[w][i]amerge=inputs=2",
                                "-ar", str(SR), st])
        time.sleep(1.5)
        winsound.PlaySound(wav, winsound.SND_FILENAME)
        rec.wait()
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", st, "-f", "f32le", "-"], capture_output=True, check=True).stdout
    rw, ri = np.frombuffer(raw, np.float32)[0::2], np.frombuffer(raw, np.float32)[1::2]
    # il primo bip trovato nel mic Intel fa da ancora; gli altri si cercano +-60 ms attorno a ogni OFFSET
    t0 = primo(ri, bip, 0, len(ri) - len(bip))
    w = int(0.06 * SR)
    # scarto grezzo webcam dal 1o bip (finestra larga), poi ogni bip cercato +-60 ms attorno a quello
    s0 = primo(rw, bip, max(0, t0 - int(0.35 * SR)), t0 + int(0.35 * SR) + len(bip)) - t0
    diffs = []
    for o in OFFSET:
        c = t0 + int(o * SR)
        ti = primo(ri, bip, max(0, c - w), c + w + len(bip))
        tw = primo(rw, bip, max(0, c + s0 - w), c + s0 + w + len(bip))
        diffs.append((tw - ti) / SR * 1000 + D_INTEL / C * 1000)
    r = {"ritardo_ms": float(np.median(diffs)), "bip_ms": [round(d, 3) for d in diffs], "D_INTEL": D_INTEL,
         "livello_webcam": float(np.abs(rw).max()), "livello_intel": float(np.abs(ri).max()), "quando": time.strftime("%d/%m %H:%M")}
    json.dump(r, open(f"{OUT}/ritardo_webcam.json", "w"), indent=1)
    print(r)


if __name__ == "__main__":
    main()
