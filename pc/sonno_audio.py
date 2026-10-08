"""Sonno dall'audio dell'A21s (Termux registra blocchi da 30' in /sdcard/Recordings/sonno).
  python sonno_audio.py sync             -> scarica i blocchi finiti, verifica, li cancella dal telefono, li analizza,
                                            e se una notte e' finita manda il report su Telegram (una volta sola)
  python sonno_audio.py report [AAAAMMGG] -> report della notte che finisce quel giorno (default: oggi)
Sul telefono tocca SOLO /sdcard/Recordings/sonno/*.m4a gia' copiati e verificati.
"""
import senza_finestre  # noqa: F401  (niente finestre dei processi figli: va importato per primo)
import csv, os, subprocess, sys
import a21
from datetime import datetime, timedelta
import numpy as np, onnxruntime as ort

if os.name == "nt":  # adb/ffmpeg/ssh lanciati da pythonw o in background aprivano una console ciascuno (lampi)
    _popen_init = subprocess.Popen.__init__

    def _senza_finestra(self, *a, **k):
        k.setdefault("creationflags", subprocess.CREATE_NO_WINDOW)
        _popen_init(self, *a, **k)
    subprocess.Popen.__init__ = _senza_finestra

PHONE_DIR = "files/home/rec"  # dentro Termux (relativo per run-as com.termux): visibile anche a loop senza schermo
ROOT = r"C:\sonno_audio"
RAW, FEAT, MIN = ROOT + r"\raw", ROOT + r"\feat", ROOT + r"\minuti"
NOTTI, DIARIO = ROOT + r"\notti.csv", ROOT + r"\diario.csv"
PC_LOG = r"C:\activity_log\activity.csv"
SERIALS = ["SERIALE_TELEFONO", f"{a21.ip()}:5555"]
MODEL = r"C:\sonno_tex\yamnet\yamnet.onnx"
TG = os.path.expanduser(r"~\Downloads\tirocinio\SLIDE_INPUT_OUTPUT_BASE\strumenti")
HOP = 0.48  # s per frame YAMNet
CL = {"russa": 38, "respiro": 36, "voce": 0, "tosse": 42, "sbuffo": 41, "musica": 132}


def adb(*a, dev=None):
    cmd = ["adb"] + (["-s", dev] if dev else []) + list(a)
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if dev and any(s in p.stderr for s in ("device offline", "not found", "no devices", "closed")):
        raise RuntimeError(f"adb {dev}: {p.stderr.strip()}")
    return p


def device():
    if f"{SERIALS[0]}\tdevice" not in adb("devices").stdout:
        adb("connect", SERIALS[1])
    ok = adb("devices").stdout
    return next((s for s in SERIALS if f"{s}\tdevice" in ok), None)


def prendi(dev, name, local):
    """Copia un file da ~/rec di Termux (run-as + exec-out: binario pulito). Ritorna i byte scritti."""
    p = subprocess.run(["adb", "-s", dev, "exec-out", "run-as", "com.termux", "cat", f"{PHONE_DIR}/{name}"],
                       capture_output=True, timeout=300)
    if p.returncode != 0 or not p.stdout:
        return -1
    with open(local, "wb") as f:
        f.write(p.stdout)
    return len(p.stdout)


