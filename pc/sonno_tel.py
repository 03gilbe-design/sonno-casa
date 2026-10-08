# Gira in Termux sull'A21s: analizza ogni blocco audio finito con YAMNet, scrive un riassunto per MINUTO
# in /sdcard/Recordings/sonno/minuti_AAAAMMGG.csv e cancella l'audio (tranne i minuti di russamento, tenuti 3 giorni).
import csv, glob, os, re, shutil, subprocess, sys, time
from datetime import datetime, timedelta
import numpy as np, onnxruntime as ort
from stato_storia import leggi_storia, registra_a

D = os.environ.get("SONNO_DIR", "/sdcard/Recordings/sonno")
HOME = os.path.expanduser("~")
HOP, SR = 0.48, 16000
GRUPPI = {  # rumori ESTERNI: non sono tuoi, non contano come risveglio
    "traffico": r"vehicle|^car|traffic|motorcycle|truck|bus$|train|aircraft|engine|siren|horn",
    "tv_musica": r"television|radio|music|song|singing",
    "animali": r"dog|bark|cat$|meow|bird|chirp|insect|cricket",
    "pioggia_vento": r"rain|wind|thunder|water|stream|drip",
    "elettrodomestici": r"fan$|air condition|mechanical|hum$|buzz|washing|dishes|microwave|blender|vacuum|toilet|clock|tick",
    "porte_allarmi": r"door|bell|alarm|telephone|ringtone|knock",
}
nomi = [r["display_name"] for r in csv.DictReader(open(f"{HOME}/yamnet_class_map.csv"))]
IDX = {g: [i for i, n in enumerate(nomi) if i > 0 and re.search(p, n, re.I)] for g, p in GRUPPI.items()}
RUSSA, RESPIRO, VOCE, TOSSE, MUSICA = 38, 36, 0, 42, 132
sess = None  # caricato solo se c'e' un blocco da analizzare (di giorno il loop gira ogni 2')


def etichetta_frame(F, sc, j):
    """Cosa si sente nel frame j: un tipo (priorita' tosse>voce>russa>movimento>respiro), +musica se c'e' sotto."""
    tipo = next((k for k in ("tosse", "voce", "russa", "movimento", "respiro") if F[k][j]), "")
    musica = sc[j, MUSICA] > 0.3
    return (tipo + "+musica" if tipo and musica else tipo) or ("musica" if musica else "silenzio")


def pezzi(etichette, hop=HOP, minimo=2):
    """Etichette per frame -> "0-4 s respiro · 4-9 s musica". Pezzi < minimo frame (~1 s) assorbiti dal precedente."""
    run = []
    for e in etichette:
        if run and run[-1][0] == e:
            run[-1][1] += 1
        else:
            run.append([e, 1])
    for i in range(len(run) - 1, 0, -1):  # pezzettini: al vicino di sinistra
        if run[i][1] < minimo:
            run[i - 1][1] += run.pop(i)[1]
    out, t = [], 0
    for e, n in run:
        if out and out[-1][2] == e:  # dopo l'assorbimento due vicini possono coincidere
            out[-1][1] = t + n
        else:
            out.append([t, t + n, e])
        t += n
    return " · ".join(f"{round(a * hop)}-{round(b * hop)} s {e}" for a, b, e in out)


def evento(f, primo):
    """(inizio_s, durata_s) dell'evento che parte dal frammento `primo` (f = segnato si'/no ogni 0,48 s): fino
    all'ultimo segnato, buchi <= 2 frammenti tollerati, +-1 s di margine, fra 3 e 20 s."""
    ultimo, j = primo, primo + 1
    while j < len(f) and j - ultimo <= 3 and (j - primo) * HOP < 19:
        if f[j]:
            ultimo = j
        j += 1
    da = max(0.0, primo * HOP - 1)
    return da, min(20.0, max(3.0, (ultimo + 1) * HOP + 1 - da))


