"""
copriva quello debole dell'A56 -> distanze sbagliate; e a turno si puo' usare una banda sola, anche NON udibile).
   python turni.py [udibile|muto] [nome]   -> registra, analizza, salva in disposizioni/<nome>
   python turni.py analizza <cartella>     -> solo analisi
Ordine fisso: A56 a 0 s, A21s a PASSO, PC cassa SX a 2*PASSO, PC cassa DX a 3*PASSO. Ogni turno = 2 bip a 0 e 1 s
Distanza BeepBeep: ognuno registra se' e l'altro nello stesso file -> ritardi di avvio/registrazione si annullano.
"""
import os, shutil, subprocess, sys, threading, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import beepbeep as b
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # beepbeep aggiunge altre cartelle: C:/sonno_bot/prova.py vincerebbe
import prova
from scipy.signal import hilbert, correlate

CHIRP = {"udibile": (1000, 6500), "muto": (18000, 20500)}
DUR, OFF, PASSO = 0.1, (0.0, 1.0), 2.0
ORDINE = ("A56", "A21s", "PC", "PCdx")
PRIMO = 0.5  # soglia primo arrivo (frazione del picco del turno)
DISP = "C:/sonno_audio/array/disposizioni"
FILE = {"A56": "tur_a56.m4a", "A21s": "tur_a21s.m4a", "PCintel": "tur_pc_intel.wav"}


def chirp(modo):
    f0, f1 = CHIRP[modo]
    return b.chirp(f0, f1, DUR)


def treno(x):
    y = np.zeros(int((OFF[-1] + DUR + 0.05) * b.SR), np.float32)
    for o in OFF:
        y[int(o * b.SR): int(o * b.SR) + len(x)] += x
    return y


def scrivi(p, x, canali=1, dx=None):
    import wave
    st = np.zeros((len(x) + (int(PASSO * b.SR) if dx else 0) + int(0.2 * b.SR), canali), np.float32)
    st[:len(x), 0] = x
    if dx:
        st[int(PASSO * b.SR): int(PASSO * b.SR) + len(x), 1] = x
    with wave.open(p, "wb") as f:
        f.setnchannels(canali); f.setsampwidth(2); f.setframerate(b.SR)
        f.writeframes((st * 32767).astype("<i2").tobytes())


def registra(modo):
    t0 = time.time(); passo = lambda n: print(f"  {time.time() - t0:5.1f} s  {n}", flush=True)
    g21, g56 = prova.Guscio(prova.SSH21), prova.Guscio(prova.SSH56)
    prova.voci()
    x = treno(chirp(modo))
    p = os.path.join(b.OUT, f"tur_{modo}.wav"); scrivi(p, x)
    pc = os.path.join(b.OUT, f"tur_{modo}_pc.wav"); scrivi(pc, x, 2, dx=True)
    for dove in (b.A56, "192.0.2.184"):  # stesso file per i due telefoni
        subprocess.run(["scp", "-q", "-P", "8022", p, f"{dove}:tur.wav"], check=True)
    passo("file pronti")
    fine_pausa = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() + 180))
    g21.manda(f"echo {fine_pausa} > ~/sonno_bot/PAUSA; pkill -f '^bash .*home/[r]ec.sh'; termux-microphone-record -q; "
              f"rm -f ~/tur_a21s.m4a; termux-volume music 15; sleep 0.3; {prova.REC} $HOME/tur_a21s.m4a")
    g56.manda(f"termux-microphone-record -q; rm -f ~/tur_a56.m4a; termux-volume music 15; {prova.REC} $HOME/tur_a56.m4a")
    era_muto, vol_pc = b.muto_pc(False), b.volume_pc(1.0)
    pcs = [subprocess.Popen(["ffmpeg", "-v", "quiet", "-y", "-f", "dshow", "-i", f"audio={n}",
                             "-t", "60", "-ar", str(b.SR), "-ac", "1", os.path.join(b.OUT, FILE["PCintel"])], stdin=subprocess.PIPE)
           for n in [prova.r.nome_dshow(prova.r.MIC_INTEL)]]
    import winsound
    try:
        time.sleep(3)
        prova.parla("silenzio, test")
        g56.manda("play-audio tur.wav &"); time.sleep(PASSO)
        g21.manda("termux-media-player play ~/tur.wav"); time.sleep(PASSO)
        winsound.PlaySound(pc, winsound.SND_FILENAME)  # SX poi DX dopo PASSO
        time.sleep(0.5); passo("bip"); prova.parla("fine test, analizzo")
    finally:
        for q in pcs:
            try:
                q.communicate(b"q", timeout=10)
            except Exception:
                q.kill()
        g56.manda("termux-microphone-record -q"); g21.manda("termux-microphone-record -q; termux-volume music 12")
        g56.chiudi(); g21.chiudi()
        b.muto_pc(era_muto); b.volume_pc(vol_pc)
        time.sleep(1)
        prova.RIPRISTINO = threading.Thread(target=prova.ripristina_a21s); prova.RIPRISTINO.start()
    subprocess.run(["scp", "-q", "-P", "8022", f"{b.A56}:tur_a56.m4a", "192.0.2.184:tur_a21s.m4a", b.OUT], check=True)
    passo("file copiati")


