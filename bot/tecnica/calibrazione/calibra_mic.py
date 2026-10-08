"""Calibrazione del microfono A21s col telefono PERSONALE che suona suoni noti, RIPETUTI (la media toglie il rumore).
   python calibra_mic.py prepara            -> C:\\sonno_audio\\calibra\\calibra.wav + scaletta.json
   python calibra_mic.py suona IP_TELEFONO  -> copia sul telefono personale (ssh Termux :8022), lo suona, l'A21s registra
   python calibra_mic.py analizza           -> risposta in frequenza (grafico) + pezzi etichettati in C:\\sonno_audio\\cal
Telefono personale: Termux con openssh + play-audio (mpv li era rotto), chiave del PC in authorized_keys. Solo col suo permesso.
"""
import json, os, subprocess, sys, time
import numpy as np
sys.path.insert(0, r"C:\sonno_tex")
import sonno_audio  # noqa: F401  -- toglie le finestre console di ffmpeg/ssh/adb

SR, OUT, CAL = 16000, r"C:\sonno_audio\calibra", r"C:\sonno_audio\cal"
PH = "/sdcard/Recordings/sonno_cal"
VOLUMI = [1.0, 0.3, 0.1]   # ~ vicino / medio / lontano
REP = 4                    # ripetizioni per volume: la media su REP sweep toglie il rumore casuale
F0, F1, TSW = 60, 7900, 4.0
NOME = sys.argv[3] if len(sys.argv) > 3 else (sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] in ("analizza", "valuta") else "letto")


