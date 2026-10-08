"""MAPPA DEL RUSSARE di una notte (priorita' 0 dell'utente: far sapere DOVE, cioe' QUANDO, ha russato).
  python mappa_russare.py AAAAMMGG            -> mappa della notte che finisce quel giorno (default: oggi)
      --leggera        niente PANNs/EfficientAT sui blocchi interi (solo YAMNet + clip + tuoi giudizi)
      --stile righe|corsie|bande   grafica: 3 righe con tutte le fonti sulla stessa striscia (predefinito), una corsia per modello, o bande nella cella; PNG *_corsie.png / *_bande.png
      --aggiorna-etichette   riscarica giudizi.csv e ridisegna (leggero)
      --panns-tutta    PANNs+EfficientAT su TUTTA la notte (~1 h, priorita' bassa): da lanciare a mano, con la verifica pesante
      --auto           usato dall'attivita' pianificata: il calcolo pesante parte solo se sei sveglio certo e il PC e' fermo da 10'
      --inizio HH:MM --fine HH:MM --brevi HH:MM-HH:MM[,..]   (corregge i confini della notte calcolati da notte.py)
Uscita in C:\\sonno_audio\\mappe\\: mappa_AAAAMMGG.csv / .json / .png ; JSON e PNG vanno anche sul telefono (~/sonno_bot/mappe/).
CERTEZZA (4 > 1): confermato da te > PANNs+EfficientAT d'accordo > solo un modello > solo YAMNet.
Sul telefono: SOLO lettura (ssh/scp) e la cartella ~/sonno_bot/mappe/. Non tocca rec.sh ne' il microfono."""
import senza_finestre  # noqa: F401  (primo: niente finestre dei processi figli)
import a21
import csv, ctypes, glob, json, os, re, subprocess, sys, time
from datetime import datetime, timedelta
import numpy as np

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
ROOT = r"C:\sonno_audio"
OUT, SRC = ROOT + r"\mappe", ROOT + r"\mappe\_src"
TRE = ROOT + r"\tre_dispositivi"
PHONE = a21.ip()
SSH = ["ssh", "-p", "8022", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", PHONE]
SCP = ["scp", "-P", "8022", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"]

GAP = 3          # ponytail: minuti di buco che uniscono due periodi
MIN_DUR = 2      # ponytail: sotto 2' un periodo e' un colpo solo, a meno che una clip lo confermi
SOGLIA = 0.2     # probabilita' sopra cui un modello "sente" russare (come accordo.py / conferma.py)
SEC_MIN = 3      # finestre sopra soglia per dire "il modello conferma" su un tratto lungo (un picco isolato non basta)
PIU_FORTE_DB = 6
SNORING = 43     # indice "Snoring" di PANNs e EfficientAT (38 e' di YAMNet: NON scambiarli)
TESTO = {4: "confermato da te", 3: "PANNs+EfficientAT d'accordo", 2: "solo un modello", 1: "solo YAMNet"}
ALTRE = {}  # ultime probabilita' per categoria di modelli()
T0 = time.time()
TUTTA = [False]  # --panns-tutta: PANNs/EfficientAT su TUTTA la notte (~1 h sul PC a priorita' bassa), non solo sui periodi di YAMNet
CACHE_DAY = [""]  # AAAAMMGG della notte in corso (nome della cache per minuto)


def bassa_priorita():
    if os.name == "nt":  # BelowNormal: i figli (ffmpeg) la ereditano
        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)


def ssh(cmd, t=60):
    return subprocess.run(SSH + [cmd], capture_output=True, text=True, timeout=t).stdout


def scp(src, dst, t=600):
    return subprocess.run(SCP + [src, dst], capture_output=True, timeout=t).returncode == 0


# ---------- stato utente / PC ----------
def sveglio_certo():
    # PC usato negli ultimi 5' = sveglio certo, qualunque cosa dica l'A21s.
    try:
        t, ev = list(csv.reader(open(r"C:\activity_log\activity.csv")))[-1][:2]
        if ev == "ACTIVE" or datetime.now() - datetime.fromisoformat(t) < timedelta(minutes=5):
            return True
    except Exception:
        pass
    try:
        s = json.loads(ssh("cat ~/stato.json", 20))
        return s.get("utente") == "sveglio" and s.get("fiducia", 0) >= 0.9
    except Exception:
        return False  # non lo so = non parto col pesante


def puo_pesante(auto):
    """Calcolo pesante: sveglio certo SEMPRE; in --auto anche PC fermo da 10'. Dopo le 18:00 il PC acceso non blocca piu'
    (ponytail: 'sveglio certo' si regge sull'uso del PC, quindi con PC fermo da 10' lo stato spesso diventa '?': senza questa
    via d'uscita la mappa pesante potrebbe non partire mai; resta a priorita' bassa)."""
    return sveglio_certo() and (not auto or pc_fermo() or datetime.now().hour >= 18)


def pc_fermo(min_=10):
    ev = list(csv.reader(open(r"C:\activity_log\activity.csv")))[-1]
    return ev[1] == "IDLE" and datetime.now() - datetime.fromisoformat(ev[0]) >= timedelta(minutes=min_)


# ---------- dati ----------
def scarica(day):
    """giudizi + sidecar delle clip del giorno e di quello prima. Se il telefono non risponde si usa la copia vecchia."""
    os.makedirs(SRC + r"\rec", exist_ok=True)
    prima = (datetime.strptime(day, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
    ok = scp(f"{PHONE}:sonno_bot/giudizi.csv", SRC + r"\giudizi.csv")
    for d in (prima, day):
        for e in ("panns", "eff"):
            scp(f"{PHONE}:rec/russa_{d}_*.{e}", SRC + r"\rec", 120)
    return ok


def giudizi():
    """{minuto: 'si'|'no'} dai tuoi giudizi sulle clip russa_*. 'si' vince su 'no' (stesso minuto, piu' clip)."""
    import mappa_etichette as ME
    g = {}
    for r in csv.DictReader(open(SRC + r"\giudizi.csv", encoding="utf-8")):
        if not r["clip"].startswith("russa_"):
            continue
        t = datetime.strptime(r["clip"].split("_", 1)[1][:13], "%Y%m%d_%H%M")
        si = (r["detto"] == "russa" and r["giusto"] == "1") or bool(r.get("era") and ME.principale(ME.mappa(r["era"])) == "russa")
        if si or g.get(t) != "si":
            g[t] = "si" if si else "no"
    return g


def clip_modelli():
    """{minuto: (max PANNs, max EfficientAT)} dalle .panns/.eff gia' fatte dal telefono (formato 'max,secondi')."""
    c = {}
    for p in glob.glob(SRC + r"\rec\russa_*.panns"):
        try:
            t = datetime.strptime(os.path.basename(p).split("_", 1)[1][:13], "%Y%m%d_%H%M")
            a = float(open(p).read().split(",")[0])
            e = float(open(p[:-6] + ".eff").read().split(",")[0]) if os.path.exists(p[:-6] + ".eff") else 0.0
            c[t] = (max(a, c.get(t, (0, 0))[0]), max(e, c.get(t, (0, 0))[1]))
        except (OSError, ValueError):
            pass
    return c


# ---------- periodi ----------
def candidati(M, a, z, brevi, escludi=()):
    """Minuti con colpi >= 3 dentro la notte, senza voce/musica/esterni forti e fuori dai risvegli brevi.
    escludi = minuti in cui un TELEFONO suonava (sorgente.py: TikTok...): il suono non e' suo, non conta per il russare."""
    ok = []
    for k in sorted(M):
        d = M[k]
        if not (a <= k <= z) or not d["russa"] or any(s <= k <= e for s, e in brevi) or k in escludi:
            continue
        if d["voce"] >= 5 or d["esterni"] >= 3 or d["esterno_top"] in ("tv_musica", "musica"):
            continue  # ponytail: soglie a occhio
        ok.append(k)
    return ok


def periodi(M, cand, gi, cm, a, z, brevi=()):
    """Unisce i minuti candidati (gap <= GAP'); un minuto che hai confermato tu e' sempre candidato."""
    minuti = sorted(set(cand) | {k for k, v in gi.items() if v == "si" and a <= k <= z and k in M})
    run = []
    for k in minuti:
        if run and k - run[-1][1] <= timedelta(minutes=GAP + 1) and not any(run[-1][1] < be and bs < k for bs, be in brevi):
            run[-1][1] = k
        else:
            run.append([k, k])
    out = []
    for s, e in run:
        n = int((e - s).total_seconds() // 60) + 1
        mm = [M[k] for k in M if s <= k <= e]
        col = [d["colpi"] for d in mm if d["russa"]]
        # respiro, russare e movimento si alternano: il periodo non e' un blocco pulito, e' una DENSITA' (% dei minuti del periodo)
        dens = dict(russare=round(100 * len(col) / n), movimento=round(100 * sum(d["picchi"] >= 4 and not d["russa"] for d in mm) / n),
                    respiro=round(100 * sum(d["respiro"] > 0 and not d["russa"] and d["picchi"] < 4 for d in mm) / n))
        vic = [k for k in set(gi) | set(cm) if s - timedelta(minutes=1) <= k <= e + timedelta(minutes=1)]
        tu_si = any(gi.get(k) == "si" for k in vic)
        tu_no = sum(gi.get(k) == "no" for k in vic)
        pn = any(cm[k][0] > SOGLIA for k in vic if k in cm)
        ef = any(cm[k][1] > SOGLIA for k in vic if k in cm)
        if n < MIN_DUR and not (tu_si or pn or ef):
            continue
        out.append(dict(da=s, a=e + timedelta(minutes=1), min=n, colpi=float(np.mean(col)) if col else 0.0, dens=dens, tu_si=tu_si,
                        tu_no=tu_no, smentito=bool(tu_no) and not tu_si and n <= MIN_DUR + 1,  # clip "non russa" in un periodo breve
                        panns=pn, eff=ef, prove=dict(clip=sum(k in cm for k in vic))))
    return out


# ---------- audio: blocchi interi A21s + altri dispositivi ----------
def blocchi_interi(a, z):
    """[(inizio, fine, path locale)] dei blocchi interi del telefono che toccano [a,z]; scarica solo quelli."""
    os.makedirs(SRC + r"\interi", exist_ok=True)
    res = []
    for r in ssh("cd ~/rec/interi && ls -l --time-style=+%Y%m%dT%H%M%S").splitlines():
        f = r.split()
        if len(f) >= 6 and f[-1].endswith(".m4a"):
            try:
                s, e = datetime.strptime(f[-1][:15], "%Y%m%d_%H%M%S"), datetime.strptime(f[-2], "%Y%m%dT%H%M%S")
            except ValueError:
                continue
            if e >= a and s <= z:
                loc = SRC + "\\interi\\" + f[-1]
                if not (os.path.exists(loc) and os.path.getsize(loc) == int(f[-3])):
                    scp(f"{PHONE}:rec/interi/{f[-1]}", loc)
                if os.path.exists(loc):
                    res.append((s, e, loc))
    return res


def altri_file(a, z):
    """File di PC (pc_*.flac) e A56 (notte_*.m4a) in tre_dispositivi che toccano [a,z]: [(dispositivo, inizio, fine, path)].
    ponytail: la durata si ricava decodificando a vuoto (i flac del PC non hanno la durata nell'header), con cache."""
    cache_f = SRC + r"\durate.json"
    cache = json.load(open(cache_f)) if os.path.exists(cache_f) else {}
    res = []
    for p in glob.glob(TRE + r"\*\*"):
        n = os.path.basename(p)
        dev = "PC" if n.startswith("pc_") else "A56" if n.startswith("notte_") else None
        if not dev or not n.endswith((".flac", ".m4a")):
            continue
        try:
            s = datetime.strptime(n.split("_", 1)[1][:15], "%Y%m%d_%H%M%S")
        except ValueError:
            continue
        if s > z or s < a - timedelta(hours=2):
            continue
        if n not in cache:
            m = re.findall(r"time=(\d+):(\d+):([\d.]+)", subprocess.run(["ffmpeg", "-i", p, "-f", "null", "-"],
                                                                        capture_output=True, text=True).stderr)
            cache[n] = int(m[-1][0]) * 3600 + int(m[-1][1]) * 60 + float(m[-1][2]) if m else 0
            json.dump(cache, open(cache_f, "w"))
        e = s + timedelta(seconds=cache[n])
        if e >= a:
            res.append((dev, s, e, p))
    return res


def decodifica(path, off, dur):
    p = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{off:.2f}", "-t", f"{dur:.2f}", "-i", path, "-ac", "1",
                        "-ar", "32000", "-f", "f32le", "-"], capture_output=True)
    return np.frombuffer(p.stdout, np.float32)


def sessioni():
    import onnxruntime as ort
    o = ort.SessionOptions()
    o.intra_op_num_threads, o.inter_op_num_threads = 2, 1  # ponytail: 2 thread, il resto resta al PC
    return [ort.InferenceSession(p, o, providers=["CPUExecutionProvider"])
            for p in (QUI + r"\panns\cnn14.onnx", QUI + r"\efficientat\mn10_as.onnx")]


def modelli(w, sess):
    """PANNs (finestre 2 s, passo 1 s) ed EfficientAT (5 s, passo 2 s): (prob PANNs[], prob Eff[])."""
    sp, se = sess
    cl = registro()["classi_audioset"]
    ALTRE.clear(); ALTRE.update(PANNs=[], EfficientAT=[])  # per finestra: {categoria: prob massima} (russa/respiro/movimento)
    def uno(sess_, x, nome):
        p = sess_.run(None, {"waveform": x[None]})[0][0]
        ALTRE[nome].append({c: float(max(p[i] for i in cl[c])) for c in ("russa", "respiro", "movimento")})
        return float(p[SNORING])
    pa = [uno(sp, w[i:i + 64000], "PANNs") for i in range(0, len(w) - 64000 + 1, 32000)]
    ef = [uno(se, w[i:i + 160000], "EfficientAT") for i in range(0, len(w) - 160000 + 1, 64000)]
    return pa, ef


def tratto(fonti, s, e, sess, acc=None):
    """Analizza [s,e] su [(inizio, fine, path)]: secondi sopra soglia / max / dB medio; None se coperto meno della meta'."""
    pa, ef, db, coperto = [], [], [], 0.0
    ultimo = s
    for fs, fe, p in sorted(fonti):  # file sovrapposti (due registrazioni dello stesso dispositivo): ogni minuto si conta una volta
        t, b = max(ultimo, fs), min(e, fe)
        ultimo = max(ultimo, b)
        while t < b:  # a pezzi da 5' (RAM bassa)
            d = min((b - t).total_seconds(), 300)
            w = decodifica(p, (t - fs).total_seconds(), d)
            if len(w) >= 64000:
                x, y = modelli(w, sess)
                if acc is not None:  # per minuto: finestre sopra soglia (anche 0 = minuto analizzato)
                    for nome, v, passo in (("PANNs", x, 1), ("EfficientAT", y, 2)):
                        for i, pr in enumerate(v):
                            m = (t + timedelta(seconds=i * passo)).replace(second=0, microsecond=0).isoformat(timespec="minutes")
                            acc[nome][m] = acc[nome].get(m, 0) + (pr > SOGLIA)
                            for c, v in ALTRE[nome][i].items():  # respiro/movimento: chiavi "PANNs:respiro", ...
                                if c != "russa":
                                    kk = acc.setdefault(f"{nome}:{c}", {})
                                    kk[m] = kk.get(m, 0) + (v > SOGLIA)
                pa += x; ef += y; db.append(10 * np.log10(np.mean(w ** 2) + 1e-12)); coperto += d
            t += timedelta(seconds=d)
    if coperto < 0.5 * (e - s).total_seconds():
        return None
    pa, ef = np.array(pa), np.array(ef)
    return dict(panns_max=round(float(pa.max()), 2), panns_s=int((pa > SOGLIA).sum()),
                eff_max=round(float(ef.max()), 2) if len(ef) else 0.0, eff_s=int((ef > SOGLIA).sum()),
                db=round(float(np.mean(db)), 1))


def verifica(per, a, z, sess):
    """Sui periodi con certezza bassa: PANNs+EfficientAT sul blocco intero A21s, poi gli stessi minuti su PC/A56 se ci sono."""
    interi, altri, n = blocchi_interi(a, z), altri_file(a, z), 0
    cache = SRC + rf"\permin_{CACHE_DAY[0]}.json"
    acc = json.load(open(cache)) if os.path.exists(cache) else {}
    acc.setdefault("PANNs", {}); acc.setdefault("EfficientAT", {})
    for p in per:
        if p["smentito"]:
            continue  # ponytail: i periodi gia' decisi si rianalizzano lo stesso, servono le celle per minuto della mappa
        s, e = p["da"] - timedelta(seconds=30), p["a"] + timedelta(seconds=30)
        r = tratto(interi, s, e, sess, acc)
        if r:
            p["prove"]["a21s"] = r
            p["panns"] |= r["panns_s"] >= SEC_MIN
            p["eff"] |= r["eff_s"] >= SEC_MIN
            n += 1
        for dev in sorted({d for d, *_ in altri}):
            x = tratto([(fs, fe, pp) for d, fs, fe, pp in altri if d == dev], s, e, sess)
            if x:
                x["si"] = x["panns_s"] >= SEC_MIN or x["eff_s"] >= SEC_MIN
                x["piu_forte_db"] = round(x["db"] - r["db"], 1) if r else None
                p["prove"][dev] = x
    if TUTTA[0]:
        tratto(interi, a, z, sess, acc)  # ponytail: calcola anche EfficientAT (stesso passaggio); costa poco in piu'
    json.dump(acc, open(cache, "w"))
    return n


def etichetta_minuti(J):
    """(nota rimossa)"""
    return f"{J['minuti_russare']} minuti di russare (PANNs)" if J.get("kaggle") else f"{J['minuti_russare']} minuti con colpi"


def certezza(p):
    if p["tu_si"]:
        return 4
    c = 3 if p["panns"] and p["eff"] else 2 if p["panns"] or p["eff"] else 1
    for dev in ("PC", "A56"):
        x = p["prove"].get(dev)
        if not x:
            continue
        if x["piu_forte_db"] is not None and x["piu_forte_db"] > PIU_FORTE_DB:
            p["sospetto_altro_dispositivo"] = True  # piu' forte sull'altro apparecchio: forse TikTok/telefono
            c = max(1, c - 1)
        elif x["si"]:
            c = min(3, c + 1)  # sentito anche da un altro dispositivo
    return c


# ---------- corsie per minuto (dal registro modelli.json) ----------
def registro():
    return json.load(open(QUI + r"\modelli.json", encoding="utf-8"))


def cats_yamnet(d):
    """Categorie presenti in un minuto YAMNet (piu' di una = scacchiera nel disegno)."""
    c = []
    if d["russa"]:
        c.append("russa")
    if d["respiro"] > 0 and not d["russa"] and d["picchi"] < 4:
        c.append("respiro")  # col russare il respiro c'e' sempre (237/237): non e' informazione
    if d["picchi"] >= 4:
        c.append("movimento")
    if d["voce"] >= 5:
        c.append("voce")
    if d["esterni"] >= 3 or d["esterno_top"] in ("tv_musica", "musica"):
        c.append("tiktok")
    return c


def cats_giudizio(r):
    """Categorie principali di una riga di giudizi.csv: sequenza (finestra) o 'era'; righe vecchie: russa/voce da 'detto'."""
    import mappa_etichette as ME
    toks = [t for t in re.split(r"[>+\[\]]", r.get("sequenza") or r.get("era") or "") if t]
    c = [ME.principale(t) for t in toks]
    if not c and r["giusto"] == "1" and r["detto"] in ("russa", "voce"):
        c = [r["detto"]]
    return [x if x in registro()["categorie"] or x == "silenzio" else "altro" for x in dict.fromkeys(c)]


def corsie(day, M, a, z, brevi):
    """Dal registro: [{nome, livello, colore, dove, celle: {minuto ISO: [categorie]}}]. Minuto assente = non analizzato."""
    iso = lambda k: k.isoformat(timespec="minutes")
    out = []
    cache = SRC + rf"\permin_{day}.json"
    pm = json.load(open(cache)) if os.path.exists(cache) else {}
    for m in registro()["modelli"]:
        if not m.get("attivo", True):
            continue
        if m["fonte"] == "minuti":
            celle = {iso(k): cats_yamnet(d) for k, d in M.items() if a <= k <= z}
        elif m["fonte"] == "permin":
            thr = m.get("min_finestre", SEC_MIN)
            celle = {k: ["russa"] if n >= thr else [] for k, n in pm.get(m["campo"], {}).items()}
            for c in ("respiro", "movimento"):
                for k, n in pm.get(f"{m['campo']}:{c}", {}).items():
                    if n >= thr:
                        celle[k] = celle.get(k, []) + [c]
        elif m["fonte"] == "giudizi":
            celle = {}
            for rg in csv.DictReader(open(SRC + r"\giudizi.csv", encoding="utf-8")):
                try:
                    t = datetime.strptime(rg["clip"].split("_", 1)[1][:13], "%Y%m%d_%H%M")
                except ValueError:
                    continue
                if a <= t <= z:
                    celle[iso(t)] = list(dict.fromkeys(celle.get(iso(t), []) + cats_giudizio(rg)))
        else:
            continue
        out.append(dict(nome=m["nome"], livello=m["livello"], colore=m["colore"], dove=m["dove"], celle=celle))
    return out


# ---------- uscita ----------
def intensita(c):  # ponytail: tagli a occhio sui colpi/minuto di YAMNet
    return "forte" if c >= 30 else "media" if c >= 10 else "lieve"


def scrivi(day, a, z, brevi, per, scartati, tempi, M=None):
    os.makedirs(OUT, exist_ok=True)
    righe = [dict(da=p["da"].isoformat(timespec="minutes"), a=p["a"].isoformat(timespec="minutes"), minuti=p["min"], densita_pct=p["dens"],
                  intensita=intensita(p["colpi"]), colpi_medi=round(p["colpi"], 1), certezza=p["c"], certezza_testo=TESTO[p["c"]],
                  sospetto_altro_dispositivo=p.get("sospetto_altro_dispositivo", False), prove=p["prove"]) for p in per]
    J = dict(notte=day, inizio=a.isoformat(timespec="minutes"), fine=z.isoformat(timespec="minutes"),
             brevi=[[s.isoformat(timespec="minutes"), e.isoformat(timespec="minutes")] for s, e in brevi],
             generata=datetime.now().isoformat(timespec="seconds"), tempi_s=tempi, periodi=righe,
             minuti_russare=sum(r["minuti"] for r in righe), scartati_da_te=scartati,
             corsie=corsie(day, M, a, z, brevi) if M else [], categorie=registro()["categorie"])
    base = f"{OUT}\\mappa_{day}"
    json.dump(J, open(base + ".json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["inizio", "fine", "minuti", "pct_russare", "pct_respiro", "pct_movimento", "intensita", "colpi_medi", "certezza", "certezza_testo"])
        for r in righe:
            w.writerow([r["da"][11:], r["a"][11:], r["minuti"], *(r["densita_pct"][k] for k in ("russare", "respiro", "movimento")), r["intensita"], r["colpi_medi"], r["certezza"], r["certezza_testo"]])
    disegna(J, base + SUFF[0] + ".png")
    return J, base


def disegna_righe(J, png):
    """Concept 3: la notte in 3 righe orizzontali uguali, tutte le fonti sulla STESSA striscia (un minuto = una striscia).
    3 categorie (russare, respiro, movimento). Colore = categoria; intensita' = chi l'ha sentita (registro: YAMNet pallido ->
    PANNs acceso; tue etichette = pieno + segno nero sotto). Piu' fonti concordi: vince il rango piu' alto. Due categorie: scacchiera."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
    from matplotlib.colors import to_rgb
    from matplotlib.patches import Rectangle
    pal = json.load(open(r"C:\sonno_bot\concept\palette.json"))
    C = {k: v["hex"] for k, v in pal.items() if isinstance(v, dict) and "hex" in v}
    fd = r"C:\sonno_bot\concept" + chr(92) + "fonts"
    for f in os.listdir(fd):
        if f.endswith(".ttf"):
            fm.fontManager.addfont(os.path.join(fd, f))
    SER, SANS = "DM Serif Display", "Barlow Condensed"
    W, H, CW, RH = 1080, 1350, 4, 34  # px; colonne immagine per minuto (3 di colore + 1 filo); righe immagine per striscia
    CATS = ("russa", "respiro", "movimento")
    NOME = {"russa": "russare", "respiro": "respiro", "movimento": "movimento"}
    CARTA, NOTTE = np.array(to_rgb(C["carta"])), np.array(to_rgb("#E7E0D0"))
    CC = {k: np.array(to_rgb(J["categorie"][k]["colore"])) for k in CATS}
    reg = {m["nome"]: m for m in registro()["modelli"]}
    tinta = lambda cat, f: CARTA + (CC[cat] - CARTA) * f  # f = intensita' del modello (registro)
    a, z = datetime.fromisoformat(J["inizio"]), datetime.fromisoformat(J["fine"])
    brevi = [(datetime.fromisoformat(x), datetime.fromisoformat(y)) for x, y in J["brevi"]]
    best, tu = {}, set()  # (minuto, categoria) -> (rango, intensita') del livello piu' alto; minuti con una tua etichetta
    for co in J["corsie"]:
        m = reg.get(co["nome"])
        if not m:
            continue
        for k, cs in co["celle"].items():
            for c in cs:
                if c not in CATS:
                    continue
                if (k, c) not in best or best[(k, c)][0] < m["rango"]:
                    best[(k, c)] = (m["rango"], m["intensita"])
                if m["fonte"] == "giudizi":
                    tu.add(k)
    import mappa_etichette as ME
    TUE = {}  # minuto -> {etichetta intera ('movimento/letto')} dalle tue categorizzazioni, solo le 3 categorie
    for rg in csv.DictReader(open(SRC + r"\giudizi.csv", encoding="utf-8")):
        try:
            t = datetime.strptime(rg["clip"].split("_", 1)[1][:13], "%Y%m%d_%H%M")
        except ValueError:
            continue
        toks = [x for x in re.split(r"[>+\[\]]", rg.get("sequenza") or rg.get("era") or "") if x]
        if not toks and rg["giusto"] == "1" and rg["detto"] in ("russa", "voce"):
            toks = [rg["detto"]]
        for x in toks:
            lab = ME.mappa(x)
            if lab.split("/")[0] in CATS and a <= t <= z:
                TUE.setdefault(t.isoformat(timespec="minutes"), set()).add(lab)
    dati = [datetime.fromisoformat(k) for k in set(k for k, _ in best) | set(TUE)]
    a_, z_ = (min(dati), max(dati)) if dati else (a, z)  # vuoti tagliati: la prima riga parte dal primo dato, l'ultima finisce all'ultimo
    colm = lambda nome, c: np.array(to_rgb(reg[nome]["colori"][c])) if "colori" in reg[nome] else tinta(c, reg[nome]["intensita"])
    tm = int((z_ - a_).total_seconds() // 60) + 1
    NR = RIGHE[0]
    pz = -(-tm // NR)  # minuti per riga
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=200, facecolor=C["carta"])
    INK, DIM = C["inchiostro"], "#4A5060"

    def T(x, y, t, **k):
        fig.text(x / W, 1 - y / H, t, va=k.pop("va", "center"), ha=k.pop("ha", "left"), **k)

    def rett(x, y, w, h, col):  # px dall'angolo in alto a sinistra
        fig.patches.append(Rectangle((x / W, 1 - (y + h) / H), w / W, h / H, transform=fig.transFigure, color=col, lw=0))

    def filo(x, y1, y2, lw):
        fig.add_artist(plt.Line2D([x / W] * 2, [1 - y1 / H, 1 - y2 / H], color=INK, lw=lw, zorder=5))
    T(36, 52, "Mappa del russare", fontsize=40, family=SER, color=INK)
    if VERS[0]:
        T(W - 36, 46, "v " + VERS[0], fontsize=40, family=SANS, weight="bold", color=C["russa"], ha="right")
    T(36, 96, f"notte del {z:%d/%m} · {a:%H:%M}–{z:%H:%M} · {etichetta_minuti(J)}", fontsize=17, family=SANS, weight="medium", color=DIM)
    T(36, 122, f"la notte in {RIGHE[0]} righe · colore = cosa · alto e pallido = scrematura, basso e acceso = preciso", fontsize=17, family=SANS, weight="medium", color=DIM)
    X0, RW, TOP = 36, 1008, 215
    PITCH = min(295, 860 // NR)
    RHP = PITCH - 72
    for r_ in range(NR):
        rs = a_ + timedelta(minutes=r_ * pz)
        y0 = TOP + r_ * PITCH
        rett(X0, y0, RW, RHP, NOTTE)  # sfondo: la notte
        fine = min(pz, int((z_ - rs).total_seconds() // 60) + 1)
        if fine < pz:
            rett(X0 + fine * RW / pz, y0, RW - fine * RW / pz, RHP, CARTA)
        px = lambda t: X0 + (t - rs).total_seconds() / 60 / pz * RW
        sq = [tuple(sorted(TUE.get((rs + timedelta(minutes=m)).isoformat(timespec="minutes"), ()))) for m in range(pz)]
        m = 0
        while m < pz:  # le tue etichette: linea SOTTO le barre; stesso colore della categoria, tono diverso per le sottocategorie
            n_ = m
            while n_ + 1 < pz and sq[n_ + 1] == sq[m]:
                n_ += 1
            for q, lab in enumerate(sq[m]):
                c = lab.split("/")[0]
                tc = np.array(to_rgb(registro()["categorie"][c].get("colore_tue", J["categorie"][c]["colore"])))
                col_ = tc if "/" not in lab else (tc * .8 + .2 if sum(map(ord, lab)) % 2 else tc * .8)  # sottocategoria: stessa tinta, un tono piu' chiaro o piu' cupo
                col_ = np.clip(col_, 0, 1)
                rett(X0 + m * RW / pz, y0 + RHP + 3 + q * 11 / len(sq[m]), (n_ - m + 1) * RW / pz, 11 / len(sq[m]), col_)
            m = n_ + 1
        for co in sorted((c for c in J["corsie"] if c["nome"] in reg and reg[c["nome"]].get("altezza") and reg[c["nome"]]["fonte"] != "giudizi"), key=lambda c: reg[c["nome"]]["rango"]):
            m_ = reg[co["nome"]]
            hh = RHP * m_["altezza"]
            ys = y0 + (RHP - hh) / 2 if ALLINEA[0] == "centro" else y0 + RHP - hh
            seq = [tuple(c for c in CATS if c in co["celle"].get((rs + timedelta(minutes=m)).isoformat(timespec="minutes"), [])) for m in range(pz)]
            m = 0
            while m < pz:  # minuti adiacenti con le stesse categorie = un solo rettangolo
                n_ = m
                while n_ + 1 < pz and seq[n_ + 1] == seq[m]:
                    n_ += 1
                cs_ = seq[m]
                for q, c in enumerate(cs_):  # piu' categorie nello stesso minuto: strisce affiancate, MAI altezza dimezzata
                    for mm in range(m, n_ + 1) if len(cs_) > 1 else [m]:
                        w1 = RW / pz * (1 if len(cs_) > 1 else n_ - m + 1) / len(cs_)
                        x1 = X0 + mm * RW / pz + (q * w1 if len(cs_) > 1 else 0)
                        if TEXTURE[0]:  # livello = tratteggio (BASSO puntini, MEDIO righe, PRECISO reticolo), categoria = colore
                            fig.patches.append(Rectangle((x1 / W, 1 - (ys + hh) / H), w1 / W, hh / H, transform=fig.transFigure,
                                                         facecolor=CARTA + (colm(co["nome"], c) - CARTA) * .35, edgecolor=colm(co["nome"], c),
                                                         hatch={1: "....", 2: "////", 3: "xxxx"}.get(m_["rango"], "//"), lw=0, zorder=3))
                        else:
                            rett(x1, ys, w1, hh, colm(co["nome"], c))
                m = n_ + 1
        h = rs.replace(minute=0, second=0) + timedelta(hours=1)
        while h < rs + timedelta(minutes=pz):  # ore sotto la riga
            filo(px(h), y0 + RHP + 12, y0 + RHP + 26, .8)
            T(px(h), y0 + RHP + 40, f"{h:%H:%M}", fontsize=14, family=SANS, weight="semibold", color=INK, ha="center")
            h += timedelta(hours=1)
        sv = [(bs + (be - bs) / 2, bs) for bs, be in brevi] + ([(z + timedelta(minutes=1), z)] if r_ == NR - 1 else [])
        for w_, ora in sv:  # risvegli (brevi e finale): linea verticale spessa con l'ora
            if rs <= w_ < rs + timedelta(minutes=pz) or (r_ == NR - 1 and w_ >= rs):
                x = min(px(w_), X0 + RW)
                filo(x, y0 - 12, y0 + RHP + 4, 3.4)
                T(x, y0 - 26, f"{ora:%H:%M}", fontsize=15, family=SANS, weight="bold", color=INK, ha="right" if x > X0 + RW - 40 else "center")
    # legenda minima: righe = categorie, colonne = fonti (dal registro)
    y = TOP + (NR - 1) * PITCH + RHP + 85
    T(36, y, "Più basso e più acceso = più preciso", fontsize=22, family=SER, color=INK)
    fonti = [co for co in J["corsie"] if co["nome"] in reg]
    cx = [190 + i * 215 for i in range(len(fonti))]
    for x, co in zip(cx, fonti):
        T(x, y + 36, co["nome"], fontsize=14, family=SANS, weight="semibold", color=INK)
        T(x, y + 55, co["livello"].replace("_", " "), fontsize=12.5, family=SANS, weight="medium", color=DIM)
    for i, c in enumerate(CATS):  # legenda COMPLETA: ogni fonte x categoria, anche se nella notte non compare
        yy = y + 92 + i * 32
        T(36, yy, NOME[c], fontsize=15, family=SANS, weight="medium", color=INK)
        for x, co in zip(cx, fonti):
            if reg[co["nome"]]["fonte"] == "giudizi":
                rett(x, yy - 5, 70, 11, np.array(to_rgb(registro()["categorie"][c]["colore_tue"])))
            else:
                rett(x, yy - 11, 70, 22, colm(co["nome"], c))
    yy = y + 92 + 3 * 32 + 8
    for i in range(2):  # campione di scacchiera
        for j in range(4):
            rett(36 + 9 * j, yy - 11 + 11 * i, 9, 11, tinta(("russa", "movimento")[(i + j) % 2], 1.0))
    T(36 + 52, yy, "due cose nello stesso minuto = strisce affiancate", fontsize=15, family=SANS, weight="medium", color=INK)
    filo(480, yy - 12, yy + 12, 3.4)
    T(494, yy, "linea nera = risveglio, con l'ora", fontsize=15, family=SANS, weight="medium", color=INK)
    fig.savefig(png, facecolor=C["carta"])
    plt.close(fig)


GRIGLIE = {"righe": 3, "alt": False, "terra": False, "opaco": False}  # D1: 3 righe, celle a piena altezza; D2: 5 righe, altezza per livello (centrata o a terra)


def disegna_griglie(J, png):
    """Variante D: griglie SOVRAPPOSTE per categoria (russare = campo pieno sullo sfondo, respiro = righe orizzontali, movimento = righe
    verticali in cima), semi-trasparenti; colore = livello piu' alto che l'ha sentita (da modelli.json). La notte in DUE immagini
    (png con suffisso _1 e _2), 3 righe ciascuna, una cella = un minuto. Linea delle tue etichette sotto, come nella A."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
    from matplotlib.colors import to_rgb
    from matplotlib.patches import Rectangle
    import mappa_etichette as ME
    plt.rcParams["hatch.linewidth"] = 1.7
    pal = json.load(open(r"C:\sonno_bot\concept\palette.json"))
    C = {k: v["hex"] for k, v in pal.items() if isinstance(v, dict) and "hex" in v}
    fd = r"C:\sonno_bot\concept" + chr(92) + "fonts"
    for f in os.listdir(fd):
        if f.endswith(".ttf"):
            fm.fontManager.addfont(os.path.join(fd, f))
    SER, SANS = "DM Serif Display", "Barlow Condensed"
    W, H = 1080, 1350
    CATS = ("russa", "respiro", "movimento")
    HAT = {"russa": None, "respiro": "-----", "movimento": "|||||"}
    NOME = {"russa": "russare", "respiro": "respiro", "movimento": "movimento"}
    reg = {m["nome"]: m for m in registro()["modelli"]}
    CARTA, NOTTE = np.array(to_rgb(C["carta"])), np.array(to_rgb("#E7E0D0"))
    a, z = datetime.fromisoformat(J["inizio"]), datetime.fromisoformat(J["fine"])
    brevi = [(datetime.fromisoformat(x), datetime.fromisoformat(y)) for x, y in J["brevi"]]
    best = {}  # (minuto, categoria) -> (rango, colore) del livello piu' alto
    for co in J["corsie"]:
        m = reg.get(co["nome"])
        if not m or m["fonte"] == "giudizi" or "colori" not in m:
            continue
        for k, cs in co["celle"].items():
            for c in cs:
                if c in CATS and ((k, c) not in best or best[(k, c)][0] < m["rango"]):
                    best[(k, c)] = (m["rango"], m["colori"][c], m["altezza"])
    TUE = {}
    for rg in csv.DictReader(open(SRC + r"\giudizi.csv", encoding="utf-8")):
        try:
            t = datetime.strptime(rg["clip"].split("_", 1)[1][:13], "%Y%m%d_%H%M")
        except ValueError:
            continue
        toks = [x for x in re.split(r"[>+\[\]]", rg.get("sequenza") or rg.get("era") or "") if x]
        if not toks and rg["giusto"] == "1" and rg["detto"] in ("russa", "voce"):
            toks = [rg["detto"]]
        for x in toks:
            lab = ME.mappa(x)
            if lab.split("/")[0] in CATS and a <= t <= z:
                TUE.setdefault(t.isoformat(timespec="minutes"), set()).add(lab)
    dati = [datetime.fromisoformat(k) for k in set(k for k, _ in best) | set(TUE)]
    a_, z_ = (min(dati), max(dati)) if dati else (a, z)
    tm = int((z_ - a_).total_seconds() // 60) + 1
    NR, PARTI = GRIGLIE["righe"], 2
    pz = -(-tm // (NR * PARTI))  # minuti per riga
    INK, DIM = C["inchiostro"], "#4A5060"
    X0, RW, TOP = 36, 1008, 215
    PITCH = min(292, 880 // NR)
    RHP = PITCH - 77
    DS = 0
    NONAN = [False]
    CHIARO = to_rgb("#F4EFE6")
    tc = lambda lab: (lambda b: b if "/" not in lab else (b * .8 + .2 if sum(map(ord, lab)) % 2 else b * .8))(
        np.array(to_rgb(registro()["categorie"][lab.split("/")[0]]["colore_tue"])))
    for parte in range(PARTI):
        fig = plt.figure(figsize=(W / 100, H / 100), dpi=200, facecolor=C["carta"])

        def T(x, y, t, **k):
            fig.text(x / W, 1 - y / H, t, va=k.pop("va", "center"), ha=k.pop("ha", "left"), **k)

        def rett(x, y, w, h, **k):
            fig.patches.append(Rectangle((x / W, 1 - (y + h) / H), w / W, h / H, transform=fig.transFigure, **k))

        def filo(x, y1, y2, lw):
            fig.add_artist(plt.Line2D([x / W] * 2, [1 - y1 / H, 1 - y2 / H], color=INK, lw=lw, zorder=30))
        dv = J.get("device")
        T(36, 52, "Mappa del russare" + (f" · {dv}" if dv else ""), fontsize=34 if dv else 40, family=SER, color=INK)
        T(W - 36, 46, (f"{dv.split()[0]} · " if dv else f"v {VERS[0]} · ") + f"{parte + 1}/{PARTI}", fontsize=40, family=SANS, weight="bold", color=C["russa"], ha="right")
        T(36, 96, f"notte del {z:%d/%m} · {a:%H:%M}–{z:%H:%M} · {etichetta_minuti(J)}", fontsize=17, family=SANS, weight="medium", color=DIM)
        T(36, 122, "livelli annidati: il più preciso (PANNs w2) è il più piccolo, al centro · russare = rosso · respiro = blu · movimento = ocra", fontsize=17, family=SANS, weight="medium", color=DIM)
        for r_ in range(NR):
            rs = a_ + timedelta(minutes=(parte * NR + r_) * pz)
            y0 = TOP + r_ * PITCH
            fine = min(pz, int((z_ - rs).total_seconds() // 60) + 1)
            if fine <= 0:
                continue
            cw = RW / pz
            rett(X0, y0, RW, RHP, color=NOTTE, lw=0)
            if fine < pz:
                rett(X0 + fine * cw, y0, RW - fine * cw, RHP, color=CARTA, lw=0)
            for m in range(fine):  # nessun modello ha analizzato quel minuto: bianco (diverso dal beige = silenzio)
                k_ = (rs + timedelta(minutes=m)).isoformat(timespec="minutes")
                if not any(k_ in c_["celle"] for c_ in J["corsie"] if c_["nome"] in reg and reg[c_["nome"]]["fonte"] != "giudizi"):
                    rett(X0 + m * cw, y0, cw, RHP, facecolor="#FFFFFF", lw=0, zorder=0.5)
                    NONAN[0] = True
            pn = next((c_["celle"] for c_ in J["corsie"] if c_["nome"] == "PANNs"), {})  # linea al centro: PANNs ha ascoltato (sotto i rettangoli)
            m = 0
            while m < fine:
                if (rs + timedelta(minutes=m)).isoformat(timespec="minutes") in pn:
                    n_ = m
                    while n_ + 1 < fine and (rs + timedelta(minutes=n_ + 1)).isoformat(timespec="minutes") in pn:
                        n_ += 1
                    rett(X0 + m * cw, y0 + RHP / 2 - RHP * .025, (n_ - m + 1) * cw, RHP * .05, facecolor="#5A544A", lw=0, zorder=12.5)
                    m = n_
                m += 1
            for co in (sorted((c_ for c_ in J["corsie"] if c_["nome"] in reg and reg[c_["nome"]]["fonte"] != "giudizi" and "colori" in reg[c_["nome"]]),
                              key=lambda c_: reg[c_["nome"]]["rango"]) if GRIGLIE["opaco"] else []):
                mo = reg[co["nome"]]  # D3: un livello per volta, dal meno al piu' preciso, tutto OPACO: il preciso copre quello sotto
                hh = RHP * mo["altezza"]
                yc = y0 + RHP - hh if GRIGLIE["terra"] else y0 + (RHP - hh) / 2
                for m in range(fine):
                    cs_ = [c for c in CATS if c in co["celle"].get((rs + timedelta(minutes=m)).isoformat(timespec="minutes"), [])]
                    NB = 6 if len(cs_) > 1 else len(cs_)  # piu' categorie nello stesso minuto: barrette verticali alternate, colori pieni, nessuna linea
                    for q in range(NB):
                        c = cs_[q % len(cs_)]
                        col = np.array(to_rgb(mo["colori"][c]))
                        rett(X0 + m * cw + q * cw / NB, yc, cw / NB, hh, zorder=10 + mo["rango"], facecolor=col, edgecolor=col, lw=.25)
            for c in ([] if GRIGLIE["opaco"] else CATS):  # ordine fisso: russare sotto, respiro, movimento in cima
                for m in range(fine):
                    b = best.get(((rs + timedelta(minutes=m)).isoformat(timespec="minutes"), c))
                    if not b:
                        continue
                    col = to_rgb(b[1])
                    hh = RHP * b[2] if GRIGLIE["alt"] else RHP
                    yc = y0 + RHP - hh if GRIGLIE["terra"] else y0 + (RHP - hh) / 2
                    if HAT[c] is None:
                        rett(X0 + m * cw, yc, cw, hh, facecolor=col + (.9,), edgecolor=to_rgb("#E7E0D0"), lw=.4, zorder=1)
                    else:
                        rett(X0 + m * cw, yc, cw, hh, facecolor="none", edgecolor=col + (.85,), hatch=HAT[c], lw=0, zorder=2 if c == "respiro" else 3)
            px = lambda t: X0 + (t - rs).total_seconds() / 60 / pz * RW
            sq = [tuple(sorted(TUE.get((rs + timedelta(minutes=m)).isoformat(timespec="minutes"), ()))) for m in range(fine)]
            for m, labs in enumerate(sq):
                for q, lab in enumerate(labs):
                    rett(X0 + m * cw, y0 + RHP + 3 + DS + q * 12 / len(labs), cw, 12 / len(labs), facecolor=tc(lab), edgecolor=tc(lab), lw=.25)
            h = rs.replace(minute=0, second=0) + timedelta(hours=1)
            while h < rs + timedelta(minutes=pz):
                filo(px(h), y0 + RHP + 18 + DS, y0 + RHP + 32 + DS, .8)
                T(px(h), y0 + RHP + 46 + DS, f"{h:%H:%M}", fontsize=14, family=SANS, weight="semibold", color=INK, ha="center")
                h += timedelta(hours=1)
            ult = parte == PARTI - 1 and r_ == NR - 1
            for w_, ora in [(bs + (be - bs) / 2, bs) for bs, be in brevi] + ([(z + timedelta(minutes=1), z)] if ult else []):
                if rs <= w_ < rs + timedelta(minutes=pz) or (ult and w_ >= rs):
                    x = min(px(w_), X0 + RW)
                    filo(x, y0 - 12, y0 + RHP + 4, 3.4)
                    T(x, y0 - 26, f"{ora:%H:%M}", fontsize=15, family=SANS, weight="bold", color=INK, ha="right" if x > X0 + RW - 40 else "center")
        y = TOP + (NR - 1) * PITCH + RHP + 78 + DS  # legenda: categoria x fonte (campioni con la texture della categoria)
        T(36, y, "Più basso e più acceso = più preciso", fontsize=22, family=SER, color=INK)
        fonti = [m for m in registro()["modelli"] if m.get("attivo", True) and m["fonte"] != "nessuna" and (m["fonte"] != "kaggle" or any(c_["nome"] == m["nome"] for c_ in J["corsie"]))]
        cx = [190 + i * min(215, 850 // len(fonti)) for i in range(len(fonti))]
        for x, m in zip(cx, fonti):
            T(x, y + 34, m["nome"], fontsize=14, family=SANS, weight="semibold", color=INK)
        for i, c in enumerate(CATS):
            yy = y + 66 + i * 30
            T(36, yy, NOME[c], fontsize=15, family=SANS, weight="medium", color=INK)
            for x, m in zip(cx, fonti):
                if m["fonte"] == "giudizi":
                    rett(x, yy - 5, 70, 11, facecolor=tc(c), lw=0)
                else:
                    col = to_rgb(m["colori"][c])
                    rett(x, yy - 11, 70, 22, facecolor=col, lw=0)
        filo(36, y + 66 + 3 * 30 - 6, y + 66 + 3 * 30 + 16, 3.4)
        T(50, y + 66 + 3 * 30 + 5, "linea nera = risveglio, con l'ora", fontsize=15, family=SANS, weight="medium", color=INK)
        rett(400, y + 66 + 3 * 30 - 4, 24, 20, facecolor=NOTTE, lw=0)
        T(430, y + 66 + 3 * 30 + 5, "beige = silenzio", fontsize=15, family=SANS, weight="medium", color=INK)
        rett(560, y + 66 + 3 * 30 + 3, 40, 4, facecolor="#5A544A", lw=0)
        T(608, y + 66 + 3 * 30 + 5, "linea al centro = PANNs ha ascoltato (niente = silenzio)", fontsize=15, family=SANS, weight="medium", color=INK)
        if NONAN[0]:
            rett(430, y + 66 + 3 * 30 + 22, 24, 20, facecolor="#FFFFFF", lw=0)
            T(460, y + 66 + 3 * 30 + 33, "bianco = non analizzato", fontsize=15, family=SANS, weight="medium", color=INK)
        fig.savefig(png.replace(".png", f"_{parte + 1}.png"), facecolor=C["carta"])
        plt.close(fig)


def due_celle(d, v, dev):
    """CSV Kaggle -> {minuto: set(categorie)}; minuto presente = il dispositivo registrava. Regola della mappa: n02 >= 3, respiro scartato col russare."""
    celle = {}
    for r in csv.DictReader(open(rf"{d}\panns_{v}_p1.csv", encoding="utf-8")):
        if r["dispositivo"] == dev:
            cs = {c for c, k in (("russa", "snoring"), ("respiro", "respiro"), ("movimento", "movimento")) if int(r[k + "_n02"]) >= 3}
            if "russa" in cs:
                cs.discard("respiro")
            celle.setdefault(r["minuto"], set()).update(cs)
    return celle


def disegna_due(kg, day, png):
    """Variante DUE: PANNs dei due telefoni sulla stessa notte. Ogni riga ha due bande (sopra A21s, sotto A56): w10 + w2 al centro,
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
    from matplotlib.colors import to_rgb
    from matplotlib.patches import Rectangle
    import mappa_etichette as ME
    pal = json.load(open(r"C:\sonno_bot\concept\palette.json"))
    C = {k: v["hex"] for k, v in pal.items() if isinstance(v, dict) and "hex" in v}
    fd = r"C:\sonno_bot\concept" + chr(92) + "fonts"
    for f in os.listdir(fd):
        if f.endswith(".ttf"):
            fm.fontManager.addfont(os.path.join(fd, f))
    SER, SANS = "DM Serif Display", "Barlow Condensed"
    W, H, CATS = 1080, 1350, ("russa", "respiro", "movimento")
    reg = {m["nome"]: m for m in registro()["modelli"]}
    CARTA, NOTTE, INK, DIM = C["carta"], "#E7E0D0", C["inchiostro"], "#4A5060"
    d0 = datetime.strptime(day, "%Y%m%d")
    a_, z_ = d0.replace(hour=1, minute=16), d0.replace(hour=13, minute=25)
    DEV = [("a21s", "A21s"), ("a56", "A56")]
    D = {(dv, v): due_celle(kg, v, dv) for dv, _ in DEV for v in ("w10", "w2")}
    tm = int((z_ - a_).total_seconds() // 60) + 1
    NR, PARTI = 5, 2
    pz = -(-tm // (NR * PARTI))
    X0, RW, TOP = 70, 974, 215
    PITCH = 176
    RHP = PITCH - 77
    BH = (RHP - 4) / 2
    TUE = {"a21s": {}, "a56": {}}  # etichette per telefono: il nome della clip non dice il dispositivo, tutte vengono dal bot dell'A21s -> default sopra A21s
    for rg in csv.DictReader(open(SRC + r"\giudizi.csv", encoding="utf-8")):
        try:
            t = datetime.strptime(rg["clip"].split("_", 1)[1][:13], "%Y%m%d_%H%M")
        except ValueError:
            continue
        toks = [x for x in re.split(r"[>+\[\]]", rg.get("sequenza") or rg.get("era") or "") if x]
        if not toks and rg["giusto"] == "1" and rg["detto"] in ("russa", "voce"):
            toks = [rg["detto"]]
        pre = rg["clip"].split("_", 1)[0].lower()
        dv_ = "a56" if pre in ("a56", "pc") else "a21s"
        for x in toks:
            lab = ME.mappa(x)
            if lab.split("/")[0] in CATS and a_ <= t <= z_:
                TUE[dv_].setdefault(t.isoformat(timespec="minutes"), set()).add(lab)
    tc = lambda lab: (lambda b: b if "/" not in lab else (b * .8 + .2 if sum(map(ord, lab)) % 2 else b * .8))(
        np.array(to_rgb(registro()["categorie"][lab.split("/")[0]]["colore_tue"])))
    col = lambda nome, c: to_rgb(reg[nome]["colori"][c])
    for parte in range(PARTI):
        fig = plt.figure(figsize=(W / 100, H / 100), dpi=200, facecolor=CARTA)

        def T(x, y, t, **k):
            fig.text(x / W, 1 - y / H, t, va=k.pop("va", "center"), ha=k.pop("ha", "left"), **k)

        def rett(x, y, w, h, **k):
            fig.patches.append(Rectangle((x / W, 1 - (y + h) / H), w / W, h / H, transform=fig.transFigure, **k))
        T(36, 52, "PANNs: A21s vs A56", fontsize=40, family=SER, color=INK)
        T(W - 36, 46, f"{parte + 1}/{PARTI}", fontsize=40, family=SANS, weight="bold", color=C["russa"], ha="right")
        T(36, 96, f"notte del 01-02/10 · {a_:%H:%M}–{z_:%H:%M} · sopra A21s (comodino), sotto A56 (telefono)", fontsize=17, family=SANS, weight="medium", color=DIM)
        T(36, 122, "russare = rosso · respiro = blu · movimento = ocra · grande = PANNs w10, piccolo al centro = w2", fontsize=17, family=SANS, weight="medium", color=DIM)
        for r_ in range(NR):
            rs = a_ + timedelta(minutes=(parte * NR + r_) * pz)
            y0 = TOP + r_ * PITCH
            fine = min(pz, int((z_ - rs).total_seconds() // 60) + 1)
            if fine <= 0:
                continue
            cw = RW / pz
            key = lambda m: (rs + timedelta(minutes=m)).isoformat(timespec="minutes")
            for k, (dv, nome) in enumerate(DEV):
                by = y0 + k * (BH + 4)
                T(X0 - 8, by + BH / 2, nome, fontsize=13, family=SANS, weight="bold", color=INK, ha="right")
                rec = D[(dv, "w10")]
                for m in range(fine):
                    fc = NOTTE if key(m) in rec else "#FFFFFF"
                    rett(X0 + m * cw, by, cw, BH, facecolor=fc, edgecolor=fc, lw=.25, zorder=1)
                m = 0
                while m < fine:  # linea centrale = ascoltato (sotto i rettangoli)
                    if key(m) in rec:
                        n_ = m
                        while n_ + 1 < fine and key(n_ + 1) in rec:
                            n_ += 1
                        rett(X0 + m * cw, by + BH / 2 - BH * .035, (n_ - m + 1) * cw, BH * .07, facecolor="#5A544A", lw=0, zorder=5)
                        m = n_
                    m += 1
                for v, nm, fr, zo in (("w10", "PANNs", .7, 10), ("w2", "PANNs w2", .35, 11)):
                    hh = BH * fr
                    for m in range(fine):
                        cs_ = [c for c in CATS if c in D[(dv, v)].get(key(m), ())]
                        NB = 6 if len(cs_) > 1 else len(cs_)
                        for q in range(NB):
                            c = col(nm, cs_[q % len(cs_)])
                            rett(X0 + m * cw + q * cw / NB, by + (BH - hh) / 2, cw / NB, hh, facecolor=c, edgecolor=c, lw=.25, zorder=zo)
            for m in range(fine):  # A21s: linea SOPRA la banda; A56: linea SOTTO la banda
                for dv_, yl in (("a21s", y0 - 15), ("a56", y0 + RHP + 3)):
                    labs = sorted(TUE[dv_].get(key(m), ()))
                    for q, lab in enumerate(labs):
                        rett(X0 + m * cw, yl + q * 12 / len(labs), cw, 12 / len(labs), facecolor=tc(lab), edgecolor=tc(lab), lw=.25)
            h = rs.replace(minute=0, second=0) + timedelta(hours=1)
            while h < rs + timedelta(minutes=pz):
                x = X0 + (h - rs).total_seconds() / 60 / pz * RW
                fig.add_artist(plt.Line2D([x / W] * 2, [1 - (y0 + RHP + 18) / H, 1 - (y0 + RHP + 32) / H], color=INK, lw=.8))
                T(x, y0 + RHP + 46, f"{h:%H:%M}", fontsize=14, family=SANS, weight="semibold", color=INK, ha="center")
                h += timedelta(hours=1)
        y = TOP + (NR - 1) * PITCH + RHP + 78
        T(36, y, "Stessa notte, stesso asse del tempo", fontsize=22, family=SER, color=INK)
        for i, c in enumerate(CATS):
            x = 36 + i * 150
            rett(x, y + 26, 22, 22, facecolor=col("PANNs", c), lw=0)
            T(x + 30, y + 37, {"russa": "russare", "respiro": "respiro", "movimento": "movimento"}[c], fontsize=15, family=SANS, weight="medium", color=INK)
        rett(500, y + 26, 22, 22, facecolor=NOTTE, lw=0)
        T(530, y + 37, "beige = silenzio (ascoltato)", fontsize=15, family=SANS, weight="medium", color=INK)
        rett(36, y + 62, 22, 22, facecolor="#FFFFFF", lw=0)
        T(66, y + 73, "bianco = non registrava", fontsize=15, family=SANS, weight="medium", color=INK)
        rett(266, y + 71, 36, 4, facecolor="#5A544A", lw=0)
        T(310, y + 73, "linea al centro = ascoltato", fontsize=15, family=SANS, weight="medium", color=INK)
        rett(540, y + 66, 22, 14, facecolor=tc("russa"), lw=0)
        T(570, y + 73, "barra = tue etichette, accanto al loro telefono (ignoto: A21s)", fontsize=15, family=SANS, weight="medium", color=INK)
        fig.savefig(png.replace(".png", f"_{parte + 1}.png"), facecolor=CARTA)
        plt.close(fig)
    for v in ("w10", "w2"):
        A, B = D[("a21s", v)], D[("a56", v)]
        com = [k for k in A if k in B and "00:00" <= k[11:] <= "23:59"]
        for c in ("russa", "respiro"):
            ab = sum(c in A[k] and c in B[k] for k in com)
            sa = sum(c in A[k] and c not in B[k] for k in com)
            sb = sum(c in B[k] and c not in A[k] for k in com)
            print(f"{v} {c}: minuti in comune {len(com)}, entrambi {ab}, solo A21s {sa}, solo A56 {sb}, nessuno {len(com) - ab - sa - sb}")


ALLINEA, TEXTURE, VERS = ["centro"], [False], [""]  # variante A: centro; B: terra; C: centro + texture
RIGHE = [5]  # --righe N (stile righe)
SUFF = [""]  # suffisso del file PNG ("_corsie" per la variante a corsie)
STILE = ["righe"]  # "righe" (predefinito, concept 3) | "corsie" = una corsia per modello | "bande" = modelli come bande nella stessa cella


def disegna(J, png):
    if STILE[0] == "griglie":
        return disegna_griglie(J, png)
    if STILE[0] == "righe":
        return disegna_righe(J, png)
    """4:5 (1080x1350 a 200 dpi), stile giornale. Una colonna lunga = il tempo (spezzata in 2 se serve), accanto una corsia stretta per
    modello (dal registro modelli.json, gia' in J["corsie"]) + "tue etichette". Una cella = un minuto. Due o piu' cose insieme:
    la cella e' una scacchiera dei loro colori (mai colori mescolati)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager as fm
    from matplotlib.colors import to_rgb
    from matplotlib.patches import Rectangle, Polygon
    pal = json.load(open(r"C:\sonno_bot\concept\palette.json"))
    C = {k: v["hex"] for k, v in pal.items() if isinstance(v, dict) and "hex" in v}
    fd = r"C:\sonno_bot\concept\fonts"
    for f in os.listdir(fd):
        if f.endswith(".ttf"):
            fm.fontManager.addfont(os.path.join(fd, f))
    SER, SANS = "DM Serif Display", "Barlow Condensed"
    W, H, PXM, R, CN = 1080, 1350, 3.5, 7, 10  # px per minuto (a 1x); righe immagine per minuto (6 di colore + 1 di filo); colonne della scacchiera
    CAT = {k: to_rgb(v["colore"]) for k, v in J["categorie"].items()}
    CAT["silenzio"] = to_rgb("#CFC8BA")
    NON, VUOTO, SVEGLIO, CARTA = to_rgb("#E6DFD0"), to_rgb("#FFFFFF"), to_rgb("#D9C58F"), to_rgb(C["carta"])
    a, z = datetime.fromisoformat(J["inizio"]), datetime.fromisoformat(J["fine"])
    t0 = a.replace(minute=0, second=0)
    t1 = (z + timedelta(minutes=1)).replace(second=0)
    t1 = t1.replace(minute=0) + timedelta(minutes=30 * -(-t1.minute // 30))  # fine colonna: mezz'ora piena dopo la sveglia
    brevi = [(datetime.fromisoformat(x), datetime.fromisoformat(y)) for x, y in J["brevi"]]
    tot = int((t1 - t0).total_seconds() // 60)
    if tot > 300:  # troppo lunga per 4:5: due colonne, taglio a un'ora piena che le rende piu' uguali
        tagli = [t0 + timedelta(hours=h) for h in range(1, int(tot // 60) + 1) if t0 + timedelta(hours=h) < t1]
        sp = min(tagli, key=lambda t: max((t - t0).total_seconds(), (t1 - t).total_seconds()))
        cols = [(t0, sp), (sp, t1)]
    else:
        cols = [(t0, t1)]
    lunga = max(int((e - s).total_seconds() // 60) for s, e in cols)
    corsie_ = J["corsie"]
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=200, facecolor=C["carta"])

    def T(x, y, t, **k):  # px dall'angolo in alto a sinistra
        fig.text(x / W, 1 - y / H, t, va=k.pop("va", "center"), ha=k.pop("ha", "left"), **k)
    INK, DIM = C["inchiostro"], "#4A5060"
    T(36, 52, "Mappa del russare", fontsize=40, family=SER, color=INK)
    T(36, 96, f"notte del {z:%d/%m} · {a:%H:%M}–{z:%H:%M} · {etichetta_minuti(J)}",
      fontsize=17, family=SANS, weight="medium", color=DIM)
    T(36, 122, ("una cella = un minuto · tre bande per cella = i modelli, dal meno al piu' preciso" if STILE[0] != "corsie" else "una cella = un minuto · la notte scorre dall'alto in basso"), fontsize=17, family=SANS, weight="medium", color=DIM)
    TOP = 214
    bw = (W - 72 - 24 * (len(cols) - 1)) / len(cols)
    disp = bw - 68  # larghezza per le corsie
    if STILE[0] == "corsie":
        gr = [[c] for c in corsie_]
        gw = [(disp - 6 * (len(gr) - 1)) / len(gr)] * len(gr)
    else:  # modelli insieme (una banda ciascuno, contigue) + corsia stretta per i giudizi
        gr = [[c for c in corsie_ if c["nome"] != "Tue etichette"], [c for c in corsie_ if c["nome"] == "Tue etichette"]]
        gr = [g for g in gr if g]
        gw = [(disp - 14) * .76, (disp - 14) * .24][:len(gr)] if len(gr) > 1 else [disp]
    gx = [sum(gw[:i]) + 14 * i if STILE[0] != "corsie" else sum(gw[:i]) + 6 * i for i in range(len(gr))]
    fine_x = gx[-1] + gw[-1]
    bande = [(gx[i] + j * gw[i] / len(g), gw[i] / len(g), co) for i, g in enumerate(gr) for j, co in enumerate(g)]  # (x, larghezza, corsia)
    for ci, (cs, ce) in enumerate(cols):
        x0 = 36 + ci * (bw + 24)
        nm = int((ce - cs).total_seconds() // 60)
        for i_g, g in enumerate(gr):
            lx, lw = x0 + 68 + gx[i_g], gw[i_g]
            arr = np.empty((nm * R, CN * len(g), 3))
            arr[:] = CARTA
            for nb, co in enumerate(g):
                for m in range(nm):
                    t = cs + timedelta(minutes=m)
                    if not a <= t <= z:
                        continue
                    k = t.isoformat(timespec="minutes")
                    if any(bs <= t <= be for bs, be in brevi):
                        col = [SVEGLIO]
                    elif k not in co["celle"]:
                        col = [NON]
                    else:
                        col = [CAT[c] for c in co["celle"][k] if c in CAT] or [VUOTO]
                    for r_ in range(R - 1):
                        for c_ in range(CN):
                            arr[m * R + r_, nb * CN + c_] = col[((r_ // 2) + c_) % len(col)]
            ax = fig.add_axes([lx / W, 1 - (TOP + nm * PXM) / H, lw / W, nm * PXM / H])
            ax.imshow(arr, aspect="auto", interpolation="nearest")
            ax.axis("off")
        h = cs
        while h < ce:  # ore: filo sottile + etichetta
            y = TOP + (h - cs).total_seconds() / 60 * PXM
            fig.add_artist(plt.Line2D([(x0 + 46) / W, (x0 + 68 + fine_x) / W], [1 - y / H] * 2, color=INK, lw=.6, alpha=.55))
            T(x0, y, f"{h:%H}:00", fontsize=14, family=SANS, weight="semibold", color=INK)
            h += timedelta(hours=1)
        for bs, be in brevi:  # risveglio breve: triangolo pieno accanto alle ore
            if cs <= bs < ce:
                yc = TOP + ((bs - cs).total_seconds() / 60 + 1) * PXM
                fig.add_artist(Polygon([[(x0 + 50) / W, 1 - (yc - 6) / H], [(x0 + 64) / W, 1 - yc / H], [(x0 + 50) / W, 1 - (yc + 6) / H]],
                                       closed=True, color=INK, transform=fig.transFigure))
    for ci in range(len(cols)):  # intestazioni delle corsie (ripetute sopra ogni colonna)
        x0 = 36 + ci * (bw + 24)
        for bx, lw, co in bande:
            lx = x0 + 68 + bx
            nome = co["nome"].split(" ", 1) if len(co["nome"]) > 9 else [co["nome"]]
            righe = [(t, INK, "semibold", 14) for t in nome] + [(co["livello"].replace("_", " "), DIM, "medium", 12.5)]
            for ri, (t, colr, wt, fs) in enumerate(reversed(righe)):
                T(lx, TOP - 14 - ri * 22, t, fontsize=fs, family=SANS, weight=wt, color=colr, va="bottom")
            fig.patches.append(Rectangle((lx / W, 1 - (TOP - 4) / H), lw / W, 4 / H, transform=fig.transFigure, color=co["colore"], lw=0))
    y = TOP + lunga * PXM + 26  # legenda
    T(36, y, "Colori = cosa si sente", fontsize=22, family=SER, color=INK)
    y += 30

    def quadr(x, yc, cc):  # piccolo campione 22x22 px (scacchiera 2x2 se piu' colori)
        for i in range(2):
            for j in range(2):
                fig.patches.append(Rectangle(((x + 11 * j) / W, 1 - (yc - 11 + 11 * (i + 1)) / H), 11 / W, 11 / H,
                                             transform=fig.transFigure, color=cc[(i + j) % len(cc)], lw=0))
    voci = [([CAT[k]], v["nome"]) for k, v in J["categorie"].items()]
    voci += [([CAT["russa"], CAT["movimento"]], "scacchiera = due cose insieme"), ([VUOTO], "ascoltato, niente"), ([NON], "non analizzato")]
    if brevi:
        voci.append(([SVEGLIO], "risveglio breve " + ", ".join(f"{b:%H:%M}" for b, _ in brevi) + " (a sinistra)"))
    for i, (cc, t) in enumerate(voci):
        x, yy = 36 + (i % 3) * 360, y + (i // 3) * 34
        quadr(x, yy, cc)
        fig.patches.append(Rectangle((x / W, 1 - (yy + 11) / H), 22 / W, 22 / H, transform=fig.transFigure, fill=False, ec=INK, lw=.4, alpha=.5))
        T(x + 32, yy, t, fontsize=14.5, family=SANS, weight="medium", color=INK)
    fig.savefig(png, facecolor=C["carta"])
    plt.close(fig)


def copia_su_telefono(base):
    day = os.path.basename(base).split("_")[1]
    kd = ROOT + rf"\kaggle\{day}"
    if os.path.exists(kd + r"\fatto") and os.path.exists(kd + r"\riepilogo.json"):  # mappa Kaggle gia' sul telefono (JSON+PNG coerenti): non si sovrascrive
        print("telefono: tengo la mappa Kaggle di", day)
        return True
    ssh("mkdir -p ~/sonno_bot/mappe")
    return all(scp(base + e, f"{PHONE}:sonno_bot/mappe/" + os.path.basename(base) + e, 120) for e in (".json", ".png"))


def kaggle_corsie(J, d, dev):
    """--kaggle DIR: PANNs su TUTTA la notte dai CSV Kaggle. w10 = livello 'PANNs' (sostituisce le sole zone), w2 = 'PANNs w2' (sopra, sottile).
    Minuto = categoria se la colonna <cat>_n02 >= 3 (come l'agente Kaggle); duplicati dello stesso minuto: OR. Respiro non si disegna col russare."""
    ISO = "%Y-%m-%dT%H:%M"
    for nome, v in (("PANNs", "w10"), ("PANNs w2", "w2")):
        celle = {}
        for r in csv.DictReader(open(rf"{d}\panns_{v}_p1.csv", encoding="utf-8")):
            if r["dispositivo"] != dev:
                continue
            cs = {c for c, k in (("russa", "snoring"), ("respiro", "respiro"), ("movimento", "movimento")) if int(r[k + "_n02"]) >= 3}
            if "russa" in cs:
                cs.discard("respiro")
            celle.setdefault(r["minuto"], set()).update(cs)
        celle = {k: sorted(x) for k, x in celle.items()}
        if dev == "a21s":  # la notte del JSON e' quella dell'A21s: niente minuti fuori
            celle = {k: x for k, x in celle.items() if J["inizio"][:16] <= k <= J["fine"][:16]}
        else:
            J["inizio"], J["fine"] = min(celle), max(celle)
            J["brevi"] = []
        J["corsie"] = [c for c in J["corsie"] if c["nome"] != nome] + [dict(nome=nome, livello="PRECISO", colore="#2A3350", dove="Kaggle " + v, celle=celle)]
        J.setdefault("kaggle", {})[f"{dev}_{v}"] = sum("russa" in x for x in celle.values())
    J["minuti_russare"] = J["kaggle"][f"{dev}_w10"]
    w10 = next((c["celle"] for c in J["corsie"] if c["nome"] == "PANNs"), {})
    for p in J.get("periodi", []):
        n = sum(1 for m, cs in w10.items() if p["da"][:16] <= m <= p["a"][:16] and "russa" in cs)
        if n >= 3 and p.get("certezza", 0) < 2:
            p["certezza"], p["certezza_testo"] = 2, TESTO[2]
            p["kaggle_min"] = n
    J["device"] = {"a21s": "A21s (comodino)", "a56": "A56 (telefono)"}.get(dev, dev)
    J["corsie"] = [c for c in J["corsie"] if dev == "a21s" or c["nome"] in ("PANNs", "PANNs w2", "Tue etichette")]


def main(argv):
    kg = dev = None
    if "--kaggle" in argv:  # --kaggle DIR [--device a21s|a56]
        i = argv.index("--kaggle")
        kg = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    if "--device" in argv:
        i = argv.index("--device")
        dev = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
    dev = dev or "a21s"
    if "--due" in argv:  # --due DIR [AAAAMMGG]: variante DUE (PANNs A21s vs A56)
        i = argv.index("--due")
        day = next((x for x in argv if x.isdigit() and len(x) == 8), "20261002")
        disegna_due(argv[i + 1], day, f"{OUT}\\mappa_{day}_DUE.png")
        return None
    if "--stile" in argv:  # --stile righe|corsie|bande (predefinito: righe)
        i = argv.index("--stile")
        STILE[0] = argv[i + 1]
        SUFF[0] = "" if STILE[0] == "righe" else "_" + STILE[0]
        argv = argv[:i] + argv[i + 2:]
    if "--variante" in argv:  # A = tutto centrato, B = tutto a terra, C = texture (centrato); poi "1" = numero di versione
        i = argv.index("--variante")
        v = argv[i + 1]
        argv = argv[:i] + argv[i + 2:]
        STILE[0], ALLINEA[0], TEXTURE[0], VERS[0], SUFF[0] = "griglie" if v[0] == "D" else "righe", "terra" if v[0] == "B" or v[:3] in ("D2t", "D3t") else "centro", v[0] == "C", v if len(v) > 1 else v + "1", "_" + (v if v[:2] in ("D2", "D3") else v[0])
        if v[:2] in ("D2", "D3"):
            GRIGLIE.update(righe=5, alt=True, terra=v[2:3] == "t", opaco=v[:2] == "D3")
    if "--righe" in argv:
        i = argv.index("--righe")
        RIGHE[0] = int(argv[i + 1])
        argv = argv[:i] + argv[i + 2:]
    TUTTA[0] = "--panns-tutta" in argv
    leggera, auto = "--leggera" in argv, "--auto" in argv
    opz = {argv[i]: argv[i + 1] for i, x in enumerate(argv[:-1]) if x in ("--inizio", "--fine", "--brevi")}
    pos = [x for i, x in enumerate(argv) if not x.startswith("--") and (i == 0 or argv[i - 1] not in opz)]
    day = pos[0] if pos else datetime.now().strftime("%Y%m%d")
    cf = SRC + rf"\confini_{day}.json"  # confini corretti a mano: restano, cosi' anche l'attivita' pianificata li usa
    if opz:
        os.makedirs(SRC, exist_ok=True)
        json.dump(opz, open(cf, "w"))
    elif os.path.exists(cf):
        opz = json.load(open(cf))
    bassa_priorita()
    CACHE_DAY[0] = day
    if "--aggiorna-etichette" in argv:  # scarica giudizi.csv dal telefono e ridisegna: niente ricalcolo pesante
        print("giudizi:", "ok" if scp(f"{PHONE}:sonno_bot/giudizi.csv", SRC + r"\giudizi.csv") else "NON scaricati (uso la copia vecchia)")
        argv = argv + ["--ridisegna"]
    if "--ridisegna" in argv:  # solo il disegno, dal JSON gia' scritto (niente analisi)
        J = json.load(open(f"{OUT}\mappa_{day}.json", encoding="utf-8"))
        if kg:
            # mostrava solo la seconda meta'. Confini sempre dall'analisi attuale (notte.py), o da quelli corretti a mano.
            import sonno_audio as SA
            scarica(day)
            r = SA.analizza(day)
            if r and r.get("blocco"):
                a, z = r["inizio"], r["fine"]
                hm = lambda x: datetime.combine(z.date(), datetime.strptime(x, "%H:%M").time())
                if "--inizio" in opz:
                    a = hm(opz["--inizio"]); a -= timedelta(days=1) if a > z else timedelta()
                if "--fine" in opz:
                    z = hm(opz["--fine"])
                J["inizio"], J["fine"] = a.isoformat(timespec="minutes"), z.isoformat(timespec="minutes")
            kaggle_corsie(J, kg, dev)
            SUFF[0] += "_kaggle" + ("" if dev == "a21s" else "_" + dev)
            print("minuti russare", J["kaggle"])
        if kg:  # JSON coerente col PNG Kaggle: lo copia kaggle_mattino.py sul telefono
            json.dump(J, open(f"{OUT}\mappa_{day}{SUFF[0]}.json", "w", encoding="utf-8"), ensure_ascii=False)
        disegna(J, f"{OUT}\mappa_{day}{SUFF[0]}.png")
        return J
    import sonno_audio as SA
    scarica(day)
    r = SA.analizza(day)
    if not r or not r.get("blocco"):
        print("nessuna notte riconosciuta per", day)
        return None
    a, z = r["inizio"], r["fine"]
    dur = timedelta(minutes=r.get("pausa", 0) / max(len(r["brevi"]), 1))
    brevi = [(s, s + dur) for s in r["brevi"]]
    hm = lambda x: datetime.combine(z.date(), datetime.strptime(x, "%H:%M").time())
    if "--inizio" in opz:
        a = hm(opz["--inizio"])
        a -= timedelta(days=1) if a > z else timedelta()
    if "--fine" in opz:
        z = hm(opz["--fine"])
    if "--brevi" in opz:
        brevi = [(hm(x.split("-")[0]), hm(x.split("-")[1])) for x in opz["--brevi"].split(",")]
    t = {"dati_s": round(time.time() - T0, 1)}
    sys.path.insert(0, r"C:\sonno_bot")
    import sorgente as SG
    _mf = r"C:\sonno_audio\media_a56.csv"
    tel = SG.minuti_telefono(SG.leggi(_mf), a, z, SG.leggi_intervalli(_mf))
    t["minuti_telefono"] = len(tel & set(r["M"]))
    per = periodi(r["M"], candidati(r["M"], a, z, brevi, tel), giudizi(), clip_modelli(), a, z, brevi)
    pesante = not leggera and puo_pesante(auto)
    t["pesante"] = pesante
    if not leggera and not pesante:
        print("calcolo pesante saltato: non sei sveglio certo" + (" o il PC e' in uso" if auto else ""))
    if pesante:
        t0 = time.time()
        t["periodi_verificati"] = verifica(per, a, z, sessioni())
        t["modelli_s"] = round(time.time() - t0)
    scartati = sum(p["smentito"] for p in per)
    per = [p for p in per if not p["smentito"]]
    for p in per:
        p["c"] = certezza(p)
    t["totale_s"] = round(time.time() - T0, 1)
    J, base = scrivi(day, a, z, brevi, per, scartati, t, r["M"])
    print("telefono:", "ok" if copia_su_telefono(base) else "NON copiato")
    return J


if __name__ == "__main__":
    J = main(sys.argv[1:])
    if J:
        for p in J["periodi"]:
            print(p["da"][11:], p["a"][11:], f"{p['minuti']:>3}'", p["intensita"], "R/r/m %d/%d/%d%%" % tuple(p["densita_pct"][k] for k in ("russare", "respiro", "movimento")), p["certezza"], p["certezza_testo"])
        print({k: J[k] for k in ("minuti_russare", "scartati_da_te", "tempi_s")})
