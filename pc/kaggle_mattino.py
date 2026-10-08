"""Ogni mattina (attivita' SonnoKaggleMattino, ogni 30'): quando sei sveglio certo analizza la notte finita su Kaggle e manda le mappe al telefono.
  pythonw kaggle_mattino.py [AAAAMMGG] [--prova] [--riusa-dataset]     --prova = stampa cosa farebbe, non carica niente
Una volta per notte (marcatore kaggle/NOTTE/fatto). Se Kaggle fallisce: log e basta, la pipeline esistente (mappa_attivita) fa il suo."""
import senza_finestre  # noqa: F401
import csv, glob, os, re, shutil, subprocess, sys
from datetime import datetime, timedelta
sys.path.insert(0, r"C:\sonno_tex")
import mappa_russare as MR
import kaggle_notte as KN

ROOT, LOG = KN.ROOT, KN.ROOT + r"\kaggle_mattino.log"
PY = os.path.join(os.path.dirname(sys.executable), "python.exe")  # figli senza finestra (CREATE_NO_WINDOW da senza_finestre)


def log(*a):
    s = datetime.now().isoformat(timespec="seconds") + " " + " ".join(map(str, a))
    if sys.stdout: print(s, flush=True)
    open(LOG, "a", encoding="utf-8").write(s + "\n")


def stato(day, esito, gpu_min=None):
    """stato_kaggle.json sul telefono (lo legge /stato): ultima notte, esito ok/errore/in corso, ora, minuti GPU se noti. Mai bloccante."""
    try:
        import json
        f = ROOT + r"\stato_kaggle.json"
        json.dump(dict(notte=day, esito=esito, t=datetime.now().isoformat(timespec="seconds"), gpu_min=gpu_min), open(f, "w"))
        MR.scp(f, f"{MR.PHONE}:sonno_bot/stato_kaggle.json", 60)
    except Exception as e:
        log("stato_kaggle", repr(e))


def gpu_minuti(O):
    try:
        import json
        t = json.load(open(os.path.join(O, "riepilogo.json"), encoding="utf-8")).get("gpu", {}).get("panns_tot_s")
        return round(t / 60) if t else None
    except Exception:
        return None


def blocchi(day):
    """(nota rimossa)"""
    d = datetime.strptime(day, "%Y%m%d")
    n21 = n56 = 0
    for dd in (d - __import__("datetime").timedelta(days=1), d):
        sub = dd.strftime("%Y-%m-%d")
        n21 += sum(1 for r in KN.run([KN.RCL, "lsf", f"gdrive:sonno/interi/{sub}/"]).stdout.split() if r.endswith(".m4a"))
    n56 = sum(1 for r in KN.run([KN.RCL, "lsf", "-R", "--include", "notte_*.m4a", "gdrive:sonno/a56/"]).stdout.split() if f"notte_{day}_" in r)
    return n21, n56


def su_drive():
    """Nomi dei blocchi interi gia' su Drive (gdrive:sonno/interi/**)."""
    return {os.path.basename(x.strip()) for x in KN.run([KN.RCL, "lsf", "-R", "--files-only", "gdrive:sonno/interi/"]).stdout.split()}


def pendenti(day, ora=None, nomi=None, drive=None):
    """Blocchi A21s della notte ANCORA sul telefono e piu' vecchi di 70' (l'archiviazione tiene l'ultima ora): se ce ne
    meta' notte. nomi = elenco di ~/rec/interi (per i test); None = lo chiede all'A21s."""
    ora = ora or datetime.now()
    if nomi is None:
        nomi = MR.ssh("ls ~/rec/interi", 30).split()
    if drive is None:
        drive = su_drive()  # ancora sul telefono ma gia' su Drive (l'archiviazione cancella dopo) = non manca
    d = datetime.strptime(day, "%Y%m%d")
    out = []
    for n in nomi:
        m = re.match(r"(\d{8}_\d{6})\.m4a$", n)
        if not m:
            continue
        t = datetime.strptime(m[1], "%Y%m%d_%H%M%S")
        if d - timedelta(hours=6) <= t <= ora - timedelta(minutes=70) and n not in drive:  # dalle 18 della sera prima
            out.append(n)
    return out


