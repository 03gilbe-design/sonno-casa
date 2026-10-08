"""Catalogo condiviso su Drive: chi ha registrato cosa, e chi ha analizzato cosa.
  gdrive:sonno/CATALOGO/registrazioni.csv  una riga per file audio su Drive
  gdrive:sonno/CATALOGO/analisi.csv        una riga per (registrazione, modello, copertura)
Funzioni: aggiorna_registrazioni, lavoro_mancante, prenota, registra_risultato, registra_analisi_locali.
Uso: python catalogo.py [aggiorna|locali|test]
Su Drive non si cancella MAI niente: si scarica, si modifica, si ricarica (con controllo che nel frattempo non sia cambiato).
Ore in registrazioni.csv = ora locale italiana; `quando` in analisi.csv = UTC (Colab non e' in Italia)."""
import senza_finestre  # noqa: F401  (niente finestre dei processi figli: va importato per primo)
import csv, glob, hashlib, json, os, random, re, socket, subprocess, sys, tempfile, time
from datetime import datetime, timedelta, timezone

RCLONE = r"~\AppData\Local\Microsoft\WinGet\Packages\Rclone.Rclone_Microsoft.Winget.Source_8wekyb3d8bbwe\rclone-v1.75.1-windows-amd64\rclone.exe"
BASE = "gdrive:sonno"
CAT = BASE + "/CATALOGO"
REG, ANA = "registrazioni.csv", "analisi.csv"
COL_REG = ["id", "percorso_drive", "dispositivo", "tipo", "inizio", "fine", "durata_s", "durata_fonte", "formato",
           "freq_hz", "canali", "size", "md5", "utilizzabile", "pos_x", "pos_y", "pos_metodo", "pos_quando", "note"]
COL_ANA = ["id_registrazione", "modello", "versione_modello", "copertura", "intervallo", "stato", "chi", "quando",
           "risultato", "durata_calcolo_s", "note"]
SCADENZA_S = 3 * 3600  # una prenotazione senza risultato si libera dopo 3 h
MUTO = (datetime(2026, 9, 30, 8, 55), datetime(2026, 10, 1, 22, 10))  # microfono A21s silenziato da Android
NOTA_MUTO = "microfono silenziato da Android (periodo di esempio): audio probabilmente muto"
AUDIO = (".m4a", ".flac", ".wav", ".mp3")
LOCALE = r"C:\sonno_audio\catalogo"  # copia locale comoda (la verita' e' su Drive)
MODELLI = {"YAMNet": r"C:\sonno_tex\yamnet\yamnet.onnx", "PANNs": r"C:\sonno_tex\panns\cnn14.onnx",
           "EfficientAT": r"C:\sonno_tex\efficientat\mn10_as.onnx"}
CHI = socket.gethostname()


# ---------- rclone ----------
def rc(*a, timeout=900, ok=(0,)):
    cmd = [RCLONE, *a, "--timeout", "120s", "--contimeout", "60s", "--low-level-retries", "8", "--tpslimit", "3"]
    for i in range(4):  # rate limit Drive: ritenta con pausa
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode in ok or r.returncode == 3:
            return r
        time.sleep(15)
    raise RuntimeError(f"rclone {a[0]} fallito: {r.stderr[-300:]}")