def turni_in(r, x):
    """I 4 turni (A56, A21s, PC, PCdx) in una registrazione: pettine a 2 denti (0 e 1 s) sull'inviluppo della
    correlazione, i 4 migliori non sovrapposti, in ordine di tempo. Per ogni dente il PRIMO arrivo (>= PRIMO del max)."""
    cc = np.abs(hilbert(correlate(r, x, "valid", method="fft")))
    d = int(OFF[1] * b.SR)
    pett = cc[:-d] + cc[d:]
    scelti, p2 = [], pett.copy()
    for _ in ORDINE:
        i = int(np.argmax(p2)); scelti.append(i)
        p2[max(0, i - int(1.5 * b.SR)): i + int(1.5 * b.SR)] = 0
    scelti.sort()
    fondo, out = np.median(cc) + 1e-12, {}
    for chi, s0 in zip(ORDINE, scelti):
        tt, snr = [], []
        for o in (0, d):
            lo = max(0, s0 + o - 480); w = cc[lo: s0 + o + 480]
            j = lo + int(np.argmax(w >= PRIMO * w.max()))
            while j + 1 < len(cc) and cc[j + 1] > cc[j]:
                j += 1
            a, c0, c = cc[j - 1], cc[j], cc[min(j + 1, len(cc) - 1)]
            tt.append((j + 0.5 * (a - c) / (a - 2 * c0 + c + 1e-12)) / b.SR); snr.append(20 * np.log10(c0 / fondo))
        out[chi] = (np.array(tt), float(np.median(snr)))
    return out


def analizza(cartella, modo):
    x = chirp(modo); t = {}
    for o, f in FILE.items():
        p = os.path.join(cartella, f)
        if os.path.exists(p):
            for chi, (tt, snr) in turni_in(b.decodifica(p), x).items():
                t[o, chi] = tt
                print(f"{chi:4s} -> {o:8s}: SNR {snr:5.1f} dB  t {np.round(tt, 4)}")
    orecchio = {"A56": "A56", "A21s": "A21s", "PC": "PCintel"}
    ris = {}
    for X, Y in (("A56", "A21s"), ("A56", "PC"), ("A21s", "PC")):
        oX, oY = orecchio[X], orecchio[Y]
        if (oX, Y) in t and (oY, X) in t:
            dd = b.C / 2 * ((t[oX, Y] - t[oX, X]) - (t[oY, Y] - t[oY, X]))
            ris[f"{X}-{Y}"] = dd
            print(f"{X}-{Y}: {np.median(dd):.3f} m  (bip {np.round(dd, 3)})  scarto fra i 2 bip {abs(dd[0] - dd[1]) * 100:.1f} cm")
    return ris


# ---------------------------------------------------------------------------------------------------------------
# suona il suo file con i bip ai suoi turni. Chi e' chi = ordine nel tempo (serve ritardo di avvio < S/2).
# Dal PC Intel misuro il ritardo di avvio di ognuno -> salvato -> il giro dopo parte compensato (sincronia progressiva).
S = 1.2
SESSIONE = 3600