def classifica(path):
    """File audio -> (sc, db, base, est, esterno, F) per frame da 0,48 s; None se troppo corto."""
    global sess
    sess = sess or ort.InferenceSession(f"{HOME}/yamnet.onnx", providers=["CPUExecutionProvider"])
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True).stdout
    w = np.frombuffer(pcm, np.float32)
    if len(w) < SR:
        return None
    outs = [sess.run(None, {"waveform": w[i:i + SR * 60]}) for i in range(0, len(w) - SR, SR * 60)]
    sc, emb = np.concatenate([o[0] for o in outs]), np.concatenate([o[1] for o in outs])
    n = int(HOP * SR)
    db = np.array([20 * np.log10(np.sqrt(np.mean(w[i * n:(i + 1) * n] ** 2)) + 1e-9) for i in range(len(sc))])
    base = np.percentile(db, 20)
    est = {g: sc[:, ix].max(1) for g, ix in IDX.items()}
    esterno = np.max(np.stack(list(est.values())), 0) > 0.3
    # classe per frame: modello PERSONALE (tarato sui suoi suoni) se c'e', altrimenti YAMNet generico
    if os.path.exists(f"{HOME}/modello_personale.npz"):
        P = np.load(f"{HOME}/modello_personale.npz")  # solo array numerici e stringhe, niente pickle
        z = ((emb - P["mu"]) / P["sd"]) @ P["W"].T + P["b"]
        pr = np.exp(z - z.max(1, keepdims=True)); pr /= pr.sum(1, keepdims=True)
        cls = np.where(pr.max(1) > 0.6, P["classi"][pr.argmax(1)], "incerto")
        cls[db <= float(P["soglia_db"])] = "ambiente"
        F = {k: cls == k for k in ("russa", "voce", "tosse", "respiro", "movimento", "sbuffo")}
    else:
        F = dict(russa=sc[:, RUSSA] > 0.2, voce=(sc[:, VOCE] > 0.5) & ~esterno, tosse=sc[:, TOSSE] > 0.3,
                 respiro=sc[:, RESPIRO] > 0.3, movimento=(db > base + 12) & ~esterno, sbuffo=np.zeros(len(sc), bool))
    return sc, db, base, est, esterno, F


def dividi_clip(clip):
    """Scrive clip.txt con la divisione nel tempo (per le clip gia' salvate senza .txt)."""
    r = classifica(clip)
    if r:
        sc, F = r[0], r[5]
        with open(clip[:-4] + ".txt", "w") as f:
            f.write(pezzi([etichetta_frame(F, sc, j) for j in range(len(sc))]))


COLONNE = ["t", "db", "base", "picchi_miei", "voce", "colpi_russa", "respiro", "tosse", "esterni", "esterno_top", "sbuffi"]
SCARTATO = "scartato_sveglio"  # in esterno_top: il minuto NON e' un buco, e' audio scartato perche' sveglio al 100%


def riga_scartata(t):
    """Riga minuti_*.csv di un minuto scartato: numeri VUOTI (float('') fallisce: stato.muto() non lo conta camera
    muta; notte.minuti() lo salta), esterno_top = SCARTATO. 11 colonne come le altre."""
    return [t.strftime("%Y-%m-%dT%H:%M")] + [""] * 8 + [SCARTATO, ""]


def silenzia(path, scarti):
    """Azzera (silenzio digitale, stessa durata: la linea del tempo del blocco non si sposta) i secondi (a, b)
    in `scarti`. True se ok. Non tocca il microfono, solo il file gia' chiuso."""
    expr = "+".join(f"between(t,{a},{b})" for a, b in scarti)
    tmp = path + ".sil.m4a"
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-af", f"volume=0:enable='{expr}'",
                        "-c:a", "aac", "-b:a", "64k", "-ar", "16000", "-ac", "1", tmp], capture_output=True)
    if r.returncode == 0 and os.path.exists(tmp):
        os.replace(tmp, path)
        return True
    if os.path.exists(tmp):
        os.remove(tmp)
    return False


