"""Modulo ARRAY (ramo K di RICERCA_MAPPA): BeepBeep = distanza fra dispositivi SENZA orologi sincronizzati.
   python beepbeep.py            -> A56 e PC fanno 3 bip a testa, A21s + A56 + PC registrano, stampa distanze
Metodo (Peng et al., BeepBeep, SenSys 2007): ognuno registra il SUO bip e quello dell'altro; la differenza dei
due intervalli misurati dai due lati = 2 * distanza / c. L'A21s (che ascolta e basta) da' la differenza delle
sue distanze dai due (iperbole). Deriva orologi trascurabile su pochi secondi (0,1 ms/min, analisi_xy.py).
"""
import os, subprocess, sys, threading, time, wave, winsound
import numpy as np
sys.path.insert(0, r"C:\sonno_tex")
import sonno_audio  # noqa: F401  (niente finestre console)
from sonno_audio import adb, device
from cal_sessione import T, riavvia_loop

SR, C = 48000, 343.0
OUT = r"C:\sonno_audio\array"
A56 = "192.0.2.54"
def mic_pc():
    """
    bip del telefono), altrimenti il microfono interno."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    nomi = [l.split('"')[1] for l in out.splitlines() if "(audio)" in l and '"' in l]
    return next((n for n in nomi if "USB" in n), next((n for n in nomi if "Microphone Array" in n), nomi[0] if nomi else ""))


PC_MIC = mic_pc()
PH = "/sdcard/Recordings/sonno_cal"
N_BIP, PAUSA_S = 5, 1.5


def chirp(f0, f1, dur=0.08):
    t = np.arange(int(dur * SR)) / SR
    x = np.sin(2 * np.pi * (f0 * t + (f1 - f0) / (2 * dur) * t ** 2)) * np.hanning(len(t))
    return (0.9 * x).astype(np.float32)


BIP = {"A56": chirp(1500, 7000, 0.5), "PC": chirp(7000, 1500, 0.5)}


def scrivi_wav(path, x, pausa_prima=0.5):
    x = np.concatenate([np.zeros(int(pausa_prima * SR), np.float32), x, np.zeros(int(0.3 * SR), np.float32)])
    with wave.open(path, "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR)
        f.writeframes((x * 32767).astype("<i2").tobytes())


def decodifica(path):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def arrivi(rec, bip, n):
    """Istanti (campioni, sotto-campione) dei picchi del filtro adattato >= 30% del piu' forte, distanti >0,5 s.
    """
    cc = np.abs(np.correlate(rec, bip, "valid"))
    picchi, cc2, soglia = [], cc.copy(), 0.3 * cc.max()
    while len(picchi) < n and cc2.max() >= soglia:
        i = int(np.argmax(cc2))
        a, b, c = cc[max(i - 1, 0)], cc[i], cc[min(i + 1, len(cc) - 1)]
        picchi.append(i + 0.5 * (a - c) / (a - 2 * b + c + 1e-12))  # sotto-campione (parabola)
        cc2[max(0, i - SR // 2): i + SR // 2] = 0
    return sorted(picchi)


def muto_pc(muto):
    """Imposta il muto del mic del PC, ritorna lo stato di prima."""
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    col = AudioUtilities.GetDeviceEnumerator().EnumAudioEndpoints(1, 1)
    for i in range(col.GetCount()):
        d = col.Item(i)
        if "Microphone Array" in AudioUtilities.CreateDevice(d).FriendlyName:
            v = d.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None).QueryInterface(IAudioEndpointVolume)
            prima = bool(v.GetMute()); v.SetMute(int(muto), None)
            return prima
    return muto


def volume_pc(v):
    """Imposta il volume generale delle casse del PC (0-1), ritorna quello di prima."""
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    from comtypes import CLSCTX_ALL
    d = AudioUtilities.GetDeviceEnumerator().GetDefaultAudioEndpoint(0, 1)
    e = d.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None).QueryInterface(IAudioEndpointVolume)
    prima = e.GetMasterVolumeLevelScalar(); e.SetMasterVolumeLevelScalar(float(v), None)
    return prima


def propri(rec, chi):
    """Arrivi del bip di `chi` tenendo solo quelli che somigliano PIU' al suo bip che all'altro.
    """
    altro = next(b for b in BIP if b != chi)
    cc_mio = np.abs(np.correlate(rec, BIP[chi], "valid")); cc_altro = np.abs(np.correlate(rec, BIP[altro], "valid"))
    return [p for p in arrivi(rec, BIP[chi], N_BIP)
            if cc_mio[int(p)] > 1.5 * cc_altro[max(0, int(p) - 200): int(p) + 200].max()]


def registra_e_suona():
    os.makedirs(OUT, exist_ok=True)
    scrivi_wav(os.path.join(OUT, "bip_a56.wav"), BIP["A56"]); scrivi_wav(os.path.join(OUT, "bip_pc.wav"), BIP["PC"])
    subprocess.run(["scp", "-q", "-P", "8022", os.path.join(OUT, "bip_a56.wav"), f"{A56}:bip_a56.wav"], check=True)
    dev = device()
    durata = int(N_BIP * 2 * (PAUSA_S + 2.5) + 12)  # ogni play via ssh costa ~1,7 s: margine abbondante
    # A21s: pausa loop (senno' riparte e fa -q), registra 48 kHz
    from datetime import datetime, timedelta
    T(dev, f"echo {(datetime.now() + timedelta(minutes=5)).isoformat(timespec='seconds')} > ~/sonno_bot/PAUSA")
    T(dev, 'pkill -f "^bash .*home/rec.sh"; termux-microphone-record -q')
    f21 = f"{PH}/beep_{int(time.time())}.m4a"
    T(dev, f"termux-microphone-record -e aac -b 128 -r {SR} -c 1 -l {durata} -f {f21}")
    ssh = ["ssh", "-p", "8022", "-o", "BatchMode=yes", A56]
    subprocess.run(ssh + [f"rm -f ~/beep_a56.m4a; termux-microphone-record -e aac -b 128 -r {SR} -c 1 -l {durata} "
                          f"-f ~/beep_a56.m4a"], timeout=30)
    era_muto = muto_pc(False)  # il mic del PC di solito e' muto: lo apro solo per la prova e poi lo rimetto
    pc = subprocess.Popen(["ffmpeg", "-v", "quiet", "-y", "-f", "dshow", "-i", f"audio={PC_MIC}", "-t", str(durata),
                           "-ar", str(SR), "-ac", "1", os.path.join(OUT, "beep_pc.wav")])
    vol_a56 = subprocess.run(ssh + ["termux-volume | tr -d ' \\n' | grep -o '\"music\",\"volume\":[0-9]*' | "
                                    "grep -o '[0-9]*$'"], capture_output=True, text=True, timeout=30).stdout.strip() or "9"
    subprocess.run(ssh + ["termux-volume music 12"], timeout=30)  # a 15 saturava il suo stesso mic
    vol_pc = volume_pc(1.0)
    time.sleep(3)
    for _ in range(N_BIP):
        subprocess.run(ssh + ["play-audio bip_a56.wav"], timeout=20); time.sleep(PAUSA_S)
        winsound.PlaySound(os.path.join(OUT, "bip_pc.wav"), winsound.SND_FILENAME); time.sleep(PAUSA_S)
    pc.wait(timeout=durata + 20)
    muto_pc(era_muto); volume_pc(vol_pc)
    subprocess.run(ssh + [f"termux-volume music {vol_a56}"], timeout=30)
    time.sleep(2)
    T(dev, "termux-microphone-record -q"); T(dev, "rm -f ~/sonno_bot/PAUSA"); riavvia_loop(dev)
    subprocess.run(ssh + ["termux-microphone-record -q"], timeout=20); time.sleep(2)
    adb("pull", f21, os.path.join(OUT, "beep_a21s.m4a"), dev=dev)
    subprocess.run(["scp", "-q", "-P", "8022", f"{A56}:beep_a56.m4a", os.path.join(OUT, "beep_a56.m4a")], check=True)


def analizza():
    rec = {k: decodifica(os.path.join(OUT, f)) for k, f in
           (("A56", "beep_a56.m4a"), ("PC", "beep_pc.wav"), ("A21s", "beep_a21s.m4a"))}
    t = {k: {b: np.array(propri(r, b)) / SR for b in BIP} for k, r in rec.items()}
    n = min(len(v) for d in t.values() for v in d.values())
    print("bip trovati per registratore:", {k: {b: len(v) for b, v in d.items()} for k, d in t.items()}, "-> uso", n)
    if n == 0:
        sys.exit("nessun bip riconosciuto in almeno un registratore")
    t = {k: {b: v[:n] for b, v in d.items()} for k, d in t.items()}
    dA56 = t["A56"]["PC"] - t["A56"]["A56"]   # intervallo misurato dal telefono
    dPC = t["PC"]["PC"] - t["PC"]["A56"]      # intervallo misurato dal PC
    dist = C / 2 * (dA56 - dPC)
    print("distanza A56 <-> PC per bip (m):", np.round(dist, 3), " media", round(float(np.mean(dist)), 3),
          " dispersione", round(float(np.std(dist)) * 100, 1), "cm")
    # A21s ascolta: (tPC - tA56) visto dall'A21s meno quello "vero" di emissione -> d(PC,A21s) - d(A56,A21s)
    emiss = dA56 - np.mean(dist) / C          # tempo fra le due emissioni
    diff = C * ((t["A21s"]["PC"] - t["A21s"]["A56"]) - emiss)
    print("A21s: distanza dal PC meno distanza dal telefono (m):", np.round(diff, 3),
          " media", round(float(np.mean(diff)), 3))
    return dist, diff


if __name__ == "__main__":
    if sys.argv[1:] != ["analizza"]:
        registra_e_suona()
    analizza()
