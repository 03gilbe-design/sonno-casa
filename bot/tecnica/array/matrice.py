"""Matrice CHI SENTE CHI (prima di BeepBeep: aprire le scatole piccole).
   python matrice.py            -> A56, A21s e PC suonano il loro bip a 3 volumi; A56, A21s e PC ascoltano; tabella
   python matrice.py analizza   -> rifa' solo la tabella dalle registrazioni in C:\\sonno_audio\\array
Tabella: per ogni bocca x orecchio x volume -> segnale/fondo del filtro adattato (dB) e se l'orecchio satura.
"""
import os, subprocess, sys, time, winsound
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import beepbeep as b  # riusa: chirp, decodifica, scrivi_wav, muto_pc, volume_pc, T, adb, device, riavvia_loop
from datetime import datetime, timedelta

DUR_BIP = 0.25
BOCCHE = {"A56": b.chirp(1000, 2500, DUR_BIP), "A21s": b.chirp(3000, 4500, DUR_BIP), "PC": b.chirp(5000, 6500, DUR_BIP)}
VOLUMI = (1.0, 0.3, 0.1)
ORECCHI = ("A56", "A21s", "PC")
SSH = ["ssh", "-p", "8022", "-o", "BatchMode=yes", b.A56]


def suona(chi, path):
    if chi == "A56":
        subprocess.run(SSH + [f"play-audio {os.path.basename(path)}"], timeout=30)
    elif chi == "A21s":
        b.T(DEV, f"play-audio ~/{os.path.basename(path)}")
    else:
        winsound.PlaySound(path, winsound.SND_FILENAME)


def registra():
    global DEV
    DEV = b.device()
    os.makedirs(b.OUT, exist_ok=True)
    wav = {}
    for chi, x in BOCCHE.items():
        for v in VOLUMI:
            p = os.path.join(b.OUT, f"m_{chi}_{v}.wav"); b.scrivi_wav(p, x * v, pausa_prima=0.1); wav[chi, v] = p
            if chi == "A56":
                subprocess.run(["scp", "-q", "-P", "8022", p, f"{b.A56}:{os.path.basename(p)}"], check=True)
            elif chi == "A21s":
                sys.path.insert(0, r"C:\sonno_tex")
                from deploy import copia
                copia(DEV, p, os.path.basename(p))
    durata = int(len(wav) * 3.5 + 15)
    b.T(DEV, f"echo {(datetime.now() + timedelta(minutes=6)).isoformat(timespec='seconds')} > ~/sonno_bot/PAUSA")
    b.T(DEV, 'pkill -f "^bash .*home/rec.sh"; termux-microphone-record -q')
    f21 = f"{b.PH}/matrice_{int(time.time())}.m4a"
    b.T(DEV, f"termux-microphone-record -e aac -b 128 -r {b.SR} -c 1 -l {durata} -f {f21}")
    subprocess.run(SSH + [f"rm -f ~/matrice_a56.m4a; termux-microphone-record -e aac -b 128 -r {b.SR} -c 1 "
                          f"-l {durata} -f ~/matrice_a56.m4a"], timeout=30)
    vol_a56 = subprocess.run(SSH + ["termux-volume | tr -d ' \\n' | grep -o '\"music\",\"volume\":[0-9]*' | "
                                    "grep -o '[0-9]*$'"], capture_output=True, text=True, timeout=30).stdout.strip() or "9"
    subprocess.run(SSH + ["termux-volume music 12"], timeout=30)
    era_muto, vol_pc = b.muto_pc(False), b.volume_pc(1.0)
    pc = subprocess.Popen(["ffmpeg", "-v", "quiet", "-y", "-f", "dshow", "-i", f"audio={b.PC_MIC}", "-t", str(durata),
                           "-ar", str(b.SR), "-ac", "1", os.path.join(b.OUT, "matrice_pc.wav")])
    time.sleep(3)
    for (chi, v), p in wav.items():  # in ordine: A56 1.0, 0.3, 0.1, A21s ..., PC ...
        suona(chi, p); time.sleep(1.2)
    pc.wait(timeout=durata + 30)
    b.muto_pc(era_muto); b.volume_pc(vol_pc)
    subprocess.run(SSH + [f"termux-volume music {vol_a56}", ], timeout=30)
    time.sleep(2)
    b.T(DEV, "termux-microphone-record -q"); b.T(DEV, "rm -f ~/sonno_bot/PAUSA"); b.riavvia_loop(DEV)
    subprocess.run(SSH + ["termux-microphone-record -q"], timeout=20); time.sleep(2)
    b.adb("pull", f21, os.path.join(b.OUT, "matrice_a21s.m4a"), dev=DEV)
    subprocess.run(["scp", "-q", "-P", "8022", f"{b.A56}:matrice_a56.m4a", os.path.join(b.OUT, "matrice_a56.m4a")],
                   check=True)


