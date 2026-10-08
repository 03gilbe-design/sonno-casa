"""Mini App Telegram per etichettare l'audio del sonno al secondo (gira sull'A21s in Termux, accanto al bot).

Serve pagina (miniapp.html), audio dei blocchi/clip, spettrogramma, etichette esistenti e modelli; riceve i salvataggi in
etichette_intervalli.csv (giudizi.csv NON si tocca mai). Solo stdlib + numpy (gia' sul telefono) + ffmpeg.

SICUREZZA: ogni endpoint tranne la pagina statica (nessun dato) vuole l'initData di Telegram.WebApp nell'header X-Init-Data,
validata con HMAC-SHA256 (doc ufficiale), auth_date < 24 h e user.id == TELEGRAM_CHAT. L'audio (tag <audio>, niente header)
usa un URL firmato /a/<id>?e=<scadenza>&s=<hmac> emesso solo dopo la validazione, valido 1 h. Altrimenti 403.
"""
import csv, hashlib, hmac, json, os, re, struct, subprocess, sys, threading, time, urllib.parse, urllib.request, uuid
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

QUI = os.environ.get("MINIAPP_QUI") or os.path.dirname(os.path.abspath(__file__))
F = lambda n: os.path.join(QUI, n)
HOME = os.path.expanduser("~")
D = os.environ.get("SONNO_DIR", os.path.join(HOME, "rec"))
_env = F(".env")
env = dict(l.strip().split("=", 1) for l in open(_env) if "=" in l) if os.path.exists(_env) else dict(os.environ)
TOKEN = (os.environ.get("MINIAPP_TOKEN") or env.get("TELEGRAM_SONNO_TOKEN", "")).encode()
CHAT = os.environ.get("MINIAPP_CHAT") or env.get("TELEGRAM_CHAT", "")
PORT = int(os.environ.get("MINIAPP_PORT", "8765"))
ETICHETTE = F("etichette_intervalli.csv")
GIUDIZI = F("giudizi.csv")
CACHE = F("miniapp_cache")
DRIVE_REMOTE = os.environ.get("MINIAPP_DRIVE_REMOTE", "gdrive:")
DRIVE_TTL = 600
DRIVE_MAX = 600 * 1024 * 1024
URL_FILE = F("miniapp_url.txt")
COLS = ["notte", "dispositivo", "inizio_s", "fine_s", "categoria", "ora_salvataggio", "fonte", "id", "clip_origine", "stato"]
BASE = ["russa", "respiro", "tosse", "movimento", "voce", "sbuffo", "silenzio"]
AUTH_MAX_S = 24 * 3600
AUDIO_TTL_S = 3600
SISTEMA_CACHE_S = 20
_sistema_cache = (0, None)
LOCK = threading.Lock()
KEY_AUDIO = hmac.new(TOKEN, b"miniapp-audio", hashlib.sha256).digest()

RE_BLOCCO = re.compile(r"^(\d{8})_(\d{6})$")
RE_CLIP = re.compile(r"^(russa|voce|tosse|sbuffo|finestra|punto)_(\d{8})_(\d{4}|\d{6})$")

def sistema_stati():
    global _sistema_cache
    now = time.time()
    if _sistema_cache[1] is not None and now - _sistema_cache[0] < SISTEMA_CACHE_S: return _sistema_cache[1]
    st, de = {}, {}
    def test(c):
        try: return subprocess.run(c, capture_output=True, text=True, timeout=3).returncode == 0
        except Exception: return False
    def put(k, ok, d): st[k], de[k] = ("ok" if ok else "giu"), d
    put("termux", True, "Termux risponde"); put("crond", test(["pgrep", "-x", "crond"]), "crond vivo"); put("sshd", test(["pgrep", "-x", "sshd"]), "sshd vivo")
    put("bot", test(["sh", "-c", "pgrep -f 'sonno_bot.*bot.py|/bot.py'"]), "bot vivo")
    put("wifi_a21", test(["ping", "-c1", "-W2", "192.0.2.3"]), "router raggiungibile")
    try:
        b = json.loads(subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=3).stdout); pct = int(b.get("percentage", 0)); ch = b.get("plugged") not in (None, "UNPLUGGED", False); put("carica_a21", ch or pct > 30, f"{pct}% {'in carica' if ch else ''}".strip())
    except Exception: put("carica_a21", False, "batteria non disponibile")
    try:
        line = subprocess.run(["df", "-k", HOME], capture_output=True, text=True, timeout=3).stdout.splitlines()[-1].split(); free = int(line[3]) * 1024; put("spazio_a21", free > 1_500_000_000, f"{free // 1024 // 1024} MB liberi")
    except Exception: put("spazio_a21", False, "spazio non disponibile")
    try:
        files = [os.path.join(D, x) for x in os.listdir(D)] if os.path.isdir(D) else []; age = now - max((os.path.getmtime(x) for x in files if os.path.isfile(x)), default=0); put("reg_a21", age < 150, f"ultimo file {int(age)} s fa")
    except Exception: put("reg_a21", False, "cartella rec non disponibile")
    st["mic_a21"], de["mic_a21"] = "?", "lo dice il guardiano"
    try:
        p = os.path.join(HOME, "guardiano_stato.json")
        if now - os.path.getmtime(p) < 600:
            for k, v in json.load(open(p, encoding="utf-8")).items():
                if not k.startswith("_") and v in ("ok", "giu", "?"): st[k], de[k] = v, "dal guardiano PC"
    except (OSError, ValueError, TypeError): pass
    out = dict(st, _t=datetime.now().astimezone().isoformat(timespec="seconds"), _dettagli=de); _sistema_cache = (now, out); return out


# ---------------------------------------------------------------- sicurezza
def valida_initdata(s, token=None, chat=None, ora=None):
    """initData Telegram -> user id (int) se firma, data e utente sono giusti, altrimenti None."""
    token = TOKEN if token is None else token
    chat = CHAT if chat is None else chat
    try:
        if not s or not token or not chat:
            return None
        kv = dict(urllib.parse.parse_qsl(s, keep_blank_values=True, strict_parsing=True))
        h = kv.pop("hash", "")
        dcs = "\n".join(f"{k}={kv[k]}" for k in sorted(kv))
        secret = hmac.new(b"WebAppData", token, hashlib.sha256).digest()
        if not hmac.compare_digest(hmac.new(secret, dcs.encode(), hashlib.sha256).hexdigest(), h):
            return None
        t = int(kv["auth_date"])
        if not (-60 <= (ora or time.time()) - t <= AUTH_MAX_S):
            return None
        uid = int(json.loads(kv["user"])["id"])
        return uid if uid == int(chat) else None
    except (ValueError, KeyError, TypeError):
        return None


def firma_audio(uid_, exp):
    return hmac.new(KEY_AUDIO, f"{uid_}|{exp}".encode(), hashlib.sha256).hexdigest()


def url_audio(uid_):
    exp = int(time.time()) + AUDIO_TTL_S
    return f"/a/{uid_}?e={exp}&s={firma_audio(uid_, exp)}"


def audio_ok(uid_, e, s):
    try:
        return int(e) >= time.time() and hmac.compare_digest(firma_audio(uid_, int(e)), s)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------- unita' (blocchi 30 min e clip)
_dur = {"v": None}


def _leggi_json(p, d=None):
    try:
        return json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return d


def durata(path):
    """Secondi del file (ffprobe), in cache su disco per nome+dimensione. None = non leggibile."""
    if _dur["v"] is None:
        _dur["v"] = _leggi_json(os.path.join(CACHE, "durate.json"), {})
        for n, v in (_leggi_json(F("durate_clip.json"), {}) or {}).items():  # cache del bot: solo nome clip
            _dur["v"].setdefault(n, v)
    try:
        n = os.path.basename(path)
        k = f"{n}:{os.path.getsize(path)}"
        for kk in (k, n):
            if kk in _dur["v"]:
                return _dur["v"][kk]
        v = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                                 capture_output=True, text=True, timeout=30).stdout)
        _dur["v"][k] = v
        os.makedirs(CACHE, exist_ok=True)
        json.dump(_dur["v"], open(os.path.join(CACHE, "durate.json"), "w"))
        return v
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def notte_di(t0):
    """(nota rimossa)"""
    return f"{t0 + timedelta(hours=12):%Y%m%d}"