def sync():
    os.makedirs(RAW, exist_ok=True)
    dev = device()
    if not dev:
        # minuti_*.csv sul PC, kaggle_mattino "nessun sonno di 3 h", niente scheda. ssh resta su: i minuti passano di li'.
        # ponytail: solo i minuti (servono al mattino); clip/cal/foto restano solo via adb.
        os.makedirs(MIN, exist_ok=True)
        r = subprocess.run(["scp", "-q", "-P", "8022", "-o", "ConnectTimeout=10", "-o", "BatchMode=yes",
                            f"{a21.ip()}:rec/minuti_*.csv", MIN], capture_output=True, timeout=300)
        print("adb giu: minuti via ssh", "ok" if r.returncode == 0 else "NO")
    else:
        # il telefono analizza da solo (sonno_tel.py) in ~/rec di Termux: copio riassunti per minuto e clip
        os.makedirs(MIN, exist_ok=True)
        nomi = adb("shell", f"run-as com.termux ls {PHONE_DIR}", dev=dev).stdout.split()
        for name in nomi:
            if name.startswith("minuti_"):
                prendi(dev, name, os.path.join(MIN, name))
                if datetime.now() - datetime.strptime(name[7:15], "%Y%m%d") > timedelta(days=7):
                    adb("shell", f"run-as com.termux rm {PHONE_DIR}/{name}", dev=dev)  # copia sul PC da giorni
        # suoni registrati dal bot (🎙️ Registra) -> C:\sonno_audio\cal per cal_train
        cal_pc = ROOT + r"\cal"
        os.makedirs(cal_pc, exist_ok=True)
        # i suoni RESTANO sul telefono (lista 📂 Audio del bot); quelli cancellati dal bot li cancello anche qui
        canc = adb("shell", "run-as com.termux cat files/home/cal/cancellati.txt", dev=dev).stdout.split()
        for name in canc:
            if name.endswith(".m4a") and os.path.exists(os.path.join(cal_pc, name)):
                os.remove(os.path.join(cal_pc, name))
        for name in adb("shell", "run-as com.termux ls files/home/cal", dev=dev).stdout.split():
            if name.endswith(".m4a") and "__tg__" in name and not os.path.exists(os.path.join(cal_pc, name)):
                size = int(adb("shell", f"run-as com.termux stat -c %s files/home/cal/{name}", dev=dev).stdout.strip() or -1)
                p = subprocess.run(["adb", "-s", dev, "exec-out", "run-as", "com.termux", "cat", f"files/home/cal/{name}"],
                                   capture_output=True, timeout=300)
                if size > 0 and len(p.stdout) == size:
                    open(os.path.join(cal_pc, name), "wb").write(p.stdout)
        for name in sorted(x for x in nomi if x.endswith(".m4a") and x.split("_")[0] in ("russa", "voce", "tosse", "sbuffo")):
            local = os.path.join(RAW, name)
            if os.path.exists(local):
                continue  # gia' copiata
            size = int(adb("shell", f"run-as com.termux stat -c %s {PHONE_DIR}/{name}", dev=dev).stdout.strip() or -1)
            if size > 0 and prendi(dev, name, local) == size:
                print("ok", name)
            else:
                print("copia fallita:", name)
    # disco C: piccolo: clip di russamento tenute 3 giorni (per riascoltarle/tarare)
    for name in os.listdir(RAW):
        if name.endswith(".m4a") and datetime.now().timestamp() - os.path.getmtime(os.path.join(RAW, name)) > 3 * 86400:
            os.remove(os.path.join(RAW, name))
    cane_da_guardia(dev)
    # segnali certi di veglia dal SUO telefono (schermo acceso/spento/sbloccato): se non risponde, niente
    subprocess.run([sys.executable, r"C:\sonno_bot\tecnica\app_sonno\schermo_a56.py"], capture_output=True, timeout=300)
    if dev:
        try:
            manda_al_bot(dev)
        except Exception as e:
            print("manda_al_bot:", e)
    try:
        pc_al_telefono()
    except Exception as e:
        print("pc_al_telefono:", e)
    try:
        pulisci_pc_telefono()
    except Exception as e:
        print("pulisci_pc_telefono:", e)
    # report del mattino: ora lo manda il TELEFONO (@IlTuoBot, ~/sonno_bot/bot.py), indipendente dal PC.
    # auto() resta per usarlo a mano (python -c "import sonno_audio; sonno_audio.auto()").


A56_SCHERMO = ROOT + r"\a56_schermo.csv"
A56_AZIONI = ROOT + r"\a56_azioni.csv"


def a56_usato(start, end):
    """Minuti con il SUO telefono sbloccato (da sbloccato a spento): segnale certo di veglia."""
    att, su = set(), None
    if not os.path.exists(A56_SCHERMO):
        return att
    for riga in csv.reader(open(A56_SCHERMO, encoding="utf-8")):
        t, e = datetime.fromisoformat(riga[0]), riga[1]
        if e == "sbloccato" and su is None:
            su = t
        elif e == "spento" and su is not None:
            m = max(su, start).replace(second=0, microsecond=0)
            # ponytail: sessione max 3h: un "spento" perso non deve cancellare una notte intera di sonno
            while m < min(t, end, su + timedelta(hours=3)):
                att.add(m); m += timedelta(minutes=1)
            su = None
    if os.path.exists(A56_AZIONI):
        for riga in csv.reader(open(A56_AZIONI, encoding="utf-8")):
            a, b = datetime.fromisoformat(riga[0]), datetime.fromisoformat(riga[1]) + timedelta(minutes=1)
            att -= {m for m in att if a.replace(second=0, microsecond=0) <= m <= b}
    return att