def copia_quando_chiusi(nomi=("tur_a56.m4a", "tur_a21s.m4a")):
    """(nota rimossa)"""
    for host, f in ((b.A56, nomi[0]), ("192.0.2.184", nomi[1])):
        cmd = f"a=0; for i in 1 2 3 4 5 6 7 8 9 10; do s=$(stat -c %s ~/{f} 2>/dev/null); [ \"$s\" = \"$a\" ] && [ -n \"$s\" ] && break; a=$s; sleep 0.5; done; echo $s"
        subprocess.run(["ssh", "-p", "8022", "-o", "ConnectTimeout=8", host, cmd], stdin=subprocess.DEVNULL, capture_output=True, timeout=30)
    subprocess.run(["scp", "-q", "-P", "8022", f"{b.A56}:{nomi[0]}", f"192.0.2.184:{nomi[1]}", b.OUT], check=True)


def carica_se_cambiato(locale, remoto):
    import hashlib
    firma = hashlib.md5(open(locale, "rb").read()).hexdigest(); segno = locale + "." + remoto.split(":")[0] + ".caricato"
    if os.path.exists(segno) and open(segno).read() == firma:
        return
    subprocess.run(["scp", "-q", "-P", "8022", locale, remoto], check=True); open(segno, "w").write(firma)
GIRO = ("A56", "A21s", "PC", "PCdx") * 2
AVVIO = os.path.join(b.OUT, "avvio_pingpong.json")


# turni larghi S = 1,2 s (un avvio tardi di 0,65 s con S = 0,7 scambiava i turni).
def chirp_di(chi, modo="udibile"):
    return chirp(modo)


def file_pingpong(modo):
    n = int((len(GIRO) * S + 0.5) * b.SR)
    per = {k: np.zeros((n, 2 if k == "PC" else 1), np.float32) for k in ("A56", "A21s", "PC")}
    for i, chi in enumerate(GIRO):
        a = int(i * S * b.SR); x = chirp_di(chi, modo)
        if chi == "PCdx":
            per["PC"][a:a + len(x), 1] = x
        else:
            per[chi][a:a + len(x), 0] = x
    import wave
    for k, st in per.items():
        with wave.open(os.path.join(b.OUT, f"pp_{k}.wav"), "wb") as f:
            f.setnchannels(st.shape[1]); f.setsampwidth(2); f.setframerate(b.SR)
            f.writeframes((st * 32767).astype("<i2").tobytes())


def pingpong(modo="udibile", nome="pingpong"):
    import json, winsound
    t0 = time.time(); passo = lambda n: print(f"  {time.time() - t0:5.1f} s  {n}", flush=True)
    g21, g56 = prova.Guscio(prova.SSH21), prova.Guscio(prova.SSH56)
    prova.voci(); file_pingpong(modo)
    # accavallare i turni; per le distanze la sincronia di partenza non serve
    rit = {"A56": 0.0, "A21s": 0.0, "PC": 0.0}
    passo("file pronti")
    fine_pausa = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() + SESSIONE))
    g21.manda(f"echo {fine_pausa} > ~/sonno_bot/PAUSA; pkill -f '^bash .*home/[r]ec.sh'; termux-microphone-record -q; "
              f"rm -f ~/tur_a21s.m4a; termux-volume music 15; sleep 0.3; {prova.REC} $HOME/tur_a21s.m4a")
    g56.manda(f"termux-microphone-record -q; rm -f ~/tur_a56.m4a; termux-volume music 15; {prova.REC} $HOME/tur_a56.m4a")
    t_rec = time.time()
    era_muto, vol_pc = b.muto_pc(False), b.volume_pc(1.0)
    pcs = subprocess.Popen(["ffmpeg", "-v", "quiet", "-y", "-f", "dshow", "-i", f"audio={prova.r.nome_dshow(prova.r.MIC_INTEL)}",
                            "-t", "60", "-ar", str(b.SR), "-ac", "1", os.path.join(b.OUT, FILE["PCintel"])], stdin=subprocess.PIPE)
    for k, dove in (("A56", b.A56), ("A21s", "192.0.2.184")):
        carica_se_cambiato(os.path.join(b.OUT, f"pp_{k}.wav"), f"{dove}:pp.wav")
    avvia = {"A56": lambda: g56.manda("play-audio pp.wav &"), "A21s": lambda: g21.manda("termux-media-player play ~/pp.wav"),
             "PC": lambda: winsound.PlaySound(os.path.join(b.OUT, "pp_PC.wav"), winsound.SND_FILENAME | winsound.SND_ASYNC)}
    try:
        time.sleep(max(0.0, t_rec + 3 - time.time())); prova.parla("silenzio, test")
        tb, mx = time.time(), max(rit.values())
        for chi in sorted(avvia, key=lambda c: -rit[c]):  # il piu' lento parte per primo
            time.sleep(max(0.0, tb + (mx - rit[chi]) - time.time())); avvia[chi]()
        time.sleep(len(GIRO) * S + 0.3); passo("bip"); prova.parla("fine test, analizzo")
    finally:
        try:
            pcs.communicate(b"q", timeout=10)
        except Exception:
            pcs.kill()
        g56.manda("termux-microphone-record -q"); g21.manda("termux-microphone-record -q; termux-volume music 12")
        g56.chiudi(); g21.chiudi(); b.muto_pc(era_muto); b.volume_pc(vol_pc); time.sleep(1)
    copia_quando_chiusi()
    passo("file copiati")
    d = os.path.join(DISP, nome); os.makedirs(d, exist_ok=True)
    for f in FILE.values():
        shutil.copy(os.path.join(b.OUT, f), d)
    return analizza_pp(d, modo, rit)