_un = {"t": 0, "v": {}}
_drive = {"t": 0, "v": {}, "err": ""}
_drive_lock = threading.Lock()
_drive_audio = {}
_API_CACHE_VERSION = 1

def _api_sig(extra=""):
    """Firma economica: cache valida finche' sorgenti e indice etichette non cambiano."""
    h = hashlib.sha256(extra.encode())
    for root in (D, ETICHETTE, GIUDIZI, F("mappe")):  # mappe: minuti di russare (Kaggle) nelle etichette dell'elenco
        paths = []
        if os.path.isdir(root):
            try:
                paths = [os.path.join(root, n) for n in os.listdir(root)
                         if n.endswith(('.m4a', '.csv', '.json'))]
            except OSError:
                pass
        elif os.path.exists(root):
            paths = [root]
        for p in sorted(paths):
            try:
                s = os.stat(p)
                h.update(f"{p}|{s.st_mtime_ns}|{s.st_size}".encode())
            except OSError:
                pass
    return h.hexdigest()[:24]

def _api_cached(name, sig):
    p = os.path.join(CACHE, f"api_{name}.json")
    x = _leggi_json(p)
    if isinstance(x, dict) and x.get("v") == _API_CACHE_VERSION and x.get("sig") == sig:
        return x.get("data")
    return None

def _api_store(name, sig, data):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, f"api_{name}.json")
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"v": _API_CACHE_VERSION, "sig": sig, "data": data}, f, ensure_ascii=False)
    os.replace(tmp, p)

def _refresh_audio_urls(x):
    """Cache conserva struttura; firme audio vengono sempre rinnovate."""
    if not isinstance(x, dict): return x
    for p in x.get("pezzi", []):
        if isinstance(p.get("audio"), str):
            p["audio"] = url_audio(urllib.parse.unquote(p["audio"].split("/a/", 1)[-1].split("?", 1)[0]))
    for ps in (x.get("ascolti") or {}).values():
        for p in ps:
            if isinstance(p.get("audio"), str):
                aid = urllib.parse.unquote(p["audio"].split("/a/", 1)[-1].split("?", 1)[0])
                p["audio"] = url_audio(aid)
    return x

# (416 KB) veniva disegnato lungo 30' e copriva il blocco vero: notte "a pezzi". Durata = dimensione / byte al secondo
# (rec.sh: 14.110.786 B = 1800 s).
M4A_BPS = 14110786 / 1800
DRIVE_DISCO = os.path.join(CACHE, "drive_lsf.txt")


A56_BPS = 96000 / 8
PC_PEZZO_S = 1800.0  # sonno_audio.py: pezzi FLAC da 30'


def dur_archivio(device, size):
    """
    il cambio dispositivo prendeva il file sbagliato e scaricava file interi). PC: il pezzo da 30'
    (ponytail: un pezzo chiuso prima resta lungo 30'; serve ffprobe se conta). A56: byte / bitrate."""
    if device == "pc":
        return PC_PEZZO_S
    return round(size / A56_BPS, 1) if size else 86400.0


def _drive_righe(righe):
    out = {}
    for riga in righe:
        x, _, size = riga.rpartition("|") if "|" in riga else (riga, "", "")
        size = int(size) if size.isdigit() else 0
        n = os.path.basename(x.strip())
        rel = x.strip().replace("\\", "/")
        device = "a56" if "/a56/" in "/" + rel else ("pc" if "/pc/" in "/" + rel else "")
        if not device and n.endswith(".m4a") and RE_BLOCCO.match(n[:-4]):
            i = n[:-4]
            out[i] = dict(id=i, remote=DRIVE_REMOTE + "sonno/" + rel, tipo="blocco", t0=datetime.strptime(i, "%Y%m%d_%H%M%S"), drive=True, dur=round(size / M4A_BPS, 1) if size else 1800.0)
        elif device and n.lower().endswith((".m4a", ".flac")):
            m = re.search(r"(\d{8}_\d{6})", n)
            if m:
                i = f"drive_{device}_{m.group(1)}_{hashlib.sha1(rel.encode()).hexdigest()[:8]}"
                out[i] = dict(id=i, remote=DRIVE_REMOTE + "sonno/" + rel, tipo="archivio_" + device,
                              dispositivo=device, t0=datetime.strptime(m.group(1), "%Y%m%d_%H%M%S"),
                              drive=True, dur=dur_archivio(device, size), estensione=os.path.splitext(n)[1].lower())
    return out


def _drive_aggiorna():
    """rclone lsf -> _drive; l'ultima lista buona resta (anche su disco) se il Drive non risponde."""
    try:
        r = subprocess.run(["rclone", "lsf", "--recursive", "--files-only", "--format", "ps", "--separator", "|",
                            "--filter", "- clip/**", "--filter", "+ *.m4a", "--filter", "+ *.flac", "--filter", "- *", DRIVE_REMOTE + "sonno/"],
                           capture_output=True, text=True, timeout=120, check=False)
        if r.returncode:
            _drive.update(t=time.time(), err="Drive non raggiungibile (rclone lsf)")
            return
        _drive.update(t=time.time(), v=_drive_righe(r.stdout.splitlines()), err="")
        try:
            os.makedirs(CACHE, exist_ok=True)
            with open(DRIVE_DISCO + ".tmp", "w", encoding="utf-8") as f:
                f.write(r.stdout)
            os.replace(DRIVE_DISCO + ".tmp", DRIVE_DISCO)
        except OSError:
            pass
    except (OSError, subprocess.SubprocessError):
        _drive.update(t=time.time(), err="rclone non disponibile: Drive non usato")
    finally:
        _drive["corre"] = False


def _drive_lsf():
    """
    Mini App non aspetta mai il Drive se c'e' gia' una lista (memoria o disco); il rinnovo gira in background."""
    if not _drive["t"] and not _drive.get("v") and os.path.exists(DRIVE_DISCO):
        try:
            _drive.update(v=_drive_righe(open(DRIVE_DISCO, encoding="utf-8").read().splitlines()), t=os.path.getmtime(DRIVE_DISCO))
        except (OSError, ValueError):
            pass
    if time.time() - _drive["t"] < DRIVE_TTL:
        return _drive.get("v", {})
    if not _drive.get("v") and not _drive["t"]:
        _drive["corre"] = True
        _drive_aggiorna()  # primissima volta, niente da mostrare: si aspetta
    elif not _drive.get("corre"):
        _drive["corre"] = True
        threading.Thread(target=_drive_aggiorna, daemon=True).start()
    return _drive.get("v", {})

def _drive_prune():
    try:
        fs = [(os.path.getmtime(os.path.join(CACHE, p)), p, os.path.getsize(os.path.join(CACHE, p))) for p in os.listdir(CACHE) if p.startswith("drive_") and p.endswith((".m4a", ".flac", ".download", ".partial"))]
        total = sum(x[2] for x in fs)
        for _, p, n in sorted(fs):
            if total <= DRIVE_MAX: break
            try: os.remove(os.path.join(CACHE, p)); total -= n
            except OSError: pass
    except OSError: pass

_serve = {"p": None}
SERVE_ADDR = "127.0.0.1:8099"