def decodifica(path):
    raw = subprocess.run(["ffmpeg", "-v", "quiet", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def sweep():
    t = np.arange(int(TSW * SR)) / SR
    k = np.log(F1 / F0)
    return 0.8 * np.sin(2 * np.pi * F0 * TSW / k * (np.exp(t * k / TSW) - 1)).astype(np.float32)


def marcatore():
    t = np.arange(int(0.2 * SR)) / SR
    b = 0.8 * np.sin(2 * np.pi * 1000 * t)
    z = np.zeros(int(0.3 * SR))
    return np.concatenate([b, z, b, z, b, np.zeros(SR)]).astype(np.float32)


def suoni_veri():
    """(nota rimossa)"""
    s = {}
    for f in sorted(os.listdir(CAL)):
        lab = f.split("__")[0]
        if lab in ("russa", "respiro") and f.endswith(".wav") and "__calibra" not in f:
            w = decodifica(os.path.join(CAL, f))[: 8 * SR]
            s.setdefault(lab, w / (np.abs(w).max() + 1e-9) * 0.8)
    if os.environ.get("EQ"):  # compensa l'altoparlante del telefono (niente bassi): inversa della curva misurata
        s = {k: eq_inversa(w) for k, w in s.items()}
    return s


def eq_inversa(w, max_db=20):
    """Alza le bande che il test 'letto' ha sentito deboli (tetto +20 dB, l'altoparlante satura)."""
    bande, y = np.load(os.path.join(OUT, "curva_letto.npy"))
    X, fr = np.fft.rfft(w), np.fft.rfftfreq(len(w), 1 / SR)
    g = np.clip(-np.interp(fr, bande, y), 0, max_db)
    x = np.fft.irfft(X * 10 ** (g / 20), len(w))
    return (x / (np.abs(x).max() + 1e-9) * 0.8).astype(np.float32)


def prepara():
    os.makedirs(OUT, exist_ok=True)
    pezzi, scaletta, pos = [marcatore()], [], len(marcatore())
    def metti(lab, w, vol):
        nonlocal pos
        pezzi.append(w * vol); scaletta.append({"lab": lab, "vol": vol, "da": pos, "a": pos + len(w)}); pos += len(w)
        pezzi.append(np.zeros(SR, np.float32)); pos += SR
    veri = suoni_veri()
    for vol in VOLUMI:
        for _ in range(REP):
            metti("sweep", sweep(), vol)
            for lab, w in veri.items():
                metti(lab, w, vol)
            metti("ambiente", np.zeros(3 * SR, np.float32), vol)
    scrivi(pezzi, scaletta, f"suoni veri: {list(veri)}")


def prepara_musica():
    """Musica tipo quella che ascolta di notte (slowed+reverb) da sola e con sotto il suo russare/respiro VERI."""
    os.makedirs(OUT, exist_ok=True)
    pezzi, scaletta, pos = [marcatore()], [], len(marcatore())
    def metti(lab, w):
        nonlocal pos
        pezzi.append(w.astype(np.float32)); scaletta.append({"lab": lab, "vol": 1.0, "da": pos, "a": pos + len(w)})
        pos += len(w); pezzi.append(np.zeros(SR, np.float32)); pos += SR
    norm = lambda w: w / (np.abs(w).max() + 1e-9) * 0.8
    raw = r"C:\sonno_audio\raw"
    russa = norm(np.concatenate([decodifica(os.path.join(raw, f"russa_20260928_044{i}.m4a")) for i in (1, 2, 3)]))
    respiro = norm(decodifica(os.path.join(raw, "russa_20260928_0938.m4a")))
    L = 25 * SR
    giro = lambda w: np.resize(w, L)
    metti("sweep", sweep()); metti("sweep_giu", sweep()[::-1])
    metti("russa", giro(russa)); metti("respiro", giro(respiro)); metti("ambiente", np.zeros(5 * SR))
    for f in sorted(os.listdir(os.path.join(OUT, "musica"))):
        m = decodifica(os.path.join(OUT, "musica", f)); m = norm(m[len(m) // 3: len(m) // 3 + L])  # pezzo centrale
        for lab, w in (("musica", m), ("musica+russa", m * .5 + giro(russa)),
                       ("musica+russa_piano", m * .5 + giro(russa) * .3), ("musica+respiro", m * .5 + giro(respiro))):
            metti(lab, norm(w) if lab != "musica" else w)
    scrivi(pezzi, scaletta, "musica")


def scrivi(pezzi, scaletta, nota):
    tutto = np.concatenate(pezzi)
    import wave
    with wave.open(os.path.join(OUT, "calibra.wav"), "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR)
        f.writeframes((np.clip(tutto, -1, 1) * 32767).astype("<i2").tobytes())
    json.dump(scaletta, open(os.path.join(OUT, "scaletta.json"), "w"))
    print(f"calibra.wav {len(tutto) / SR / 60:.1f} min, {len(scaletta)} pezzi, {nota}")


def suona(ip):
    from sonno_audio import adb, device
    from cal_sessione import T
    dev, durata = device(), int(len(decodifica(os.path.join(OUT, "calibra.wav"))) / SR) + 10
    ssh = ["ssh", "-p", "8022", "-o", "StrictHostKeyChecking=accept-new", ip]
    subprocess.run(["scp", "-P", "8022", os.path.join(OUT, "calibra.wav"), f"{ip}:calibra.wav"], check=True)
    # pausa del bot (scade da sola fra 15'), senno' tieni_vivo riavvia rec.sh che fa "-q" e taglia la registrazione
    from datetime import datetime, timedelta
    T(dev, f"echo {(datetime.now() + timedelta(minutes=15)).isoformat(timespec='seconds')} > ~/sonno_bot/PAUSA")
    T(dev, 'pkill -f "^bash .*home/rec.sh"; termux-microphone-record -q')
    adb("shell", f"mkdir -p {PH}", dev=dev)
    fr = f"{PH}/calibra_{NOME}_{int(time.time())}.m4a"  # nome nuovo: termux-microphone-record NON sovrascrive
    T(dev, f"termux-microphone-record -e aac -b {os.environ.get('KBPS', 128)} -r 16000 -c 1 -l {durata} -f {fr}")
    time.sleep(3)
    if '"isRecording": true' not in T(dev, "termux-microphone-record -i"):
        T(dev, "rm -f ~/sonno_bot/PAUSA"); sys.exit("A21s non registra: test annullato")
    vol = os.environ.get("VOL")  # volume VERO del telefono (0-15), non solo digitale
    subprocess.run(ssh + [(f"termux-volume music {vol}; " if vol else "") + "play-audio calibra.wav"], timeout=durata + 30)
    time.sleep(5)
    T(dev, "termux-microphone-record -q")
    time.sleep(2)
    T(dev, "rm -f ~/sonno_bot/PAUSA")
    from cal_sessione import riavvia_loop
    riavvia_loop(dev)
    adb("pull", fr, os.path.join(OUT, f"registrato_{NOME}.m4a"), dev=dev)
    print("registrato:", os.path.join(OUT, f"registrato_{NOME}.m4a"))


def analizza():
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    scaletta = json.load(open(os.path.join(OUT, "scaletta.json")))
    rec = decodifica(os.path.join(OUT, f"registrato_{NOME}.m4a"))
    m = marcatore()[: int(1.2 * SR)]
    cerca = rec[: 30 * SR]
    cc = np.correlate(cerca, m, "valid")  # ponytail: correlazione diretta, basta per 30 s
    off = int(np.argmax(np.abs(cc)))
    print(f"marcatore trovato a {off / SR:.2f} s")
    if off + scaletta[-1]["a"] > len(rec):
        sys.exit(f"registrazione troppo corta ({len(rec) / SR:.0f} s): niente pezzi, rifai 'suona'")
    n, bande = 4096, np.geomspace(F0, F1, 40)
    fr = np.fft.rfftfreq(n, 1 / SR)
    ref = np.abs(np.fft.rfft(sweep()[: n * (len(sweep()) // n)].reshape(-1, n), axis=1)) ** 2
    fig, ax = plt.subplots(figsize=(8, 10))  # 4:5
    for vol in VOLUMI:
        sp = []
        for p in scaletta:
            if p["lab"] == "sweep" and p["vol"] == vol:
                seg = rec[off + p["da"]: off + p["a"]]
                seg = seg[: n * (len(seg) // n)].reshape(-1, n)
                sp.append((np.abs(np.fft.rfft(seg, axis=1)) ** 2).sum(0))
        media = np.mean(sp, 0) / (ref.sum(0) * vol ** 2 + 1e-12)   # media sulle REP ripetizioni
        db = 10 * np.log10(media + 1e-12)
        y = [db[(fr >= a) & (fr < b)].mean() for a, b in zip(bande[:-1], bande[1:])]
        ax.semilogx(bande[:-1], np.array(y) - np.nanmax(y), label=f"volume {vol}")
        if vol == 1.0 and NOME == "letto":
            np.save(os.path.join(OUT, "curva_letto.npy"), np.array([bande[:-1], np.array(y) - np.nanmax(y)]))
    ax.set(xlabel="Hz", ylabel="dB (0 = banda piu' forte)", title="Microfono A21s: cosa sente di ogni frequenza")
    ax.axvspan(80, 1000, alpha=.1, label="zona russamento")
    ax.legend(); ax.grid(alpha=.3)
    fig.savefig(os.path.join(OUT, f"risposta_{NOME}.png"), dpi=135)
    extra(rec, off, scaletta)
    # pezzi etichettati (verita' certa) -> cal_train.py li usa per il modello personale
    import wave
    for i, p in enumerate(scaletta):
        if p["lab"] == "sweep":
            continue
        seg = rec[off + p["da"]: off + p["a"]]
        with wave.open(os.path.join(CAL, f"{p['lab']}__calibra_{NOME}__v{p['vol']}_{i:03d}.wav"), "wb") as f:
            f.setnchannels(1); f.setsampwidth(2); f.setframerate(SR)
            f.writeframes((np.clip(seg, -1, 1) * 32767).astype("<i2").tobytes())
    print("risposta.png + pezzi in", CAL, "-> ora: python cal_train.py")


def extra(rec, off, scaletta):
    """AGC (livello registrato vs suonato), rumore di fondo, riflessi (risposta all'impulso Farina) -> report.txt"""
    import matplotlib.pyplot as plt
    seg = lambda p, coda=0: rec[off + p["da"]: off + p["a"] + coda]
    db = lambda w: 20 * np.log10(np.sqrt(np.mean(w ** 2)) + 1e-9)
    righe, fondo = [], np.median([db(seg(p)) for p in scaletta if p["lab"] == "ambiente"])
    righe.append(f"rumore di fondo (PC ecc.): {fondo:.1f} dBFS")
    for lab in ("sweep", "russa", "respiro"):
        liv = {v: np.mean([db(seg(p)) for p in scaletta if p["lab"] == lab and p["vol"] == v]) for v in VOLUMI}
        if not all(np.isfinite(list(liv.values()))):
            continue
        atteso = {v: 20 * np.log10(v) for v in VOLUMI}
        righe.append(f"{lab}: " + "  ".join(f"vol {v}: {liv[v]:.1f} dB (sopra fondo {liv[v] - fondo:+.1f}, "
                                            f"scende {liv[v] - liv[1.0]:+.1f} atteso {atteso[v]:+.1f})" for v in VOLUMI))
    righe.append("AGC: se 'scende' e' molto meno di 'atteso', il telefono alza da solo il volume (AGC attivo).")
    # Farina: filtro inverso = sweep rovesciato con inviluppo che compensa l'energia per ottava
    t = np.arange(int(TSW * SR)) / SR
    inv = sweep()[::-1] * np.exp(-t * np.log(F1 / F0) / TSW)
    sw = [seg(p, SR) for p in scaletta if p["lab"] == "sweep" and p["vol"] == 1.0]
    if sw:
        m = np.mean([w[: min(map(len, sw))] for w in sw], 0)  # media delle ripetizioni = meno rumore
        ir = np.convolve(m, inv)
        i0 = int(np.argmax(np.abs(ir)))
        h = np.abs(ir[i0 - 80: i0 + int(0.3 * SR)])
        h = 20 * np.log10(h / h.max() + 1e-9)
        coda = np.flatnonzero(h[80:] > -30)
        righe.append(f"riflessi: energia sopra -30 dB fino a {coda[-1] / SR * 1000:.0f} ms dal suono diretto "
                     f"(stanza/letto: <50 ms asciutto, >150 ms eco)")
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.plot((np.arange(len(h)) - 80) / SR * 1000, h); ax.set(xlabel="ms", ylabel="dB", ylim=(-60, 2),
                                                               title="Riflessi: suono diretto (0) e echi dopo")
        ax.grid(alpha=.3); fig.savefig(os.path.join(OUT, f"riflessi_{NOME}.png"), dpi=135)
    open(os.path.join(OUT, f"report_{NOME}.txt"), "w", encoding="utf-8").write("\n".join(righe))
    print("\n".join(righe))


def valuta():
    """Per ogni pezzo: cosa ci sente YAMNet (come sonno_tel: russa>0.2, musica>0.3)."""
    import onnxruntime as ort
    from collections import defaultdict
    from sonno_audio import MODEL
    sess = ort.InferenceSession(MODEL)
    scaletta = json.load(open(os.path.join(OUT, "scaletta.json")))
    rec = decodifica(os.path.join(OUT, f"registrato_{NOME}.m4a"))
    off = int(np.argmax(np.abs(np.correlate(rec[: 30 * SR], marcatore()[: int(1.2 * SR)], "valid"))))
    R = defaultdict(list)
    for p in scaletta:
        sc = sess.run(None, {"waveform": rec[off + p["da"]: off + p["a"]]})[0]
        R[p["lab"]].append([(sc[:, 38] > .2).mean() * 100, sc[:, 38].max(), (sc[:, 132] > .3).mean() * 100,
                            sc[:, 36].max(), sc[:, 0].max()])
    righe = [f"{NOME}: pezzo -> % frame russa | russa max | % frame musica | respiro max | voce max"]
    righe += [f"{k:20s} {' '.join(f'{x:6.2f}' for x in np.mean(v, 0))}" for k, v in R.items()]
    open(os.path.join(OUT, f"valuta_{NOME}.txt"), "w", encoding="utf-8").write("\n".join(righe))
    print("\n".join(righe))


if __name__ == "__main__":
    suona(sys.argv[2]) if sys.argv[1] == "suona" else {"prepara": prepara, "analizza": analizza, "musica": prepara_musica, "valuta": valuta}[sys.argv[1]]()
