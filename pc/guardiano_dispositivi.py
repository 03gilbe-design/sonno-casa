"""Guardiano dei dispositivi di registrazione del sonno: A21s (principale), A56 (riserva), PC (terza).
Un giro = rileva stato di ognuno -> tabella delle combinazioni (decidi) -> azioni -> csv/json -> avviso SOLO ai cambi.
  python guardiano_dispositivi.py            giro vero (attivita' SonnoGuardiano ogni 2')
  python guardiano_dispositivi.py --prova    rileva e dice cosa farebbe, senza agire ne' scrivere
Tabella e motivazioni: STATI_DISPOSITIVI.md. Test: test_guardiano.py

CONTROLLI (ogni giro, per dispositivo): (a) sessione microfono in `dumpsys audio` con silenced:false;
(b) il file corrente CRESCE (A56: stessa dimensione tra due giri = fermo); (c) audio non nullo: RMS dell'ultimo pezzo
decodificato con ffmpeg sul PC. (c) vale per A21s (penultimo blocco, chiuso) e PC (coda del flac); per l'A56 il file unico
e' un mp4 APERTO (moov scritto solo alla chiusura): non decodificabile, quindi (c) = "non verificabile" e si fidano (a)+(b).
ESITI: ok / muto (mic silenziato, audio a zero, o A56 serve ma schermo col PIN) / fermo / riavviato -> guardiano_rec.csv,
guardiano_rec.json (copiato sull'A21s in ~/guardiano_rec.json: stato.py lo mette in stato.json["rec"] per la card /stato).

- livello persona (stato.json["livello"]) = ?, sveglio?, dorme?, dorme  ->  `incerto`: A56 parte se non registra (il PC parte da solo dopo
  5' senza input, registra_se_dormi.ps1; l'A21s e' sempre acceso). Sveglio SICURO di giorno: nessuna riserva. Meglio registrare in piu'.
  una volta partito resta attivo anche dopo il blocco col PIN (mai aggirato).
- A56 col PIN e serve registrare: NON si tocca, esito "muto", UN solo Telegram per episodio (stato in stati_attuali.json: a56_muto_dal).
- Max 1 tentativo di riavvio ogni 10' per dispositivo (COOL)."""
import senza_finestre  # noqa: F401  (niente finestre dei processi figli: va importato per primo)
import array, csv, glob, json, math, os, re, shutil, subprocess, sys, tempfile, time
import a21
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

ROOT = r"C:\sonno_audio"
REC_CSV, REC_JSON = ROOT + r"\guardiano_rec.csv", ROOT + r"\guardiano_rec.json"
A56_USB = "SERIALE_TELEFONO"
RMS_MIN = 2.0
CSV, JSON, LOCK = ROOT + r"\stati_dispositivi.csv", ROOT + r"\stati_attuali.json", ROOT + r"\guardiano.lock"
PC_DIR = ROOT + r"\tre_dispositivi"
ADB_DIR = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\platform-tools")
ADB = ADB_DIR + r"\adb.exe"
A21, A56 = a21.ip(), "192.0.2.54"
A21_ADB = A21 + ":5555"
NOFINESTRA = 0x08000000  # CREATE_NO_WINDOW: da pythonw ogni processo figlio aprirebbe una console

FRESCO_S = 150            # file di registrazione non cresciuto da 150 s = fermo (i blocchi hanno ~2 s di buco)
SPAZIO_KB = 1_500_000     # A21s sotto 1,5 GB -> archivia su Drive subito
BATT_BASSA = 30           # A21s scollegato sotto 30% = avviso; sotto 20% rec.sh smette di registrare (fermo_batteria)
COOL = {"ripara": 600, "a56": 600, "pc": 600, "archivia": 2700}  # s tra due tentativi uguali
INCERTO = ("?", "sveglio?", "dorme?", "dorme")  # livelli di stato.json da "si inizia a essere incerti" in poi
BAD_A = ("mic_silenziato", "fermo", "fermo_batteria", "irraggiungibile")


# ---------------------------------------------------------------- rilevamento
def run(cmd, t=20):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=t, creationflags=NOFINESTRA, errors="replace")
        return p.stdout, p.stderr, p.returncode
    except Exception as e:  # timeout / exe mancante: mai bloccarsi
        return "", str(e), -1


def riaccendi_hotspot():
    """Riaccende hotspot Windows se spento; errori solo nel log."""
    ps = r'''
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | ? { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime] > $null
$p = [Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime]::GetInternetConnectionProfile()
if ($null -eq $p) { throw "profilo Internet assente" }
$m = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($p)
if ($m.TetheringOperationalState -eq 'On') { 'ON'; exit 0 }
$t = $asTask.MakeGenericMethod([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult]).Invoke($null, @($m.StartTetheringAsync()))
$t.Wait(25000) | Out-Null
'RIACCESO ' + $t.Result.Status
'''
    try:
        o, e, rc = run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps], 30)
        if rc != 0:
            raise RuntimeError(e.strip() or o.strip() or f"codice {rc}")
        return None if "ON" in o else "hotspot riacceso"
    except Exception as e:
        try:
            with open(os.path.join(ROOT, "guardiano_hotspot.log"), "a", encoding="utf-8") as f:
                f.write(f"{datetime.now().isoformat(timespec='seconds')} hotspot: {e}\n")
        except OSError:
            pass
        return None