def _drive_http(src):
    """
    """
    if not src.startswith(DRIVE_REMOTE):
        return None
    if _serve["p"] is None or _serve["p"].poll() is not None:
        _serve["p"] = subprocess.Popen(["rclone", "serve", "http", DRIVE_REMOTE, "--addr", SERVE_ADDR, "--read-only"],
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        try:
            urllib.request.urlopen(f"http://{SERVE_ADDR}/", timeout=2).close()
            return f"http://{SERVE_ADDR}/" + urllib.parse.quote(src[len(DRIVE_REMOTE):])
        except OSError:
            time.sleep(1)
    return None


TEMPI = os.path.join(CACHE, "tempi_audio.csv")


def tipo_audio(src):
    return "a56" if "/a56/" in src else "pc" if "/pc/" in src else "a21s"


def tempo_tipico(tipo, n=20):
    """(nota rimossa)"""
    try:
        v = [float(r[2]) for r in csv.reader(open(TEMPI, encoding="utf-8")) if len(r) > 2 and r[1] == tipo][-n:]
    except (OSError, ValueError):
        return None
    return round(sorted(v)[len(v) // 2]) if len(v) >= 2 else None


def _drive_cut(src, start, dur):
    os.makedirs(CACHE, exist_ok=True)
    out = os.path.join(CACHE, "drive_" + hashlib.sha256(f"{src}|{start:.1f}|{dur:.1f}".encode()).hexdigest()[:24] + ".m4a")
    if os.path.exists(out): return out
    t0 = time.time()
    p = _drive_cut_scarica(src, start, dur, out)
    try:
        with open(TEMPI, "a", encoding="utf-8", newline="") as f:
            csv.writer(f).writerow([datetime.now().isoformat(timespec="seconds"), tipo_audio(src), round(time.time() - t0, 1)])
    except OSError:
        pass
    return p


def _drive_cut_scarica(src, start, dur, out):
    if os.path.exists(out): return out
    with _drive_lock:
        if os.path.exists(out): return out
        tmp = out + ".download"
        try:
            if start <= 0:
                subprocess.run(["rclone", "copyto", src, tmp], timeout=180, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                os.replace(tmp, out)
            else:
                # e la si ricodificava. Ora la sorgente intera si scarica una volta (drive_src_*, stessa cache e pulizia)
                # e il pezzo si taglia senza ricodifica (m4a) - solo il FLAC del PC va codificato.
                sorg = os.path.join(CACHE, "drive_src_" + hashlib.sha256(src.encode()).hexdigest()[:24] + os.path.splitext(src)[1].lower())
                url = _drive_http(src) if src.lower().endswith(".m4a") and not os.path.exists(sorg) else None
                if url:
                    try:
                        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(max(0, start)), "-t", str(max(.1, dur)), "-i", url, "-c:a", "copy", "-f", "mp4", tmp],
                                       timeout=240, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        os.replace(tmp, out)
                        return out
                    except (OSError, subprocess.SubprocessError):
                        pass  # sotto: sorgente intera come prima
                if not os.path.exists(sorg):
                    subprocess.run(["rclone", "copyto", src, sorg + ".download"], timeout=900, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    os.replace(sorg + ".download", sorg)
                os.utime(sorg)  # usata adesso: la pulizia (piu' vecchie prima) la tiene
                cod = ["-c:a", "copy"] if sorg.endswith(".m4a") else ["-c:a", "aac", "-b:a", "48k"]
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(max(0, start)), "-t", str(max(.1, dur)), "-i", sorg, *cod, out], timeout=240, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except (OSError, subprocess.SubprocessError) as e: raise RuntimeError("Drive audio non disponibile") from e
        finally:
            try: os.remove(tmp)
            except OSError: pass
        _drive_prune()
    return out


def unita():
    """{id: dict(id, path, t0, tipo)} — id = nome file senza .m4a. Blocchi: rec/interi + rec (non quello in registrazione)."""
    if time.time() - _un["t"] < 15:
        return _un["v"]
    out = {}
    cand = []
    for d in (os.path.join(D, "interi"), D):
        try:
            cand += [(d, n) for n in os.listdir(d) if n.endswith(".m4a")]
        except OSError:
            pass
    for d, n in cand:
        i, p = n[:-4], os.path.join(d, n)
        m, c = RE_BLOCCO.match(i), RE_CLIP.match(i)
        try:
            st = os.stat(p)
            if m:
                if st.st_size < 100_000 or time.time() - st.st_mtime < 120:
                    continue  # troppo corto / ancora in registrazione (senza moov non suona)
                out[i] = dict(id=i, path=p, tipo="blocco", t0=datetime.strptime(i, "%Y%m%d_%H%M%S"))
            elif c:
                hm = c.group(3)
                out[i] = dict(id=i, path=p, tipo=c.group(1), t0=datetime.strptime(c.group(2) + hm.ljust(6, "0"), "%Y%m%d%H%M%S"))
        except (OSError, ValueError):
            continue
    for i, u in _drive_lsf().items():
        if i not in out: out[i] = u
    _un.update(t=time.time(), v=out)
    return out


_ore = {"t": 0, "v": {}}


def ore():
    """(nota rimossa)"""
    if time.time() - _ore["t"] < 15:
        return _ore["v"]
    sp = [(u["t0"], u["t0"] + timedelta(seconds=(u.get("dur") if u.get("drive") else durata(u["path"])) or 0)) for u in unita().values() if u["tipo"] == "blocco"]
    out = {}
    for u in unita().values():
        if u["tipo"] != "blocco" and not u.get("drive") and not any(a <= u["t0"] < b for a, b in sp):
            h = u["t0"].replace(minute=0, second=0)
            out[f"ora_{h:%Y%m%d_%H}"] = h
    _ore.update(t=time.time(), v=out)
    return out


def get_unit(i):
    """Unita' per id: blocco intero (un pezzo) oppure 'ora_*' = un'ora fatta con le clip che ci sono (pezzi; i buchi = nessuna
    registrazione). -> dict(id, tipo, t0, dur, pezzi=[dict(id, i, f, path)]) | None. Gli id vengono solo dai file del sonno."""
    u = unita().get(i)
    if u and u["tipo"] == "blocco":
        if u.get("drive"):
            p = _drive_cut(u["remote"], 0, u["dur"])
            return dict(id=i, tipo="blocco", t0=u["t0"], dur=u["dur"], path=p, drive=True, pezzi=[dict(id=i, i=0.0, f=u["dur"], path=p, drive=True)])
        d = durata(u["path"])
        return dict(id=i, tipo="blocco", t0=u["t0"], dur=d, path=u["path"], pezzi=[dict(id=i, i=0.0, f=d, path=u["path"])]) if d else None
    if i in ore():
        t0 = ore()[i]
        pz = []
        for c in sorted(unita().values(), key=lambda c: c["t0"]):
            if c["tipo"] == "blocco" or c.get("drive") or not timedelta(minutes=-3) <= c["t0"] - t0 < timedelta(hours=1):
                continue
            d = durata(c["path"])
            o = (c["t0"] - t0).total_seconds()
            if d and o + d > 0:
                pz.append(dict(id=c["id"], i=round(o, 1), f=round(o + d, 1), path=c["path"]))
        return dict(id=i, tipo="ora", t0=t0, dur=3600.0, path=None, pezzi=pz) if pz else None
    return None


def unita_di(t):
    """Unita' che contiene l'istante t: il blocco intero, altrimenti l'ora di clip (se esiste)."""
    for u in sorted(unita().values(), key=lambda u: u["t0"]):
        if u["tipo"] == "blocco" and u["t0"] <= t < u["t0"] + timedelta(seconds=(u.get("dur") if u.get("drive") else durata(u["path"])) or 0):
            return u
    h = f"ora_{t.replace(minute=0, second=0):%Y%m%d_%H}"
    return dict(id=h, t0=ore()[h]) if h in ore() else None


# ---------------------------------------------------------------- esclusioni (dispositivo che suona, fuori stanza)
PERSONA = {"russa", "respiro", "movimento", "tosse", "sbuffo", "starnuto", "io_che_mi_muovo_nel_lett", "tiro_sul_con_il_naso", "respiro_sibilio_affa"}
_ex = {"k": None, "v": []}


def tratto_suona(x):
    """
    di 2 ore di Musictube si chiamava "Telegram" per una notifica iniziale)."""
    app = [a for a in x[3] if a and a != "?"]
    nome = max(set(app), key=app.count) if app else ""
    return dict(ini=x[0], fine=x[1], stato="dispositivo_suona", testo=f"{x[2]} {nome} suonava".replace("  ", " "), blocca="tutto")


def esclusioni():
    """Tratti da non etichettare: analisi/presenza.csv (dispositivo_suona = blocca tutto; fuori_stanza* = blocca la persona;
    -> [dict(ini, fine, stato, testo, blocca 'tutto'|'persona'|'')]"""
    fp, fm = F("analisi/presenza.csv"), F("media_a56.csv")
    k = tuple(os.path.getmtime(x) if os.path.exists(x) else 0 for x in (fp, fm))
    if k == _ex["k"]:
        return _ex["v"]
    out = []
    try:
        for r in csv.DictReader(open(fp, encoding="utf-8", newline="")):
            st = r.get("stato", "")
            try:
                a = datetime.fromisoformat(r["inizio"])
                b = datetime.fromisoformat(r["fine"]) if r.get("fine") else a + timedelta(minutes=1)
            except (ValueError, TypeError):
                continue  # ora ignota ('??:??') o riga che non e' un intervallo
            if st == "dispositivo_suona":
                out.append(dict(ini=a, fine=b, stato=st, testo="telefono suonava", blocca="tutto"))
            elif st.startswith("fuori_stanza"):
                out.append(dict(ini=a, fine=b, stato=st, testo="fuori stanza", blocca="persona"))
            elif st == "non_dataset":
                out.append(dict(ini=a, fine=b, stato=st, testo="non per dataset (test)", blocca=""))
    except OSError:
        pass
    try:
        att = {}  # dev -> [ini, fine, app] del tratto in corso
        righe = []
        for r in csv.reader(open(fm, encoding="utf-8", newline="")):
            if len(r) < 3 or r[2] != "si" or (len(r) > 4 and r[4] == "cuffie"):
                continue
            try:
                righe.append((datetime.fromisoformat(r[0]).replace(tzinfo=None), r))
            except ValueError:
                continue
        for t, r in sorted(righe, key=lambda x: x[0]):
            x = att.get(r[1])
            if x and t - x[1] <= timedelta(minutes=2):  # il PC campiona ogni ~2 minuti: tratti vicini = uno
                x[1] = max(x[1], t + timedelta(minutes=1))
                x[3].append(r[3] if len(r) > 3 else "")
            else:
                if x:
                    out.append(tratto_suona(x))
                att[r[1]] = [t, t + timedelta(minutes=1), r[1].upper() if r[1] == "a56" else r[1], [r[3] if len(r) > 3 else ""]]
        for x in att.values():
            out.append(tratto_suona(x))
    except OSError:
        pass
    _ex.update(k=k, v=out)
    return out


# ---------------------------------------------------------------- etichette
def categorie():
    p = F("suoni.txt")
    return [s.strip() for s in open(p, encoding="utf-8") if s.strip()] if os.path.exists(p) else list(BASE)


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-5]


def leggi_etichette():
    try:
        return list(csv.DictReader(open(ETICHETTE, encoding="utf-8", newline="")))
    except OSError:
        return []


def scrivi_etichette(rows):
    os.makedirs(os.path.dirname(ETICHETTE) or ".", exist_ok=True)
    tmp = ETICHETTE + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        w.writerows(rows)
    os.replace(tmp, ETICHETTE)  # atomico: mai un csv a meta'


def parse_seq(seq):
    """'a>[b+c]>d' -> [['a'], ['b','c'], ['d']]; 'a+b' (clip precisa) -> [['a','b']]."""
    return [[c for c in p.strip().strip("[]").split("+") if c] for p in seq.split(">") if p.strip()]


_gi = {"m": None, "v": []}


def importati():
    """Intervalli da giudizi.csv (bot): sequenza ordinata -> parti uguali della durata della clip, [b+c] = stesso istante
    sovrapposto. giusto=freccia -> tenue. Le clip gia' passate in etichette_intervalli.csv (clip_origine) non si reimportano."""
    try:
        mt = os.path.getmtime(GIUDIZI)
    except OSError:
        return []
    if _gi["m"] != mt:
        v = []
        try:
            righe = list(csv.DictReader(open(GIUDIZI, encoding="utf-8", newline="")))
        except OSError:
            righe = []
        for r in righe:
            clip = (r.get("clip") or "").strip()
            c = RE_CLIP.match(clip[:-4]) if clip.endswith(".m4a") else None
            if not c:
                continue
            seq = (r.get("sequenza") or "").strip() or ((r.get("detto") or "") if r.get("giusto") == "1" else "")
            if not seq:
                continue
            hm = c.group(3)
            t0 = datetime.strptime(c.group(2) + hm.ljust(6, "0"), "%Y%m%d%H%M%S")
            p = os.path.join(D, clip)
            d = durata(p) if os.path.exists(p) else (_dur["v"] or {}).get(clip)
            d = d or (20.0 if clip.startswith("finestra_") else None)
            if not d:
                continue
            try:
                salv = datetime.fromisoformat(r.get("ora") or "")
            except ValueError:
                salv = t0
            parti = parse_seq(seq)
            j = 0
            for k, cats in enumerate(parti):
                a = t0 + timedelta(seconds=d * k / len(parti))
                b = t0 + timedelta(seconds=d * (k + 1) / len(parti))
                for cat in cats:
                    v.append(dict(id=f"g:{clip}:{j}", clip=clip, ini=a, fine=b, cat=cat, salvato=salv,
                                  fonte="bot-freccia" if r.get("giusto") == "freccia" else "bot"))
                    j += 1
        _gi.update(m=mt, v=v)
    fatte = {r["clip_origine"] for r in leggi_etichette() if r.get("clip_origine")}
    return [x for x in _gi["v"] if x["clip"] not in fatte]


def _dt(s):
    """ISO con frazione di 1+ cifre (anche python < 3.11)."""
    a, _, fr = s.partition(".")
    return datetime.fromisoformat(a + ("." + fr.ljust(6, "0")[:6] if fr else ""))


def tutti_intervalli():
    """Tutti gli intervalli validi (miniapp + importati non ancora toccati), come dict con datetime."""
    out = []
    for r in leggi_etichette():
        if r.get("stato") == "cancellato":
            continue
        try:
            out.append(dict(id=r["id"], clip=r.get("clip_origine", ""), ini=_dt(r["inizio_s"]), fine=_dt(r["fine_s"]), cat=r["categoria"],
                            salvato=_dt(r["ora_salvataggio"]), fonte=r.get("fonte") or "miniapp", stato=r.get("stato") or "ok"))
        except (ValueError, KeyError):
            continue
    return out + importati()


def intervalli_unita(u):
    d = u["dur"]
    t0, t1 = u["t0"], u["t0"] + timedelta(seconds=d)
    return [dict(id=x["id"], i=round((x["ini"] - t0).total_seconds(), 1), f=round((x["fine"] - t0).total_seconds(), 1),
                 cat=x["cat"], fonte=x["fonte"], clip=x["clip"], stato=x.get("stato", "ok"))
            for x in sorted(tutti_intervalli(), key=lambda x: x["ini"]) if x["ini"] < t1 and x["fine"] > t0]


def ultima():
    """Zona dell'ultima categorizzazione (per ora di salvataggio): {ini, fine, clip, notte} o None."""
    t = tutti_intervalli()
    if not t:
        return None
    ult = max(t, key=lambda x: x["salvato"])
    gruppo = [x for x in t if x["clip"] and x["clip"] == ult["clip"]] or [ult]
    ini, fine = min(x["ini"] for x in gruppo), max(x["fine"] for x in gruppo)
    u = unita_di(ini)
    return dict(ini=iso(ini), fine=iso(fine), notte=notte_di(ini), unita=u["id"] if u else None,
                i=round((ini - u["t0"]).total_seconds(), 1) if u else None, f=round((fine - u["t0"]).total_seconds(), 1) if u else None)


def salva(b):
    """op add|upd|del su etichette_intervalli.csv (scrittura immediata, atomica). Gli importati si 'materializzano' alla
    prima modifica: tutta la clip d'origine passa nel csv (fonte=miniapp, clip_origine=clip) e il bot non si tocca."""
    u = get_unit(str(b.get("unita")))
    if not u:
        raise ValueError("unita'")
    d = u["dur"]
    op, ora = b.get("op"), datetime.now()
    cats = categorie()

    def tempo(x):
        return u["t0"] + timedelta(seconds=round(min(max(float(x), 0.0), d), 1))

    def controlla(ini, fine, cat, dispositivo="a21s"):
        """Niente etichette dove un dispositivo suonava / fuori stanza (persona); niente in un buco senza registrazione."""
        if (fine - ini).total_seconds() < 0.2 or cat not in cats and cat not in ("",):
            raise ValueError("categoria o intervallo")
        o, f = (ini - u["t0"]).total_seconds(), (fine - u["t0"]).total_seconds()
        copertura = u["pezzi"] if dispositivo == "a21s" else ascolti_unita(u).get(dispositivo, [])
        if dispositivo not in ("a21s", "a56", "pc") or not any(p["i"] < f and p["f"] > o for p in copertura):
            raise ValueError("nessuna registrazione qui")
        for e in esclusioni():
            if e["ini"] < fine and e["fine"] > ini and (e["blocca"] == "tutto" or e["blocca"] == "persona" and cat.split("/")[0] in PERSONA):
                raise ValueError("tratto escluso: " + e["testo"])

    def riga(i, ini, fine, cat, clip="", fonte="miniapp", stato="ok", dispositivo="a21s"):
        return dict(notte=notte_di(ini), dispositivo=dispositivo, inizio_s=iso(ini), fine_s=iso(fine), categoria=cat,
                    ora_salvataggio=ora.strftime("%Y-%m-%dT%H:%M:%S"), fonte=fonte, id=i, clip_origine=clip, stato=stato)

    def una(b, rows):
        """Applica UNA op alle righe in memoria; ritorna l'id nuovo (add) o None."""
        op = b.get("op")
        if op == "add":
            ini, fine = tempo(b["i"]), tempo(b["f"])
            dispositivo = b.get("dispositivo", "a21s")
            controlla(ini, fine, b.get("cat"), dispositivo)
            nuovo = uuid.uuid4().hex[:10]
            fonte = b.get("fonte") if b.get("fonte") in ("miniapp", "miniapp_bozza", "miniapp_bozza_confermata") else "miniapp"
            stato = "da_confermare" if b.get("stato") == "da_confermare" else "ok"
            for r in rows:  # idempotente: un salvataggio rimandato (coda offline, sendBeacon doppio) non duplica
                if r.get("stato") != "cancellato" and (r["inizio_s"], r["fine_s"], r["categoria"], r.get("dispositivo", "a21s")) == (iso(ini), iso(fine), b["cat"], dispositivo):
                    return r["id"]
            rows.append(riga(nuovo, ini, fine, b["cat"], fonte=fonte, stato=stato, dispositivo=dispositivo))
            return nuovo
        if op == "conf":  # conferma: da_confermare -> ok (le righe non si riscrivono, cambia solo stato e fonte bozza)
            for r in rows:
                if r["id"] == str(b.get("id")) and r.get("stato") != "cancellato":
                    r["stato"] = "ok"
                    if r.get("fonte") == "miniapp_bozza":
                        r["fonte"] = "miniapp_bozza_confermata"
                    return None
            raise ValueError("id")
        if op not in ("upd", "del", "res"):  # res = annulla una cancellazione
            raise ValueError("op")
        iid = str(b.get("id"))
        if iid.startswith("g:") and not any(r.get("clip_origine") == iid.split(":")[1] for r in rows):
            clip = iid.split(":")[1]
            for x in importati():
                if x["clip"] == clip:
                    rows.append(riga(x["id"], x["ini"], x["fine"], x["cat"], clip))
        r = next((r for r in rows if r["id"] == iid and (r.get("stato") == "cancellato") == (op == "res")), None)
        if not r:
            raise ValueError("id")
        if op == "res":
            r["stato"], r["ora_salvataggio"] = "ok", ora.strftime("%Y-%m-%dT%H:%M:%S")
        elif op == "del":
            r["stato"], r["ora_salvataggio"] = "cancellato", ora.strftime("%Y-%m-%dT%H:%M:%S")
        else:
            ini = tempo(b["i"]) if "i" in b else _dt(r["inizio_s"])
            fine = tempo(b["f"]) if "f" in b else _dt(r["fine_s"])
            cat = b.get("cat", r["categoria"])
            if cat != r["categoria"] and cat not in cats:
                raise ValueError("categoria")
            if (ini, fine, cat) != (_dt(r["inizio_s"]), _dt(r["fine_s"]), r["categoria"]):  # invariata = nessun controllo
                controlla(ini, fine, cat, r.get("dispositivo", "a21s"))
            r.update(riga(iid, ini, fine, cat, r.get("clip_origine", ""), (r.get("fonte") if r.get("stato") == "da_confermare" else "miniapp"), r.get("stato") or "ok", r.get("dispositivo", "a21s")))  # modificata a mano = fonte miniapp (tranne bozza ancora da confermare)
        return None

    with LOCK:
        rows = leggi_etichette()
        if op == "lot":  # piu' op insieme, tutto o niente (spostare un taglio = 2 pezzi; conferma in blocco); soft = salta i non etichettabili
            ops = b.get("ops")
            if not isinstance(ops, list) or len(ops) > 800:
                raise ValueError("lot")
            nuovi, saltati = [], 0
            for x in ops:
                try:
                    nuovi.append(una(x, rows))
                except ValueError:
                    if not (b.get("soft") and x.get("op") == "add"):
                        raise
                    saltati += 1
            nuovo = [n for n in nuovi if n]
        else:
            nuovo, saltati = una(b, rows), 0
        scrivi_etichette(rows)
    return dict(ok=True, nuovo=nuovo, saltati=saltati, intervalli=intervalli_unita(u))


# ---------------------------------------------------------------- modelli (mappe/mappa_*.json copiate dal PC)
_mp = {}


def modelli_unita(u):
    d = u["dur"]
    t0 = u["t0"]
    out = []
    import glob
    for f in sorted(glob.glob(os.path.join(F("mappe"), "mappa_*.json"))):
        mt = os.path.getmtime(f)
        if _mp.get(f, (0,))[0] != mt:
            _mp[f] = (mt, _leggi_json(f, {}) or {})
        for c in (_mp[f][1].get("corsie") or []):
            if c.get("livello") == "TU":
                continue  # le sue etichette sono le sue: non sono un modello
            celle, ks, cov = [], [], [None, None]
            for k, cats in (c.get("celle") or {}).items():
                try:
                    a = _dt(k)
                except ValueError:
                    continue
                res = 60 if len(k) == 16 else float(c.get("risoluzione_s") or 1)
                o = (a - t0).total_seconds()
                if o + res <= 0 or o >= d:
                    continue
                cov = [o if cov[0] is None else min(cov[0], o), o + res if cov[1] is None else max(cov[1], o + res)]
                if cats:
                    celle.append([o, res, list(cats)])
            if cov[0] is not None:
                out.append(dict(nome=c.get("nome", "?"), colore=c.get("colore"), livello=c.get("livello"), cop=cov, celle=sorted(celle)))
    return out


# ---------------------------------------------------------------- spettrogramma (precalcolato, in cache)
NF, HOP, SR, BINS = 512, 800, 8000, 56  # finestra 64 ms, passo 0,1 s a 8 kHz
_sp = {}  # id -> "calcolo" | "errore"
SPLOCK = threading.Lock()  # un calcolo alla volta: l'A21s registra e analizza


def percorso_spec(u):
    sig = hashlib.md5("|".join(f"{p['id']}:{os.path.getsize(p['path'])}" for p in u["pezzi"]).encode()).hexdigest()[:10]
    return os.path.join(CACHE, f"{u['id']}_{sig}.spec")


def bande(path):
    """Audio -> (db [n x bande], livello dB [n]) con passo HOP/SR s. Chunk da 3000 frame: poca RAM sull'A21s."""
    import numpy as np
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "s16le", "-"], capture_output=True, timeout=900)
    x = np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768
    n = (len(x) - NF) // HOP + 1
    if n < 1:
        raise ValueError("audio troppo corto")
    win = np.hanning(NF).astype(np.float32)
    ed = np.unique(np.round(np.geomspace(2, NF // 2 + 1, BINS + 1)).astype(int))
    w = np.diff(ed)
    view = np.lib.stride_tricks.sliding_window_view(x, NF)[::HOP][:n]
    db, lv = [], []
    for a in range(0, n, 3000):
        sp = np.abs(np.fft.rfft(view[a:a + 3000] * win, axis=1)) ** 2
        band = np.add.reduceat(sp[:, :ed[-1]], ed[:-1], axis=1) / w
        db.append(10 * np.log10(band + 1e-12))
        lv.append(10 * np.log10(sp.mean(axis=1) + 1e-12))
    return np.concatenate(db), np.concatenate(lv)


def calcola_spec(u, out):
    """Blocco = un file; ora = le clip messe al loro posto su una griglia da 0,1 s (buchi a zero). Scala: percentili sul tutto."""
    import numpy as np
    step = HOP / SR
    n = int(round(u["dur"] / step)) if u["tipo"] == "ora" else None
    DB = LV = None
    for p in u["pezzi"]:
        db, lv = bande(p["path"])
        if n is None:
            DB, LV = db, lv
            break
        if DB is None:
            DB, LV = np.full((n, db.shape[1]), np.nan, np.float32), np.full(n, np.nan, np.float32)
        c0 = int(round(p["i"] / step))
        a, b = max(c0, 0), min(c0 + len(db), n)
        if b > a:
            DB[a:b], LV[a:b] = db[a - c0:b - c0], lv[a - c0:b - c0]
    if DB is None:
        raise ValueError("nessun audio")
    ok = ~np.isnan(LV)
    lo, hi = np.percentile(DB[ok], 5), np.percentile(DB[ok], 99.7)
    l0, l1 = np.percentile(LV[ok], 2), np.percentile(LV[ok], 99.8)
    img = np.nan_to_num(np.clip((DB - lo) / max(hi - lo, 1e-6) * 255, 0, 255)).astype(np.uint8)
    lev = np.nan_to_num(np.clip((LV - l0) / max(l1 - l0, 1e-6) * 255, 0, 255)).astype(np.uint8)
    os.makedirs(CACHE, exist_ok=True)
    tmp = out + ".tmp"
    with open(tmp, "wb") as f:
        f.write(struct.pack("<IIff", len(img), img.shape[1], step, 0.0) + img.tobytes() + lev.tobytes())
    os.replace(tmp, out)


def spec(u):
    """(bytes | None, stato): None + 'calcolo' = in preparazione (il client richiede tra 2 s)."""
    out = percorso_spec(u)
    if os.path.exists(out):
        return open(out, "rb").read(), "ok"
    if _sp.get(out) != "calcolo":
        _sp[out] = "calcolo"

        def lavoro():
            with SPLOCK:
                try:
                    calcola_spec(u, out)
                    _sp.pop(out, None)
                except Exception as e:  # noqa: BLE001
                    _sp[out] = "errore"
                    print("spec", u["id"], e, file=sys.stderr, flush=True)
        threading.Thread(target=lavoro, daemon=True).start()
    return None, _sp.get(out, "calcolo")


# ---------------------------------------------------------------- tagli proposti (bozza)
# Livelli per zoom: grosso (eventi, ~minuti), medio (secondi), fine (singoli colpi/respiri). Parametri in colonne da 0,1 s.
LIVELLI = {"grosso": (50, 200, 100), "medio": (10, 30, 20), "fine": (3, 6, 5)}  # (finestra di media, buco da chiudere, durata minima)
PESO_LIV = {"PRECISO": 3, "MEDIO": 2, "BASSO": 1}
_pr = {}


def _runs(mask, gap, minlen):
    """Booleani -> [(a, b)] di True; chiude i buchi <= gap, scarta i tratti < minlen."""
    import numpy as np
    d = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    r = list(zip(np.flatnonzero(d == 1).tolist(), np.flatnonzero(d == -1).tolist()))
    out = []
    for a, b in r:
        if out and a - out[-1][1] <= gap:
            out[-1] = (out[-1][0], b)
        else:
            out.append((a, b))
    return [(a, b) for a, b in out if b - a >= minlen]


def _cat_modello(a, b, modelli):
    """Categoria piu' votata nei modelli fra a e b (s): peso = livello (PANNs 3, EfficientAT 2, YAMNet 1) x secondi."""
    w = {}
    for m in modelli:
        for o, res, cats in m["celle"]:
            ov = min(b, o + res) - max(a, o)
            if ov > 0:
                for c in cats:
                    w[c] = w.get(c, 0) + ov * PESO_LIV.get(m["livello"], 1)
    return max(w, key=w.get) if w else None


def proposte(u):
    """Segmentazione proposta in pezzi CONSECUTIVI per ogni livello: eventi dove il livello dello spettrogramma si stacca dal fondo
    (+ categoria dai modelli per minuto/secondo, se ci sono), il resto 🤫 silenzio. Solo dove c'e' registrazione e non ci sono
    esclusioni bloccanti. None = spettrogramma non ancora pronto. Niente modelli pesanti: l'A21s resta libero per registrare."""
    import numpy as np
    dati, st = spec(u)
    if dati is None:
        return None
    mod = modelli_unita(u)
    k = (u["id"], len(dati), tuple(os.path.getmtime(f) for f in sorted(__import__("glob").glob(F("mappe/mappa_*.json")))), esclusioni_k())
    if k in _pr:
        return _pr[k]
    n, bins, step, _ = struct.unpack("<IIff", dati[:16])
    lev = np.frombuffer(dati, dtype=np.uint8, count=n, offset=16 + n * bins).astype(np.float32)
    cop = np.zeros(n, bool)  # dove c'e' audio
    for p in u["pezzi"]:
        cop[max(int(p["i"] / step), 0):min(int(p["f"] / step), n)] = True
    ch = 100  # fondo = 20o percentile per blocchi da 10 s, interpolato
    cen = np.arange(0, n, ch) + ch / 2
    bg = np.interp(np.arange(n), cen[:len(range(0, n, ch))], [np.percentile(lev[a:a + ch][cop[a:a + ch]], 20) if cop[a:a + ch].any() else 0 for a in range(0, n, ch)])
    ecc = lev - bg
    soglia = max(10.0, 0.3 * np.percentile(ecc[cop], 98)) if cop.any() else 10.0
    ex = [(e["ini"], e["fine"], e["blocca"]) for e in esclusioni() if e["ini"] < u["t0"] + timedelta(seconds=u["dur"]) and e["fine"] > u["t0"]]
    out = {}
    for nome, (fin, gap, mn) in LIVELLI.items():
        sm = np.convolve(ecc, np.ones(fin) / fin, mode="same")
        ev = _runs((sm > soglia) & cop, gap, mn)
        # pezzi consecutivi: eventi + silenzio nel mezzo, dentro ogni tratto registrato
        taglia = sorted({0, n, *[x for a, b in ev for x in (a, b)], *[int(p["i"] / step) for p in u["pezzi"] if 0 < p["i"] / step < n], *[min(int(p["f"] / step), n) for p in u["pezzi"]]})
        pezzi = []
        for a, b in zip(taglia, taglia[1:]):
            if b - a < 1 or not cop[a:b].any():
                continue
            e = any(x <= a and b <= y for x, y in ev)
            ia, fb = a * step, b * step
            cat = _cat_modello(ia, fb, mod) if e else "silenzio"
            pezzi.append(dict(i=round(ia, 1), f=round(fb, 1), cat=cat or "?", src=("modello" if cat else "energia") if e else "silenzio"))
        # unisce silenzi adiacenti e toglie i tratti dove non si puo' etichettare
        ris = []
        for p in pezzi:
            t0, t1 = u["t0"] + timedelta(seconds=p["i"]), u["t0"] + timedelta(seconds=p["f"])
            if any(x < t1 and y > t0 and (bl == "tutto" or bl == "persona" and p["cat"].split("/")[0] in PERSONA) for x, y, bl in ex):
                continue
            if ris and p["cat"] == "silenzio" and ris[-1]["cat"] == "silenzio" and abs(ris[-1]["f"] - p["i"]) < .06:
                ris[-1]["f"] = p["f"]
            else:
                ris.append(p)
        out[nome] = ris
    _pr.clear() if len(_pr) > 20 else None
    _pr[k] = out
    return out


def esclusioni_k():
    return _ex["k"]


# ---------------------------------------------------------------- API
CORTO_S = 120
_att = {"k": None, "v": {}}


def russa_minuti(notte):
    """{minuto 'AAAA-MM-GGTHH:MM': True} col russare secondo Kaggle (PANNs) dalla mappa della notte; {} se non c'e'."""
    p = F(f"mappe/mappa_{notte}.json")
    try:
        k = (p, os.path.getmtime(p))
        if _att["k"] != k:
            J = _leggi_json(p, {})
            c = next((x["celle"] for x in J.get("corsie", []) if x.get("nome") == "PANNs"), {})
            _att.update(k=k, v={m: True for m, cats in c.items() if "russa" in cats})
        return _att["v"]
    except OSError:
        return {}


def russa_da(u):
    """
    minuto di russare (Kaggle PANNs), None se nel blocco non russa o la notte non ha la mappa."""
    rm = russa_minuti(notte_di(u["t0"]))
    a, b = f"{u['t0']:%Y-%m-%dT%H:%M}", f"{u['t0'] + timedelta(seconds=u['dur'] or 0):%Y-%m-%dT%H:%M}"
    m = min((x for x in rm if a <= x < b), default=None)
    return max(0.0, (datetime.strptime(m, "%Y-%m-%dT%H:%M") - u["t0"]).total_seconds()) if m else None


def russa_blocco(t0, dur, notte):
    """Minuti di russare (Kaggle) dentro [t0, t0+dur); None se la notte non ha ancora la mappa."""
    rm = russa_minuti(notte)
    if not rm:
        return None
    a, b = f"{t0:%Y-%m-%dT%H:%M}", f"{t0 + timedelta(seconds=dur or 0):%Y-%m-%dT%H:%M}"
    return sum(1 for m in rm if a <= m < b)


def regole():
    """
    con le grafiche, le cose generate e cosa dice l'AI; verificare i numeri". regole/regole.json (estratte dal codice, con
    file:riga), l'ultima verifica dei numeri (regole/numeri_*.md) e l'ultima scheda notte mandata (cosa ha detto il bot)."""
    import glob
    num = sorted(glob.glob(F("regole/numeri_*.md")))
    sc = _leggi_json(F("scheda_notte.json"), {}) or {}
    return dict(regole=_leggi_json(F("regole/regole.json"), []) or [],
                numeri=open(num[-1], encoding="utf-8").read() if num else "", numeri_file=os.path.basename(num[-1]) if num else "",
                scheda=dict(day=sc.get("day", ""), testo=sc.get("testo", "")))


def elenco():
    sig = _api_sig("elenco")
    cached = _api_cached("elenco", sig)
    if cached is not None:
        return cached
    ns = {}
    nn = lambda t: ns.setdefault(notte_di(t), dict(notte=notte_di(t), blocchi=[], ore=[]))
    for u in unita().values():
        if u["tipo"] == "blocco":
            dur = u.get("dur") if u.get("drive") else durata(u["path"])
            nn(u["t0"])["blocchi"].append(dict(id=u["id"], t0=iso(u["t0"]), tipo="blocco", dur=dur, drive=bool(u.get("drive")),
                                               russa=russa_blocco(u["t0"], dur, notte_di(u["t0"]))))
    cnt = {}
    for u in unita().values():
        h = f"ora_{u['t0'].replace(minute=0, second=0):%Y%m%d_%H}"
        if u["tipo"] != "blocco" and h in ore():
            cnt[h] = cnt.get(h, 0) + 1
    for h, t0 in ore().items():
        nn(t0)["ore"].append(dict(id=h, t0=iso(t0), tipo="ora", n=cnt.get(h, 0)))
    for n in ns.values():
        n["blocchi"].sort(key=lambda x: x["t0"])
        # pezzetto = blocco corto seguito subito (< 3') da un altro blocco: e' la ripartenza di rec.sh, non una registrazione a se'
        b = n["blocchi"]
        n["blocchi"] = [x for k, x in enumerate(b) if not ((x["dur"] or 0) < CORTO_S and k + 1 < len(b)
                        and datetime.fromisoformat(b[k + 1]["t0"][:19]) - datetime.fromisoformat(x["t0"][:19]) < timedelta(minutes=3))]
        # mettere in cima i blocchi in cui dormiva; il resto del giorno va in un gruppo a parte in fondo.
        J = _leggi_json(F(f"mappe/mappa_{n['notte']}.json"), {}) or {}
        if J.get("inizio") and J.get("fine"):
            n["sonno"] = [J["inizio"], J["fine"]]
        n["ore"].sort(key=lambda x: x["t0"])
    out = dict(notti=sorted(ns.values(), key=lambda n: n["notte"], reverse=True), categorie=categorie(), ultima=ultima(), drive_errore=_drive.get("err", ""),
               tempi={k: tempo_tipico(k) for k in ("a21s", "a56", "pc")})
    _api_store("elenco", sig, out)
    return out


def blocco(i, uid_):
    sig = _api_sig("blocco|" + i)
    cached = _api_cached("blocco_" + hashlib.sha256(i.encode()).hexdigest()[:20], sig)
    if cached is not None:
        return _refresh_audio_urls(cached)
    u = get_unit(i)
    if not u:
        return None
    ids = sorted(ore()) if u["tipo"] == "ora" else [x["id"] for x in sorted(unita().values(), key=lambda x: x["t0"]) if x["tipo"] == "blocco" and not (x.get("drive") and x["dur"] < CORTO_S)]
    if u["id"] not in ids:
        ids = sorted(ids + [u["id"]])
    k = ids.index(u["id"])
    t1 = u["t0"] + timedelta(seconds=u["dur"])
    ex = [dict(i=round((e["ini"] - u["t0"]).total_seconds(), 1), f=round((e["fine"] - u["t0"]).total_seconds(), 1), stato=e["stato"], testo=e["testo"], blocca=e["blocca"])
          for e in esclusioni() if e["ini"] < t1 and e["fine"] > u["t0"]]
    out = dict(id=u["id"], t0=iso(u["t0"]), dur=u["dur"], tipo=u["tipo"], notte=notte_di(u["t0"]),
                pezzi=[dict(i=p["i"], f=p["f"], audio=url_audio(p["id"])) for p in u["pezzi"]],
                prec=ids[k - 1] if k else None, succ=ids[k + 1] if k + 1 < len(ids) else None,
                intervalli=intervalli_unita(u), modelli=modelli_unita(u), esclusioni=ex,
                ascolti=ascolti_unita(u), inizio_russa=russa_da(u))
    _api_store("blocco_" + hashlib.sha256(i.encode()).hexdigest()[:20], sig, out)
    return out


def audio_alternativi():
    """Manifest prodotti dal PC; percorsi ammessi solo dentro la cache dedicata."""
    from pathlib import Path
    root = Path(F('audio_dispositivi')).resolve()
    out = {}
    for r in _drive_lsf().values():
        if r.get("tipo") in ("archivio_a56", "archivio_pc"):
            out[r["id"]] = dict(r)
    for mf in sorted(root.glob('????????/manifest.json'))[-2:]:
        for r in (_leggi_json(str(mf), {}) or {}).get('file', []):
            try:
                if not re.fullmatch(r'alt_(a56|pc)_[a-f0-9]{20}', r['id']):
                    continue
                p = (mf.parent / r['file']).resolve()
                if p.parent != mf.parent.resolve() or p.suffix != '.m4a' or not p.is_file():
                    continue
                out[r['id']] = dict(r, path=str(p))
            except (KeyError, TypeError, OSError):
                continue
    return out


def ascolti_unita(u):
    out = {'a56': [], 'pc': []}
    t = u['t0'].timestamp()
    for r in audio_alternativi().values():
        if r.get('dispositivo') not in out:
            continue
        i = (r['t0'].timestamp() if isinstance(r['t0'], datetime) else r['t0']) - t
        f = i + r['dur']
        if i < u['dur'] and f > 0:
            aid = r['id']
            if r.get('drive'):
                aid = "drive_audio_" + hashlib.sha1(f"{r['id']}|{max(0, i):.1f}|{min(u['dur'], f)-max(0, i):.1f}".encode()).hexdigest()[:20]
                _drive_audio[aid] = dict(r, start=max(0, -i), dur=min(u['dur'], f)-max(0, i))
            out[r['dispositivo']].append(dict(i=max(0,i), f=min(u['dur'],f),
                offset=max(0,-i), audio=url_audio(aid)))
    return {k: sorted(v, key=lambda p:p['i']) for k,v in out.items()}


# ---------------------------------------------------------------- HTTP
class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "x"
    sys_version = ""

    def log_message(self, *a):  # niente log: negli URL ci sono le firme
        pass

    def _r(self, code, body=b"", ctype="application/json", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text") or ctype == "application/json" else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _auth(self):
        return valida_initdata(self.headers.get("X-Init-Data", ""))

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        try:
            u = urllib.parse.urlsplit(self.path)
            q = dict(urllib.parse.parse_qsl(u.query))
            if u.path in ("/", "/index.html"):  # pagina statica: nessun dato privato
                return self._r(200, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "miniapp.html"), "rb").read(), "text/html")
            if u.path == "/grafo_stati.html":
                return self._r(200, open(F("grafo_stati.html"), "rb").read(), "text/html")
            if u.path.startswith("/a/"):
                i = u.path[3:]
                if not audio_ok(i, q.get("e"), q.get("s", "")):
                    return self._r(403, {"errore": "no"})
                ULTIMO_UTENTE[0] = time.time()
                return self._audio(i)
            uid_ = self._auth()
            if not uid_:
                return self._r(403, {"errore": "no"})
            ULTIMO_UTENTE[0] = time.time()
            if u.path == "/api/elenco":
                return self._r(200, elenco())
            if u.path == "/api/regole":
                return self._r(200, regole())
            if u.path == "/api/sistema":
                return self._r(200, sistema_stati())
            if u.path == "/api/blocco":
                b = blocco(q.get("id", ""), uid_)
                return self._r(200, b) if b else self._r(404, {"errore": "id"})
            if u.path == "/api/proposte":
                un = get_unit(q.get("id", ""))
                if not un:
                    return self._r(404, {"errore": "id"})
                esclusioni()
                pr = proposte(un)
                return self._r(200, dict(livelli=pr)) if pr else self._r(202, {"stato": "calcolo"})
            if u.path == "/api/spec":
                un = get_unit(q.get("id", ""))
                if not un:
                    return self._r(404, {"errore": "id"})
                dati, st = spec(un)
                return self._r(200, dati, "application/octet-stream") if dati else self._r(202, {"stato": st})
            self._r(404, {"errore": "no"})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa: BLE001
            print("GET", type(e).__name__, e, file=sys.stderr, flush=True)
            try:
                self._r(500, {"errore": "interno"})
            except OSError:
                pass

    def do_POST(self):
        try:
            if urllib.parse.urlsplit(self.path).path != "/api/salva":
                return self._r(403, {"errore": "no"})
            n = int(self.headers.get("Content-Length") or 0)
            if n > 262144:
                return self._r(413, {"errore": "grande"})
            b = json.loads(self.rfile.read(n) or b"{}")
            # sendBeacon non puo' mettere header: l'initData puo' stare nel corpo (stessa validazione)
            if not valida_initdata(self.headers.get("X-Init-Data") or (b.pop("initData", "") if isinstance(b, dict) else "")):
                return self._r(403, {"errore": "no"})
            try:
                return self._r(200, salva(b))
            except (ValueError, KeyError, TypeError) as e:
                return self._r(400, {"errore": f"dati: {e}"})
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:  # noqa: BLE001
            print("POST", type(e).__name__, e, file=sys.stderr, flush=True)
            try:
                self._r(500, {"errore": "interno"})
            except OSError:
                pass

    def _audio(self, i):
        un = _drive_audio.get(i) if i.startswith('drive_audio_') else (audio_alternativi().get(i) if i.startswith('alt_') or i.startswith('drive_') else unita().get(i))
        if not un:
            return self._r(404, {"errore": "id"})
        if un.get("drive"):
            try:
                p = _drive_cut(un["remote"], un.get("start", 0), un.get("dur", un.get("dur", 1800)))
                un = dict(un, path=p)
            except RuntimeError: return self._r(503, {"errore": "Drive non disponibile"})
        size = os.path.getsize(un["path"])
        a, b, code = 0, size - 1, 200
        m = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range", ""))
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                a, b = int(m.group(1)), min(int(m.group(2) or size - 1), size - 1)
            else:
                a = max(size - int(m.group(2)), 0)
            if a > b:
                return self._r(416, b"", extra={"Content-Range": f"bytes */{size}"})
            code = 206
        self.send_response(code)
        self.send_header("Content-Type", "audio/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(b - a + 1))
        self.send_header("Cache-Control", "private, max-age=3600")
        if code == 206:
            self.send_header("Content-Range", f"bytes {a}-{b}/{size}")
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(un["path"], "rb") as f:
            f.seek(a)
            resto = b - a + 1
            while resto > 0:
                chunk = f.read(min(65536, resto))
                if not chunk:
                    break
                self.wfile.write(chunk)
                resto -= len(chunk)


ULTIMO_UTENTE = [0.0]


def batteria_bassa(soglia=30):
    """(nota rimossa)"""
    try:
        return int(json.loads(subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=10).stdout).get("percentage", 100)) < soglia
    except Exception:  # noqa: BLE001 - sul PC (test) o batteria illeggibile: non si blocca niente
        return False


def precarica():
    """
    di tutti i blocchi dell'ultima notte presa dal Drive, cosi' avanti/indietro e' immediato. Solo con >= 1,2 GB liberi
    (la registrazione ha la precedenza sul disco). ponytail: solo l'ultima notte; le altre restano a richiesta."""
    # (spettrogramma lento saltando alle 6:30). Ora: priorita' bassa (vale anche per ffmpeg/rclone figli) e pausa
    try:
        os.nice(10)  # Linux: solo questo thread e i suoi figli
    except (OSError, AttributeError):
        pass
    while True:
        try:
            st = os.statvfs(D)
            if st.f_bavail * st.f_frsize >= 1.2e9:
                bl = [u for u in unita().values() if u["tipo"] == "blocco" and u.get("drive")]
                # blocchi fra mezzanotte e le 7
                notte = max((notte_di(u["t0"]) for u in bl if u["t0"].hour < 7), default=None)
                bl = [u for u in bl if notte_di(u["t0"]) == notte and u["dur"] >= CORTO_S]
                for u in sorted(bl, key=lambda u: (-(russa_blocco(u["t0"], u["dur"], notte) or 0), u["t0"])):
                    while time.time() - ULTIMO_UTENTE[0] < 90:
                        time.sleep(15)
                    if batteria_bassa():
                        break
                    g = get_unit(u["id"])
                    if g and not os.path.exists(percorso_spec(g)):
                        with SPLOCK:
                            calcola_spec(g, percorso_spec(g))
                    blocco(u["id"], 0)
        except Exception as e:  # noqa: BLE001
            print("precarica", e, file=sys.stderr, flush=True)
        time.sleep(600)


def pulsante_menu():
    """Quando il tunnel cambia URL (miniapp_url.txt) mette il pulsante 🎧 (web_app) come menu button della chat."""
    ultimo = None
    while True:
        try:
            url = open(URL_FILE).read().strip()
            if url.startswith("https://") and url != ultimo:
                body = json.dumps(dict(chat_id=int(CHAT), menu_button=dict(type="web_app", text="🎧", web_app=dict(url=url)))).encode()
                r = urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{TOKEN.decode()}/setChatMenuButton", body,
                                                                  {"Content-Type": "application/json"}), timeout=20)
                if json.load(r).get("ok"):
                    ultimo = url
        except (OSError, ValueError):
            pass  # niente file o rete assente: riprovo al giro dopo
        time.sleep(20)


def main():
    if not TOKEN or not CHAT:
        sys.exit("manca TELEGRAM_SONNO_TOKEN / TELEGRAM_CHAT")
    threading.Thread(target=pulsante_menu, daemon=True).start()
    threading.Thread(target=precarica, daemon=True).start()
    s = ThreadingHTTPServer(("127.0.0.1", PORT), H)  # solo locale: l'unica porta pubblica e' il tunnel
    s.daemon_threads = True
    print("miniapp su 127.0.0.1:%d" % PORT, flush=True)
    s.serve_forever()


if __name__ == "__main__":
    main()