def analizza(path):
    t0 = datetime.strptime(os.path.basename(path)[:15], "%Y%m%d_%H%M%S")
    out = f"{D}/minuti_{t0:%Y%m%d}.csv"
    # Senza storia, o storia vecchia (>5'), registra=True: nel dubbio si registra.
    storia = leggi_storia(f"{HOME}/stato_storia.csv") if os.path.exists(f"{HOME}/SCARTO_ATTIVO") else []
    n_min = max(1, int((os.path.getmtime(path) - t0.timestamp()) // 60) + 1)
    minuto = lambda i: t0 + timedelta(seconds=60 * i)
    if storia and not any(registra_a(minuto(i), storia) for i in range(n_min)):  # tutto il blocco: via senza analisi
        with open(out, "a", newline="") as f:
            wr = csv.writer(f)
            if f.tell() == 0:
                wr.writerow(COLONNE)
            for i in range(n_min):
                wr.writerow(riga_scartata(minuto(i)))
        os.remove(path)
        return
    r = classifica(path)
    if r is None:
        return
    sc, db, base, est, esterno, F = r
    scarti = []  # (inizio_s, fine_s) dei minuti scartati di questo blocco
    nuovo = not os.path.exists(out)
    russati = []
    with open(out, "a", newline="") as f:
        wr = csv.writer(f)
        if nuovo:
            wr.writerow(COLONNE)
        for m in range(0, len(sc), int(60 / HOP)):
            if storia and not registra_a(t0 + timedelta(seconds=m * HOP), storia):
                scarti.append((round(m * HOP), round(m * HOP) + 60))
                wr.writerow(riga_scartata(t0 + timedelta(seconds=m * HOP)))
                continue
            s = slice(m, m + int(60 / HOP))
            c = {k: int(v[s].sum()) for k, v in F.items()}
            gtop = max(est, key=lambda g: (est[g][s] > 0.3).sum())
            for tipo, minimo in (("russa", 3), ("voce", 10), ("tosse", 1), ("sbuffo", 1)):
                if c[tipo] >= minimo:
                    # la clip parte 3 s prima del PRIMO colpo del minuto, non dall'inizio del minuto: prima prendeva
                    primo = m + int(np.flatnonzero(F[tipo][s])[0])
                    # ogni 0,48 s): dal primo all'ultimo frammento segnato, buchi <= 2 frammenti (~1 s) tollerati,
                    # +-1 s di margine, fra 3 e 20 s (sotto i 3 s non si capisce cosa si sente)
                    russati.append((tipo, *evento(F[tipo], primo)))
            wr.writerow([(t0 + timedelta(seconds=m * HOP)).strftime("%Y-%m-%dT%H:%M"), round(float(np.median(db[s])), 1),
                         round(float(base), 1), c["movimento"], c["voce"], c["russa"], c["respiro"], c["tosse"],
                         int(esterno[s].sum()), gtop if (est[gtop][s] > 0.3).any() else "", c["sbuffo"]])
    # tieni 20s per episodio (max 3 per tipo per blocco) per riascoltare/tarare, il resto si cancella
    for tipo in ("russa", "voce", "tosse", "sbuffo"):
        for sec, dur in [(x, d) for t, x, d in russati if t == tipo][:3]:
            nome = f"{D}/{tipo}_{t0 + timedelta(seconds=sec):%Y%m%d_%H%M}"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(sec), "-t", f"{dur:.1f}", "-i", path, "-c", "copy",
                            nome + ".m4a"])
            j0 = int(sec / HOP)
            with open(nome + ".txt", "w") as f:
                f.write(pezzi([etichetta_frame(F, sc, j) for j in range(j0, min(len(sc), j0 + int(dur / HOP)))]))
    # In rec/interi/ (fuori dal glob 2*.m4a: niente doppia analisi). Sotto 1 GB liberi via i piu' vecchi, se no la
    # registrazione si ferma a disco pieno.
    interi = os.path.join(D, "interi"); os.makedirs(interi, exist_ok=True)
    if scarti and not silenzia(path, scarti):  # blocco misto: i minuti scartati diventano silenzio; se non riesce, via tutto
        os.remove(path)
        return
    os.replace(path, os.path.join(interi, os.path.basename(path)))
    for vecchio in sorted(glob.glob(f"{interi}/*.m4a")):
        if shutil.disk_usage(D).free > 1e9:
            break
        os.remove(vecchio)


if __name__ == "__main__":
    if sys.argv[1:] == ["dividi"]:  # clip gia' salvate senza divisione nel tempo
        for p in sum((glob.glob(f"{D}/{t}_*.m4a") for t in ("russa", "voce", "tosse", "sbuffo")), []):
            if not os.path.exists(p[:-4] + ".txt"):
                dividi_clip(p)
    if sys.argv[1:] == ["analizza"]:  # tutti i blocchi finiti (l'ultimo e' in registrazione)
        for p in sorted(glob.glob(f"{D}/2*.m4a")):
            if time.time() - os.path.getmtime(p) > 90:  # fermo da 90s = blocco finito
                t0 = time.time()
                analizza(p)
                print(f"{time.strftime('%F %T')} tempo yamnet {os.path.basename(p)} {time.time() - t0:.0f}s", flush=True)
        for p in sum((glob.glob(f"{D}/{t}_*.m4a") for t in ("russa", "voce", "tosse", "sbuffo")), []):  # clip: 3 giorni
            if time.time() - os.path.getmtime(p) > 7 * 86400:  # 7 giorni: reggono anche se il PC manca
                os.remove(p)
                if os.path.exists(p[:-4] + ".txt"):
                    os.remove(p[:-4] + ".txt")  # divisione nel tempo della clip