def tabella():
    rec = {"A56": "matrice_a56.m4a", "A21s": "matrice_a21s.m4a", "PC": "matrice_pc.wav"}
    righe = []
    for o, f in rec.items():
        r = b.decodifica(os.path.join(b.OUT, f))
        satura = np.mean(np.abs(r) > 0.98) > 1e-4
        for chi, x in BOCCHE.items():
            cc = np.abs(np.correlate(r, x, "valid"))
            fondo = np.median(cc) + 1e-12
            # i 3 volumi escono in ordine: prendo i 3 picchi piu' forti distinti e li ordino nel tempo
            pk, c2 = [], cc.copy()
            for _ in range(3):
                i = int(np.argmax(c2)); pk.append(i); c2[max(0, i - b.SR): i + b.SR] = 0
            pk.sort()
            snr = [20 * np.log10(cc[i] / fondo) for i in pk]
            righe.append((chi, o, snr, satura))
    print("bocca -> orecchio | segnale/fondo dB a volume 1.0 / 0.3 / 0.1 | orecchio satura")
    for chi, o, snr, sat in righe:
        print(f"{chi:5s} -> {o:5s} | " + " / ".join(f"{s:5.1f}" for s in snr) + f" | {'SI' if sat else 'no'}")
    print("regola: >20 dB = sente bene; 10-20 = al limite; <10 = non sente (quel picco e' rumore)")


def distanze():
    """BeepBeep per le 3 coppie. Emissioni = i 3 picchi del PROPRIO bip (clock di chi suona); negli altri orecchi:
    A56<->A21s = 0,97 m con dispersione 0,0 cm)."""
    rec = {o: b.decodifica(os.path.join(b.OUT, f)) for o, f in
           (("A56", "matrice_a56.m4a"), ("A21s", "matrice_a21s.m4a"), ("PC", "matrice_pc.wav"))}
    cc = {(o, e): np.abs(np.correlate(r, x, "valid")) for o, r in rec.items() for e, x in BOCCHE.items()}
    sub = lambda c, i: i + 0.5 * (c[max(i - 1, 0)] - c[min(i + 1, len(c) - 1)]) / (
        c[max(i - 1, 0)] - 2 * c[i] + c[min(i + 1, len(c) - 1)] + 1e-12)
    em = {}
    for e in BOCCHE:
        c, pk = cc[(e, e)].copy(), []
        for _ in range(3):
            i = int(np.argmax(c)); pk.append(sub(cc[(e, e)], i)); c[max(0, i - b.SR): i + b.SR] = 0
        em[e] = np.sort(pk) / b.SR
    t = {o: {} for o in rec}
    for o in rec:
        for e in BOCCHE:
            if o == e:
                t[o][e] = em[e]; continue
            c = cc[(o, e)]
            t0 = sub(c, int(np.argmax(c))) / b.SR  # il piu' forte = volume 1.0 = il primo della sequenza
            vals = []
            for ta in t0 + (em[e] - em[e][0]):
                lo = max(0, int((ta - 0.05) * b.SR)); j = lo + int(np.argmax(c[lo: int((ta + 0.05) * b.SR)]))
                vals.append(sub(c, j) / b.SR)
            t[o][e] = np.array(vals)
    for X, Y in (("A56", "A21s"), ("A56", "PC"), ("A21s", "PC")):
        d = b.C / 2 * ((t[X][Y] - t[X][X]) - (t[Y][Y] - t[Y][X]))
        print(f"{X:4s} <-> {Y:4s}: {np.round(d, 3)} m  media {np.mean(d):.2f} m  dispersione {np.std(d) * 100:.1f} cm")


if __name__ == "__main__":
    if sys.argv[1:] not in (["analizza"], ["distanze"]):
        registra()
    if sys.argv[1:] != ["distanze"]:
        tabella()
    distanze()
