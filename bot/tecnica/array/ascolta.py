"""
   python ascolta.py [secondi] [nome]  -> ping-pong, <secondi> di rumori suoi, ping-pong; poi posizione di ogni rumore
   python ascolta.py analizza <nome>
Orologi: il ping-pong (stesso chirp, turni noti) da' in OGNI registrazione l'istante dei bip di tutti -> offset di ogni
orologio rispetto al PC, all'inizio e alla fine (deriva lineare). Rumori: attacchi nel file del PC, TDOA con GCC-PHAT
verso A56 e A21s, posizione = punto della griglia che meglio spiega le 2 differenze di arrivo.
"""
import json, os, shutil, subprocess, sys, threading, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import turni as T
b, prova = T.b, T.prova

UN_GIRO = ("A56", "A21s", "PC", "PCdx", "A21s", "A56")
T.S = 0.7
CIAK_S = 5.0
RESIDUO_OK = 5.0  # cm: sotto = rumore sentito in modo coerente da tutti
VICINO = 0.3  # m
SIGMA_TDOA = 0.0002  # s: errore tipico di una differenza di arrivo (verifica_rumori.py, GCC-PHAT)
ERR_MAX_CM = 50


def file_ciak(secondi):
    import wave
    x = T.chirp("muto"); n = int(secondi * b.SR); y = np.zeros(n, np.float32)
    for k in range(int(secondi / CIAK_S)):
        a = int((0.5 + k * CIAK_S) * b.SR); y[a:a + len(x)] = x
    p = os.path.join(b.OUT, "ciak.wav")
    with wave.open(p, "wb") as f:
        f.setnchannels(1); f.setsampwidth(2); f.setframerate(b.SR); f.writeframes((y * 32767).astype("<i2").tobytes())
    return p


def ciak_in(r, t0, t1):
    """istanti dei ciak (chirp muto) fra t0 e t1: picchi distanti > CIAK_S/2 sopra 10x la mediana."""
    from scipy.signal import hilbert, correlate, find_peaks
    a = int(t0 * b.SR); x = T.chirp("muto")
    cc = np.abs(hilbert(correlate(r[a:int(t1 * b.SR)], x, "valid", method="fft")))
    pk, _ = find_peaks(cc, distance=int(CIAK_S / 2 * b.SR), height=10 * np.median(cc))
    return pk / b.SR + t0, cc[pk] / np.median(cc)
ORECCHI = {"A56": "tur_a56.m4a", "A21s": "tur_a21s.m4a", "PC": "tur_pc_intel.wav"}
D_PC_SELF = 0.27  # m: cassa sx -> mic Intel sopra lo schermo (HARDWARE.md)


GUIDA = [
    ("finestra aperta, rumore fuori dalla finestra", 12, 8),
    ("chiudi la finestra, stesso rumore fuori", 10, 8),
    ("tavolo da lavoro, colpi sul tavolo", 8, 6),
    ("centro della stanza, batti le mani", 8, 6),
    ("sul letto, respira e russa come quando dormi", 8, 10),
    ("porta chiusa, bussa sulla porta", 10, 6),
    ("porta aperta, batti le mani fuori dalla porta", 10, 6),
]