def archivio_pronto(day):
    """(True|False, perche'): se mancano blocchi su Drive lancia SUBITO l'archiviazione e ricontrolla."""
    p = pendenti(day)
    if not p:
        return True, "audio della notte tutto su Drive"
    log(f"{len(p)} blocchi della notte ancora sul telefono: archivio adesso")
    try:
        subprocess.run([PY, QUI("archivia_interi.py"), "--tieni-ore", "1"], capture_output=True, timeout=3000)
    except subprocess.TimeoutExpired:
        pass
    p = pendenti(day)
    return (not p), (f"ancora {len(p)} blocchi sul telefono: riprovo al giro dopo" if p else "archiviato ora")


def pc_usato(minuti=15):
    """Ultimo evento di activity.csv: ACTIVE = lo sta usando; IDLE recente = lo usava fino a poco fa."""
    try:
        t, ev = list(csv.reader(open(r"C:\activity_log\activity.csv")))[-1][:2]
        return ev == "ACTIVE" or datetime.now() - datetime.fromisoformat(t) < timedelta(minutes=minuti)
    except Exception:
        return False


def notte_finita(day, ora=None, analizza=None):
    """(True|False, perche'): la notte ha un sonno >= 3 h finito da >= 20' (analisi del PC, notte.py). Errore = False."""
    ora = ora or datetime.now()
    try:
        if analizza is None:
            import sonno_audio as SA
            analizza = SA.analizza
        r = analizza(day)
    except Exception as e:  # noqa: BLE001
        return False, f"analisi notte non riuscita ({type(e).__name__})"
    if not r or not r.get("blocco") or r.get("durata", 0) < 3:
        return False, "nessun sonno di almeno 3 h ancora"
    ultimo = max(r["M"]) if r.get("M") else r["fine"]
    if (ultimo - r["fine"]).total_seconds() < 20 * 60 or (ora - r["fine"]).total_seconds() < 20 * 60:
        return False, f"sonno fino alle {r['fine']:%H:%M}, dati fino alle {ultimo:%H:%M}: forse dorme ancora"
    return True, f"sonno {r['inizio']:%H:%M}-{r['fine']:%H:%M}"


def sonno_in_corso(day, ora=None, analizza=None):
    """Inizio del sonno se dorme da >= 2 h e il sonno e' ancora in corso (fine negli ultimi 15'), se no None."""
    ora = ora or datetime.now()
    try:
        if analizza is None:
            import sonno_audio as SA
            analizza = SA.analizza
        r = analizza(day)
    except Exception:  # noqa: BLE001
        return None
    if not (r and r.get("blocco") and r.get("durata", 0) >= 2):
        return None
    # e quel dato non e' troppo vecchio (< 90').
    ultimo = max(r["M"]) if r.get("M") else r["fine"]
    if (ultimo - r["fine"]).total_seconds() <= 15 * 60 and (ora - ultimo).total_seconds() <= 90 * 60:
        return r["inizio"]
    return None


def verdetto_parziale(csv_path, inizio, dev="a21s"):
    """(minuti dopo l'inizio, minuti con respiro o russare secondo Kaggle PANNs n02>=3) dal CSV parziale."""
    tot = segni = 0
    da = f"{inizio:%Y-%m-%dT%H:%M}"
    for r in csv.DictReader(open(csv_path, encoding="utf-8")):
        if r.get("dispositivo") != dev or r["minuto"] < da:
            continue
        tot += 1
        segni += int(r.get("snoring_n02") or 0) >= 3 or int(r.get("respiro_n02") or 0) >= 3
    return tot, segni