def ssh(host, cmd, t=22):
    o, _, rc = run(["ssh", "-p", "8022", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6", host, cmd], t)
    return o if rc == 0 and "@t" in o else None


def adb(dev, cmd, t=20):
    return run([ADB, "-s", dev, "shell", cmd], t)


def adb_bytes(dev, cmd, t=40):
    try:
        return subprocess.run([ADB, "-s", dev, "exec-out", cmd], capture_output=True, timeout=t, creationflags=NOFINESTRA).stdout
    except Exception:
        return b""


def dev_a56():
    """USB se collegato (piu' stabile), altrimenti Wi-Fi."""
    o = run([ADB, "devices"], 10)[0]
    for d in (A56_USB, A56 + ":5555"):
        if re.search(rf"^{re.escape(d)}\s+device", o, re.M):
            return d
    m = re.search(r"(adb-\S+_adb-tls-connect\._tcp)", run([ADB, "mdns", "services"], 10)[0])
    return m.group(1) if m else None


def mic_sessione(dev):
    """'ok' = sessione MIC con silenced:false; 'silenziato' = solo sessioni silenced:true; 'assente' = nessuna; None = adb non risponde."""
    o, e, rc = adb(dev, "dumpsys audio | grep 'source client=MIC'", 15)
    if rc != 0 and not o:
        return None
    if not o.strip():
        return "assente"
    return "ok" if "silenced:false" in o else "silenziato"


def bloccato_a56(dev):
    """True = schermo col blocco (PIN) attivo: non si tocca. None = non so."""
    o, _, rc = adb(dev, "dumpsys window | grep -E 'isKeyguardShowing|mDreamingLockscreen'", 15)
    if not o.strip():
        return None
    return "isKeyguardShowing=true" in o or "mDreamingLockscreen=true" in o


def rms_file(path, coda_s=10):
    """RMS (int16) degli ultimi coda_s secondi di un file audio chiuso/decodificabile; None se ffmpeg non ci riesce."""
    try:
        p = subprocess.run(["ffmpeg", "-v", "error", "-sseof", f"-{coda_s}", "-i", path, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                           capture_output=True, timeout=60, creationflags=NOFINESTRA)
        a = array.array("h", p.stdout[: len(p.stdout) // 2 * 2])
        return math.sqrt(sum(x * x for x in a) / len(a)) if len(a) > 8000 else None
    except Exception:
        return None


def rms_a21():
    """Penultimo blocco di ~/rec (l'ultimo e' ancora aperto): scaricato via adb e decodificato qui."""
    nome = adb(A21_ADB, "run-as com.termux ls -t files/home/rec | grep -E '^[0-9]+_[0-9]+[.]m4a$' | sed -n 2p", 15)[0].strip()
    if not nome:
        # telefono, mean_volume (dBFS) -> RMS int16 come rms_file.
        # (ssh() vuole il marcatore @t del probe: qui run diretto)
        o = run(["ssh", "-p", "8022", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6", A21,
                 "cd ~/rec && f=$(ls -t | grep -E '^[0-9]+_[0-9]+[.]m4a$' | sed -n 2p) && "
                 "ffmpeg -hide_banner -nostats -sseof -10 -i $f -af volumedetect -f null - 2>&1 | grep mean_volume"], 60)[0]
        m = re.search(r"mean_volume: (-?[\d.]+) dB", o or "")
        if not m:
            return None
        db = float(m.group(1))
        # il "silenzio" AAC di un microfono silenziato e' -91 dB (RMS 0,9 > RMS_MIN): sotto -85 dB = zeri
        return 0.0 if db <= -85 else 32768 * 10 ** (db / 20)
    dati = adb_bytes(A21_ADB, "run-as com.termux cat files/home/rec/" + nome)
    if len(dati) < 2000:
        return None
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "b.m4a")
        open(f, "wb").write(dati)
        return rms_file(f)


def rms_pc(flac):
    """Il flac aperto non ha durata: si ricompone intestazione (primi 8 KB) + ultimi 600 KB e si decodifica."""
    try:
        with open(flac, "rb") as fh:
            testa = fh.read(8192)
            fh.seek(0, 2); n = fh.tell()
            fh.seek(max(8192, n - 600_000)); coda = fh.read()
        with tempfile.TemporaryDirectory() as d:
            f = os.path.join(d, "c.flac")
            open(f, "wb").write(testa + coda)
            p = subprocess.run(["ffmpeg", "-v", "error", "-i", f, "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                               capture_output=True, timeout=60, creationflags=NOFINESTRA)
        a = array.array("h", p.stdout[-16000 * 2 * 10:][: len(p.stdout[-16000 * 2 * 10:]) // 2 * 2])
        return math.sqrt(sum(x * x for x in a) / len(a)) if len(a) > 8000 else None
    except Exception:
        return None


def cresce(prec, nome, file, size, t=None):
    """True/False se la dimensione e' cambiata dal giro prima (stesso file); None se non c'e' confronto o e' troppo presto."""
    t = t or time.time()
    p = (prec.get("crescita") or {}).get(nome) or {}
    if p.get("file") != file or size is None:
        return None
    if t - p.get("t", 0) < 90:
        return None
    return size > p.get("size", 0)


def _campi(o):
    d = {}
    for m in re.finditer(r"@(\w+) ?([^\n]*)", o):
        d[m.group(1)] = m.group(2).strip()
    return d


PROBE = ('echo @t $(date +%s); f=$(ls -t {dir}/*.m4a 2>/dev/null|head -1); echo @m $([ -n "$f" ] && stat -c %Y "$f"); '
         "echo @df $(df -k ~|tail -1|awk '{{print $4}}'); echo @bat $(termux-battery-status|tr -d '\\n '); "
         "echo @loop $(pgrep -f '^bash .*rec.sh'|head -1); echo @st; {extra}true")


def _batt(d):
    pct = re.search(r'"percentage":(\d+)', d.get("bat", ""))
    return (int(pct.group(1)) if pct else None), ("UNPLUGGED" in d.get("bat", ""))


def silenziato_a21():
    """True = microfono silenziato da Android (file di zeri), False = ok, None = non verificabile."""
    cmd = [ADB, "-s", A21_ADB, "shell", "dumpsys audio | grep 'source client=MIC'"]
    o, e, _ = run(cmd, 15)
    if re.search(r"offline|not found|no devices|closed|cannot connect", e + o):
        run([ADB, "kill-server"], 8); run([ADB, "start-server"], 8); run([ADB, "connect", A21_ADB], 10)
        o, e, _ = run(cmd, 15)
    return None if not o.strip() else "silenced:true" in o


def probe_a21_adb(script):
    """
    l'ssh dell'A21s va in timeout ma adb risponde -> non e' 'irraggiungibile'. None se anche adb non risponde."""
    pre = "export HOME=/data/data/com.termux/files/home PATH=/data/data/com.termux/files/usr/bin:$PATH; cd $HOME; "
    try:
        r = subprocess.run([ADB, "-s", A21_ADB, "shell", "run-as com.termux /data/data/com.termux/files/usr/bin/bash"],
                           input=(pre + script + "\n").encode(), capture_output=True, timeout=30, creationflags=NOFINESTRA)
    except (OSError, subprocess.TimeoutExpired):
        return None
    o = r.stdout.decode("utf-8", "replace")
    return o if "@t" in o else None


def rileva_a21(prec):
    probe = PROBE.format(dir="~/rec", extra="head -c 400 ~/stato.json 2>/dev/null; ")
    o = ssh(A21, probe) or probe_a21_adb(probe)
    if o is None:
        return {"stato": "irraggiungibile"}, {}
    d = _campi(o)
    kb = int(d["df"]) if d.get("df", "").isdigit() else None
    pct, scoll = _batt(d)
    eta = int(d["t"]) - int(d["m"]) if d.get("m", "").isdigit() else 10 ** 6
    registra = eta < FRESCO_S  # blocchi da pochi secondi: file fresco = sta crescendo
    s = {"eta_file_s": eta, "libero_mb": kb // 1024 if kb else None, "batt": pct, "scollegato": scoll,
         "loop": bool(d.get("loop"))}
    s["spazio_basso"] = bool(kb and kb < SPAZIO_KB)
    if not registra:
        s["stato"] = "fermo_batteria" if scoll and pct is not None and pct <= 20 else "fermo"
    else:
        mic = silenziato_a21()  # True silenziato, False ok, None non verificabile
        rms = rms_a21() if mic is not True else None
        s.update(mic="silenziato" if mic else "ok" if mic is False else "?", rms=None if rms is None else round(rms, 1))
        if mic is True or (rms is not None and rms < RMS_MIN):
            s["stato"] = "mic_silenziato"
        elif scoll and pct is not None and pct <= BATT_BASSA:
            s["stato"] = "batteria_bassa"
        else:
            s["stato"] = "ok"
    st = o.split("@st", 1)[-1]
    m = re.search(r'"utente": "([^"]*)", "fiducia": ([0-9.]+)(?:, "livello": "([^"]*)")?', st)
    persona = {"stato": m.group(1), "fiducia": float(m.group(2)), "livello": m.group(3) or m.group(1)} if m else {}
    return s, persona


def rileva_a56(prec):
    dev = dev_a56()
    if not dev:
        return {"stato": "irraggiungibile"}
    o = adb(dev, "run-as com.termux sh -c 'f=$(ls -t files/home/rec_a56/*.m4a 2>/dev/null|head -1); echo @f $f; "
                 "echo @sz $(stat -c %s $f); echo @m $(stat -c %Y $f); echo @t $(date +%s); echo @df $(df -k files/home|tail -1)'", 20)[0]
    d = _campi(o)
    if d.get("df"):
        d["df"] = (d["df"].split() + ["", "", "", ""])[3]
    if "t" not in d:  # adb muto: ripiego su ssh come prima
        o = ssh(A56, PROBE.format(dir="~/rec_a56", extra=""))
        if o is None:
            return {"stato": "irraggiungibile", "dev": dev}
        d = _campi(o); d["f"] = d.get("f", "?")
    kb = int(d["df"]) if d.get("df", "").isdigit() else None
    pct, scoll = _batt(d)
    if not d.get("bat"):  # batteria dal dumpsys battery se non c'e' ssh
        b = adb(dev, "dumpsys battery | grep -E 'level|powered'", 10)[0]
        mm = re.search(r"level: (\d+)", b)
        pct = int(mm.group(1)) if mm else None
        scoll = bool(b) and "AC powered: false" in b and "USB powered: false" in b and "Wireless powered: false" in b
    eta = int(d["t"]) - int(d["m"]) if d.get("m", "").isdigit() else 10 ** 6
    size = int(d["sz"]) if d.get("sz", "").isdigit() else None
    mic, blocco = mic_sessione(dev), bloccato_a56(dev)
    cr = cresce(prec, "a56", d.get("f"), size)
    s = {"dev": dev, "eta_file_s": eta, "libero_mb": kb // 1024 if kb else None, "batt": pct, "scollegato": scoll,
         "spazio_basso": bool(kb and kb < 2_000_000), "mic": mic, "cresce": cr, "bloccato": blocco,
         "_file": d.get("f"), "_size": size, "rms": "non verificabile (mp4 aperto)"}
    vivo = eta < FRESCO_S and cr is not False and mic in ("ok", None)
    s["stato"] = ("muto" if eta < FRESCO_S and mic == "silenziato" else
                  "ok" if vivo else
                  "batteria_bassa" if scoll and pct is not None and pct <= 15 else "fermo")
    return s


def rileva_pc(prec):
    ultimi = glob.glob(PC_DIR + r"\*\pc_*.flac")
    ult = max(ultimi, key=os.path.getmtime, default=None)
    eta = time.time() - (os.path.getmtime(ult) if ult else 0)
    libero_mb = __import__("shutil").disk_usage("C:\\").free // 2 ** 20
    s = {"eta_file_s": int(eta), "libero_mb": libero_mb, "spazio_basso": libero_mb < 5000, "_file": ult,
         "_size": os.path.getsize(ult) if ult else None}
    if eta >= FRESCO_S:
        s["stato"] = "fermo"
        return s
    ff = run(["powershell.exe", "-NoProfile", "-Command",
              "@(Get-CimInstance Win32_Process -Filter \"Name='ffmpeg.exe'\" | ? { $_.CommandLine -match 'dshow' }).Count"], 20)[0].strip()
    rms = rms_pc(ult)
    s.update(ffmpeg=bool(ff) and ff != "0", rms=None if rms is None else round(rms, 1))
    s["stato"] = "muto" if rms is not None and rms < RMS_MIN else "ok" if s["ffmpeg"] else "fermo"
    return s


def rileva(prec):
    """Tutti i dispositivi in parallelo (timeout brevi). Ritorna (stati, persona)."""
    with ThreadPoolExecutor(3) as ex:
        fa, f5, fp = ex.submit(rileva_a21, prec), ex.submit(rileva_a56, prec), ex.submit(rileva_pc, prec)
        a21, persona = fa.result()
        a56, pc = f5.result(), fp.result()
    # anti-lampo: un solo fallimento ssh dell'A21s (wifi che sfarfalla) non conta; al 2o giro di fila si'
    if a21["stato"] == "irraggiungibile":
        n = prec.get("fallimenti_a21", 0) + 1
        a21["fallimenti"] = n
        if n < 2 and prec.get("stati", {}).get("a21"):
            a21 = dict(prec["stati"]["a21"], fallimenti=n)
    if persona:
        persona["t"] = time.time()
    elif prec.get("persona") and time.time() - prec["persona"].get("t", 0) < 1200:
        persona = prec["persona"]  # A21s muto: vale l'ultimo stato persona se recente (<20')
    return {"a21": a21, "a56": a56, "pc": pc}, persona


# ---------------------------------------------------------------- decisione (pura, testata)
def serve_riserva(persona, ora):
    """
    Nel dubbio: si' di notte (21-11); di giorno in dubbio no (non svegliare/infastidire per niente)."""
    st, fid = persona.get("stato", "?"), persona.get("fiducia", 0)
    if persona.get("livello") in INCERTO:
        return True  # incerto o verso il sonno: sempre, a qualunque ora
    if st in ("sveglio", "fuori") and fid >= 0.7:
        return False
    if st == "dorme":
        return True
    return ora >= 21 or ora < 11


def decidi(stati, ctx):
    """stati: {'a21','a56','pc'} -> {'stato', 'spazio_basso'}; ctx: serve (bool), ripara_fatta, a56_tentato, pc_tentato.
    Ritorna (scenario, azioni, avviso|None). Azioni: ripara_a21, avvia_a56, avvia_pc, archivia."""
    a, a56, pc = stati["a21"]["stato"], stati["a56"]["stato"], stati["pc"]["stato"]
    batt = stati["a21"].get("batt")
    a56_da = a56 in ("fermo", "muto")  # non registra (o registra zeri)
    if a not in BAD_A:
        if a == "batteria_bassa":
            return ("a21_batteria", ["avvia_a56"] if ctx["serve"] and a56_da else [],
                    f"A21s al {batt}% e scollegato: collegalo, sotto il 20% smette di registrare")
        # 'a21_spazio', A56 mai avviato, nessuna registrazione di riserva). Ora archivia E valuta l'A56.
        spazio = ["archivia"] if stati["a21"].get("spazio_basso") else []
        if a56_da and not ctx.get("a56_tentato") and (ctx.get("incerto") or ctx.get("a56_sera")):
            return "a56_in_piu", spazio + ["avvia_a56"], None
        if spazio:
            return "a21_spazio", spazio, "A21s con poco spazio: archivio su Drive subito"
        return "tutto_ok", [], None
    if a in ("fermo", "mic_silenziato") and not ctx["ripara_fatta"]:
        return f"a21_{a}_ripara", ["ripara_a21"], None
    nome = {"mic_silenziato": "microfono silenziato", "fermo": "fermo", "irraggiungibile": "irraggiungibile",
            "fermo_batteria": "fermo per batteria scarica"}[a]
    if not ctx["serve"]:
        return "a21_giu_sveglio", [], None
    azioni = []
    if a56_da and not ctx["a56_tentato"]:
        azioni.append("avvia_a56")
    if pc != "ok" and not ctx["pc_tentato"]:
        azioni.append("avvia_pc")
    if azioni:
        return "a21_giu_avvio_riserve", azioni, None
    ok = [n for n, s in (("A56", a56), ("PC", pc)) if s == "ok"]
    if ok:
        return "a21_giu_riserva", [], f"A21s {nome}: registra {' + '.join(ok)}"
    return "tutti_giu", [], "TUTTI GIU: A21s, A56 e PC non registrano. Controlla subito"


# ---------------------------------------------------------------- azioni
def ripara_a21():
    os.environ["PATH"] = ADB_DIR + os.pathsep + os.environ["PATH"]
    sys.path.insert(0, r"C:\sonno_tex")
    import sonno_audio, cal_sessione
    dev = sonno_audio.device()
    if not dev:
        return "adb non raggiunge A21s"
    cal_sessione.riavvia_loop(dev)
    return "loop riavviato in primo piano"


def avvia_a56():
    """Registrazione unica in primo piano. Schermo col PIN (o stato non noto): NON si tocca, ritorna 'BLOCCATO...'."""
    dev = dev_a56()
    if not dev:
        return "A56 non raggiungibile via adb"
    if bloccato_a56(dev) is not False:
        return "BLOCCATO: schermo col PIN, non si tocca"
    try:  # lo script e' nella home Termux; lo si ricopia sempre (idempotente)
        subprocess.run([ADB, "-s", dev, "shell", "run-as com.termux sh -c 'cat > files/home/rec_a56_unico.sh'"],
                       input=open(r"C:\sonno_tex\rec_a56_unico.sh", "rb").read().replace(b"\r\n", b"\n"), timeout=20,
                       creationflags=NOFINESTRA)
    except Exception as e:
        return f"script non copiato: {e}"
    for _ in range(2):
        adb(dev, "input keyevent KEYCODE_WAKEUP", 10)
        if bloccato_a56(dev) is not False:  # il risveglio ha mostrato il PIN: ci si ferma, niente aggiramenti
            return "BLOCCATO: schermo col PIN, non si tocca"
        adb(dev, "am start -n com.termux/.app.TermuxActivity", 10)
        time.sleep(2)
        adb(dev, "input text 'bash%s~/rec_a56_unico.sh'", 10)
        adb(dev, "input keyevent KEYCODE_ENTER", 10)
        time.sleep(6)
        if mic_sessione(dev) == "ok":
            adb(dev, "input keyevent KEYCODE_HOME", 10)
            return "registrazione unica avviata in primo piano"
        adb(dev, "run-as com.termux sh -c 'termux-microphone-record -q'", 10)
    return "avvio fallito (microfono silenziato o Termux non in primo piano)"


def avvia_pc():
    fine = datetime.fromtimestamp(time.time() + 6 * 3600).isoformat(timespec="seconds")
    subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                      r"C:\sonno_bot\tecnica\app_sonno\registra_pc_notte.ps1", "-Fine", fine],
                     creationflags=NOFINESTRA | 0x8)
    return f"registrazione PC avviata fino {fine[11:16]}"


def archivia():
    subprocess.Popen([sys.executable.replace("python.exe", "pythonw.exe"), r"C:\sonno_tex\archivia_interi.py",
                      "--tieni-ore", "1"], creationflags=NOFINESTRA | 0x8)
    return "archiviazione su Drive avviata"


AZIONI = {"ripara_a21": (ripara_a21, "ripara"), "avvia_a56": (avvia_a56, "a56"),
          "avvia_pc": (avvia_pc, "pc"), "archivia": (archivia, "archivia")}


AVVISI = r"C:\sonno_audio\avvisi.log"
URGENTE = ("silenziat", "muto", "tutti giù", "tutti giu", "non registra", "fermo")


def puo_avvisare(testo, righe, adesso):
    """
    6 h; no se un messaggio qualsiasi e' partito negli ultimi 30', salvo gli urgenti (registrazione ferma/muta)."""
    if any(x == testo and adesso - t < 6 * 3600 for t, x in righe):
        return False
    return any(u in testo.lower() for u in URGENTE) or not any(adesso - t < 1800 for t, _ in righe)


def avvisa(testo):
    adesso = time.time()
    try:
        righe = [(float(r.split("\t", 2)[0]), r.split("\t", 2)[2].rstrip("\n")) for r in open(AVVISI, encoding="utf-8") if r.count("\t") >= 2]
    except OSError:
        righe = []
    # avvisi delle ultime 24 h (ricordati per id) e non si manda niente di nuovo (prima del limite: non e' un messaggio).
    ids = _leggi_ids()
    if livello(testo) == "ok":
        vecchi = [x for x in ids if adesso - x["t"] < 86400]
        tolti = [x for x in vecchi if "OK" in run([sys.executable, r"C:\sonno_tex\tg_IlTuoBot.py", "--cancella", str(x["id"])], 60)[0]]
        _scrivi_ids([x for x in ids if x not in tolti and adesso - x["t"] < 86400])
        if tolti:
            with open(AVVISI, "a", encoding="utf-8") as f:
                f.write(f"{adesso:.0f}\t{datetime.now():%Y-%m-%d %H:%M}\t(cancellati {len(tolti)} avvisi) {testo.replace(chr(10), ' ')}\n")
            return
    if not puo_avvisare(testo, righe[-200:], adesso):
        return
    with open(AVVISI, "a", encoding="utf-8") as f:
        f.write(f"{adesso:.0f}\t{datetime.now():%Y-%m-%d %H:%M}\t{testo.replace(chr(10), ' ')}\n")
    for script in (r"C:\sonno_tex\tg_IlTuoBot.py",  # se l'A21s e' giu' non trova il token: ripiego sul bot del PC
                   os.path.expanduser(r"~\Downloads\tirocinio\SLIDE_INPUT_OUTPUT_BASE\strumenti\telegram_manda_messaggio_di_testo.py")):
        o, _, _ = run([sys.executable, script, formatta(testo)] + (["--muto"] if livello(testo) in ("ok", "info") else []), 60)
        if "OK" in o:
            m = re.search(r"OK id=(\d+)", o)
            if m and livello(testo) != "ok" and script.endswith("tg_IlTuoBot.py"):
                _scrivi_ids([x for x in ids if adesso - x["t"] < 86400] + [{"t": adesso, "id": int(m.group(1))}])
            return


def decidi_riserva(giu, giu_dal, adesso):
    """(nuovo giu_dal, riserva accesa?): accesa dopo 10' di A21s irraggiungibile, spenta appena torna."""
    giu_dal = (giu_dal or adesso) if giu else None
    return giu_dal, bool(giu and adesso - giu_dal >= 600)


def riserva_a56(giu, prec, adesso):
    """(nota rimossa)"""
    giu_dal, on = decidi_riserva(giu, prec.get("a21_giu_dal"), adesso)
    if on != bool(prec.get("riserva_on")):
        cmd = ("touch ~/riserva_on; pgrep -f '[b]ot_riserva.py' >/dev/null || (cd ~ && nohup setsid python ~/bot_riserva.py >/dev/null 2>&1 < /dev/null &)"
               if on else "rm -f ~/riserva_on")
        run(["ssh", "-p", "8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=6", A56, cmd], 20)
    return giu_dal, on


AVVISI_ID = r"C:\sonno_audio\avvisi_id.json"


def _leggi_ids():
    try:
        return json.load(open(AVVISI_ID, encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _scrivi_ids(v):
    try:
        json.dump(v, open(AVVISI_ID, "w", encoding="utf-8"))
    except OSError:
        pass


def livello(testo):
    """(nota rimossa)"""
    t = testo.lower()
    if any(u in t for u in URGENTE):
        return "urgente"
    if any(k in t for k in ("a posto", "rientrat", "di nuovo", "tornato", "riparte", "ripartit")):
        return "ok"
    if any(k in t for k in ("batteria", "carica", "spazio", "pieno", "bloccato", "irraggiungibile", "non risponde", "%")):
        return "attenzione"
    return "info"


def formatta(testo):
    """Pallino colorato + titolo in grassetto per livello; ok/info arrivano senza suono (--muto in avvisa)."""
    import html
    ico, tit = {"urgente": ("\U0001F534", "URGENTE"), "attenzione": ("\U0001F7E0", "Attenzione"),
                "ok": ("\U0001F7E2", "Risolto"), "info": ("\U0001F535", "Info")}[livello(testo)]
    return f"{ico} <b>{tit}</b> \u00b7 \U0001F6E1\uFE0F guardiano\n{html.escape(testo)}"


# ---------------------------------------------------------------- giro
def contesto(stati, persona, prec, ora):
    t = time.time()
    fatto = lambda k: t - prec.get("ultimo", {}).get(k, 0) < COOL[k]
    a56 = stati["a56"]
    return {"serve": serve_riserva(persona, ora), "ripara_fatta": fatto("ripara"),
            "a56_tentato": fatto("a56"), "pc_tentato": fatto("pc"),
            "incerto": persona.get("livello") in INCERTO,
            # sera: A56 in carica e SBLOCCATO (lo sta usando): si parte ora in primo piano, resta attivo dopo il blocco
            "a56_sera": ora >= 21 and a56.get("bloccato") is False and (a56.get("scollegato") is False or (a56.get("batt") or 0) >= 30)}


def esiti(stati, ctx, eseguite):
    """{'a21s','a56','pc'} -> (esito, dettaglio). Esiti: ok / muto / fermo / riavviato."""
    r = {}
    a, a56, pc = stati["a21"], stati["a56"], stati["pc"]
    r["a21s"] = ("ok" if a["stato"] in ("ok", "batteria_bassa") else "muto" if a["stato"] == "mic_silenziato" else "fermo",
                 f"{a['stato']} mic={a.get('mic')} rms={a.get('rms')} eta={a.get('eta_file_s')}s")
    serve = ctx["serve"] or ctx.get("incerto")
    e56 = "ok" if a56["stato"] == "ok" else "muto" if a56["stato"] == "muto" or (a56.get("bloccato") and serve) else "fermo"
    r["a56"] = (e56, f"{a56['stato']} mic={a56.get('mic')} cresce={a56.get('cresce')} bloccato={a56.get('bloccato')} "
                     f"batt={a56.get('batt')} eta={a56.get('eta_file_s')}s")
    r["pc"] = ("ok" if pc["stato"] == "ok" else "muto" if pc["stato"] == "muto" else "fermo",
               f"{pc['stato']} ffmpeg={pc.get('ffmpeg')} rms={pc.get('rms')} eta={pc.get('eta_file_s')}s")
    for k, az in (("a21s", "ripara_a21"), ("a56", "avvia_a56"), ("pc", "avvia_pc")):
        m = next((x for x in eseguite if x.startswith(az + ":")), None)
        if m and not any(w in m for w in ("ERRORE", "BLOCCATO", "fallito", "non ")):
            r[k] = ("riavviato", r[k][1] + " | " + m)
    return r


def registra_esiti(prec, rec, ora_iso, serve=True):
    """Aggiorna rec (con 'dal'), avvisa UNA volta per episodio di A56 muto, scrive csv/json e copia sull'A21s.
    """
    vecchio = prec.get("rec") or {}
    out = {}
    for k, (e, det) in rec.items():
        stesso = (vecchio.get(k) or {}).get("esito") == e
        dal = vecchio[k]["dal"] if stesso else ora_iso
        nome = {"a21s": "A21s", "a56": "A56", "pc": "PC"}[k]
        testo = f"{nome}: registra" if e in ("ok", "riavviato") else f"{nome}: {e.upper()} dalle {dal[11:16]}"
        out[k] = {"esito": e, "dal": dal, "testo": testo, "dettaglio": det}
    avvisato = prec.get("a56_muto_avvisato")
    if rec["a56"][0] == "muto":
        if not avvisato and serve:  # UN messaggio per episodio, mai ripetuto finche' l'A56 non torna ok
            avvisa(f"A56 MUTO dalle {out['a56']['dal'][11:16]}: schermo col PIN o microfono silenziato, non registra.\n"
                   "Sbloccalo un attimo (riparto da solo) o usa l'A21s.")
            avvisato = ora_iso
    elif rec["a56"][0] == "ok":
        avvisato = None
    nuovo = not os.path.exists(REC_CSV)
    with open(REC_CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuovo:
            w.writerow(["ora", "dispositivo", "esito", "dettaglio"])
        for k, v in out.items():
            w.writerow([ora_iso, k, v["esito"], v["dettaglio"]])
    doc = {"t": ora_iso, **out}
    json.dump(doc, open(REC_JSON, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    try:  # per stato.py sull'A21s -> stato.json["rec"] -> card /stato del bot
        subprocess.run([ADB, "-s", A21_ADB, "shell", "run-as com.termux sh -c 'cat > files/home/guardiano_rec.json'"],
                       input=json.dumps(doc, ensure_ascii=False).encode(), timeout=15, creationflags=NOFINESTRA)
    except Exception:
        pass
    return out, avvisato


def previsione_batteria(storia, ora_ts):
    """storia: [[ts, pct, in_carica], ...] dello stesso telefono. -> (stato, minuti_al_vuoto|None)
    stato: 'in_carica' | 'rischio_scarica' (a questo ritmo si spegne prima delle 9) | 'batteria_bassa' (<=20%) | 'ok'.
    """
    if not storia or storia[-1][1] is None:
        return "?", None
    ts, pct, carica = storia[-1]
    if carica:
        return "in_carica", None
    ora_fa = [x for x in storia if not x[2] and x[1] is not None and ts - x[0] <= 3600]
    vuoto = None
    if len(ora_fa) >= 2 and ora_fa[0][1] > pct and ts - ora_fa[0][0] >= 900:
        vuoto = int(pct / ((ora_fa[0][1] - pct) / ((ts - ora_fa[0][0]) / 60)))
    alle9 = (datetime.fromtimestamp(ora_ts).replace(hour=9, minute=0) - datetime.fromtimestamp(ora_ts)).total_seconds() / 60 % 1440
    if vuoto is not None and vuoto < alle9:
        return "rischio_scarica", vuoto
    return ("batteria_bassa" if pct <= 20 else "ok"), vuoto


IRR_MIN = 10


def avviso_irraggiungibile(irr_da, adesso, gia_avvisato):
    """
    mattino e' rimasta ferma e stanotte non avrebbe registrato. Un solo avviso per episodio, dopo IRR_MIN minuti."""
    if irr_da is None or gia_avvisato or adesso - irr_da < IRR_MIN * 60:
        return None
    return (f"A21s non risponde dalle {datetime.fromtimestamp(irr_da):%H:%M} (ssh e adb). Sbloccalo e apri Termux: "
            "senza di lui stanotte non registra e l'analisi resta ferma.")


def prontezza_sera(stati, batteria, ora):
    """Controllo PRIMA di dormire (21-23): cosa non e' pronto per la notte e cosa fare. [] = tutto pronto.
    """
    if not 21 <= ora < 23:
        return []
    a, a56 = stati["a21"], stati["a56"]
    p = []
    if a["stato"] in BAD_A:
        p.append(f"A21s {a['stato'].replace('_', ' ')}: sbloccalo e apri Termux")
    elif a.get("scollegato") and (a.get("batt") or 0) < 70:
        p.append(f"A21s al {a.get('batt')}% e scollegato: mettilo in carica")
    if a.get("spazio_basso"):
        p.append("A21s quasi pieno: archivio su Drive in corso")
    if a56.get("stato") == "irraggiungibile":
        p.append("A56 non raggiungibile: se lo usi per dormire, accendi il wifi")
    elif a56.get("stato") != "ok":
        if a56.get("scollegato") is not False:
            p.append(f"A56 al {a56.get('batt')}% non in carica: collegalo (controlla che carichi)")
        if a56.get("bloccato") is not False:
            p.append("A56 bloccato: lascialo sbloccato finche' non ti confermo che registra")
    if batteria.get("a56", {}).get("stato") == "rischio_scarica":
        p.append("A56 si scarica prima del mattino")
    return p


def giro(prova=False):
    prec = {}
    try:
        prec = json.load(open(JSON, encoding="utf-8"))
    except Exception:
        pass
    ora = datetime.now().hour
    stati, persona = rileva(prec)
    ctx = contesto(stati, persona, prec, ora)
    scenario, azioni, avviso = decidi(stati, ctx)
    eseguite = []
    if not prova:
        hotspot = riaccendi_hotspot()
        if hotspot:
            eseguite.append(hotspot)
        # -> lo si ricollega a HOTSPOT via adb. Password in un file locale, fuori da git.
        pw_f = os.path.join(ROOT, "hotspot_sonnopc.txt")
        if a21.ip() == "192.0.2.184" and os.path.exists(pw_f):
            pw = open(pw_f, encoding="utf-8").read().strip()
            o = run([ADB, "-s", "192.0.2.184:5555", "shell", f"cmd wifi connect-network HOTSPOT wpa2 {pw}"], 20)[0]
            if o is not None:
                eseguite.append("A21s ricollegato all'hotspot del PC")
    ultimo = dict(prec.get("ultimo", {}))
    for _ in range(3 if not prova else 1):  # azione -> ri-rileva -> eventuale escalation (max 3 passi)
        if prova or not azioni:
            break
        for az in azioni:
            f, chiave = AZIONI[az]
            if time.time() - ultimo.get(chiave, 0) < COOL[chiave]:
                continue
            ultimo[chiave] = time.time()
            try:
                eseguite.append(f"{az}: {f()}")
            except Exception as e:
                eseguite.append(f"{az}: ERRORE {e}")
        time.sleep(8)
        prec2 = dict(prec, ultimo=ultimo, persona=persona, fallimenti_a21=1)  # 1: al 2o fallimento vale subito
        stati, p2 = rileva(prec2)
        persona = p2 or persona
        ctx = contesto(stati, persona, prec2, ora)
        scenario, azioni, avviso = decidi(stati, ctx)
        azioni = [a for a in azioni if a != "archivia"]
    rec = esiti(stati, ctx, eseguite)
    adesso = time.time()
    crescita = {k: {"file": stati[k].get("_file"), "size": stati[k].get("_size"), "t": adesso} for k in ("a56", "pc")}
    out = {"t": datetime.now().isoformat(timespec="seconds"), "stati": stati, "persona": persona, "scenario": scenario,
           "serve_riserva": ctx["serve"], "azioni": eseguite, "ultimo": ultimo, "crescita": crescita,
           "fallimenti_a21": stati["a21"].get("fallimenti", 0) if stati["a21"]["stato"] == "irraggiungibile" else 0,
           "avvisato": prec.get("avvisato", "tutto_ok")}
    batt = {}
    for k in ("a21", "a56"):  # storico 2h per la previsione; stato batteria visibile in guardiano.json
        st_k = (prec.get("batt_storia", {}).get(k, []) + [[adesso, stati[k].get("batt"), stati[k].get("scollegato") is False]])
        out.setdefault("batt_storia", {})[k] = [x for x in st_k if adesso - x[0] <= 7200]
        batt[k] = previsione_batteria(out["batt_storia"][k], adesso)
    out["batteria"] = {k: {"stato": s, "minuti_al_vuoto": m} for k, (s, m) in batt.items()}
    s56, m56 = batt["a56"]
    if s56 == "rischio_scarica" and (ctx["serve"] or ctx.get("a56_sera")) and prec.get("scarica_avvisata") != datetime.now().strftime("%Y%m%d"):
        if not prova:
            avvisa(f"A56 al {stati['a56'].get('batt')}%: a questo ritmo si spegne verso "
                   f"{(datetime.now() + timedelta(minutes=m56)):%H:%M}. Mettilo in carica (in camera).")
        out["scarica_avvisata"] = datetime.now().strftime("%Y%m%d")
    else:
        out["scarica_avvisata"] = prec.get("scarica_avvisata")
    # sbloccarlo (max 1 volta ogni 30'): sbloccato, il giro dopo lo avvia in primo piano.
    out["chiesto_sblocco"] = prec.get("chiesto_sblocco", 0)
    if any("BLOCCATO" in e for e in eseguite) and adesso - out["chiesto_sblocco"] > 1800 and not prova:
        avvisa("Sei a letto? Sblocca l'A56 per 10 secondi (lascialo in camera): la registrazione di riserva parte subito.")
        out["chiesto_sblocco"] = adesso
    # Samsung lo riaccende da sola -> a ogni giro, se e' acceso, lo si spegne (adb ha il permesso, Termux no).
    if not prova and stati["a21"]["stato"] != "irraggiungibile":
        lp = run([ADB, "-s", A21_ADB, "shell", "settings get global low_power"], 10)[0]
        if lp and lp.strip() == "1":
            run([ADB, "-s", A21_ADB, "shell", "settings put global low_power 0"], 10)
            eseguite.append("risparmio energetico A21s spento (staccava il Wi-Fi)")
    ULT = ROOT + r"\ultima_notte.csv"
    if stati["a21"]["stato"] != "irraggiungibile" and (not os.path.exists(ULT) or adesso - os.path.getmtime(ULT) > 1800) and not prova:
        riga = ssh(A21, "tail -1 ~/sonno_bot/notti.csv", 15)
        if riga and riga.count(",") >= 5:
            open(ULT, "w", encoding="utf-8").write(riga.strip())
    # A21s irraggiungibile a lungo: avviso anche da sveglio (una volta per episodio)
    irr = stati["a21"]["stato"] == "irraggiungibile"
    out["irr_da"] = (prec.get("irr_da") or adesso) if irr else None
    out["irr_avvisato"] = bool(irr and prec.get("irr_avvisato"))
    t_irr = avviso_irraggiungibile(out["irr_da"], adesso, out["irr_avvisato"])
    if t_irr and os.path.exists(ULT):  # day,inizio,fine,durata,...: la notte la dice il PC se il bot non puo'
        c = open(ULT, encoding="utf-8").read().split(",")
        t_irr += f"\nUltima notte: {c[1][11:16]}-{c[2][11:16]}, {float(c[3]):.1f} h."
    # prontezza della sera: un messaggio al giorno con la lista di cosa sistemare (niente se e' tutto pronto)
    oggi = datetime.now().strftime("%Y%m%d")
    pronti = prontezza_sera(stati, out["batteria"], ora) if prec.get("sera_avvisata") != oggi else []
    out["sera_avvisata"] = oggi if pronti else prec.get("sera_avvisata")
    libero_gb = shutil.disk_usage("C:\\").free / 2**30
    out["pc_libero_gb"] = round(libero_gb, 1)
    if not prova:
        out["a21_giu_dal"], out["riserva_on"] = riserva_a56(stati["a21"]["stato"] == "irraggiungibile", prec, time.time())
    # Stato minimo per grafo Mini App, solo da giro reale e A21s raggiungibile.
    if not prova and stati["a21"]["stato"] != "irraggiungibile":
        live = {"reg_a56": "ok" if stati["a56"].get("stato") == "ok" else "giu",
                "carica_a56": "ok" if stati["a56"].get("scollegato") is not True or stati["a56"].get("batt", 0) >= 30 else "giu",
                "sblocco_a56": "ok" if stati["a56"].get("bloccato") is False else "giu",
                "pc": "ok", "reg_pc": "ok" if stati["pc"].get("stato") == "ok" else "giu",
                "disco_pc": "ok" if libero_gb >= 3 else "giu",
                "mic_a21": "giu" if stati["a21"].get("stato") == "mic_silenziato" else
                           "ok" if stati["a21"].get("mic") == "ok" or (stati["a21"].get("rms") or 0) >= RMS_MIN else "?",
                "risparmio": "giu" if any("risparmio energetico A21s spento" in x for x in eseguite) else "ok",
                "raggiungibile": "ok", "guardiano": "ok", "_t": datetime.now().astimezone().isoformat(timespec="seconds")}
        payload = json.dumps(live, ensure_ascii=False).replace("'", "'\\''")
        ssh(A21, "printf '%s' '" + payload + "' > ~/guardiano_stato.json; echo @t", 15)
    # copie Kaggle gia' su Drive + flac PC >12 h gia' su Drive. Avviso solo se resta sotto 1,5 GB.
    out["disco_pulito"] = prec.get("disco_pulito", 0)
    if libero_gb < 3 and adesso - out["disco_pulito"] > 3600 and not prova:
        pw = sys.executable.replace("python.exe", "pythonw.exe")
        subprocess.Popen([pw, r"C:\sonno_tex\pulisci_kaggle.py"], creationflags=NOFINESTRA | 0x8)
        subprocess.Popen([pw, r"C:\sonno_tex\archivia_interi.py", "--pc-ore", "12"], creationflags=NOFINESTRA | 0x8)
        out["disco_pulito"] = adesso
    disco = libero_gb < 1.5 and prec.get("disco_avvisato") != oggi
    out["disco_avvisato"] = oggi if disco else prec.get("disco_avvisato")
    if disco and not prova:
        avvisa(f"PC: solo {libero_gb:.1f} GB liberi su C anche dopo la pulizia automatica.")
    if prova:
        print("irraggiungibile:", t_irr, "| sera:", pronti or prontezza_sera(stati, out["batteria"], 21), "| disco C GB:", round(libero_gb, 1))
    else:
        if t_irr:
            avvisa(t_irr); out["irr_avvisato"] = True
        if pronti:
            avvisa("Prima di dormire:\n- " + "\n- ".join(pronti))
    if prova:
        print("batteria:", out["batteria"])
        print(json.dumps({"stati": stati, "persona": persona, "serve_riserva": ctx["serve"], "incerto": ctx["incerto"],
                          "a56_sera": ctx["a56_sera"], "scenario": scenario, "FAREBBE": azioni, "avviso": avviso,
                          "esiti": {k: list(v) for k, v in rec.items()}}, indent=1, ensure_ascii=False, default=str))
        return
    out["rec"], out["a56_muto_avvisato"] = registra_esiti(prec, rec, out["t"], ctx["serve"])
    if avviso and scenario != out["avvisato"]:
        avvisa(avviso); out["avvisato"] = scenario
    elif scenario == "tutto_ok" and out["avvisato"] != "tutto_ok":
        avvisa("Di nuovo tutto a posto: l'A21s registra."); out["avvisato"] = "tutto_ok"
    nuovo = not os.path.exists(CSV)
    with open(CSV, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuovo:
            w.writerow(["t", "a21s", "a21s_libero_mb", "a21s_batt", "a56", "pc", "persona", "serve_riserva", "scenario", "azioni"])
        s = stati
        w.writerow([out["t"], s["a21"]["stato"], s["a21"].get("libero_mb"), s["a21"].get("batt"), s["a56"]["stato"],
                    s["pc"]["stato"], persona.get("stato", "?"), int(ctx["serve"]), scenario, " | ".join(eseguite)])
    json.dump(out, open(JSON + ".tmp", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    os.replace(JSON + ".tmp", JSON)


def main():
    prova = "--prova" in sys.argv
    if not prova:  # un solo giro alla volta (stale dopo 3')
        try:
            if time.time() - os.path.getmtime(LOCK) < 180:
                return
        except OSError:
            pass
        open(LOCK, "w").write(str(os.getpid()))
    try:
        giro(prova)
    finally:
        if not prova:
            try: os.remove(LOCK)
            except OSError: pass


if __name__ == "__main__":
    main()