def stato(remoto):
    """(md5, modtime, size) del file su Drive, None se non esiste."""
    r = rc("lsjson", "--hash", "--files-only", remoto)
    try:
        e = json.loads(r.stdout)[0]
    except (ValueError, IndexError):
        return None
    return (e.get("Hashes", {}).get("md5"), e["ModTime"], e["Size"])


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def leggi_csv(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def scrivi_csv(path, righe, colonne):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, colonne, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(righe)


def leggi_catalogo(nome, tmp=None):
    """Righe di CATALOGO/nome (lista vuota se il file non c'e' ancora)."""
    tmp = tmp or tempfile.mkdtemp(prefix="cat_")
    p = os.path.join(tmp, nome)
    if stato(f"{CAT}/{nome}") is None:
        return []
    rc("copyto", f"{CAT}/{nome}", p)
    return leggi_csv(p)


def modifica_sicura(nome, colonne, modifica, tentativi=6):
    """scarica -> modifica(righe)->righe -> ricarica, solo se su Drive il file e' ancora quello scaricato; se no riprova."""
    tmp = tempfile.mkdtemp(prefix="cat_")
    p = os.path.join(tmp, nome)
    for _ in range(tentativi):
        s0 = stato(f"{CAT}/{nome}")
        righe = []
        if s0:
            rc("copyto", f"{CAT}/{nome}", p)
            righe = leggi_csv(p)
        nuove = modifica(righe)
        scrivi_csv(p, nuove, colonne)
        if stato(f"{CAT}/{nome}") != s0:  # qualcuno ha scritto nel frattempo
            time.sleep(random.uniform(2, 8))
            continue
        rc("copyto", p, f"{CAT}/{nome}")
        s1 = stato(f"{CAT}/{nome}")
        if s1 and s1[0] and s1[0] != md5(p):
            continue
        os.makedirs(LOCALE, exist_ok=True)
        scrivi_csv(os.path.join(LOCALE, nome), nuove, colonne)
        return nuove
    raise RuntimeError(f"{nome}: troppe collisioni su Drive")


# ---------- registrazioni ----------
def _locale(nome, size):
    """Copia locale con la stessa dimensione (per ffprobe senza scaricare)."""
    for pat in (rf"C:\sonno_audio\tre_dispositivi\*\{nome}", rf"C:\sonno_audio\mappe\_src\interi\{nome}",
                rf"C:\sonno_audio\interi_prova\{nome}", rf"C:\sonno_audio\_archivia_tmp\**\{nome}"):
        for f in glob.glob(pat, recursive=True):
            if os.path.getsize(f) == size:
                return f
    return None


def _probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries",
                        "stream=codec_name,sample_rate,channels:format=duration,format_name", "-of", "json", path],
                       capture_output=True, text=True, timeout=300)
    j = json.loads(r.stdout)
    s, f = j["streams"][0], j["format"]
    if "duration" not in f:  # flac scritto in streaming: nessuna durata nell'intestazione, la ricavo decodificando
        d = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "null", "-", "-progress", "pipe:1"],
                           capture_output=True, text=True, timeout=600).stdout
        us = [int(x.split("=")[1]) for x in d.split() if x.startswith("out_time_us=")]
        f["duration"] = us[-1] / 1e6
    return float(f["duration"]), s["codec_name"], int(s["sample_rate"]), int(s["channels"])