def conferma_notturna(day):
    """
    Una volta per notte, dopo >= 2 h di sonno in corso: Kaggle sulla finestra fino ad adesso in una cartella SEPARATA
    (kaggle/<notte>_parziale), poi un messaggio muto: inizio confermato o no. Il mattino rifa' tutta la notte come prima."""
    P = ROOT + rf"\kaggle\{day}_parziale"
    if os.path.exists(P + r"\fatto"):
        return
    inizio = sonno_in_corso(day)
    if not inizio:
        return
    os.makedirs(P, exist_ok=True)
    open(P + r"\fatto", "w").write(datetime.now().isoformat())  # una volta sola anche se Kaggle fallisce
    fin = datetime.now().strftime("%H:%M")
    log("conferma notturna", day, "inizio previsto", f"{inizio:%H:%M}", "finestra fino", fin)
    r = subprocess.run([PY, QUI("kaggle_notte.py"), day, "--fine", fin, "--dir", P], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=5400)
    csvp = P + r"\panns_w10_p1.csv"
    if r.returncode or not os.path.exists(csvp):
        log("conferma notturna ERRORE", (r.stderr or r.stdout)[-300:].replace("\n", " | "))
        return
    tot, segni = verdetto_parziale(csvp, inizio)
    if tot < 30:
        prove = P + r"\tentativi"
        n = int(open(prove).read()) + 1 if os.path.exists(prove) else 1
        open(prove, "w").write(str(n))
        log(f"conferma notturna: solo {tot} minuti analizzati (audio non ancora su Drive?), tentativo {n}/3")
        if n < 3:
            os.remove(P + r"\fatto")  # riprova al giro dopo
        return
    ok = segni >= 0.15 * tot
    testo = (f"🌙 Kaggle a meta' notte: {'confermato' if ok else 'NON ancora confermato'} che dormi dalle {inizio:%H:%M} "
             f"(respiro/russare in {segni} dei {tot} minuti dopo). Al risveglio arriva la notte intera.")
    log("conferma notturna", testo)
    subprocess.run([PY, QUI("tg_IlTuoBot.py"), testo, "--muto"], timeout=60)  # arriva, ma senza notifica: dorme