SONNO = ("deep_sleep", "light_sleep", "rem", "not_awake")


def sleep_affidabile(eventi, usato):
    """eventi = righe di a56_eventi_sleep.csv [ts, evento, ...]; scarta il sonno dentro minuti di uso del telefono."""
    return [r for r in eventi
            if r[1] not in SONNO or datetime.fromisoformat(r[0]).replace(second=0, microsecond=0) not in usato]


A56_FILE = ["segnale_uso.py", "a56_watchdog.sh", "sonno_webhook.py", "sensori_minuti.py", "sensori_notte.sh"]


def segnale_a56_pronto(testo, ora=None):
    """C1 si installa solo dopo un heartbeat prodotto davvero dall'A56."""
    import json
    try:
        d = json.loads(testo)
        ora = ora or datetime.now()
        return (d.get("fonte") == "a56_locale" and d.get("schermo") in ("Awake", "Asleep", "Dozing", "Dreaming")
                and 0 <= (ora-datetime.fromisoformat(d["raccolto"])).total_seconds() <= 120
                and datetime.fromisoformat(d["a56"]) <= ora)
    except (ValueError, TypeError, KeyError, AttributeError):
        return False


def aggiorna_a56(a56):
    """Copia sull'A56 (home di Termux, solo file nostri) gli script cambiati sul PC; se cambia il ricevitore della
    """
    os.environ["MSYS_NO_PATHCONV"] = "1"
    # l'A56 tiene la versione buona b24e65c (musica si abbassa). Si toglie dopo la prova di giorno.
    if os.path.exists(r"C:\sonno_audio\A56_FERMO"):
        return
    if subprocess.run(["adb", "-s", a56, "shell", "echo ok"], capture_output=True, text=True, timeout=20).stdout.strip() != "ok":
        return
    base = r"C:\sonno_bot\tecnica\app_sonno"
    for n in A56_FILE:
        if n == "sonno_webhook.py":
            segnale = subprocess.run(["adb", "-s", a56, "shell", "cat /sdcard/Documents/sonno/uso_recente.json"],
                                     capture_output=True, text=True, timeout=10)
            if segnale.returncode or not segnale_a56_pronto(segnale.stdout):
                print("C1 non installato: prima verificare segnale locale A56")
                continue
        dati = open(os.path.join(base, n), "rb").read().replace(bytes([13, 10]), bytes([10]))  # a-capo Linux: sh con CR non gira
        loc = os.path.join(ROOT, "tmp_bot", "x_a56"); os.makedirs(os.path.dirname(loc), exist_ok=True)
        open(loc, "wb").write(dati)
        rem = subprocess.run(["adb", "-s", a56, "shell", f"run-as com.termux stat -c %s files/home/{n}"],
                             capture_output=True, text=True).stdout.strip()
        if rem == str(len(dati)):
            continue
        subprocess.run(["adb", "-s", a56, "push", loc, "/data/local/tmp/x_a56"], capture_output=True)
        subprocess.run(["adb", "-s", a56, "shell", f"cat /data/local/tmp/x_a56 | run-as com.termux sh -c "
                        f"'cat > files/home/{n}.new && mv files/home/{n}.new files/home/{n}'; rm /data/local/tmp/x_a56"],
                       capture_output=True)
        print("A56 aggiornato:", n)
        if n == "sonno_webhook.py":
            subprocess.run(["adb", "-s", a56, "shell", "run-as com.termux pkill -f sonno_webhook.py"], capture_output=True)
        if n == "a56_watchdog.sh":  # gira in un ciclo: senza riavvio resta la versione vecchia
            try:
                subprocess.run(["adb", "-s", a56, "shell", "run-as com.termux sh -c 'kill $(cat files/home/.a56_watchdog.pid); "
                                "cd files/home && HOME=$PWD PATH=/data/data/com.termux/files/usr/bin:$PATH setsid nohup "
                                "sh a56_watchdog.sh </dev/null >/dev/null 2>&1 &'"], capture_output=True, timeout=15)
            except subprocess.TimeoutExpired:
                pass
    subprocess.run(["adb", "-s", a56, "shell", "pm grant com.termux android.permission.WRITE_SECURE_SETTINGS"],
                   capture_output=True, timeout=20)


