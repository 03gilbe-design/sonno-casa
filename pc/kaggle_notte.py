"""Analisi di una notte su GPU gratis di Kaggle, tutto da riga di comando.
Fa: dataset privato (blocchi A21s della fascia + notte A56 da Drive) -> kernel T4 (PANNs, finestra:passo in --vars; EfficientAT su CPU solo con --eff)
 -> poll ogni 60 s (max 45 min) -> download in C:/sonno_audio/kaggle/NOTTE/ -> confronto con le zone scremate (permin) -> catalogo.
Quando lanciarlo: sveglio + PC libero (usa solo rete). NOTTE = giorno in cui finisce la notte. Pesi Cnn14 scaricati dal notebook (Zenodo)."""
import senza_finestre  # noqa: F401
import csv, glob, json, os, re, shutil, subprocess, sys, time
from datetime import datetime, timedelta
# kaggle_mattino moriva qui in silenzio (trovato con avvia_logga.py). Solo se ci sono.
for _s in (sys.stdout, sys.stderr):
    if _s is not None:
        _s.reconfigure(encoding="utf-8", errors="replace")

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
ROOT = r"C:\sonno_audio"
KAG = r"~\AppData\Local\Programs\Python\Python312\Scripts\kaggle.exe"
RCL = r"~\AppData\Local\Microsoft\WinGet\Packages\Rclone.Rclone_Microsoft.Winget.Source_8wekyb3d8bbwe\rclone-v1.75.1-windows-amd64\rclone.exe"
USER, KSLUG = "utente", "sonno-analisi-notte"
SEC_MIN = 3  # come mappa_russare.py: >= 3 finestre sopra soglia 0.2 = minuto "russa"
T = {}


def run(cmd, **k):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", **k)


def kag(*a):
    return run([KAG, *a], env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})


def finestra(day, ini, fin):
    """(inizio, fine) della notte che FINISCE il giorno `day`. ini > fin (es. 21:00 > 13:30) = ini e' la sera prima.
    """
    d = datetime.strptime(day, "%Y%m%d")
    a = datetime.combine(d - timedelta(days=1) if ini > fin else d, datetime.strptime(ini, "%H:%M").time())
    return a, datetime.combine(d, datetime.strptime(fin, "%H:%M").time())




def prepara(day, ini, fin, W):
    """Copia in W i blocchi A21s (interi, che toccano [ini,fin]) e la notte A56 del giorno; ritorna quanti file."""
    d = datetime.strptime(day, "%Y%m%d")
    a, z = finestra(day, ini, fin)
    loc = ROOT + r"\mappe\_src\interi"
    n = 0
    for dd in (d - timedelta(days=1), d):
        sub = dd.strftime("%Y-%m-%d")
        for r in run([RCL, "lsf", f"gdrive:sonno/interi/{sub}/"]).stdout.split():
            m = re.match(r"(\d{8})_(\d{6})\.m4a$", r)
            if not m:
                continue
            s = datetime.strptime(m[1] + m[2], "%Y%m%d%H%M%S")
            if not (a - timedelta(minutes=30) < s < z):
                continue
            dst = os.path.join(W, f"a21s_{r}")
            if os.path.exists(os.path.join(loc, r)):
                shutil.copy(os.path.join(loc, r), dst)
            else:
                run([RCL, "copyto", f"gdrive:sonno/interi/{sub}/{r}", dst])
            n += 1
    # l'A56 era escluso e Kaggle analizzava solo l'A21s (muto). Ora: file iniziati fra le 18 della sera prima e le 12.
    prima = (d - timedelta(days=1)).strftime("%Y%m%d")
    for r in run([RCL, "lsf", "-R", "--include", "notte_*.m4a", "gdrive:sonno/a56/"]).stdout.split():
        m = re.search(r"notte_(\d{8})_(\d{2})", r)
        if m and ((m[1] == prima and int(m[2]) >= 12) or (m[1] == day and int(m[2]) < 12)):
            run([RCL, "copyto", f"gdrive:sonno/a56/{r}", os.path.join(W, f"a56_{os.path.basename(r)}")])
            n += 1
    shutil.copy(QUI + r"\efficientat\mn10_as.onnx", W)
    shutil.copy(os.path.expanduser("~/panns_data/class_labels_indices.csv"), W)
    return n