def registra(secondi, nome, guida=None):
    import winsound
    T.GIRO = UN_GIRO; T.file_pingpong("udibile")
    g21, g56 = prova.Guscio(prova.SSH21), prova.Guscio(prova.SSH56)
    prova.voci()
    for f in ["ora fai i rumori e dimmi dove sei", "ultimo ping pong", "via", "stop"] + [g[0] for g in (guida or [])]:
        if f not in prova.FRASI:
            prova.FRASI.append(f)
    prova.voci()
    for k, dove in (("A56", b.A56), ("A21s", "192.0.2.184")):
        T.carica_se_cambiato(os.path.join(b.OUT, f"pp_{k}.wav"), f"{dove}:pp.wav")
    fine_pausa = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(time.time() + T.SESSIONE))
    lim = int((secondi + 40) * 1000)
    rec = prova.REC.replace("--ei limit 90000", f"--ei limit {lim}")
    g21.manda(f"echo {fine_pausa} > ~/sonno_bot/PAUSA; pkill -f '^bash .*home/[r]ec.sh'; termux-microphone-record -q; "
              f"rm -f ~/tur_a21s.m4a; termux-volume music 15; sleep 0.3; {rec} $HOME/tur_a21s.m4a")
    g56.manda(f"termux-microphone-record -q; rm -f ~/tur_a56.m4a; termux-volume music 15; {rec} $HOME/tur_a56.m4a")
    era_muto, vol_pc = b.muto_pc(False), b.volume_pc(1.0)
    t_rec0 = time.time(); etichette = []
    pc = subprocess.Popen(["ffmpeg", "-v", "quiet", "-y", "-f", "dshow", "-i", f"audio={prova.r.nome_dshow(prova.r.MIC_INTEL)}",
                           "-t", str(secondi + 60), "-ar", str(b.SR), "-ac", "1", os.path.join(b.OUT, ORECCHI["PC"])],
                          stdin=subprocess.PIPE)
    try:
        rit = json.load(open(T.AVVIO))
    except Exception:
        rit = {"A56": 0.0, "A21s": 0.0, "PC": 0.0}
    avvia = {"A56": lambda: g56.manda("play-audio pp.wav &"), "A21s": lambda: g21.manda("termux-media-player play ~/pp.wav"),
             "PC": lambda: winsound.PlaySound(os.path.join(b.OUT, "pp_PC.wav"), winsound.SND_FILENAME | winsound.SND_ASYNC)}

    def giro():
        tb, mx = time.time(), max(rit.values())
        for chi in sorted(avvia, key=lambda c: -rit[c]):
            time.sleep(max(0.0, tb + (mx - rit[chi]) - time.time())); avvia[chi]()
        time.sleep(len(UN_GIRO) * T.S + 0.4)
    try:
        time.sleep(3); prova.parla("silenzio, test"); giro()
        prova.parla("ora fai i rumori e dimmi dove sei")
        ciak = subprocess.Popen([sys.executable, "-c", f"import winsound; winsound.PlaySound(r'{file_ciak(secondi)}', 1)"])
        if guida:  # voce: istruzione, tempo per andarci, 'via', rumore, 'stop' (orari nel tempo del file PC)
            for frase, prep, dur in guida:
                prova.parla(frase); time.sleep(prep); prova.parla("via")
                a = time.time() - t_rec0; time.sleep(dur); etichette.append((frase, round(a, 2), round(time.time() - t_rec0, 2)))
                prova.parla("stop")
        else:
            time.sleep(secondi)
        prova.parla("ultimo ping pong"); giro(); prova.parla("fine test, analizzo")
    finally:
        try:
            pc.communicate(b"q", timeout=10)
        except Exception:
            pc.kill()
        g56.manda("termux-microphone-record -q"); g21.manda("termux-microphone-record -q; termux-volume music 12")
        g56.chiudi(); g21.chiudi(); b.muto_pc(era_muto); b.volume_pc(vol_pc); time.sleep(1.5)
    T.copia_quando_chiusi()
    d = os.path.join(T.DISP, nome); os.makedirs(d, exist_ok=True)
    json.dump(etichette, open(os.path.join(d, "etichette.json"), "w"), indent=1, ensure_ascii=False)
    for f in ORECCHI.values():
        shutil.copy(os.path.join(b.OUT, f), d)
    return d


def bip_finestra(r, x, t0, t1):
    """6 bip del ping-pong dentro [t0, t1) s, in ordine di tempo (tempo assoluto nel file).
    """
    a, z = int(t0 * b.SR), int(t1 * b.SR)
    T.GIRO = UN_GIRO
    return T.bip_in(r[a:z], x, len(UN_GIRO)) + t0


def gcc_phat(a, c, max_lag):
    n = 1 << int(np.ceil(np.log2(len(a) + len(c))))
    A, C = np.fft.rfft(a, n), np.fft.rfft(c, n)
    R = A * np.conj(C); R /= np.abs(R) + 1e-12
    cc = np.fft.irfft(R, n); cc = np.concatenate([cc[-max_lag:], cc[:max_lag + 1]])
    i = int(np.argmax(np.abs(cc)))
    y0, y1, y2 = np.abs(cc[max(i - 1, 0)]), np.abs(cc[i]), np.abs(cc[min(i + 1, len(cc) - 1)])
    return (i - max_lag + 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2 + 1e-12)) / b.SR, float(y1 / (np.median(np.abs(cc)) + 1e-12))


