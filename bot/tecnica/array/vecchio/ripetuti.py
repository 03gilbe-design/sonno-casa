"""Distanze con 10 bip ripetuti (come online: chirp a banda separata, tante ripetizioni, mediana).
   python ripetuti.py           -> A56 poi A21s suonano UN file da 10 bip (1 al secondo); ascoltano A56, A21s,
                                   PC webcam e PC mic Intel; stampa distanza A56<->A21s e differenze dal PC
   python ripetuti.py analizza  -> solo analisi dei file in C:\\sonno_audio\\array\\rip_*
"""
import os, subprocess, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import beepbeep as b
from matrice import BOCCHE, SSH
from datetime import datetime, timedelta

# e la sequenza e' unica (con passo fisso un bip si puo' scambiare col vicino)
OFFSET = (0.0, 0.4, 1.2)  # s dall'inizio del treno
N, DUR_TRENO = len(OFFSET), OFFSET[-1] + 0.3
VOL56 = int(os.environ.get("VOL56", 15))
PRIMO = 0.5  # soglia primo arrivo (frazione del picco massimo): manopola di calibrazione
BOCCHE = dict(BOCCHE)  # A56 1-2,5 kHz, A21s 3-4,5 kHz, PC 5-6,5 kHz: suonano INSIEME
MIC_INTEL = "Microphone Array"
PC_DX_S = 2  # s fra il treno della cassa SX e quello della DX
RIS = {}  # risultati dell'ultima analizza(): "A56-A21s" -> (mediana m, dispersione m); usato da scena.py


def treno(x):
    y = np.zeros(int(DUR_TRENO * b.SR), np.float32)
    for o in OFFSET:
        i = int(o * b.SR); y[i: i + len(x)] += x
    return y