def _riga(e):
    """Riga di registrazioni.csv da un'entry di lsjson (percorso relativo a sonno/)."""
    pc = e["Path"]
    top, nome = pc.split("/")[0], pc.split("/")[-1]
    m = re.search(r"(\d{8})_(\d{4,6})", nome)
    if top not in ("interi", "pc", "a56", "clip") or not nome.lower().endswith(AUDIO) or not m:
        return None
    dt = datetime.strptime(m[1] + m[2].ljust(6, "0"), "%Y%m%d%H%M%S")
    stem = os.path.splitext(nome)[0]
    disp = {"interi": "A21s", "pc": "PC", "a56": "A56", "clip": "A21s"}[top]
    tipo = "clip" if top == "clip" else "intero"
    rid = f"{disp}-clip_{stem}" if tipo == "clip" else f"{disp}_{m[1]}_{m[2]}"
    size = e["Size"]
    durata, fonte, cod, hz, ch = None, "", "", "", ""
    loc = _locale(nome, size)
    if loc:
        try:
            durata, cod, hz, ch = _probe(loc); fonte = "misurata"
        except Exception:
            loc = None
    if durata is None and top == "interi":  # A21s: sempre aac 64 kbps 16 kHz mono (rec.sh)
        durata, fonte, cod, hz, ch = size * 8 / 64000, "stimata dalla dimensione (64 kbps)", "aac", 16000, 1
    if durata is None:  # ultima strada: scarica, misura, butta la copia temporanea
        tmp = tempfile.mkdtemp(prefix="probe_")
        try:
            rc("copyto", f"{BASE}/{pc}", os.path.join(tmp, nome))
            durata, cod, hz, ch = _probe(os.path.join(tmp, nome)); fonte = "misurata (scaricato)"
        except Exception as ex:
            fonte = f"sconosciuta ({type(ex).__name__})"
    ini = dt
    fin = dt + timedelta(seconds=durata) if durata else None
    util, nota = "si", []
    if disp == "A21s" and fin:
        if fin <= MUTO[0] or ini >= MUTO[1]:
            pass
        elif ini >= MUTO[0] and fin <= MUTO[1]:
            util = "no"; nota.append(NOTA_MUTO)
        else:
            util = "parziale"; nota.append("in parte " + NOTA_MUTO)
    if disp == "PC":
        nota.append("registrata dal PC (microfono: vedi nome/sessione)")
    return dict(id=rid, percorso_drive=f"{BASE}/{pc}", dispositivo=disp, tipo=tipo,
                inizio=ini.isoformat(timespec="seconds"), fine=fin.isoformat(timespec="seconds") if fin else "",
                durata_s=round(durata, 1) if durata else "", durata_fonte=fonte,
                formato=(f"{cod}/{os.path.splitext(nome)[1][1:]}" if cod else ""), freq_hz=hz, canali=ch,
                size=size, md5=(e.get("Hashes") or {}).get("md5", ""), utilizzabile=util,
                pos_x="", pos_y="", pos_metodo="", pos_quando="", note="; ".join(nota))


def aggiorna_registrazioni():
    """Scansiona Drive e aggiunge al catalogo solo i file nuovi. Ritorna quanti ne ha aggiunti."""
    r = rc("lsjson", "-R", "--hash", "--files-only", BASE)
    esistenti = {x["percorso_drive"] for x in leggi_catalogo(REG) if x["durata_s"]}  # senza durata: si rifa
    nuove = []
    for e in json.loads(r.stdout):
        if f"{BASE}/{e['Path']}" in esistenti:
            continue
        x = _riga(e)
        if x:
            nuove.append(x)
    if not nuove:
        return 0

    def modifica(righe):
        nuovi = {x["percorso_drive"] for x in nuove}
        righe = [x for x in righe if x["percorso_drive"] not in nuovi] + nuove  # ponytail: sostituisce solo le righe rifatte
        return sorted(righe, key=lambda x: (x["inizio"], x["id"]))
    modifica_sicura(REG, COL_REG, modifica)
    return len(nuove)