def analizza(cartella, secondi=None):
    from scipy.signal import butter, sosfiltfilt, correlate
    x = T.chirp("udibile")
    try:
        etichette = json.load(open(os.path.join(cartella, "etichette.json"), encoding="utf-8"))
    except Exception:
        etichette = []
    rec = {k: b.decodifica(os.path.join(cartella, f)) for k, f in ORECCHI.items()}
    durata = {k: len(v) / b.SR for k, v in rec.items()}
    # 1) ping-pong iniziale e finale in ogni registrazione
    tb = {}
    ini_pc = bip_finestra(rec["PC"], x, 0.0, 14.0)
    orologio_grezzo = {}
    for k, r in rec.items():
        orologio_grezzo[k] = float(bip_finestra(r, x, 0.0, 14.0)[2] - ini_pc[2])
    for k, r in rec.items():
        ini = bip_finestra(r, x, 0.0, 14.0)
        # ping-pong finale: solo DOPO l'ultimo passo della prova guidata (colpi alla porta = falsi bip)
        dopo = (etichette[-1][2] + 1.5 + (orologio_grezzo.get(k, 0.0))) if etichette else durata[k] - 16.0
        fin = bip_finestra(r, x, max(dopo, durata[k] - 20.0), durata[k])
        for fase, tt in (("ini", ini), ("fin", fin)):
            for i, chi in enumerate(UN_GIRO):
                tb[fase, k, chi, i] = tt[i]
    # distanze (BeepBeep sul giro iniziale): orecchio del PC = mic Intel
    idx = {c: [i for i, g in enumerate(UN_GIRO) if g == c] for c in ("A56", "A21s", "PC")}

    def dist(X, Y, fase="ini"):
        v = [b.C / 2 * ((tb[fase, X, Y, j] - tb[fase, X, X, i]) - (tb[fase, Y, Y, j] - tb[fase, Y, X, i]))
             for i in idx[X] for j in idx[Y]]
        return float(np.median(v))
    D = {("PC", "A56"): dist("A56", "PC"), ("A56", "A21s"): dist("A56", "A21s"), ("PC", "A21s"): dist("A21s", "PC")}
    a, bb, c = D["PC", "A56"], D["A56", "A21s"], D["PC", "A21s"]
    xa = (a ** 2 - bb ** 2 + c ** 2) / (2 * c)
    P = {"PC": np.array([0.0, 0.0]), "A21s": np.array([c, 0.0]), "A56": np.array([xa, np.sqrt(max(a ** 2 - xa ** 2, 0))])}
    print("distanze", {f"{k[0]}-{k[1]}": round(v, 3) for k, v in D.items()})
    lati = sorted([a, bb, c]); ang = np.degrees(np.arccos(np.clip((lati[1] ** 2 + lati[2] ** 2 - lati[0] ** 2) / (2 * lati[1] * lati[2]), -1, 1)))
    print(f"angolo minimo del triangolo {ang:.1f} gradi" + ("  !!! QUASI IN LINEA: di traverso la posizione e' inaffidabile" if ang < 15 else ""))
    #    fa da testimone. off_k = t_k(proprio) - (t_PC(stesso bip) - volo). Inizio: dal ping-pong iniziale; fine: la coppia
    #    di bip propri con la sua spaziatura-firma (A56 3,5 s, A21s 2,1 s), poi il PC cercato solo +-0,15 s dal previsto.
    from scipy.signal import hilbert, correlate, find_peaks
    dPC = {"A56": a, "A21s": c}

    def primo_arrivo(r, t_c, tol=0.15):
        a0 = max(0, int((t_c - tol) * b.SR)); cc = np.abs(hilbert(correlate(r[a0:int((t_c + tol) * b.SR) + len(x)], x, "valid", method="fft")))
        j = int(np.argmax(cc >= T.PRIMO * cc.max()))
        while j + 1 < len(cc) and cc[j + 1] > cc[j]:
            j += 1
        y0, y1, y2 = cc[max(j - 1, 0)], cc[j], cc[min(j + 1, len(cc) - 1)]
        return (a0 + j + 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2 + 1e-12)) / b.SR

    orologio = {"PC": (0.0, 0.0)}
    for k in ("A56", "A21s"):
        i0, i1 = idx[k][0], idx[k][-1]; firma = (i1 - i0) * T.S; volo = dPC[k] / b.C
        t_k0, t_p0 = tb["ini", k, k, i0], tb["ini", "PC", k, i0]
        off0 = t_k0 - (t_p0 - volo)
        r = rec[k]; t_a = (etichette[-1][2] + off0) if etichette else durata[k] - 20
        cc = np.abs(hilbert(correlate(r[int(t_a * b.SR):], x, "valid", method="fft")))
        pk, pr = find_peaks(cc, distance=int(0.2 * b.SR), height=0.3 * cc.max()); pt = pk / b.SR + t_a
        coppie = [(p1, p2) for p1 in pt for p2 in pt if abs(p2 - p1 - firma) < 0.05]
        pts = [(t_p0, off0)]
        if coppie:
            t_k1 = primo_arrivo(r, coppie[0][0], 0.02)
            t_p1 = primo_arrivo(rec["PC"], t_k1 - off0 + volo)
            pts.append((t_p1, t_k1 - (t_p1 - volo)))
        (ta, oa) = pts[0]; (tz, oz) = pts[-1]
        der = (oz - oa) / (tz - ta) if tz > ta else 0.0; off = oa - der * ta
        orologio[k] = (off, der)
        print(f"orologio {k}: scarto {oa * 1000:9.2f} ms  deriva {der * 6e4:7.3f} ms/min  ({len(pts)} punti)")
    # 3) rumori: attacchi nel file del PC fra i due ping-pong
    r = rec["PC"]
    sos = butter(4, [150, 6000], "bandpass", fs=b.SR, output="sos")
    f = sosfiltfilt(sos, r); env = np.sqrt(np.convolve(f ** 2, np.ones(480) / 480, "same"))
    t_ini = max(tb["ini", "PC", c2, i] for (fz, k2, c2, i) in tb if fz == "ini" and k2 == "PC") + 0.6
    t_fin = min(tb["fin", "PC", c2, i] for (fz, k2, c2, i) in tb if fz == "fin" and k2 == "PC") - 0.4
    fondo = np.median(env[int(t_ini * b.SR): int(t_fin * b.SR)])
    eventi, j = [], int(t_ini * b.SR)
    while j < int(t_fin * b.SR):
        if env[j] > 8 * fondo:
            eventi.append(j / b.SR); j += int(0.6 * b.SR)
        else:
            j += 48
    print(f"{len(eventi)} rumori trovati")
    xs, ys = np.linspace(-4.0, c + 4.0, 391), np.linspace(-5.0, 5.0, 341)
    GX, GY = np.meshgrid(xs, ys)
    dist_da = {k: np.hypot(GX - v[0], GY - v[1]) for k, v in P.items()}
    ris, grezzi = [], []
    for te in eventi:
        # correlazione normale, ricerca entro +-25 ms (4 m = 12 ms + errore orologi)
        a0, n = int((te - 0.1) * b.SR), int(0.5 * b.SR)
        han = np.hanning(n)
        seg_pc = sosfiltfilt(sos, r[a0:a0 + n]) * han
        tdoa, qual = {}, {}
        for k in ("A56", "A21s"):
            o, der = orologio[k]
            k0 = int(round((te - 0.1 + o + der * te) * b.SR))  # stesso istante nell'orologio di k (off = o + der*t_PC)
            seg = sosfiltfilt(sos, rec[k][k0:k0 + n]) * han
            # GCC-PHAT (sbiancato, finestre uguali) sbaglia 0,02-0,2 ms su sorgenti note
            L = int(0.025 * b.SR); N = 2 * n; A, C = np.fft.rfft(seg, N), np.fft.rfft(seg_pc, N); R = A * np.conj(C); R /= np.abs(R) + 1e-9
            cc = np.fft.irfft(R, N); w = np.concatenate([cc[-L:], cc[:L + 1]]); i = int(np.argmax(w))
            y0, y1, y2 = w[max(i - 1, 0)], w[i], w[min(i + 1, len(w) - 1)]
            tdoa[k] = (i - L + 0.5 * (y0 - y2) / (y0 - 2 * y1 + y2 + 1e-12)) / b.SR  # arrivo_k - arrivo_PC (s)
            qual[k] = float(y1 / (np.median(np.abs(w)) + 1e-12))
        grezzi.append((te, tdoa, qual))
    # quelli previsti = errore fisso degli orologi (era A56 +2,9 ms, A21s +0,7 ms -> quasi nessun rumore tornava)
    atteso = {k: (np.linalg.norm(P[k] - P["PC"])) / b.C for k in ("A56", "A21s")}
    voce = [g for g in grezzi if all(abs(g[1][k] - atteso[k]) < 0.004 for k in atteso)]
    corr = {k: 0.0 for k in atteso}
    print(f"correzione orologi dalla voce del PC ({len(voce)} frasi): " + ", ".join(f"{k} {v * 1000:+.2f} ms" for k, v in corr.items()))
    for te, tdoa, qual in grezzi:
        tdoa = {k: v - corr[k] for k, v in tdoa.items()}
        # posizione: minimi quadrati sulla griglia
        err = sum(((dist_da[k] - dist_da["PC"]) / b.C - tdoa[k]) ** 2 for k in tdoa)
        i = np.unravel_index(np.argmin(err), err.shape)
        pos = np.array([GX[i], GY[i]]); res = float(np.sqrt(err[i] / 2) * b.C * 100)
        ris.append(dict(t=round(te - t_ini, 2), x=round(float(pos[0]), 2), y=round(float(pos[1]), 2), residuo_cm=round(res, 1),
                        tdoa_ms={k: round(v * 1000, 3) for k, v in tdoa.items()}, qualita={k: round(v, 1) for k, v in qual.items()}))
        vic = min(P, key=lambda k: np.linalg.norm(P[k] - pos)); dv = float(np.linalg.norm(P[vic] - pos))
        u = {k: (pos - v) / (np.linalg.norm(pos - v) + 1e-9) for k, v in P.items()}
        J = np.array([u["A56"] - u["PC"], u["A21s"] - u["PC"]])
        try:
            gdop = float(SIGMA_TDOA * b.C * np.sqrt(np.trace(np.linalg.inv(J.T @ J))) * 100)
        except np.linalg.LinAlgError:
            gdop = float("inf")
        ris[-1]["errore_previsto_cm"] = round(gdop, 1)
        et = next((f for f, e0, e1 in etichette if e0 - 0.5 <= te <= e1 + 1.0), "")
        ris[-1].update(buono=res < RESIDUO_OK and gdop < ERR_MAX_CM, vicino_a=vic if dv < VICINO else None, etichetta=et)
        stato = ("OK " if res < RESIDUO_OK else "-- ") + (f"vicino a {vic}" if dv < VICINO else "")
        print(f"  {stato:18s} [{et[:22]:22s}] t={te - t_ini:6.2f} s  pos ({pos[0]:5.2f}, {pos[1]:5.2f}) m +-{gdop:5.0f} cm  residuo {res:6.1f} cm  tdoa {ris[-1]['tdoa_ms']}")
    json.dump(dict(P={k: v.tolist() for k, v in P.items()}, D={f"{k[0]}-{k[1]}": v for k, v in D.items()}, eventi=ris,
                   t_ini=float(t_ini), t_fin=float(t_fin), etichette=etichette,
                   orologio={k: [float(o), float(dr)] for k, (o, dr) in orologio.items()}, correzione_voce=corr),
              open(os.path.join(cartella, "eventi.json"), "w"), indent=1)
    return P, ris


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["analizza"]:
        analizza(os.path.join(T.DISP, a[1])); sys.exit()
    if a[:1] == ["guidata"]:
        sec = sum(p + d + 3 for _, p, d in GUIDA) + 10
        analizza(registra(sec, a[1] if len(a) > 1 else "guidata", GUIDA)); sys.exit()
    sec = int(a[0]) if a else 60
    analizza(registra(sec, a[1] if len(a) > 1 else "ascolta"))