def bip_in(r, x, n):
    """Gli n bip piu' forti distanti >= S/2, in ordine di tempo, ognuno al PRIMO arrivo (picco, poi parabola)."""
    from scipy.signal import find_peaks
    cc = np.abs(hilbert(correlate(r, x, "valid", method="fft")))
    pk, pr = find_peaks(cc, distance=int(S / 2 * b.SR), height=0)
    pk = np.sort(pk[np.argsort(pr["peak_heights"])[-n:]])
    out = []
    for i in pk:
        lo = max(0, i - 480); w = cc[lo: i + 20]
        j = lo + int(np.argmax(w >= PRIMO * cc[i]))
        while j + 1 < len(cc) and cc[j + 1] > cc[j]:
            j += 1
        a, c0, c = cc[j - 1], cc[j], cc[min(j + 1, len(cc) - 1)]
        out.append((j + 0.5 * (a - c) / (a - 2 * c0 + c + 1e-12)) / b.SR)
    return np.array(out)


def analizza_pp(cartella, modo="udibile", rit=None):
    import json
    x = chirp(modo); t = {}
    for o, f in FILE.items():
        tt = bip_in(b.decodifica(os.path.join(cartella, f)), x, len(GIRO))  # tutti i bip, in ordine di tempo
        for chi in set(GIRO):
            t[o, chi] = tt[[i for i, c in enumerate(GIRO) if c == chi]]
    orecchio = {"A56": "A56", "A21s": "A21s", "PC": "PCintel"}
    ris = {}
    for X, Y in (("A56", "A21s"), ("A56", "PC"), ("A21s", "PC")):
        oX, oY = orecchio[X], orecchio[Y]
        # ogni bip di Y con ogni bip di X (stessi bip nei due file) -> mediana
        dd = np.array([b.C / 2 * ((ty - tx) - (ty2 - tx2)) for tx, tx2 in zip(t[oX, X], t[oY, X])
                       for ty, ty2 in zip(t[oX, Y], t[oY, Y])])
        ris[X, Y] = float(np.median(dd)); ris[X, Y, "std"] = float(1.4826 * np.median(np.abs(dd - np.median(dd))))
        print(f"{X}-{Y}: {np.median(dd):.3f} m  dispersione {ris[X, Y, 'std'] * 100:.1f} cm  ({len(dd)} coppie)")
    # ritardo di avvio visto dal PC Intel: arrivo - turno previsto - volo; relativo al PC
    volo = {"A56": ris["A56", "PC"] / b.C, "A21s": ris["A21s", "PC"] / b.C, "PC": 0.0}
    prima = {chi: GIRO.index(chi) * S for chi in ("A56", "A21s", "PC")}
    lat = {chi: float(t["PCintel", chi][0] - prima[chi] - volo[chi]) for chi in prima}
    lat = {chi: v - lat["PC"] for chi, v in lat.items()}
    print("ritardo di avvio rispetto al PC (ms):", {k: round(v * 1000) for k, v in lat.items()})
    rit = rit or {"A56": 0.0, "A21s": 0.0, "PC": 0.0}
    nuovo = {k: rit[k] + lat[k] for k in lat}; m = min(nuovo.values())
    json.dump({k: v - m for k, v in nuovo.items()}, open(AVVIO, "w"))
    return ris, lat