def nome_dshow(parte):
    out = subprocess.run(["ffmpeg", "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    return next((l.split('"')[1] for l in out.splitlines() if "(audio)" in l and parte in l), None)


def a21s_registra_ok(dev):
    """(nota rimossa)"""
    for _ in range(5):
        try:
            b.T(dev, "termux-microphone-record -q; rm -f ~/sonno_bot/PAUSA"); b.riavvia_loop(dev); time.sleep(4)
            if '"isRecording": true' in b.T(dev, "termux-microphone-record -i"):
                return True
        except Exception as e:
            print("ripristino A21s:", e)
        time.sleep(5); dev = b.device()
    print("!!! A21s NON registra: controllare a mano")
    return False


def registra():
    import prova
    prova.voci()
    dev = b.device()
    os.makedirs(b.OUT, exist_ok=True)
    for chi, x in BOCCHE.items():
        p = os.path.join(b.OUT, f"rip_{chi}.wav"); b.scrivi_wav(p, treno(x), pausa_prima=0.1)
        if chi == "PC":
            t = treno(x); st = np.zeros((int(0.1 * b.SR) + PC_DX_S * b.SR + len(t) + int(0.3 * b.SR), 2), np.float32)
            i = int(0.1 * b.SR); st[i:i + len(t), 0] = t; st[i + PC_DX_S * b.SR:i + PC_DX_S * b.SR + len(t), 1] = t
            import wave
            with wave.open(p, "wb") as f:
                f.setnchannels(2); f.setsampwidth(2); f.setframerate(b.SR); f.writeframes((st * 32767).astype("<i2").tobytes())
        import hashlib
        firma = hashlib.md5(open(p, "rb").read()).hexdigest(); segno = p + ".caricato"
        if os.path.exists(segno) and open(segno).read() == firma:
            continue
        if chi == "A56":
            subprocess.run(["scp", "-q", "-P", "8022", p, f"{b.A56}:rip_A56.wav"], check=True)
        elif chi == "A21s":
            sys.path.insert(0, r"C:\sonno_tex")
            from deploy import copia
            copia(dev, p, "rip_A21s.wav")
        open(segno, "w").write(firma)  # dopo il caricamento: se fallisce, riprova la volta dopo
    durata = int(DUR_TRENO + 12)
    muto21 = b.adb("shell", "settings get system all_sound_off", dev=dev).stdout.strip()
    b.adb("shell", "settings put system all_sound_off 0", dev=dev)
    b.T(dev, f"echo {(datetime.now() + timedelta(minutes=4)).isoformat(timespec='seconds')} > ~/sonno_bot/PAUSA")
    b.T(dev, 'pkill -f "^bash .*home/rec.sh"; termux-microphone-record -q')
    f21 = f"{b.PH}/rip_{int(time.time())}.m4a"
    vol21 = b.T(dev, "termux-volume | tr -d ' \\n' | grep -o '\"music\",\"volume\":[0-9]*' | grep -o '[0-9]*$'").strip() or "12"
    b.T(dev, "termux-volume music 15")
    b.T(dev, f"termux-microphone-record -e aac -b 128 -r {b.SR} -c 1 -l {durata} -f {f21}")
    subprocess.run(SSH + [f"rm -f ~/rip_a56.m4a; termux-microphone-record -e aac -b 128 -r {b.SR} -c 1 "
                          f"-l {durata} -f ~/rip_a56.m4a"], timeout=30)
    vol56 = subprocess.run(SSH + ["termux-volume | tr -d ' \\n' | grep -o '\"music\",\"volume\":[0-9]*' | "
                                  "grep -o '[0-9]*$'"], capture_output=True, text=True, timeout=30).stdout.strip() or "9"
    subprocess.run(SSH + [f"termux-volume music {VOL56}"], timeout=30)
    prova.parla("silenzio, test")
    era_muto, vol_pc = b.muto_pc(False), b.volume_pc(1.0)
    pcs = [subprocess.Popen(["ffmpeg", "-v", "quiet", "-y", "-f", "dshow", "-i", f"audio={n}", "-t", str(durata),
                             "-ar", str(b.SR), "-ac", "1", os.path.join(b.OUT, f"rip_pc_{k}.wav")])
           for k, n in (("webcam", b.PC_MIC if "USB" in b.PC_MIC else None), ("intel", nome_dshow(MIC_INTEL))) if n]
    try:
        time.sleep(1)
        b.T(dev, "termux-media-player play ~/rip_A21s.wav")  # non blocca
        import winsound
        winsound.PlaySound(os.path.join(b.OUT, "rip_PC.wav"), winsound.SND_FILENAME | winsound.SND_ASYNC)
        t_play = time.time()
        subprocess.run(SSH + ["play-audio rip_A56.wav"], timeout=40)
        time.sleep(max(0, t_play + PC_DX_S + DUR_TRENO + 0.3 - time.time()))  # fine treno cassa DX
        prova.parla("fine test, analizzo")  # subito: il resto (registrazione, ripristino) e' silenzioso ma annunciato
        for p in pcs:
            p.wait(timeout=durata + 30)
    finally:
        b.muto_pc(era_muto); b.volume_pc(vol_pc)
        subprocess.run(SSH + [f"termux-volume music {vol56}"], timeout=30)
        b.T(dev, f"termux-volume music {vol21}")
        if muto21 in ("0", "1"):
            b.adb("shell", f"settings put system all_sound_off {muto21}", dev=dev)
        time.sleep(2)
        a21s_registra_ok(dev)
        subprocess.run(SSH + ["termux-microphone-record -q"], timeout=20); time.sleep(2)
    b.adb("pull", f21, os.path.join(b.OUT, "rip_a21s.m4a"), dev=dev)
    subprocess.run(["scp", "-q", "-P", "8022", f"{b.A56}:rip_a56.m4a", os.path.join(b.OUT, "rip_a56.m4a")], check=True)


def arrivi(r, x, offset=None):
    """Pettine sulla sequenza nota (OFFSET): trovo l'inizio che massimizza la somma dei picchi, poi rifinisco
    ogni bip entro +-20 ms (sotto-campione). Ritorna tempi (s) e SNR mediano (dB)."""
    from scipy.signal import hilbert, find_peaks, correlate
    cc = np.abs(hilbert(correlate(r, x, "valid", method="fft")))  # inviluppo: niente salti fra lobi
    O = [int(o * b.SR) for o in (offset or OFFSET)]
    L = len(cc) - O[-1]
    if L <= 0:
        return None, 0.0
    s0 = int(np.argmax(sum(cc[o: o + L] for o in O)))
    fondo, t, snr = np.median(cc) + 1e-12, [], []
    for o in O:
        lo = max(0, s0 + o - 960); w = cc[lo: s0 + o + 960]
        pk, _ = find_peaks(w, height=PRIMO * w.max())
        i = lo + (int(pk[0]) if len(pk) else int(np.argmax(w)))
        a, c0, c = cc[max(i - 1, 0)], cc[i], cc[min(i + 1, len(cc) - 1)]
        t.append((i + 0.5 * (a - c) / (a - 2 * c0 + c + 1e-12)) / b.SR); snr.append(20 * np.log10(c0 / fondo))
    return np.array(t), float(np.median(snr))


def analizza(cartella=None):
    cartella = cartella or b.OUT
    rec = {"A56": "rip_a56.m4a", "A21s": "rip_a21s.m4a", "PCwebcam": "rip_pc_webcam.wav", "PCintel": "rip_pc_intel.wav"}
    t = {}
    for o, f in rec.items():
        p = os.path.join(cartella, f)
        if not os.path.exists(p):
            continue
        r = b.decodifica(p)
        sat = np.mean(np.abs(r) > 0.98)
        for e, x in BOCCHE.items():
            if e == "PC":
                # a uno dei due e fra due registrazioni c'e' 2 s = 343 m di errore
                t6, snr = arrivi(r, x, OFFSET + tuple(o + PC_DX_S for o in OFFSET))
                t[o, "PC"], t[o, "PCdx"] = (t6[:N], t6[N:]) if t6 is not None else (None, None)
            else:
                t[o, e], snr = arrivi(r, x)
            print(f"{e:4s} -> {o:8s}: SNR {snr:5.1f} dB  saturazione {sat * 100:.3f}%")
    # BeepBeep per ogni coppia; il PC ha due orecchi possibili (Intel, webcam) -> una riga per orecchio
    orecchio = {"A56": ["A56"], "A21s": ["A21s"], "PC": ["PCintel"] if ("PCintel", "PC") in t else []}
    print()
    for X, Y in (("A56", "A21s"), ("A56", "PC"), ("A21s", "PC")):
        for oX in orecchio[X]:
            for oY in orecchio[Y]:
                if t.get((oX, Y)) is None or t.get((oY, X)) is None:
                    continue
                dd = b.C / 2 * ((t[oX, Y] - t[oX, X]) - (t[oY, Y] - t[oY, X]))
                print(f"{X:4s}({oX:8s}) <-> {Y:4s}({oY:8s}): mediana {np.median(dd):.3f} m  dispersione {np.std(dd) * 100:.1f} cm")
                RIS[f"{X}-{Y}"] = (float(np.median(dd)), float(np.std(dd)))
    d =b.C / 2 * ((t["A56", "A21s"] - t["A56", "A56"]) - (t["A21s", "A21s"] - t["A21s", "A56"]))
    print(f"\nA56 <-> A21s: mediana {np.median(d):.3f} m  (per bip {np.round(d, 3)})  dispersione {np.std(d) * 100:.1f} cm")
    emiss = (t["A56", "A21s"] - t["A56", "A56"]) - np.median(d) / b.C  # istante A21s - istante A56 (clock A56)
    for o in ("PCwebcam", "PCintel"):
        if (o, "A56") in t:
            diff = b.C * ((t[o, "A21s"] - t[o, "A56"]) - emiss)
            RIS[f"tdoa_{o}"] = (float(np.median(diff)), float(np.std(diff)))
            print(f"{o}: d(PC,A21s) - d(PC,A56) = {np.median(diff):.3f} m  dispersione {np.std(diff) * 100:.1f} cm"
                  f"  (per bip {np.round(diff, 2)})")


def prova_sorgenti(sorgenti=(1, 6, 9)):
    """
    Per ogni sorgente Android (1 MIC, 6 VOICE_RECOGNITION, 9 UNPROCESSED) registra il proprio treno e da' l'SNR."""
    dev = b.device()
    muto21 = b.adb("shell", "settings get system all_sound_off", dev=dev).stdout.strip()
    b.adb("shell", "settings put system all_sound_off 0", dev=dev)
    b.T(dev, f"echo {(datetime.now() + timedelta(minutes=3)).isoformat(timespec='seconds')} > ~/sonno_bot/PAUSA")
    b.T(dev, 'pkill -f "^bash .*home/rec.sh"; termux-microphone-record -q')
    try:
        for s in sorgenti:
            f = f"{b.PH}/src{s}_{int(time.time())}.m4a"
            # il wrapper termux-microphone-record non passa 'source': chiamo l'API direttamente
            b.T(dev, f"$PREFIX/libexec/termux-api MicRecorder -a record --es file {f} --ei limit 14000 --es encoder aac "
                     f"--ei bitrate 128000 --ei srate {b.SR} --ei channels 1 --ei source {s}")
            time.sleep(1.5); b.T(dev, "termux-media-player play ~/rip_A21s.wav"); time.sleep(11)  # play-audio: OpenSL senza uscita (DeviceId:0) sull A21s; time.sleep(3)
            b.T(dev, "termux-microphone-record -q"); time.sleep(1)
            loc = os.path.join(b.OUT, f"src{s}.m4a"); b.adb("pull", f, loc, dev=dev)
            t, snr = arrivi(b.decodifica(loc), BOCCHE["A21s"])
            print(f"sorgente {s}: SNR proprio bip {snr:5.1f} dB  intervalli ms {np.round(np.diff(t) * 1000 - 1000, 2)}")
    finally:
        if muto21 in ("0", "1"):
            b.adb("shell", f"settings put system all_sound_off {muto21}", dev=dev)
        a21s_registra_ok(dev)


if __name__ == "__main__":
    if sys.argv[1:] == ["sorgenti"]:
        prova_sorgenti(); sys.exit()
    if sys.argv[1:] != ["analizza"]:
        registra()
    analizza()