def dataset(day, W, riusa):
    slug = f"sonno-notte-{day}"
    json.dump({"title": f"sonno notte {day}", "id": f"{USER}/{slug}", "licenses": [{"name": "CC0-1.0"}], "isPrivate": True}, open(W + r"\dataset-metadata.json", "w"))
    if riusa:
        return slug
    esiste = "ready" in kag("datasets", "status", f"{USER}/{slug}").stdout
    # ogni notte nuova (dataset per notte) faceva solo "version" su un dataset inesistente e falliva.
    r = (kag("datasets", "version", "-p", W, "-r", "zip", "-m", "aggiornato", "-d") if esiste
         else kag("datasets", "create", "-p", W, "-r", "zip"))
    print(r.stdout[-200:], r.stderr[-300:])
    audio = [f for f in os.listdir(W) if f.endswith((".m4a", ".flac"))]
    for _ in range(90):
        # (0 file analizzati). Si aspetta che l'elenco file del dataset contenga l'audio appena caricato.
        if "ready" in kag("datasets", "status", f"{USER}/{slug}").stdout and \
                all(a in kag("datasets", "files", f"{USER}/{slug}", "--page-size", "200").stdout for a in audio[:3]):
            return slug
        time.sleep(10)
    raise SystemExit("dataset non pronto (audio non visibile su Kaggle)")


def kernel(day, slug, vars_, eff):
    K = ROOT + rf"\kaggle\{day}\kernel"
    os.makedirs(K, exist_ok=True)
    cfg = f'import os\nos.environ["PANNS_VARS"] = "{vars_}"\n' + ("" if eff else 'os.environ["SOLO_PANNS"] = "1"\n')
    open(K + r"\analizza.py", "w", encoding="utf-8").write(cfg + open(QUI + r"\kaggle_nb\analizza.py", encoding="utf-8").read())
    json.dump({"id": f"{USER}/{KSLUG}", "title": "sonno analisi notte", "code_file": "analizza.py", "language": "python", "kernel_type": "script",
               "is_private": True, "enable_gpu": True, "enable_internet": True, "dataset_sources": [f"{USER}/{slug}"],
               "competition_sources": [], "kernel_sources": []}, open(K + r"\kernel-metadata.json", "w"))
    r = kag("kernels", "push", "-p", K)
    print(r.stdout[-200:], r.stderr[-300:])
    if "successfully" not in r.stdout:
        raise SystemExit("push fallito")
    t0 = time.time()
    T["coda_s"] = None
    s = ""
    while time.time() - t0 < 45 * 60:
        s = kag("kernels", "status", f"{USER}/{KSLUG}").stdout
        if T["coda_s"] is None and "RUNNING" in s:
            T["coda_s"] = round(time.time() - t0)
        if "COMPLETE" in s or "ERROR" in s or "CANCEL" in s:
            break
        time.sleep(60)
    T["kernel_wall_s"] = round(time.time() - t0)
    if "COMPLETE" not in s:
        raise SystemExit("kernel non completato: " + s.strip())


def minuti_russa(f):
    """{(dispositivo, minuto): finestre sopra soglia} per la categoria russa."""
    return {(r["dispositivo"], r["minuto"]): int(r["russa_n02"]) for r in csv.DictReader(open(f, encoding="utf-8"))}