def calibra(max_giri=3, soglia_cm=1.0, soglia_ms=100):
    """
    sentono tutti in modo coerente (dispersione < soglia_cm) e partono insieme (ritardo < soglia_ms)."""
    for g in range(1, max_giri + 1):
        ris, lat = pingpong("udibile", f"calibra_{g}")
        disp = max(v for k, v in ris.items() if len(k) == 3) * 100
        ritardo = max(abs(v) for v in lat.values()) * 1000
        ok = disp < soglia_cm
        try:
            grafico_audio(os.path.join(DISP, f"calibra_{g}"), f"audio giro {g}")
        except Exception as e:
            print("grafico non inviato:", e)
        print(f"giro {g}: dispersione max {disp:.2f} cm, ritardo max {ritardo:.0f} ms -> {'CALIBRATO' if ok else 'rifaccio'}")
        if ok:
            prova.parla("calibrato"); return True
    prova.parla("non calibrato"); return False


def grafico_audio(cartella, titolo, modo="udibile"):
    """
    sente ogni bip (colore = chi l'ha fatto). E' esattamente cio' che usa il calcolo delle distanze."""
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from scipy.signal import hilbert
    BG, BIANCO = "#141416", "#d4d4d8"; COL = {"A56": "#e63946", "A21s": "#4ea8de", "PC": "#f4a261", "PCdx": "#f4a261"}
    NOMI = {"A56": "tuo telefono", "A21s": "A21s", "PCintel": "PC"}
    x = chirp(modo)
    fig, axs = plt.subplots(3, 1, figsize=(8, 10), facecolor=BG, sharex=False)
    for ax, (o, f) in zip(axs, FILE.items()):
        r = b.decodifica(os.path.join(cartella, f)); tt = bip_in(r, x, len(GIRO))
        cc = np.abs(hilbert(correlate(r, x, "valid", method="fft"))); cc = cc / cc.max()
        g1 = len(GIRO) // 2; tt, giro1 = tt[:g1], GIRO[:g1]
        t = np.arange(len(cc)) / b.SR; a0, a1 = max(0, tt[0] - 0.5), tt[-1] + 0.5
        k = (t >= a0) & (t <= a1)
        ax.set_facecolor(BG); ax.plot(t[k], 20 * np.log10(cc[k] + 1e-4), color=BIANCO, lw=0.5, alpha=0.7)
        for ti, chi in zip(tt, giro1):
            j = int(ti * b.SR); pk = cc[j: j + 480].max()
            ax.plot([ti], [20 * np.log10(pk / 2 + 1e-4)], "o", color=COL[chi], ms=7)
            ax.axvline(ti, color=COL[chi], lw=1, alpha=0.5)
            nome = {"PC": "PC sx", "PCdx": "PC dx"}.get(chi, NOMI.get(chi, chi))
            ax.text(ti + 0.03, 4, f"{nome}\n{ti:.4f} s",
                    color=COL[chi], fontsize=8, va="bottom", ha="left")
        ax.set_ylim(-60, 12); ax.set_title(f"orecchio: {NOMI[o]}  (orologio suo, s)", color=BIANCO, fontsize=12)
        ax.tick_params(colors=BIANCO); [sp.set_color("#3a3a40") for sp in ax.spines.values()]
        ax.set_ylabel("dB", color=BIANCO)
    fig.suptitle(titolo, color=BIANCO, fontsize=16); fig.tight_layout(rect=(0, 0, 1, 0.96))
    out = os.path.join(b.OUT, "grafici", "audio_giro.png"); fig.savefig(out, facecolor=BG, dpi=110); plt.close(fig)
    sys.path.insert(0, "C:/sonno_bot")
    import manda_valutazione as mv
    mv.file("sendPhoto", "photo", out, f"🎧 {titolo}: quando ogni orecchio sente ogni bip (colore = chi suona)")