def main(argv):
    prova = "--prova" in argv
    day = next((x for x in argv if x.isdigit() and len(x) == 8), datetime.now().strftime("%Y%m%d"))
    O = ROOT + rf"\kaggle\{day}"
    os.makedirs(O, exist_ok=True)
    if os.path.exists(O + r"\fatto") and not prova:
        return
    if prova:
        print("notte", day, "| sveglio certo:", MR.sveglio_certo(), "| blocchi Drive (A21s tutti i file dei 2 giorni, A56):", blocchi(day))
        print("farei:", KN.__file__, day, "(senza --eff)", "--riusa-dataset" if "--riusa-dataset" in argv else "")
        print("poi: mappa_russare.py --ridisegna --variante D3c --kaggle", O, "--device <ogni dispositivo nei CSV>", day, "-> PNG sul telefono")
        print("marcatore:", O + r"\fatto")
        return
    # ancora iniziata, marcata "fatto" e mai rifatta. Ora serve un sonno vero (>= 3 h) finito da >= 20'.
    # non partiva mai.
    finita, perche = (True, "--subito") if "--subito" in argv else notte_finita(day)
    if not finita:
        log(f"aspetto {day}: {perche}")
        conferma_notturna(day)
        return
    # Kaggle usa solo rete: basta anche il PC usato negli ultimi 15'. Se salta, lo si scrive nel log.
    if not (MR.sveglio_certo() or pc_usato()):
        log(f"salto {day}: sveglio non certo (A21s non risponde?) e PC non usato da 15'")
        if datetime.now().hour >= 12 and not os.path.exists(O + r"\avvisato_salto"):  # una volta per notte
            open(O + r"\avvisato_salto", "w").write(datetime.now().isoformat())
            subprocess.run([PY, QUI("tg_IlTuoBot.py"), f"⚠️ Analisi della notte {day[6:]}/{day[4:6]} non ancora partita: "
                            "non so se sei sveglio (A21s non risponde) e il PC non e' usato. Parte da sola appena usi il PC."], timeout=60)
        return
    if not os.path.exists(O + r"\riepilogo.json"):
        pronto, perche = archivio_pronto(day)
        if not pronto:
            log(f"aspetto {day}: {perche}")
            return
        log("parto Kaggle", day)
        stato(day, "in corso")
        try:
            r = subprocess.run([PY, QUI("kaggle_notte.py"), day] + (["--riusa-dataset"] if "--riusa-dataset" in argv else []),
                               capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=7200)
            log("kaggle_notte rc", r.returncode, (r.stderr or r.stdout)[-400:].replace("\n", " | "))
        except Exception as e:
            log("kaggle_notte ERRORE", repr(e))
    if not os.path.exists(O + r"\riepilogo.json") or not os.path.exists(O + r"\panns_w10_p1.csv"):
        n = len(glob.glob(O + r"\falliti_*"))
        open(O + rf"\falliti_{n}", "w").write("1")
        log(f"Kaggle senza risultato (tentativo {n + 1}/3): fallback pipeline scrematura PC")
        stato(day, "errore")
        if n >= 2:
            open(O + r"\fatto", "w").write("senza kaggle")
            subprocess.run([PY, QUI("tg_IlTuoBot.py"), f"⚠️ Kaggle non ha analizzato la notte {day[6:]}/{day[4:6]} "
                            "(3 tentativi): uso l'analisi del PC. Dettagli in kaggle_mattino.log."], timeout=60)
        return
    if not os.path.exists(MR.OUT + rf"\mappa_{day}.json"):
        log("manca mappa_%s.json della pipeline: riprovo piu' tardi (il disegno parte da quel JSON)" % day)
        return
    devs = sorted({r["dispositivo"] for r in csv.DictReader(open(O + r"\panns_w10_p1.csv", encoding="utf-8"))})
    log("dispositivi con dati:", devs)
    if "a56" in devs and shutil.disk_usage("C:\\").free > 3 * 2**30:
        subprocess.Popen([PY, QUI("stessa_stanza.py"), day, "--scrivi"], stdout=open(ROOT + r"\stessa_stanza.log", "a"),
                         stderr=subprocess.STDOUT)
    if not devs:
        n = len(glob.glob(O + r"\falliti_*"))
        open(O + rf"\falliti_{n}", "w").write("0 file")
        os.makedirs(O + r"\vuoti", exist_ok=True)
        for f in [O + r"\riepilogo.json"] + glob.glob(O + r"\panns_*.csv"):  # spostati, non cancellati: il prossimo giro rifa'
            os.replace(f, os.path.join(O + r"\vuoti", f"{n}_" + os.path.basename(f)))
        log(f"Kaggle ha analizzato 0 file (tentativo {n + 1}/3): riprovo al prossimo giro")
        stato(day, "errore")
        if n >= 2:
            open(O + r"\fatto", "w").write("0 file")
            subprocess.run([PY, QUI("tg_IlTuoBot.py"), f"⚠️ Kaggle ha analizzato 0 file per la notte {day[6:]}/{day[4:6]} "
                            "(3 tentativi). Uso l'analisi del PC. Dettagli in kaggle_mattino.log."], timeout=60)
        return
    ko = 0
    for dev in devs:
        r = subprocess.run([PY, QUI("mappa_russare.py"), "--ridisegna", "--variante", "D3c", "--kaggle", O, "--device", dev, day],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900)
        base = MR.OUT + rf"\mappa_{day}_D3c_kaggle" + ("" if dev == "a21s" else "_" + dev)
        pngs = sorted(glob.glob(base + "_[0-9]*.png") + glob.glob(base + ".png"), key=os.path.getmtime)  # il disegno aggiunge _<versione>
        png = pngs[-1] if pngs else ""
        if r.returncode or not png or datetime.now().timestamp() - os.path.getmtime(png) > 600:
            ko += 1
            log("mappa", dev, "ERRORE", (r.stderr or r.stdout)[-300:].replace("\n", " | "))
            continue
        pagine = ordina_pagine([p for p in pngs if os.path.getmtime(p) >= os.path.getmtime(png) - 120])
        MR.ssh("mkdir -p ~/sonno_bot/mappe")
        if dev == "a21s":  # JSON coerente col PNG Kaggle (corsie PANNs da Kaggle)
            jn = MR.OUT + rf"\mappa_{day}_D3c_kaggle.json"
            log("json", "ok" if os.path.exists(jn) and MR.scp(jn, f"{MR.PHONE}:sonno_bot/mappe/mappa_{day}.json", 120) else "NON copiato (resta quello della pipeline)")
        for i, p in enumerate(pagine, 1):
            # il bot legge mappe/mappa_<giorno>.png (+ _pag2...): la mappa Kaggle dell'A21s; le altre col loro nome
            nome = (f"mappa_{day}.png" if i == 1 else f"mappa_{day}_pag{i}.png") if dev == "a21s" else os.path.basename(p)
            log("mappa", dev, p, "->", "telefono ok" if MR.scp(p, f"{MR.PHONE}:sonno_bot/mappe/{nome}", 120) else "telefono NON copiato")
    open(O + r"\fatto", "w").write(datetime.now().isoformat())
    stato(day, "errore" if ko == len(devs) else "ok", gpu_minuti(O))
    log("fatto", day)
    if ko < len(devs):
        try:
            MR.ssh("cd ~/sonno_bot && python -W ignore -c 'import bot; d=\"%s\"; bot.IN_FONDO[0]=True; bot.manda_notte(bot.analizza(d), d)'" % day)
            subprocess.run([PY, QUI("tg_IlTuoBot.py"), f"🔔 Notte {day[6:]}/{day[4:6]} analizzata da Kaggle: la scheda con la mappa e' qui sopra."], timeout=60)
        except Exception as e:  # noqa: BLE001
            log("scheda finale", repr(e))
    else:
        subprocess.run([PY, QUI("tg_IlTuoBot.py"), f"⚠️ Notte {day[6:]}/{day[4:6]}: Kaggle finito ma la mappa non si disegna "
                        "(nessuna scheda). Dettagli in kaggle_mattino.log."], timeout=60)