def pc_al_telefono(max_file=4):
    """
    chiuse da >= 2' vanno sull'A21s in ~/rec/pc/ come m4a mono 32 kHz 48k (~20 MB a mezz'ora), per il pulsante PC del
    video del tratto (bot.audio_tratto fonte='pc'). Quelle gia' mandate sono in pc_mandati.txt."""
    import glob, tempfile, time
    fatti_p = os.path.join(ROOT, "pc_mandati.txt")
    fatti = set(open(fatti_p).read().split()) if os.path.exists(fatti_p) else set()
    nuovi = [p for p in sorted(glob.glob(os.path.join(ROOT, "tre_dispositivi", "*", "pc_*.flac")), reverse=True)  # prima i recenti
             if os.path.basename(p) not in fatti and time.time() - os.path.getmtime(p) > 120
             and os.path.getsize(p) > 100_000][:max_file]
    ssh = ["ssh", "-p", "8022", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", a21.ip()]
    if not nuovi or subprocess.run(ssh + ["mkdir -p ~/rec/pc"], capture_output=True, timeout=60).returncode:
        return
    for p in nuovi:
        m4a = os.path.join(tempfile.gettempdir(), os.path.basename(p)[:-5] + ".m4a")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", p, "-ac", "1", "-ar", "32000", "-c:a", "aac", "-b:a", "48k",
                        m4a], capture_output=True, timeout=600)
        ok = os.path.exists(m4a) and subprocess.run(
            ["scp", "-q", "-P", "8022", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", m4a, f"{a21.ip()}:rec/pc/"],
            capture_output=True, timeout=600).returncode == 0
        if os.path.exists(m4a):
            os.remove(m4a)  # disco C quasi pieno: il FLAC originale resta, la copia compressa no
        if ok:
            open(fatti_p, "a").write(os.path.basename(p) + "\n")
            print("PC -> telefono:", os.path.basename(p))


def pc_da_togliere(locali, drive, ora, giorni=2, min_b=1_000_000):
    """locali = {nome.m4a: mtime} di ~/rec/pc sull'A21s; drive = righe 'percorso|byte' di rclone lsf su sonno/pc.
    -> nomi da cancellare sul telefono: piu' vecchi di `giorni` e col FLAC (stesso nome base) su Drive > min_b."""
    su_drive = set()
    for r in drive:
        p, _, b = r.strip().rpartition("|")
        if b.isdigit() and int(b) > min_b:
            su_drive.add(os.path.splitext(p.rsplit("/", 1)[-1])[0])
    return sorted(n for n, t in locali.items() if n.endswith(".m4a") and ora - t > giorni * 86400
                  and n[:-4] in su_drive)


def pulisci_pc_telefono(prova=False):
    """
    Una volta al giorno: cancella SUL TELEFONO (os.remove) solo quelle >2 giorni il cui FLAC e' su Drive. Drive mai toccato.
    prova=True: stampa soltanto cosa toglierebbe (python sonno_audio.py pulizia_prova)."""
    import json, re
    fatto = os.path.join(ROOT, "pc_pulizia_giorno.txt")
    oggi = f"{datetime.now():%Y-%m-%d}"
    if not prova and os.path.exists(fatto) and open(fatto).read().strip() == oggi:
        return
    ssh = ["ssh", "-p", "8022", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", a21.ip()]
    elenco = subprocess.run(ssh + ["python -c 'import os,json,time;d=os.path.expanduser(\"~/rec/pc\");"
                                   "print(json.dumps([time.time(),{n:os.path.getmtime(os.path.join(d,n)) for n in "
                                   "(os.listdir(d) if os.path.isdir(d) else [])}]))'"],
                            capture_output=True, text=True, timeout=60)
    # stesso remote di C:\sonno_bot\miniapp.py (DRIVE_REMOTE); rclone gira sull'A21s
    remote = os.environ.get("MINIAPP_DRIVE_REMOTE", "gdrive:") + "sonno/pc"
    drive = subprocess.run(ssh + [f"rclone lsf -R --files-only --format ps --separator '|' {remote}"],
                           capture_output=True, text=True, timeout=300)
    if elenco.returncode or drive.returncode:  # telefono o Drive giu' -> non tocco niente
        print("pulizia rec/pc: saltata (ssh/rclone)", elenco.stderr[-150:].strip(), drive.stderr[-150:].strip())
        return
    ora, locali = json.loads(elenco.stdout)
    via = [n for n in pc_da_togliere(locali, drive.stdout.splitlines(), ora) if re.fullmatch(r"pc_\d{8}_\d{6}\.m4a", n)]
    if prova:
        print(f"PROVA (niente cancellato): {len(via)}/{len(locali)} m4a da togliere:", " ".join(via))
        return
    if via:
        r = subprocess.run(ssh + ["python -c 'import os,sys;[os.remove(os.path.expanduser(\"~/rec/pc/\"+n)) "
                                  "for n in sys.argv[1:]]' " + " ".join(via)], capture_output=True, text=True, timeout=120)
        if r.returncode:
            print("pulizia rec/pc: os.remove fallito", r.stderr[-200:])
            return
    open(fatto, "w").write(oggi)
    log(f"pulizia rec/pc: {len(via)}/{len(locali)} m4a tolte dal telefono (FLAC su Drive): {' '.join(via)}")


def al_bot(src, n, dev):
    """
    """
    r = subprocess.run(["scp", "-q", "-P", "8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", src,
                        f"{a21.ip()}:sonno_bot/{n}"], capture_output=True, timeout=120)
    if r.returncode == 0:
        return
    adb("push", src, "/sdcard/Recordings/tmp_bot", dev=dev)
    adb("shell", f"cat /sdcard/Recordings/tmp_bot | run-as com.termux sh -c 'cat > files/home/sonno_bot/{n}'", dev=dev)
    adb("shell", "rm /sdcard/Recordings/tmp_bot", dev=dev)


def manda_al_bot(dev):
    """Al bot sul telefono: uso.csv (minuti con PC o A56 usati, ultime 48h) + dispositivi.json (ultimo contatto
    """
    import json
    fine = datetime.now(); inizio = fine - timedelta(days=8)
    pc, a56 = pc_attivo(inizio, fine), a56_usato(inizio, fine)
    minuti = sorted(pc | a56)
    ultimo_a56 = ""
    if os.path.exists(A56_SCHERMO):
        ultimo_a56 = open(A56_SCHERMO, encoding="utf-8").read().split("\n")[-2].split(",")[0][:16]
    tmp = os.path.join(ROOT, "tmp_bot"); os.makedirs(tmp, exist_ok=True)
    # fonte: pc = alla scrivania (fuori dal letto: serve per "a letto" / "in piedi"), a56 = telefono (anche a letto)
    open(os.path.join(tmp, "uso.csv"), "w").write("".join(f"{m:%Y-%m-%dT%H:%M},{'pc' if m in pc else 'a56'}\n"
                                                          for m in minuti))
    import glob, shutil
    flac = sorted(glob.glob(os.path.join(ROOT, "tre_dispositivi", "*", "*.flac")), key=os.path.getmtime)
    sleep = [r.split(",")[:2] for r in open(ROOT + r"\a56_eventi_sleep.csv", encoding="utf-8").read().split("\n")
             if "sleep_tracking_st" in r] if os.path.exists(ROOT + r"\a56_eventi_sleep.csv") else []
    json.dump({"pc": f"{fine:%Y-%m-%dT%H:%M}", "a56": ultimo_a56.replace(" ", "T"),
               "pc_gb": round(shutil.disk_usage("C:/").free / 2**30, 1),
               "pc_rec": datetime.fromtimestamp(os.path.getmtime(flac[-1])).isoformat(timespec="minutes") if flac else "",
               "a56_sleep": sleep[-1] if sleep else [],  # [ora, sleep_tracking_started|stopped]
               "pc_tot": round(shutil.disk_usage("C:/").total / 2**30, 1),
               "err": json.load(open(os.path.join(ROOT, "array", "grafici", "disposizione_card_err.json")))
               if os.path.exists(os.path.join(ROOT, "array", "grafici", "disposizione_card_err.json")) else {}},
              open(os.path.join(tmp, "dispositivi.json"), "w"))
    card = os.path.join(ROOT, "array", "grafici", "disposizione_card.png")  # tecnica/array/card_disposizione.py
    cal = glob.glob(os.path.join(ROOT, "array", "disposizioni", "calibra_*"))
    if cal and (not os.path.exists(card) or max(map(os.path.getmtime, cal)) > os.path.getmtime(card)):
        # disposizione nuova -> card nuova (ultima calibrazione VALIDA; quelle sbagliate le scarta lei)
        subprocess.run([sys.executable, r"C:\sonno_bot\tecnica\array\card_disposizione.py"], capture_output=True,
                       timeout=600)
    file = [(os.path.join(tmp, n), n) for n in ("uso.csv", "dispositivi.json")]
    if os.path.exists(card):
        file.append((card, "disposizione.png"))
    for src, n in file:
        al_bot(src, n, dev)
    # movimenti dal telefono personale nel letto (A56, sensori_minuti.py: t,mov,luce,n) -> al bot come movimenti.csv
    a56 = "192.0.2.54:5555"
    try:
        aggiorna_a56(a56)
    except Exception as e:
        print("aggiorna_a56:", e)
    sens = os.path.join(ROOT, "sensori_a56"); os.makedirs(sens, exist_ok=True)
    elenco = subprocess.run(["adb", "-s", a56, "shell", "run-as com.termux ls files/home/notte_sensori"],
                            capture_output=True, text=True)
    for n in elenco.stdout.split():
        if n.endswith("_minuti.csv"):
            p = subprocess.run(["adb", "-s", a56, "exec-out", "run-as", "com.termux", "cat",
                                f"files/home/notte_sensori/{n}"], capture_output=True, timeout=60)
            if p.returncode == 0 and p.stdout:
                open(os.path.join(sens, n), "wb").write(p.stdout)
    righe = sorted({l for f in glob.glob(os.path.join(sens, "*_minuti.csv"))
                    for l in open(f, encoding="utf-8").read().split("\n")[1:] if l.count(",") == 3})
    open(os.path.join(tmp, "movimenti.csv"), "w").write("t,mov,luce,n\n" + "\n".join(righe[-3000:]) + "\n")
    al_bot(os.path.join(tmp, "movimenti.csv"), "movimenti.csv", dev)
    fb = os.path.join(ROOT, "foto_bot"); os.makedirs(fb, exist_ok=True)
    for n in adb("shell", "run-as com.termux ls files/home/sonno_bot/foto", dev=dev).stdout.split():
        if n.endswith(".jpg") and not os.path.exists(os.path.join(fb, n)):
            p = subprocess.run(["adb", "-s", dev, "exec-out", "run-as", "com.termux", "cat",
                                f"files/home/sonno_bot/foto/{n}"], capture_output=True, timeout=120)
            if p.returncode == 0 and p.stdout:
                open(os.path.join(fb, n), "wb").write(p.stdout)


def load(path):
    pcm = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                         capture_output=True).stdout
    return np.frombuffer(pcm, np.float32)


def analyze_new():
    os.makedirs(FEAT, exist_ok=True)
    sess = None
    for name in sorted(os.listdir(RAW)):
        out = os.path.join(FEAT, name[:-4] + ".csv")
        if os.path.exists(out):
            continue
        sess = sess or ort.InferenceSession(MODEL)
        w = load(os.path.join(RAW, name))
        if len(w) < 16000:
            continue
        sc = np.concatenate([sess.run(None, {"waveform": w[i:i + 16000 * 60]})[0]
                             for i in range(0, len(w) - 16000, 16000 * 60)])  # a pezzi di 1'
        n = int(HOP * 16000)
        db = [20 * np.log10(np.sqrt(np.mean(w[i * n:(i + 1) * n] ** 2)) + 1e-9) for i in range(len(sc))]
        t0 = datetime.strptime(name[:15], "%Y%m%d_%H%M%S")
        with open(out, "w", newline="") as f:
            wr = csv.writer(f)
            wr.writerow(["t", "db"] + list(CL))
            for i, row in enumerate(sc):
                wr.writerow([(t0 + timedelta(seconds=i * HOP)).isoformat(timespec="seconds"), round(db[i], 1)]
                            + [round(float(row[c]), 3) for c in CL.values()])
        print("analizzato", name)


def pc_attivo(start, end):
    """Minuti in cui il PC era usato (tastiera/mouse veri): se usi il PC non dormi."""
    ev = []
    for r in csv.DictReader(open(PC_LOG)):
        ev.append((datetime.fromisoformat(r["timestamp"]), r["event"]))
    att = set()
    for (a, e), nxt in zip(ev, ev[1:] + [(datetime.now(), "")]):
        if e == "ACTIVE" and nxt[0] > start and a < end:
            m = max(a, start).replace(second=0)
            while m < min(nxt[0], end):
                att.add(m); m += timedelta(minutes=1)
    return att


def storico():
    return list(csv.DictReader(open(NOTTI))) if os.path.exists(NOTTI) else []


# analisi della notte: UNICA versione in C:\sonno_bot\notte.py (la usa anche il bot sul telefono)
sys.path.insert(0, r"C:\sonno_bot")
import notte  # noqa: E402


def sveglio_attivo(start, end):
    """
    """
    return pc_attivo(start, end) | a56_usato(start, end)


def analizza(day):
    return notte.analizza(MIN, day, pc_fn=sveglio_attivo, storico=storico())


testo = notte.testo


def salva(r):
    rows = [x for x in storico() if x["day"] != r["day"]]
    rows.append(dict(day=r["day"], inizio=r["inizio"].isoformat(), fine=r["fine"].isoformat(),
                     durata=round(r["durata"], 2), eff=round(r["eff"], 3), risvegli=len(r["risvegli"]),
                     russa_min=r["russa"], punteggio=r["punteggio"], inviato=datetime.now().isoformat(timespec="minutes")))
    with open(NOTTI + ".tmp", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[-1])); w.writeheader(); w.writerows(rows)
    os.replace(NOTTI + ".tmp", NOTTI)  # atomico: storico mai a metà