def grafico(ris, titolo):
    """(nota rimossa)"""
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    BG, ROSSO, BIANCO = "#141416", "#e63946", "#d4d4d8"
    a, c, bb = ris["A56", "PC"], ris["A21s", "PC"], ris["A56", "A21s"]
    xa = (a ** 2 - bb ** 2 + c ** 2) / (2 * c)
    P = {"PC": np.array([0.0, 0.0]), "A21s": np.array([c, 0.0]), "tuo telefono": np.array([xa, np.sqrt(max(a ** 2 - xa ** 2, 0))])}
    fig = plt.figure(figsize=(8, 10), facecolor=BG); ax = fig.add_axes([0.05, 0.15, 0.9, 0.65])
    ax.set_facecolor(BG); ax.set_aspect("equal"); ax.axis("off")
    ax.set_xlim(-0.25 * c, 1.25 * c); ax.set_ylim(-0.55 * c, 0.55 * c)
    lati = ((("PC", "tuo telefono"), ("A56", "PC"), 1), (("tuo telefono", "A21s"), ("A56", "A21s"), 1), (("PC", "A21s"), ("A21s", "PC"), -1))
    for (n1, n2), k, lato in lati:
        p1, p2 = P[n1], P[n2]; ax.plot(*zip(p1, p2), color=ROSSO, lw=2.5)
        m = (p1 + p2) / 2 + [0, lato * 0.09 * c]
        ax.text(*m, f"{ris[k]:.3f} m  (±{ris[k + ('std',)] * 100:.1f} cm)", color=BIANCO, ha="center", va="center", fontsize=14)
    for n, p in P.items():
        ax.plot(*p, "o", color=BIANCO, ms=16)
        ax.text(p[0], p[1] + (0.2 if n == "tuo telefono" else -0.2) * c, n, color=BIANCO, ha="center", va="center", fontsize=16)
    fig.text(0.5, 0.9, titolo.split(":")[0], ha="center", color=BIANCO, fontsize=24)
    fig.text(0.5, 0.85, titolo.split(":", 1)[-1].strip(), ha="center", color=BIANCO, fontsize=13, alpha=0.8)
    fig.text(0.5, 0.08, f"controllo: {a:.3f} + {bb:.3f} = {a + bb:.3f} m  vs  PC-A21s {c:.3f} m", ha="center", color=BIANCO, fontsize=12, alpha=0.7)
    out = os.path.join(b.OUT, "grafici", "triangolo_giro.png"); fig.savefig(out, facecolor=BG, dpi=110); plt.close(fig)
    sys.path.insert(0, "C:/sonno_bot")
    import manda_valutazione as mv
    mv.file("sendPhoto", "photo", out, f"📐 {titolo}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] in (["calibra"], ["mcd"]):
        for f in ("calibrato", "non calibrato"):
            if f not in prova.FRASI:
                prova.FRASI.append(f)
        prova.voci(); calibra(); sys.exit()
    if a[:1] == ["pingpong"]:
        pingpong(a[1] if len(a) > 1 else "udibile", a[2] if len(a) > 2 else "pingpong"); sys.exit()
    if a[:1] == ["fine"]:  # fine sessione: registrazione notturna A21s di nuovo attiva
        prova.ripristina_a21s(); sys.exit()
    if a[:1] == ["analizza"]:
        analizza(os.path.join(DISP, a[1]), a[2] if len(a) > 2 else "muto"); sys.exit()
    modo = a[0] if a else "muto"; nome = a[1] if len(a) > 1 else f"turni_{modo}"
    registra(modo)
    d = os.path.join(DISP, nome); os.makedirs(d, exist_ok=True)
    for f in FILE.values():
        if os.path.exists(os.path.join(b.OUT, f)):
            shutil.copy(os.path.join(b.OUT, f), d)
    analizza(d, modo)
    prova.RIPRISTINO.join()
