"""
   python canale.py           -> 3 s silenzio (rumore di fondo), poi A56, A21s, PC suonano a turno 7 toni lunghi
                                 (150 Hz..10 kHz, 2 s l'uno: lungo = il rumore che cambia ogni ~1 s si media);
                                 ascoltano A56, A21s, PC Intel, PC webcam
   python canale.py analizza  -> solo tabella
Per bocca x orecchio x frequenza: ARRIVA (dB sopra il rumore a quella frequenza), DEFORMA (armoniche 2f+3f rispetto a f, dB).
"""
import os, subprocess, sys, time, winsound
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import beepbeep as b
from matrice import SSH
from ripetuti import a21s_registra_ok, nome_dshow, MIC_INTEL
from datetime import datetime, timedelta

FREQ = (150, 300, 600, 1200, 2500, 5000, 10000)
TONO, GAP, SILENZIO = 2.0, 0.3, 3.0
BOCCHE = ("A56", "A21s", "PC")
DUR_BOCCA = len(FREQ) * (TONO + GAP)


def toni():
    t = np.arange(int(TONO * b.SR)) / b.SR; env = np.minimum(1, np.minimum(t, TONO - t) / 0.02)  # rampe 20 ms: niente click
    return np.concatenate([np.concatenate([0.9 * np.sin(2 * np.pi * f * t) * env, np.zeros(int(GAP * b.SR))])
                           for f in FREQ]).astype(np.float32)


def registra(segnale=None, nome="toni", pref="canale"):
    """Silenzio (rumore di fondo), poi A56, A21s, PC suonano `segnale` a turno; 4 orecchi registrano -> {pref}_*.
    Riusato da sweep.py (sweep esponenziale)."""
    segnale = toni() if segnale is None else segnale
    dur_bocca = len(segnale) / b.SR
    dev = b.device(); os.makedirs(b.OUT, exist_ok=True)
    p = os.path.join(b.OUT, f"{nome}.wav"); b.scrivi_wav(p, segnale, pausa_prima=0.0)
    subprocess.run(["scp", "-q", "-P", "8022", p, f"{b.A56}:{nome}.wav"], check=True)
    sys.path.insert(0, r"C:\sonno_tex"); from deploy import copia; copia(dev, p, f"{nome}.wav")
    durata = int(SILENZIO + 3 * (dur_bocca + 3) + 20)
    b.T(dev, f"echo {(datetime.now() + timedelta(minutes=4)).isoformat(timespec='seconds')} > ~/sonno_bot/PAUSA")
    b.T(dev, 'pkill -f "^bash .*home/rec.sh"; termux-microphone-record -q')
    vol21 = b.T(dev, "termux-volume | tr -d ' \\n' | grep -o '\"music\",\"volume\":[0-9]*' | grep -o '[0-9]*$'").strip() or "12"
    b.T(dev, "termux-volume music 15")
    f21 = f"{b.PH}/{pref}_{int(time.time())}.m4a"
    b.T(dev, f"termux-microphone-record -e aac -b 128 -r {b.SR} -c 1 -l {durata} -f {f21}")
    subprocess.run(SSH + [f"rm -f ~/{pref}_a56.m4a; termux-microphone-record -e aac -b 128 -r {b.SR} -c 1 -l {durata} "
                          f"-f ~/{pref}_a56.m4a"], timeout=30)
    vol56 = subprocess.run(SSH + ["termux-volume | tr -d ' \\n' | grep -o '\"music\",\"volume\":[0-9]*' | grep -o '[0-9]*$'"],
                           capture_output=True, text=True, timeout=30).stdout.strip() or "9"
    subprocess.run(SSH + ["termux-volume music 15"], timeout=30)
    era_muto, vol_pc = b.muto_pc(False), b.volume_pc(1.0)
    pcs = [subprocess.Popen(["ffmpeg", "-v", "quiet", "-y", "-f", "dshow", "-i", f"audio={n}", "-t", str(durata),
                             "-ar", str(b.SR), "-ac", "1", os.path.join(b.OUT, f"{pref}_pc_{k}.wav")])
           for k, n in (("webcam", b.PC_MIC if "USB" in b.PC_MIC else None), ("intel", nome_dshow(MIC_INTEL))) if n]
    try:
        time.sleep(1 + SILENZIO)
        subprocess.run(SSH + [f"play-audio {nome}.wav"], timeout=60); time.sleep(1)
        b.T(dev, f"termux-media-player play ~/{nome}.wav"); time.sleep(dur_bocca + 1.5)
        winsound.PlaySound(p, winsound.SND_FILENAME)
        for q in pcs:
            q.wait(timeout=durata + 30)
    finally:
        b.muto_pc(era_muto); b.volume_pc(vol_pc)
        subprocess.run(SSH + [f"termux-volume music {vol56}"], timeout=30)
        b.T(dev, f"termux-volume music {vol21}"); time.sleep(1)
        a21s_registra_ok(dev)
        subprocess.run(SSH + ["termux-microphone-record -q"], timeout=20); time.sleep(2)
    b.adb("pull", f21, os.path.join(b.OUT, f"{pref}_a21s.m4a"), dev=dev)
    subprocess.run(["scp", "-q", "-P", "8022", f"{b.A56}:{pref}_a56.m4a", os.path.join(b.OUT, f"{pref}_a56.m4a")], check=True)