LOG = ROOT + r"\sync.log"


def log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M} {msg}\n")


def tg(msg):
    p = subprocess.run([sys.executable, os.path.join(TG, "telegram_manda_messaggio_di_testo.py"), msg],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if "OK" not in p.stdout:
        log(f"TELEGRAM FALLITO: {p.stdout[-300:]} {p.stderr[-300:]}")


def cane_da_guardia(dev):
    """Allarme Telegram (una volta) se da >1h non arrivano blocchi: telefono riavviato, Termux ucciso, wifi/IP cambiato."""
    flag = ROOT + r"\allarme.flag"
    ultimi = sorted(os.listdir(MIN)) if os.path.isdir(MIN) else []
    ultimo = datetime.now()
    if ultimi:
        righe = open(os.path.join(MIN, ultimi[-1])).read().split()
        if len(righe) > 1:
            ultimo = datetime.fromisoformat(righe[-1].split(",")[0])
    fermo = datetime.now() - ultimo > timedelta(minutes=100)  # blocco 30' + analisi + sync 30' + margine
    if fermo and not os.path.exists(flag):
        tg("⚠️ <b>Registrazione sonno ferma</b> dall'ultimo blocco delle " + f"{ultimo:%H:%M}. "
           + ("Telefono non raggiungibile via wifi (riavviato? IP cambiato?)." if not dev else
              "Telefono raggiungibile ma non registra (Termux chiuso?).")
           + " Collegalo al PC col cavo e dimmelo: lo faccio ripartire io.")
        open(flag, "w").close(); log("ALLARME inviato")
    elif not fermo and os.path.exists(flag):
        os.remove(flag); tg("✅ Registrazione sonno ripartita."); log("allarme rientrato")


def auto():
    """Se l'ultima notte e' finita da almeno 45' (e non gia' mandata): report su Telegram + voto del mattino."""
    fatti = {x["day"] for x in storico()}
    for d in (datetime.now() - timedelta(days=1), datetime.now()):
        day = d.strftime("%Y%m%d")
        if day in fatti:
            continue
        r = analizza(day)
        finestra_chiusa = datetime.now() >= datetime.strptime(day, "%Y%m%d").replace(hour=16)
        if not r or not r["blocco"] or datetime.now() - r["fine"] < timedelta(minutes=45) \
                or (max(r["M"]) - r["fine"] < timedelta(minutes=30) and not finestra_chiusa):
            continue  # notte non ancora finita (o finita ma senza audio dopo: aspetto fino alle 16)
        salva(r)
        tg("🌙 " + testo(r, html=True))
        # clip della notte: 3 di russamento (inizio/meta'/fine), 1 di voce, 1 di tosse -> le ascolta e dice se e' giusto
        for tipo, quante in (("russa", 3), ("voce", 1), ("tosse", 1)):
            clip = [os.path.join(RAW, n) for n in sorted(os.listdir(RAW)) if n.startswith(tipo + "_")
                    and r["inizio"] <= datetime.strptime(n[-17:-4], "%Y%m%d_%H%M") <= r["fine"]]
            if clip:
                scelte = [clip[i] for i in sorted({0, len(clip) // 2, len(clip) - 1})][:quante]
                subprocess.run([sys.executable, os.path.join(TG, "telegram_manda_audio_riproducibile.py"),
                                f"{tipo.capitalize()} stanotte (20s)"] + scelte, capture_output=True)
        # diario del mattino, in un processo separato che aspetta la risposta 2h
        subprocess.Popen([sys.executable, __file__, "voto", day], creationflags=0x08000008)  # DETACHED|NO_WINDOW


def voto(day):
    out = subprocess.run([sys.executable, os.path.join(TG, "telegram_chiedi_scelta_con_pulsanti.py"),
                          "Come ti senti stamattina?", "1 distrutto", "2 stanco", "3 normale", "4 bene", "5 riposato",
                          "--aspetta", "7200"], capture_output=True, text=True).stdout
    s = next((x.split(":", 1)[1].strip() for x in out.splitlines() if x.startswith("SCELTA:")), "")
    nuovo = not os.path.exists(DIARIO)
    with open(DIARIO, "a", newline="") as f:
        w = csv.writer(f)
        if nuovo: w.writerow(["day", "voto", "ora_risposta"])
        w.writerow([day, s[:1], datetime.now().isoformat(timespec="minutes")])


def _prova():
    """Prova offline con dati finti (python sonno_audio.py prova)."""
    import tempfile
    global A56_SCHERMO, A56_AZIONI
    d = tempfile.mkdtemp()
    A56_SCHERMO, A56_AZIONI = d + r"\s.csv", d + r"\a.csv"
    open(A56_SCHERMO, "w").write("2026-09-29 13:34:00,sbloccato\n2026-09-29 14:12:00,spento\n")
    open(A56_AZIONI, "w").write("2026-09-29T13:40:10,2026-09-29T13:40:50,tocca\n")
    i, f = datetime(2026, 9, 29, 0), datetime(2026, 9, 29, 3)
    u = a56_usato(i, f)
    assert datetime(2026, 9, 29, 1, 34) in u and datetime(2026, 9, 29, 1, 50) in u
    assert not {datetime(2026, 9, 29, 1, 40), datetime(2026, 9, 29, 1, 41)} & u  # azione adb + 1' margine
    assert datetime(2026, 9, 29, 1, 42) in u
    ev = [["2026-09-29T13:50:19", "deep_sleep", "", ""], ["2026-09-29T14:30:00", "deep_sleep", "", ""],
          ["2026-09-29T13:50:30", "sleep_tracking_started", "", ""]]
    assert sleep_affidabile(ev, u) == [ev[1], ev[2]]
    print("prova ok")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "prova":
        _prova()
    elif cmd == "sync":
        try:
            sync()
        except Exception:
            import traceback; log("ERRORE " + traceback.format_exc())  # pythonw non mostra nulla
            raise
    elif cmd == "pulizia_prova":
        pulisci_pc_telefono(prova=True)
    elif cmd == "voto":
        voto(sys.argv[2])
    else:
        print(testo(analizza(sys.argv[2] if len(sys.argv) > 2 else datetime.now().strftime("%Y%m%d"))))