def ordina_pagine(pagine):
    """mappa_..._1.png, _2.png ... in ordine di pagina (non di data)."""
    n = lambda p: int(re.search(r"_(\d+)\.png$", p).group(1)) if re.search(r"_(\d+)\.png$", p) else 0
    return sorted(pagine, key=n)


def QUI(f):
    return os.path.join(r"C:\sonno_tex", f)


def aggiorna_copertura(argv):
    """Anche se Kaggle e' gia' finito/fallito: la copertura e' indipendente."""
    if '--prova' in argv or datetime.now().hour < 12:
        return
    day = next((x for x in argv if x.isdigit() and len(x) == 8), datetime.now().strftime('%Y%m%d'))
    try:
        import copertura_mattino
        copertura_mattino.main([day, '--pubblica'])
    except Exception as e:
        log('copertura_mattino', type(e).__name__, str(e)[:160])


if __name__ == "__main__":
    if "--prova" not in sys.argv:
        os.makedirs(ROOT, exist_ok=True)
    import traceback
    try:
        main(sys.argv[1:])
    except BaseException as e:  # noqa: BLE001 - anche SystemExit/MemoryError: scriverlo e' tutto quello che serve
        log("ERRORE giro", type(e).__name__, str(e)[:200], traceback.format_exc()[-300:].replace("\n", " | "))
        raise
    finally:
        try:
            aggiorna_copertura(sys.argv[1:])
        except BaseException as e:  # noqa: BLE001
            log("ERRORE copertura", type(e).__name__, str(e)[:200])