def livello(x, f):
    """dB dell'energia a f (+-2%) in x."""
    F = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2; fr = np.fft.rfftfreq(len(x), 1 / b.SR)
    return 10 * np.log10(F[(fr > f * 0.98) & (fr < f * 1.02)].sum() + 1e-20)


def analizza():
    rec = {"A56": "canale_a56.m4a", "A21s": "canale_a21s.m4a", "PCintel": "canale_pc_intel.wav", "PCwebcam": "canale_pc_webcam.wav"}
    ref = toni()
    for o, f in rec.items():
        if not os.path.exists(os.path.join(b.OUT, f)):
            continue
        x = b.decodifica(os.path.join(b.OUT, f))
        # ogni bocca: trovo l'inizio del suo blocco di toni con la correlazione (i 3 blocchi escono in ordine)
        cc = np.abs(np.correlate(x, ref[: int(2 * b.SR)], "valid")); inizi, c2 = [], cc.copy()
        for _ in BOCCHE:
            i = int(np.argmax(c2)); inizi.append(i); c2[max(0, i - int(DUR_BOCCA * b.SR)): i + int(DUR_BOCCA * b.SR)] = 0
        inizi.sort()
        rumore = x[int(0.5 * b.SR): int((0.5 + SILENZIO) * b.SR)]
        print(f"\n== orecchio {o} ==   (ARRIVA = dB sopra il rumore; DEFORMA = armoniche rispetto al tono, dB)")
        print("bocca  " + "".join(f"{f:>12d}" for f in FREQ))
        for chi, i0 in zip(BOCCHE, inizi):
            riga_a, riga_d = [], []
            for k, f in enumerate(FREQ):
                s = x[i0 + int((k * (TONO + GAP) + 0.3) * b.SR): i0 + int((k * (TONO + GAP) + TONO - 0.3) * b.SR)]
                r = rumore[: len(s)]
                if len(s) < b.SR:
                    riga_a.append(np.nan); riga_d.append(np.nan); continue
                riga_a.append(livello(s, f) - livello(r, f))
                arm = [livello(s, h) for h in (2 * f, 3 * f) if h < b.SR / 2 - 500]
                riga_d.append(10 * np.log10(sum(10 ** (a / 10) for a in arm) + 1e-20) - livello(s, f) if arm else np.nan)
            print(f"{chi:5s} A" + "".join(f"{v:12.1f}" for v in riga_a))
            print(f"{'':5s} D" + "".join(f"{v:12.1f}" for v in riga_d))
    print("\nlettura: A < 10 = quella frequenza praticamente non arriva (PERDITA); D > -20 = DEFORMAZIONE forte")


if __name__ == "__main__":
    if sys.argv[1:] != ["analizza"]:
        registra()
    analizza()
