"""
un audio con le registrazioni dei vari dispositivi"). Dati veri: notte 28->29, PC in tre_dispositivi\\20260929 (FLAC
Per ogni momento: 40 s da tutti e due, ritardo con GCC-PHAT (orologi diversi, cerca entro +-10 s), 20 s allineati,
somma pesata (maximum ratio combining: ogni orecchio pesato per quanto e' pulito, rumore stimato sui tratti quieti).
Stampa anche CHI SENTE PIU' FORTE il suono (dB sopra il proprio fondo): e' l'indizio di "da dove viene".
"""
import glob, os, subprocess, sys
from datetime import datetime, timedelta
import numpy as np

sys.path.insert(0, r"C:\sonno_tex")
SR = 16000
GIORNO = "20260929"
PC_DIR = rf"C:\sonno_audio\tre_dispositivi\{GIORNO}"
OUT = r"C:\sonno_audio\insieme"
FIN, MARGINE = 20, 10  # secondi tenuti, secondi di margine per il ritardo fra orologi


def pcm(args):
    return np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", *args, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                                        capture_output=True).stdout, np.float32)


def pezzo_pc(t, dur):
    fs = sorted(glob.glob(os.path.join(PC_DIR, "pc_*.flac")))
    ok = [f for f in fs if datetime.strptime(os.path.basename(f)[3:18], "%Y%m%d_%H%M%S") <= t]
    if not ok:
        return None
    t0 = datetime.strptime(os.path.basename(ok[-1])[3:18], "%Y%m%d_%H%M%S")
    return pcm(["-ss", str((t - t0).total_seconds()), "-t", str(dur), "-i", ok[-1]])


def pezzo_a21s(t, dur):
    """Taglia sul telefono (ffmpeg li') e porta sul PC solo i secondi che servono."""
    from sonno_audio import device
    from cal_sessione import T
    d = device()
    nomi = T(d, "ls ~/rec/interi").split()
    ok = [n for n in nomi if n.endswith(".m4a") and datetime.strptime(n[:15], "%Y%m%d_%H%M%S") <= t]
    if not ok:
        return None
    t0 = datetime.strptime(ok[-1][:15], "%Y%m%d_%H%M%S")
    T(d, f"ffmpeg -v error -y -ss {(t - t0).total_seconds():.1f} -t {dur} -i ~/rec/interi/{ok[-1]} -ac 1 -ar {SR} ~/tmp_insieme.wav")
    raw = subprocess.run(["adb", "-s", d, "exec-out", "run-as com.termux cat files/home/tmp_insieme.wav"],
                         capture_output=True).stdout
    T(d, "rm -f ~/tmp_insieme.wav")
    return np.frombuffer(raw[44:], np.int16).astype(np.float32) / 32768 if len(raw) > 44 else None


def gcc_phat(x, ref, max_s):
    """Ritardo (campioni) di x rispetto a ref: picco della correlazione con spettro 'sbiancato' (robusto all'eco)."""
    n = 1 << (len(x) + len(ref)).bit_length()
    X, R = np.fft.rfft(x, n), np.fft.rfft(ref, n)
    G = X * np.conj(R); G /= np.abs(G) + 1e-12
    c = np.fft.irfft(G, n)
    m = int(max_s * SR)
    c = np.concatenate([c[-m:], c[:m + 1]])
    return int(np.argmax(np.abs(c))) - m, float(np.max(np.abs(c)) / (np.mean(np.abs(c)) + 1e-12))


def fondo(x):
    """Rumore di fondo = RMS dei 20% tratti da 50 ms piu' quieti."""
    f = x[: len(x) // 800 * 800].reshape(-1, 800)
    r = np.sqrt((f ** 2).mean(1))
    return float(np.sqrt(np.mean(np.sort(r)[: max(1, len(r) // 5)] ** 2))) + 1e-9


def db_sopra(x):
    f = x[: len(x) // 800 * 800].reshape(-1, 800)
    return float(20 * np.log10(np.sqrt((f ** 2).mean(1)).max() / fondo(x)))


def salva(path, x):
    import wave
    y = np.clip(x / (np.abs(x).max() + 1e-9) * 0.9, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((y * 32767).astype(np.int16).tobytes())


def momento(hhmm):
    t = datetime.strptime(GIORNO + hhmm.replace(":", ""), "%Y%m%d%H%M")
    a = pezzo_a21s(t - timedelta(seconds=MARGINE), FIN + 2 * MARGINE)
    p = pezzo_pc(t - timedelta(seconds=MARGINE), FIN + 2 * MARGINE)
    if a is None or p is None or len(a) < SR * FIN or len(p) < SR * FIN:
        return f"{hhmm}: manca audio (A21s {None if a is None else len(a) // SR} s, PC {None if p is None else len(p) // SR} s)"
    k, forza = gcc_phat(p, a, MARGINE)  # p[i + k] ~ a[i]
    i0 = MARGINE * SR
    aa, pp = a[i0: i0 + FIN * SR], p[i0 + k: i0 + k + FIN * SR]
    if len(pp) < FIN * SR:
        return f"{hhmm}: allineamento fuori dal pezzo (ritardo {k / SR:+.2f} s)"
    na, np_ = aa / fondo(aa), pp / fondo(pp)  # stesso fondo = 1 per tutti e due
    sa, sp = max(db_sopra(aa), 0.1), max(db_sopra(pp), 0.1)
    wa, wp = 10 ** (sa / 20), 10 ** (sp / 20)  # MRC: pesa di piu' chi sente il suono piu' sopra il suo fondo
    ins = (wa * na + wp * np_) / (wa + wp)
    os.makedirs(OUT, exist_ok=True)
    nome = hhmm.replace(":", "")
    for suf, x in (("a21s", aa), ("pc", pp), ("insieme", ins)):
        salva(os.path.join(OUT, f"{nome}_{suf}.wav"), x)
    chi = "A21s" if sa > sp + 3 else "PC" if sp > sa + 3 else "uguale"
    return (f"{hhmm}: ritardo PC {k / SR:+.2f} s (picco x{forza:.0f}) | sopra il fondo: A21s {sa:.0f} dB, PC {sp:.0f} dB, "
            f"insieme {db_sopra(ins):.0f} dB | piu' vicino: {chi}")


if __name__ == "__main__":
    os.environ["MSYS_NO_PATHCONV"] = "1"
    for h in sys.argv[1:] or ["00:00"]:
        print(momento(h), flush=True)