# ---------- analisi ----------
def _ora():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _eta_s(quando):
    return (datetime.now(timezone.utc) - datetime.strptime(quando, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds()


def _libera(a):
    """True se la riga non blocca piu' nessuno: fallita, o prenotata scaduta."""
    return a["stato"] == "fallita" or (a["stato"] == "prenotata" and _eta_s(a["quando"]) > SCADENZA_S)


def _copre(a, copertura):
    """La riga 'fatta' `a` soddisfa la copertura richiesta? (tutta copre anche 'zone scremate')."""
    return a["stato"] == "fatta" and (a["copertura"] == "tutta" or a["copertura"] == copertura)


def versione_modello(nome):
    p = MODELLI.get(nome)
    if not p or not os.path.exists(p):
        return ""
    cache_f = os.path.join(LOCALE, "hash_modelli.json")
    os.makedirs(LOCALE, exist_ok=True)
    cache = json.load(open(cache_f)) if os.path.exists(cache_f) else {}
    k = f"{p}|{os.path.getsize(p)}|{int(os.path.getmtime(p))}"
    if k not in cache:
        cache[k] = "onnx:" + md5(p)[:12]
        json.dump(cache, open(cache_f, "w"))
    return cache[k]


def lavoro_mancante(modello, copertura="tutta", dispositivi=None, tipi=("intero",)):
    """Id delle registrazioni ancora da analizzare con `modello` (ne' fatte ne' prenotate da meno di 3 h)."""
    regs = leggi_catalogo(REG)
    ana = leggi_catalogo(ANA)
    occupato = set()
    for a in ana:
        if a["modello"] != modello:
            continue
        if _copre(a, copertura) or (a["stato"] == "prenotata" and not _libera(a) and a["copertura"] == copertura):
            occupato.add(a["id_registrazione"])
    return [x["id"] for x in regs if x["id"] not in occupato and x["utilizzabile"] != "no" and x["tipo"] in tipi
            and (dispositivi is None or x["dispositivo"] in dispositivi)]


def _upsert(righe, nuova):
    k = (nuova["id_registrazione"], nuova["modello"], nuova["copertura"])
    out = [a for a in righe if (a["id_registrazione"], a["modello"], a["copertura"]) != k]
    return out + [nuova]


def prenota(id_reg, modello, chi=None, copertura="tutta"):
    """True se la prenotazione e' tua; False se qualcun altro ha gia' fatto o prenotato (da meno di 3 h)."""
    chi = chi or CHI
    esito = []

    def modifica(righe):
        esito.clear()
        for a in righe:
            if a["id_registrazione"] == id_reg and a["modello"] == modello:
                if _copre(a, copertura) or (a["stato"] == "prenotata" and not _libera(a) and a["copertura"] == copertura):
                    esito.append(False)
                    return righe
        esito.append(True)
        return _upsert(righe, dict(id_registrazione=id_reg, modello=modello, versione_modello=versione_modello(modello),
                                   copertura=copertura, intervallo="", stato="prenotata", chi=chi, quando=_ora(),
                                   risultato="", durata_calcolo_s="", note=""))
    modifica_sicura(ANA, COL_ANA, modifica)
    return esito[-1]


def registra_risultato(id_reg, modello, copertura="tutta", chi=None, risultato="", intervallo="",
                       durata_calcolo_s="", stato="fatta", versione=None, note="", quando=None):
    nuova = dict(id_registrazione=id_reg, modello=modello,
                 versione_modello=versione if versione is not None else versione_modello(modello),
                 copertura=copertura, intervallo=intervallo, stato=stato, chi=chi or CHI, quando=quando or _ora(),
                 risultato=risultato, durata_calcolo_s=durata_calcolo_s, note=note)
    modifica_sicura(ANA, COL_ANA, lambda righe: _upsert(righe, nuova))


def registra_molti(nuove):
    """Come registra_risultato ma per tante righe (dict con le colonne di COL_ANA) in una sola scrittura."""
    def modifica(righe):
        for n in nuove:
            righe = _upsert(righe, n)
        return righe
    modifica_sicura(ANA, COL_ANA, modifica)


# ---------- analisi gia' fatte in locale ----------
def _intervalli(minuti):
    """(nota rimossa)"""
    ts = sorted(datetime.fromisoformat(m) for m in minuti)
    out, a, b = [], None, None
    for t in ts:
        if b is not None and t - b == timedelta(minutes=1):
            b = t
            continue
        if a:
            out.append((a, b))
        a = b = t
    if a:
        out.append((a, b))
    return ";".join(f"{x:%H:%M}-{y + timedelta(minutes=1):%H:%M}" for x, y in out)


def registra_analisi_locali():
    """Carica su Drive (analisi/MODELLO/) e registra: YAMNet per minuto (A21s) e PANNs/EfficientAT zone scremate."""
    regs = {x["id"]: x for x in leggi_catalogo(REG)}
    blocchi = {}  # id A21s -> (inizio, durata_s)
    for x in regs.values():
        if x["dispositivo"] == "A21s" and x["tipo"] == "intero" and x["durata_s"]:
            blocchi[x["id"]] = (datetime.fromisoformat(x["inizio"]), float(x["durata_s"]))
    for f in glob.glob(r"C:\sonno_audio\mappe\_src\interi\2*.m4a"):  # blocchi non ancora su Drive: stesso id di domani
        m = re.search(r"(\d{8})_(\d{6})", f)
        blocchi.setdefault(f"A21s_{m[1]}_{m[2]}", (datetime.strptime(m[1] + m[2], "%Y%m%d%H%M%S"), 1800.0))
    nuove, pubblicati = [], []

    def minuti_in(ms, ini, dur):
        a, z = ini.replace(second=0), ini + timedelta(seconds=dur)
        return [m for m in ms if a <= datetime.fromisoformat(m) < z]

    def riga(rid, modello, ms, ini, dur, chi, quando, risultato, note):
        n = len(ms)
        if not n:
            return
        tutta = n >= 0.95 * (dur / 60)
        nuove.append(dict(id_registrazione=rid, modello=modello, versione_modello=versione_modello(modello),
                          copertura="tutta" if tutta else "zone scremate", intervallo="" if tutta else _intervalli(ms),
                          stato="fatta", chi=chi, quando=quando, risultato=risultato, durata_calcolo_s="", note=note))

    # YAMNet: minuti_AAAAMMGG.csv (una riga per minuto, calcolata sul telefono A21s)
    for f in sorted(glob.glob(r"C:\sonno_audio\minuti\minuti_2*.csv")):
        nome = os.path.basename(f)
        rc("copyto", f, f"{BASE}/analisi/YAMNet/{nome}")
        ms = [r["t"] for r in leggi_csv(f)]
        q = datetime.fromtimestamp(os.path.getmtime(f), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for rid, (ini, dur) in blocchi.items():
            riga(rid, "YAMNet", minuti_in(ms, ini, dur), ini, dur, "A21s", q,
                 f"gdrive:sonno/analisi/YAMNet/{nome}", "scrematura per minuto (colonne di sonno_audio.analizza)")
    # PANNs / EfficientAT: permin_AAAAMMGG.json = {modello: {minuto: finestre sopra soglia}}
    for f in sorted(glob.glob(r"C:\sonno_audio\mappe\_src\permin_2*.json")):
        d = json.load(open(f))
        q = datetime.fromtimestamp(os.path.getmtime(f), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for modello in ("PANNs", "EfficientAT"):
            if modello not in d:
                continue
            nome = os.path.basename(f)
            tmp = os.path.join(tempfile.mkdtemp(prefix="cat_"), nome)
            json.dump(d[modello], open(tmp, "w"))
            rc("copyto", tmp, f"{BASE}/analisi/{modello}/{nome}")
            for rid, (ini, dur) in blocchi.items():
                riga(rid, modello, minuti_in(list(d[modello]), ini, dur), ini, dur, CHI, q,
                     f"gdrive:sonno/analisi/{modello}/{nome}", "mappa russare: finestre sopra soglia 0.2 per minuto")
    registra_molti(nuove)
    return len(nuove)


LEGGIMI = """# Catalogo del sonno: come contribuire da un altro computer o da Colab

Due tabelle CSV in questa cartella (`gdrive:sonno/CATALOGO/`), da leggere con pandas/csv. Su Drive non si cancella mai niente.

## registrazioni.csv (una riga per file audio)
`id`, `percorso_drive` (dentro `sonno/`), `dispositivo` (A21s / A56 / PC), `tipo` (intero = registrazione lunga, clip = frammento),
`inizio`/`fine` (ora locale italiana, ISO), `durata_s` (+ `durata_fonte`: misurata o stimata), `formato`, `freq_hz`, `canali`, `size`, `md5`,
`utilizzabile` (si / parziale / no: "no" = microfono silenziato, audio muto), `pos_x,pos_y,pos_metodo,pos_quando` (posizione: vuota = non calcolata), `note`.
Chi ha registrato = `dispositivo`; quando = `inizio`.

## analisi.csv (una riga per registrazione + modello + copertura)
`id_registrazione`, `modello` (nomi di modelli.json: YAMNet, EfficientAT, PANNs), `versione_modello`, `copertura` (tutta / zone scremate; `intervallo` dice quali minuti),
`stato` (fatta / prenotata / fallita), `chi` (PC, Colab, A21s, nome macchina), `quando` (UTC), `risultato` (percorso su Drive in `analisi/MODELLO/`), `durata_calcolo_s`, `note`.
Una analisi "tutta" vale anche per "zone scremate". Una prenotazione vecchia di piu' di 3 ore e' scaduta e si puo' rifare.

## Procedura (Colab o altro PC)
1. Prendi `catalogo.py` dal repo (o riscrivi le 3 regole sotto) e collega rclone a `gdrive:` (account utente, scope drive.file).
2. Scarica i due CSV e cerca le registrazioni senza una riga `fatta` (o `prenotata` da meno di 3 h) per il tuo modello:
   `catalogo.lavoro_mancante("PANNs", "tutta")` -> lista di id.
3. PRIMA di calcolare prenota: `catalogo.prenota(id, "PANNs", chi="Colab")` -> True = e' tua, False = lascia stare. A mano: aggiungi una riga con `stato=prenotata`, `quando`=ora UTC, e ricaricala.
4. Calcola. Carica il risultato in `analisi/MODELLO/` (copy, mai delete) e scrivi la riga:
   `catalogo.registra_risultato(id, "PANNs", "tutta", chi="Colab", risultato="gdrive:sonno/analisi/PANNs/...", durata_calcolo_s=123)`.
5. Scrittura sicura sul CSV (fa gia' tutto `catalogo.py`): scarica, modifica, controlla che su Drive md5/modtime siano ancora quelli scaricati, ricarica; se sono cambiati riparti da zero.
6. Posizione: se la calcoli, riempi `pos_x,pos_y,pos_metodo,pos_quando` della riga in registrazioni.csv (stessa procedura sicura).
"""


def scrivi_leggimi():
    p = os.path.join(tempfile.mkdtemp(prefix="cat_"), "LEGGIMI.md")
    open(p, "w", encoding="utf-8", newline="\n").write(LEGGIMI)
    rc("copyto", p, f"{CAT}/LEGGIMI.md")


def test():
    """Test con id finto: prenota -> registra -> lavoro_mancante non lo ripropone. Poi lo toglie dal catalogo (solo la riga finta)."""
    fid = "TEST_FINTO_000"
    fin = dict(id=fid, percorso_drive="finto", dispositivo="PC", tipo="intero", inizio="2000-01-01T12:00:00", utilizzabile="si")
    modifica_sicura(REG, COL_REG, lambda r: [x for x in r if x["id"] != fid] + [{**{c: "" for c in COL_REG}, **fin}])
    modifica_sicura(ANA, COL_ANA, lambda r: [x for x in r if x["id_registrazione"] != fid])
    try:
        assert fid in lavoro_mancante("PANNs", "tutta"), "dovrebbe mancare"
        assert prenota(fid, "PANNs", "test") is True
        assert prenota(fid, "PANNs", "altro") is False, "doppia prenotazione"
        assert fid not in lavoro_mancante("PANNs", "tutta"), "prenotata: non riproporre"
        registra_risultato(fid, "PANNs", "tutta", chi="test", risultato="finto")
        assert fid not in lavoro_mancante("PANNs", "tutta"), "fatta: non riproporre"
        assert fid not in lavoro_mancante("PANNs", "zone scremate"), "tutta copre zone scremate"
        assert fid in lavoro_mancante("YAMNet", "tutta"), "altro modello: manca"
        print("test OK")
    finally:  # ponytail: pulizia delle sole righe finte, scritte da me un attimo fa (non e' un cancellare dati altrui)
        modifica_sicura(REG, COL_REG, lambda r: [x for x in r if x["id"] != fid])
        modifica_sicura(ANA, COL_ANA, lambda r: [x for x in r if x["id_registrazione"] != fid])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "aggiorna"
    if cmd == "aggiorna":
        print("nuove registrazioni:", aggiorna_registrazioni())
    elif cmd == "locali":
        print("analisi registrate:", registra_analisi_locali())
    elif cmd == "leggimi":
        scrivi_leggimi()
    elif cmd == "test":
        test()