def confronto(day, O):
    """Minuti di russare su tutta la notte per ogni variante, dentro/fuori le zone scremate (permin PANNs del PC, solo A21s)."""
    pf = ROOT + rf"\mappe\_src\permin_{day}.json"
    scr = json.load(open(pf)).get("PANNs", {}) if os.path.exists(pf) else {}
    scr_si = {k for k, v in scr.items() if v >= SEC_MIN}
    out = {"zone_scremate_PC": {"analizzati": len(scr), "russa": len(scr_si)}}
    for f in sorted(glob.glob(O + r"\panns_w*.csv")):
        m = minuti_russa(f)
        for dev in sorted({d for d, _ in m}):
            ru = {k[1] for k, v in m.items() if k[0] == dev and v >= SEC_MIN}
            dentro = {k for k in ru if k in scr}
            out[f"{os.path.basename(f)[:-4]}|{dev}"] = dict(minuti=sum(1 for k in m if k[0] == dev), russa=len(ru), in_zone=len(dentro),
                                                            fuori_zone=len(ru) - len(dentro), zone_russa_ritrovate=len(dentro & scr_si))
    return out


def catalogo(day, O, tempi):
    try:
        import catalogo as C
    except Exception as e:
        print("catalogo non disponibile:", e)
        return
    regs = [x["id"] for x in C.leggi_catalogo(C.REG)]
    nuove = {}
    for p in sorted(glob.glob(O + r"\panns_w*.csv")):
        nome = f"kaggle_{day}_{os.path.basename(p)}"
        C.rc("copyto", p, f"{C.BASE}/analisi/PANNs/{nome}")
        for dev in {r["dispositivo"] for r in csv.DictReader(open(p, encoding="utf-8"))}:
            for rid in regs:
                if (dev == "a56" and rid.startswith("A56_") and rid[4:12] == day) or (dev == "a21s" and rid.startswith("A21s_") and day in rid[5:13]):
                    nuove[rid] = dict(id_registrazione=rid, modello="PANNs", versione_modello="pth:Cnn14_mAP=0.431 (Kaggle T4)", copertura="tutta", intervallo="",
                                      stato="fatta", chi="Kaggle", quando=C._ora(), risultato=f"gdrive:sonno/analisi/PANNs/{nome}",
                                      durata_calcolo_s=round(tempi.get("panns_tot_s", 0)), note="csv per minuto con 3 categorie (russa/respiro/movimento)")
    if nuove:
        C.registra_molti(list(nuove.values()))  # ponytail: una riga per registrazione, vince l'ultima variante
    print("catalogo: righe", len(nuove))


def main(argv):
    if not argv or argv[0].startswith("-"):
        raise SystemExit(__doc__)
    day = argv[0]

    def opt(k, d):
        return argv[argv.index(k) + 1] if k in argv else d
    vars_, ini, fin = opt("--vars", "2:1,10:1"), opt("--inizio", "21:00"), opt("--fine", "13:30")
    # prima"): non deve lasciare riepilogo.json nella cartella della notte, se no il mattino salterebbe Kaggle.
    O = opt("--dir", ROOT + rf"\kaggle\{day}")
    W = O + r"\ds"
    os.makedirs(W, exist_ok=True)
    os.makedirs(O + r"\out", exist_ok=True)
    t = time.time()
    if "--riusa-dataset" not in argv:
        print("file nel dataset:", prepara(day, ini, fin, W))
    slug = dataset(day, W, "--riusa-dataset" in argv)
    T["upload_s"] = round(time.time() - t)
    kernel(day, slug, vars_, "--eff" in argv)
    t = time.time()
    kag("kernels", "output", f"{USER}/{KSLUG}", "-p", O + r"\out")
    T["download_s"] = round(time.time() - t)
    for f in glob.glob(O + r"\out\*.csv"):
        shutil.copy(f, O)
    tempi = json.load(open(O + r"\out\tempi.json"))
    res = dict(tempi=T, gpu=tempi, confronto=confronto(day, O))
    json.dump(res, open(O + r"\riepilogo.json", "w"), indent=1)
    print(json.dumps(res, indent=1))
    catalogo(day, O, tempi)


if __name__ == "__main__":
    main(sys.argv[1:])
