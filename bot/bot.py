"""@IlTuoBot — gira sul telefono (Termux) accanto al letto, INDIPENDENTE dal PC. stdlib + numpy (+ ffmpeg,
matplotlib e PIL per le immagini: senza, il bot va lo stesso in solo testo).
Menu: [🌙 Notte][📝 Nota][🔊 Ascolta] · [🎙️ Registra][⏸️ Pausa/▶️ Riprendi][⚙️ Stato]  (🛌 Riposo: /riposo).
Parole: SOLO da copy/testi.py. Immagini: concept/ (Toppa, carta e denim) e concept/mondo/. Note: ux/uso_quotidiano/note.py.
Onestà (ux/ONESTA.md): ogni dato dice quanto mi fido (sicuro / quasi sicuro / forse) e perché; dove serve, un
pulsante per correggerlo. Regole UX: messaggi automatici MUTI, un'azione = un messaggio che si aggiorna, mai errori
grezzi in chat, nessun messaggio all'avvio.
Sul telefono va copiata la stessa struttura di cartelle del PC (deploy.py albero).
"""
import csv, hashlib, glob, json, os, shutil, subprocess, sys, threading, time, traceback, urllib.parse, urllib.request, uuid
from datetime import date, datetime, timedelta

QUI = os.path.dirname(os.path.abspath(__file__))
for _d in ("ux/uso_quotidiano", "copy", "concept", "concept/mondo"):  # l'ultimo inserito vince: mondo > concept
    sys.path.insert(0, os.path.join(QUI, _d))
import notte
import testi as TX
import note as NOTE
import messaggi  # concept: fascia, _hm
import sorgente as SG  # chi emette il suono (telefono / io / fuori), sveglio certo, livelli dei modelli
try:
    import grafici  # matplotlib
except Exception:
    grafici = None
try:
    import messaggi_mondo as MM, grafici_mondo as GM  # PIL
except Exception:
    MM = GM = None

_env = os.path.join(QUI, ".env")
env = dict(l.strip().split("=", 1) for l in open(_env) if "=" in l) if os.path.exists(_env) else dict(os.environ)
TOKEN, CHAT = env.get("TELEGRAM_SONNO_TOKEN", ""), env.get("TELEGRAM_CHAT", "")
URL = f"https://api.telegram.org/bot{TOKEN}/"
HOME = os.path.expanduser("~")
D = os.environ.get("SONNO_DIR", os.path.join(HOME, "rec"))
CAL = os.environ.get("SONNO_CAL", os.path.join(HOME, "cal"))  # suoni etichettati (il PC li copia e allena)
F = lambda n: os.path.join(QUI, n)
NOTTI, DIARIO, GIUDIZI, NOTE_CSV = F("notti.csv"), F("diario.csv"), F("giudizi.csv"), F("note.csv")
MANDATI, ROCCHETTO, USO = F("mandati.json"), F("rocchetto.json"), F("uso.csv")  # uso.csv lo manda il PC
F_SUONI, PAUSA = F("suoni.txt"), F("PAUSA")  # PAUSA: riga 1 scadenza (o vuota), riga 2 "fuori" se dorme fuori
BASE = ["russa", "respiro", "tosse", "movimento", "voce", "sbuffo", "silenzio"]
# Per riaccenderne una: aggiungerla qui DOPO il suo si'. (mattino e clip restano: le valuta domattina)
APPROVATE = {"mattino_linea"}
TIPI_CLIP = ("russa", "voce", "tosse", "sbuffo", "finestra")
NOME_CLIP = {"russa": "russamento", "voce": "voce", "tosse": "tosse", "sbuffo": "uno sbuffo", "punto": "punto della notte", "finestra": "finestra della notte"}
MAX_REG = 60  # s: stop automatico della registrazione di un suono
TARATURA = {}  # registrazione in corso: file, lab, t0, msg
STATO_UI = {}  # contesti del testo libero: registra, aspetta_nome, nota, era (tutti con scadenza)
MESI = "gen feb mar apr mag giu lug ago set ott nov dic".split()


# ---------------------------------------------------------------- telegram
def traccia(m, k, r=None):
    """
    inviati.log (ora, metodo, id, chi l'ha chiamato, inizio del testo) per sapere QUALE funzione lo fa."""
    if not m.startswith(("send", "edit", "delete")):
        return
    try:
        res = (r or {}).get("result")
        mid = res.get("message_id") if isinstance(res, dict) else k.get("message_id", "")
        chi = " <- ".join(f.name for f in traceback.extract_stack()[-5:-2])
        testo = str(k.get("text") or k.get("caption") or k.get("media") or "")[:60].replace("\n", " | ")
        with open(F("inviati.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {m} {mid} [{chi}] {testo}\n")
    except Exception:  # noqa: BLE001 - il registro non deve mai fermare un invio
        pass


def api(m, **k):
    # dict/list/bool in JSON (Telegram vuole "true", non "True": se no 400 Bad Request)
    d = urllib.parse.urlencode({a: json.dumps(v) if isinstance(v, (dict, list, bool)) else v
                                for a, v in k.items()}).encode()
    try:
        r = json.load(urllib.request.urlopen(URL + m, data=d, timeout=70))
        traccia(m, k, r)
        return r
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{m} {e.code}: {e.read().decode(errors='replace')[:200]}") from None


def prova(m, **k):
    """Chiamata che puo' fallire senza conseguenze ("message is not modified", pulsante vecchio): mai in chat."""
    try:
        return api(m, **k)
    except Exception as e:
        log(f"{m}: {e}", rumore=True)


def log(s, rumore=False):
    """
    rumore (prova() fallite per costruzione, controlli grafici) e i problemi veri ci affogavano: il rumore va a parte."""
    open(F("rumore.log" if rumore else "errori.log"), "a").write(f"{datetime.now():%Y-%m-%d %H:%M} {s}\n")


def errore(dove, e):
    """UX 3_ERRORI: mai errori grezzi, sempre muto, al massimo uno all'ora."""
    import traceback
    tb = traceback.extract_tb(e.__traceback__)[-2:] if e.__traceback__ else []
    log(f"{dove}: {e} @ " + " <- ".join(f"{os.path.basename(x.filename)}:{x.lineno} {x.name}" for x in reversed(tb)))
    f = F("ultimo_errore.txt")
    if (not os.path.exists(f) or time.time() - os.path.getmtime(f) > 3600) and not in_silenzio():
        open(f, "w").write(str(e)[:200])
        prova("sendMessage", chat_id=CHAT, text=TX.t("all_errore"), disable_notification=True)


def menu():
    righe = [[{"text": TX.menu("riprendi" if k == "pausa" and in_pausa() else k)} for k in r] for r in TX.MENU_RIGHE]
    return {"keyboard": righe, "resize_keyboard": True, "is_persistent": True,
            "input_field_placeholder": TX.PLACEHOLDER_MENU}


def kb(*righe):
    """kb([("testo", "dati"), ("testo", "dati", "primary"), ...], ...) -> inline_keyboard. Terzo campo = colore
    (Bot API 'style': primary blu = scelto, success verde = si', danger rosso = no). Doc: tecnica/telegram_bot_api.html"""
    return {"inline_keyboard": [[{"text": b[0], "callback_data": b[1], **({"style": b[2]} if len(b) > 2 and b[2] else {})}
                                 for b in r] for r in righe if r]}


ULTIMO = {}


def scrivi(testo, tastiera=None, suono=False):
    """Muto di default (regola UX). suono=True solo per guasti di giorno.
    """
    if tastiera is None and ULTIMO and time.time() - ULTIMO["t"] < 120 and len(ULTIMO["testo"]) + len(testo) < 3800:
        unito = ULTIMO["testo"] + "\n\n" + testo
        if prova("editMessageText", chat_id=CHAT, message_id=ULTIMO["id"], text=unito, parse_mode="HTML"):
            ULTIMO.update(t=time.time(), testo=unito)
            return ULTIMO["id"]
    r = api("sendMessage", chat_id=CHAT, text=testo, parse_mode="HTML", reply_markup=tastiera or menu(),
            disable_notification=not suono)
    mid = r["result"]["message_id"]
    ULTIMO.clear()
    if tastiera is None:
        ULTIMO.update(id=mid, t=time.time(), testo=testo)
    return mid


def unico(tipo, msg):
    """(nota rimossa)"""
    u = leggi_json(F("ultimi.json"))
    if u.get(tipo) and u[tipo] != msg:
        prova("deleteMessage", chat_id=CHAT, message_id=u[tipo])
    u[tipo] = msg
    scrivi_json(F("ultimi.json"), u)


def modifica(msg, testo, tastiera=None):
    prova("editMessageText", chat_id=CHAT, message_id=msg, text=testo, parse_mode="HTML",
          **({"reply_markup": tastiera} if tastiera else {}))


def didascalia(msg, testo, tastiera=None):
    prova("editMessageCaption", chat_id=CHAT, message_id=msg, caption=testo, parse_mode="HTML",
          reply_markup=tastiera or {"inline_keyboard": []})


def max_4_5(path):
    """
    Se e' piu' alta di grafici.MAX_ALTEZZA la allargo con il colore del bordo (niente contenuto tagliato)."""
    try:
        from PIL import Image
    except Exception:
        return path
    im = Image.open(path)
    w, h = im.size
    mx = getattr(grafici, "MAX_ALTEZZA", 1.0)
    if h <= w * mx + 1:
        return path
    W = int(round(h / mx))
    fondo = im.convert("RGB").getpixel((0, 0))
    nuovo = Image.new("RGB", (W, h), fondo); nuovo.paste(im.convert("RGB"), ((W - w) // 2, 0))
    out = os.path.splitext(path)[0] + "_45.png"; nuovo.save(out)
    return out


def multipart(metodo, campi, nome, path, mime):
    return multipart_n(metodo, campi, {nome: (path, mime)})


def multipart_n(metodo, campi, file):
    """Come multipart ma con PIU' file {nome: (path, mime)} (rich message: foto + audio nello stesso messaggio)."""
    b = uuid.uuid4().hex
    corpo = b"".join(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
                     for k, v in campi.items())
    for nome, (path, mime) in file.items():
        corpo += (f"--{b}\r\nContent-Disposition: form-data; name=\"{nome}\"; filename=\"{os.path.basename(path)}\"\r\n"
                  f"Content-Type: {mime}\r\n\r\n").encode() + open(path, "rb").read() + b"\r\n"
    corpo += f"--{b}--\r\n".encode()
    req = urllib.request.Request(URL + metodo, data=corpo, headers={"Content-Type": f"multipart/form-data; boundary={b}"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=120))
        traccia(metodo, campi, r)
        return r
    except urllib.error.HTTPError as e:  # come api(): il perche' di Telegram nel log
        raise RuntimeError(f"{metodo} {e.code}: {e.read().decode(errors='replace')[:200]}") from None


def manda_file(metodo, campo, path, extra=None, mime="application/octet-stream"):
    if metodo == "sendPhoto":
        path, mime = max_4_5(path), "image/png"
    campi = {"chat_id": CHAT, "disable_notification": "true",
             **{k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in (extra or {}).items()}}
    return multipart(metodo, campi, campo, path, mime)["result"]["message_id"]


def foto(path, testo, tastiera=None):
    return manda_file("sendPhoto", "photo", path, {"caption": testo, "parse_mode": "HTML",
                                                   **({"reply_markup": tastiera} if tastiera else {})})


def cambia_media(msg, tipo, path, testo=None, tastiera=None, **media):
    """editMessageMedia: stesso messaggio, file nuovo (◀️▶️ nel rocchetto: niente 10 messaggi in chat)."""
    if tipo == "photo":
        path = max_4_5(path)
    m = {"type": tipo, "media": "attach://f", **media, **({"caption": testo, "parse_mode": "HTML"} if testo else {})}
    campi = {"chat_id": CHAT, "message_id": msg, "media": json.dumps(m),
             **({"reply_markup": json.dumps(tastiera)} if tastiera else {})}
    return multipart("editMessageMedia", campi, "f", path, {"photo": "image/png", "video": "video/mp4"}.get(tipo, "audio/mp4"))


def manda_voce(path, testo):
    """(nota rimossa)"""
    ogg = F("tmp_voce.ogg")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-c:a", "libopus", "-b:a", "32k", ogg], capture_output=True)
    manda_file("sendVoice", "voice", ogg, {"caption": testo}, "audio/ogg")


# ---------------------------------------------------------------- dati
def leggi_csv(p):
    return list(csv.DictReader(open(p, encoding="utf-8"))) if os.path.exists(p) else []


def tolte():
    """(nota rimossa)"""
    s = {}
    for n in note():
        if n["tipo"] == "notte" and n["valore"].endswith((":tolta", ":rimessa")):
            d, x = n["valore"].split(":")
            s[d] = x
    return {d for d, x in s.items() if x == "tolta"}


def storico():
    """Notti vere (senza quelle tolte): settimana, 30 giorni e orario 'solito' si basano su queste."""
    via = tolte()
    import notti_telefono
    fuori = notti_telefono.giorni_fuori(note())
    rows = {x["day"]: x for x in leggi_csv(NOTTI) if x["day"] not in via | fuori}
    telefono = {d: r for d, r in leggi_json(F("notti_telefono.json")).items()
                if d not in via and r.get("fonte") == "A56/SAA/uso"}
    telefono.update(notti_telefono.ricostruisci(F("a56_eventi_sleep.csv"), USO))
    for day, r in telefono.items():
        if day in via:
            continue
        audio = None if day in fuori else notte.analizza(D, day, pc_fn=uso_fn)
        if day in fuori or not audio or not audio.get("blocco") or audio.get("vuota"):
            rows[day] = r
    return [rows[d] for d in sorted(rows)]


def leggi_json(p):
    try:
        return json.load(open(p))
    except Exception:
        return {}


def scrivi_json(p, d):
    json.dump(d, open(p + ".tmp", "w")); os.replace(p + ".tmp", p)


def salva_notte(r):
    rows = [x for x in leggi_csv(NOTTI) if x["day"] != r["day"]]  # anche le tolte: ↩️ Annulla le rimette
    rows.append(dict(day=r["day"], inizio=r["inizio"].isoformat(), fine=r["fine"].isoformat(),
                     durata=round(r["durata"], 2), eff=round(r["eff"], 3), risvegli=len(r["risvegli"]),
                     russa_min=r["russa"], punteggio=r["punteggio"]))
    with open(NOTTI + ".tmp", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[-1])); w.writeheader(); w.writerows(rows)
    os.replace(NOTTI + ".tmp", NOTTI)  # atomico


def aggiungi_riga(path, intest, riga):
    nuovo = not os.path.exists(path)
    with open(path, "a", encoding="utf-8") as f:
        f.write((intest + "\n" if nuovo and intest else "") + riga + "\n")


def suoni():
    return [s.strip() for s in open(F_SUONI) if s.strip()] if os.path.exists(F_SUONI) else list(BASE)


def salva_suoni(lista):
    open(F_SUONI, "w").write("\n".join(lista) + "\n")


def sotto():
    """(nota rimossa)"""
    return {**SOTTO_DEFAULT, **leggi_json(F("sottocategorie.json"))}


def pulisci(t):
    """Nome di categoria/sottocategoria: minuscolo, solo lettere/numeri/_, max 20 caratteri."""
    return "".join(ch for ch in t.lower().strip().replace(" ", "_").replace("/", "_").replace("-", "_") if ch.isalnum() or ch == "_")[:20].strip("_")


def uso_fn(start, end):
    """Minuti con telefono (A56 sbloccato) o PC usati: se li usi non dormi (ONESTA: segnale forte).
    uso.csv lo scrive il PC (sonno_audio.sync); senza file = nessun minuto, la notte si fa solo con l'audio."""
    if not os.path.exists(USO):
        return frozenset()
    out = set()
    for l in open(USO):
        try:
            k = datetime.fromisoformat(l.strip().split(",")[0])  # riga: ts[,pc|a56]
        except ValueError:
            continue
        if start <= k < end:
            out.add(k)
    return frozenset(out)


def analizza(day):
    import notti_telefono
    st = storico()
    if day in notti_telefono.giorni_fuori(note()) or any(
            x["day"] == day and x.get("fonte") == "A56/SAA/uso" for x in st):
        return None  # la camera non misura questa notte; niente voto o dettagli audio finti
    r = notte.analizza(D, day, pc_fn=uso_fn, storico=st)
    # la notte "vuota" (pochi segni di persona) si butta SOLO se stessa_stanza.py dice A56 fuori per piu' di meta' notte;
    # altrimenti si tiene (vuota=True resta come dubbio, come gia' in notte.py).
    if r and r.get("vuota") and (not r.get("blocco") or fuori_stanza_quota(r["inizio"], r["fine"]) > 0.5):
        return dict(day=day, M=r["M"], blocco=None, vuota=True)
    return r


def fuori_stanza_quota(a, b):
    """Frazione di [a, b] in cui stessa_stanza.py (analisi/presenza.csv, fuori_stanza*) vede il telefono fuori camera."""
    if not a or not b or b <= a:
        return 0.0
    s = 0.0
    for x in leggi_csv(F("analisi/presenza.csv")):
        try:
            if x.get("stato", "").startswith("fuori_stanza"):
                i, f = max(a, datetime.fromisoformat(x["inizio"])), min(b, datetime.fromisoformat(x["fine"]))
                s += max(0.0, (f - i).total_seconds())
        except (KeyError, ValueError, TypeError):
            continue
    return s / (b - a).total_seconds()


def note():
    return leggi_csv(NOTE_CSV)


def nota(tipo, valore="1", ts=None):
    return NOTE.salva(NOTE_CSV, tipo, str(valore), ts)


def stato_mondo():
    """Lo stato del mondo di Toppa NON e' un file: si ricava da PAUSA + note.csv + giudizi.csv (ALLINEAMENTO)."""
    ns = note()
    via = [n["tipo"] for n in ns if n["tipo"] in ("viaggio", "tornato")]
    esami = [n["valore"] for n in ns if n["tipo"] == "esame" and len(n["valore"]) == 10]
    return dict(pausa=in_pausa(), viaggio=bool(via) and via[-1] == "viaggio", esame_fino=max(esami, default=None),
                giudizi=len(giudizi()), ultima_serie=MM.serie(storico()) if MM else 0)


# ---------------------------------------------------------------- onestà (ux/ONESTA.md)
def dubbi(r):
    """{chiave: motivo} di quello che puo' essere sbagliato stanotte, parole semplici."""
    out = {}
    if not r or not r.get("blocco"):
        return out
    dentro = [k for k in r["M"] if r["inizio"] <= k <= r["fine"]]
    rus = [k for k in dentro if r["M"][k]["russa"]]
    if rus and sum(r["M"][k]["esterno_top"] == "tv_musica" for k in rus) >= max(3, 0.2 * len(rus)):
        out["musica"] = TX.MOTIVI["musica"]
    b = MM.buco(r) if MM else None
    if b:
        out["buco"] = TX.MOTIVI["buco"].format(m=b[1])
    if r.get("vuota"):
        out["vuota"] = TX.MOTIVI["vuota"]
    if r["durata"] < 4:
        out["corta"] = TX.MOTIVI["corta"]
    if len(storico()) < 7:
        out["prime"] = TX.MOTIVI["prime"].format(n=len(storico()) + 1)
    return out


def fid_orari(dub):
    return TX.fiducia("forse", dub["vuota"]) if "vuota" in dub else \
        TX.fiducia("quasi", dub.get("buco", "")) if "buco" in dub else TX.fiducia("sicuro")


def fid_russa(dub):
    return TX.fiducia("forse", dub["musica"]) if "musica" in dub else TX.fiducia("quasi")


def sospetta(r):
    """Notte finta: >14h o blocco da bordo a bordo della finestra 18->16 (stanza vuota, provato: 22h 65/100)."""
    if not r or not r.get("blocco"):
        return False
    end = datetime.strptime(r["day"], "%Y%m%d").replace(hour=16)
    return r["durata"] > 14 or (r["inizio"] - (end - timedelta(hours=22)) < timedelta(minutes=15)
                                and end - r["fine"] < timedelta(minutes=15))


# ---------------------------------------------------------------- mattino
def ore_russate(r):
    ore = {}
    if r and r.get("blocco"):
        for k, d in r["M"].items():
            if r["inizio"] <= k <= r["fine"] and d["russa"]:
                ore[k.hour] = ore.get(k.hour, 0) + 1
    return ore


def pagine_mappa(day):
    """Pagine della mappa del russare: mappa_<giorno>.png (pagina 1) + mappa_<giorno>_pag2.png, _pag3... (kaggle_mattino)."""
    p = [F(f"mappe/mappa_{day}.png")] + [F(f"mappe/mappa_{day}_pag{i}.png") for i in range(2, 10)]
    return [x for x in p if os.path.exists(x)]


def pagine_tasti(day, pag, n):
    """
    la pagina attuale in blu (style primary). Ogni pagina della mappa = 5 h dall'inizio della notte (mappa_russare D3c)."""
    if n < 2:
        return []
    J = leggi_json(F(f"mappe/mappa_{day}.json")) or {}
    try:
        a, z = datetime.fromisoformat(J["inizio"]), datetime.fromisoformat(J["fine"])
    except (KeyError, ValueError, TypeError):
        return [(("· " if i == pag else "") + f"parte {i}/{n}", f"mp:{day}:{i}", "primary" if i == pag else None) for i in range(1, n + 1)]
    cel = next((c["celle"] for c in J.get("corsie", []) if c.get("nome") == "PANNs"), {})
    t = []
    for i in range(1, n + 1):
        da = a + timedelta(hours=5 * (i - 1)); al = min(da + timedelta(hours=5), z)
        ru = sum(1 for m, cs in cel.items() if f"{da:%Y-%m-%dT%H:%M}" <= m < f"{al:%Y-%m-%dT%H:%M}" and "russa" in cs)
        t.append((f"{da:%H:%M}-{al:%H:%M}" + (f" · russa {ru}'" if ru else ""), f"mp:{day}:{i}", "primary" if i == pag else None))
    return t


_NR = {}  # (cartella, giorno) -> (inizio, durata h) delle notti lunghe; le notti passate non cambiano


def notti_recenti(oggi=None, n=7):
    """[(inizio, durata)] delle ultime n notti di sonno lungo (>= 3 h), la piu' recente per prima."""
    oggi, out = oggi or datetime.now(), []
    for g in range(n):
        d = (oggi - timedelta(days=g)).strftime("%Y%m%d")
        if (D, d) not in _NR or g == 0:
            x = notte.analizza(D, d, pc_fn=uso_fn)
            _NR[(D, d)] = (x["inizio"], x["durata"]) if x and x.get("blocco") and not x.get("vuota") and x.get("durata", 0) >= 3 else None
        if _NR[(D, d)]:
            out.append(_NR[(D, d)])
    return out


def ultima_nota(tipo, ore=3):
    """Valore (int) dell'ultima nota di quel tipo nelle ultime `ore`, se no None."""
    lim = datetime.now() - timedelta(hours=ore)
    v = [n["valore"] for n in note() if n["tipo"] == tipo and n.get("ts", "") >= lim.isoformat(timespec="minutes")]
    return int(v[-1]) if v and v[-1].isdigit() else None


def commenta_ritmi(msg, testo, tasti, tipo, v):
    """Aggiunge al messaggio 'segnato' dove sei nei due ritmi (ritmi.commento) con le notti vere."""
    try:
        import ritmi
        nr = notti_recenti()
        c = ritmi.commento(datetime.now(), [i for i, _ in nr], [d for _, d in nr],
                           mente=v if tipo == "mente" else ultima_nota("mente"),
                           sonno=v if tipo == "sonno" else ultima_nota("sonno"),
                           stimolante=bool(ultima_nota("caffe", 4) or ultima_nota("te", 4)))
        modifica(msg, testo + "\n" + c, tasti)
    except Exception as e:  # noqa: BLE001
        log(f"commenta_ritmi: {e}")


def tastiera_report(day, votato=None, r=None, pag=1):
    """[Durata giusta][Correggi] / [Controlla 3 suoni][Tutta la notte] / voto 1-5 (estremi con la parola, test cieco
    """
    votato = votato or voto_di(day)
    voti = [({1: "1 male", 5: "5 bene"}.get(i, str(i)), f"v:{day}:{i}", "primary" if str(i) == str(votato) else None)
            for i in range(1, 6)]
    prima = [] if conferma_tua(day) == "durata" else [(TX.ui("rep_durata_giusta"), f"dg:{day}"), (TX.ui("rep_correggi"), f"rc:{day}")]
    n = len(pagine_mappa(day))
    giro = pagine_tasti(day, pag, n)
    return kb(giro, prima,[(TX.ui("rep_tre_suoni"), f"s3:{day}"), (TX.ui("rep_tutta"), f"tn:{day}")], voti,
              [(TX.ui("dettagli"), f"det:{day}"), (TX.ui("settimana"), "set")])


def categorie_notte(day, msg=None):
    """
    momenti piu' forti come pulsanti: ognuno apre 20 s di audio vero di quel momento (manda_punto)."""
    r = analizza(day)
    if not r or not r.get("blocco"):
        scrivi("Nessun sonno trovato per questa notte."); return
    sys.path.insert(0, HOME)
    import categorie as CAT  # ~/categorie.py (C:\sonno_tex): usa il dataset rec/dataset/*.npz
    da, a = r["inizio"] - timedelta(hours=1), r["fine"] + timedelta(hours=1)
    png, _ = CAT.disegna(da, a, F("categorie.png"))
    m = CAT.momenti(da, a)
    testo = "Ogni 5 secondi cosa si sente. Scuro = sicuro.\nTocca un momento per ascoltarlo."
    righe = [[(f"{nome} {t:%H:%M}", f"pt:{t:%Y%m%d%H%M}:{tipo}") for nome, tipo, t in m[i:i + 2]] for i in range(0, len(m), 2)]
    interi = [[(f"{nome} {x:%H:%M}-{y:%H:%M} intero", f"tr:{x:%Y%m%d%H%M%S}:{y:%Y%m%d%H%M%S}:0")]
              for nome, x, y in sorted(CAT.tratti(da, a), key=lambda z: z[0] not in ("Russare", "Respiro"))[:2]]
    tasti = kb(*interi, *righe, [("<< Notte", f"nt:{day}")])
    if msg:
        try:
            cambia_media(msg, "photo", png, testo, tasti); return
        except Exception as e:
            log(f"categorie stessa scheda: {e}")
    foto(png, testo, tasti)


def notte_ricca(day):
    import numpy as np
    """BOZZA (lui 30/09: "i pulsanti e i messaggi nuovi sono una figata, inizia a implementarli"): la notte come RICH
    MESSAGE (Bot API 10.1+). In cima il russare piu' forte PULITO da ascoltare subito ("voglio ascoltare io che russo
    pesantemente, e pulito ovviamente"); slideshow notte + categorie; tabella corta; tendine (tipi di suono, pausa piu'
    lunga, russare originale); pulsanti colorati sotto. Progetto completo: ux/nuvola/MESSAGGI_RICCHI.md."""
    r = analizza(day)
    if not r or not r.get("blocco"):
        scrivi("Nessun sonno trovato per questa notte."); return
    sys.path.insert(0, HOME)
    import categorie as CAT, respiro
    da, a = r["inizio"] - timedelta(hours=1), r["fine"] + timedelta(hours=1)
    tt, M, R, A = CAT.calcola(da, a)
    media = {}
    try:
        from concept.notte.notte_bot import disegna
        disegna(r, fonti_uso(), F("notte.png"))
        media["notte"] = (grafici.cornice(F("notte.png"), "La notte", F("slide_notte.png")), "photo")
    except Exception as e:
        log(f"notte_ricca immagine: {e}")
    CAT.disegna(da, a, F("categorie.png"))  # slide tutte uguali: tela 4:5, bordo, titolo (grafici.cornice)
    media["cat"] = (grafici.cornice(F("categorie.png"), "Cosa si sente, ogni 5 secondi", F("slide_cat.png")), "photo")
    md = [f"# Notte del {r['inizio']:%d/%m}"]
    rr = [i for i, (_, _, t) in enumerate(R) if t == "russa"]
    if rr and len(tt):
        k = int(np.argmax(M[rr[0]])); t = tt[k]
        x, y = t - timedelta(seconds=7.5), t + timedelta(seconds=12.5)
        if audio_tratto(x, y, True, F("forte_pulito.m4a")) and audio_tratto(x, y, False, F("forte.m4a")):
            media["forte"] = (F("forte_pulito.m4a"), "audio"); media["forte0"] = (F("forte.m4a"), "audio")
            md.append(f'![](tg://audio?id=forte "Russare piu\' forte, {t:%H:%M} - pulito, volume alzato")')
    md.append("<tg-slideshow>\n" + "\n".join(f'![](tg://photo?id={k} "{n}")' for k, n in
                                             (("notte", "La notte"), ("cat", "Cosa si sente, ogni 5 secondi")) if k in media)
              + "\n</tg-slideshow>")
    tr = [(x, y) for n, x, y in CAT.tratti(da, a) if n == "Russare"]
    pz = CAT.pause_vere(tt, M, R, respiro.pause_tra(da, a))
    md.append("| | |\n|:--|--:|\n" + f"| Dormito | {r['inizio']:%H:%M} - {r['fine']:%H:%M} |\n" +
              (f"| Russare continuo | {', '.join(f'{x:%H:%M}-{y:%H:%M}' for x, y in sorted(tr)[:3])} |\n" if tr else "") +
              (f"| Pause del respiro | {len(pz)}, la piu' lunga {max(d for _, d in pz):.0f} s |" if pz else "| Pause del respiro | nessuna |"))
    righe = {}
    for n, _, t in CAT.momenti_da(tt, M, R, per_riga=4):
        righe.setdefault(n, []).append(t)
    for t, n in A:
        if n != "Pausa":
            righe.setdefault(n, []).append(t)
    md.append("<details><summary>Tipi di suono trovati</summary>\n\n" +
              "\n".join(f"- **{n}**: {', '.join(f'{t:%H:%M}' for t in sorted(ts)[:6])}" for n, ts in righe.items()) + "\n</details>")
    try:
        tr_, P_ = CAT.grezzo(da, a)
        alb = CAT.albero(tr_, P_, CAT.labels())
        if alb:
            md.append(f"<details><summary>Tutti i suoni trovati ({CAT.conta(alb)})</summary>\n\n{CAT.albero_md(alb)}\n</details>")
    except Exception as e:
        log(f"notte_ricca albero: {e}")
    if pz:
        t, d = max(pz, key=lambda z: z[1])
        if audio_tratto(t - timedelta(seconds=8), t + timedelta(seconds=d + 8), True, F("pausa.m4a")):
            media["pausa"] = (F("pausa.m4a"), "audio")
            md.append(f"<details><summary>Ascolta la pausa piu' lunga ({d:.0f} s alle {t:%H:%M})</summary>\n\n"
                      f'![](tg://audio?id=pausa "Pausa {t:%H:%M}, 8 s prima e dopo - pulito, volume alzato")\n</details>')
    if "forte0" in media:
        md.append('<details><summary>Stesso russare, audio originale</summary>\n\n![](tg://audio?id=forte0 "Originale")\n</details>')
    tasti = kb([(f"Russare intero {x:%H:%M}-{y:%H:%M}", f"tr:{x:%Y%m%d%H%M%S}:{y:%Y%m%d%H%M%S}:1", "primary")
                for x, y in sorted(tr, key=lambda z: z[0] - z[1])[:1]] +
               ([("Solo pause", f"tr:{da:%Y%m%d%H%M%S}:{a:%Y%m%d%H%M%S}:1:pause")] if pz else []),
               [("Categorie", f"ct:{day}"), ("<< Notte", f"nt:{day}")])
    rm = {"markdown": "\n\n".join(md),
          "media": [{"id": k, "media": {"type": tipo, "media": f"attach://{k}"}} for k, (_, tipo) in media.items()]}
    multipart_n("sendRichMessage", {"chat_id": CHAT, "disable_notification": "true", "rich_message": json.dumps(rm),
                                    "reply_markup": json.dumps(tasti)},
                {k: (p, "image/png" if tipo == "photo" else "audio/mp4") for k, (p, tipo) in media.items()})


def audio_tratto(da, a, pulito, out, pezzi=None, fonte="a21s"):
    """Audio VERO da `da` ad `a` dai blocchi da 30' (anche piu' blocchi di fila). pulito: toglie il rumore di fondo
    (ronzio, rumore bianco, vibrazioni sotto 70 Hz) col filtro FFT di ffmpeg: niente modelli, l'originale resta.
    pezzi = [(inizio, fine)]: solo quei pezzi, uno dopo l'altro (video scremato)."""
    blocchi = blocchi_audio(fonte)
    righe = []
    for p0, p1 in pezzi or [(da, a)]:
        for f, t0 in blocchi:
            x, y = max(p0, t0), min(p1, t0 + timedelta(minutes=31))
            if x < y:
                righe.append(f"file '{f}'\ninpoint {(x - t0).total_seconds():.1f}\noutpoint {(y - t0).total_seconds():.1f}")
    if not righe:
        return None
    lista = F("tratto.txt"); open(lista, "w").write("\n".join(righe) + "\n")
    # dynaudnorm alza le parti deboli (respiro) senza far esplodere le forti (russare)
    filtro = ["-af", "highpass=f=70,afftdn=nf=-25:nt=w,dynaudnorm=f=250:g=15:m=20"] if pulito else []
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", lista, *filtro,
                        "-ac", "1", "-c:a", "aac", "-b:a", "64k", out], capture_output=True)
    return out if r.returncode == 0 else None


def blocchi_audio(fonte="a21s"):
    """[(file, inizio)] dei blocchi da ~30'. fonte 'pc' = registrazioni del PC copiate da sonno_audio.pc_al_telefono
    """
    if fonte == "pc":
        return [(f, datetime.strptime(os.path.basename(f)[3:18], "%Y%m%d_%H%M%S"))
                for f in sorted(glob.glob(os.path.join(D, "pc", "pc_*.m4a")))]
    fs = sorted(glob.glob(os.path.join(D, "interi", "2*.m4a")) + glob.glob(os.path.join(D, "2*.m4a")), key=os.path.basename)
    return [(f, datetime.strptime(os.path.basename(f)[:15], "%Y%m%d_%H%M%S")) for f in fs]


def copre(da, a, fonte):
    """La fonte ha audio per almeno meta' del tratto? (il pulsante PC appare solo se serve a qualcosa)"""
    s = sum(max(0, (min(a, t0 + timedelta(minutes=30)) - max(da, t0)).total_seconds()) for _, t0 in blocchi_audio(fonte))
    return s >= 0.5 * (a - da).total_seconds()


def tratto(da, a, pulito=False, msg=None, riga=None, fonte="a21s"):
    """
    audio intero; pulsanti Originale / Pulito sulla stessa scheda. riga = indice di una categoria: video SCREMATO,
    """
    sys.path.insert(0, HOME)
    import categorie as CAT
    tt, M, R, _ = CAT.calcola(da, a)
    tieni = pezzi = None
    import respiro
    pz = CAT.pause_vere(tt, M, R, respiro.pause_tra(da, a))  # solo dentro russare/respiro
    if riga == "pause":  # ogni pausa del respiro con 8 s prima e dopo: si sente il russare fermarsi e ripartire
        pezzi = [(t - timedelta(seconds=8), t + timedelta(seconds=d + 8)) for t, d in pz]
        tieni = [k for k, t in enumerate(tt) if any(x <= t < y for x, y in pezzi)]
        # pezzi ALLINEATI alle finestre da 5 s: audio e immagine devono durare uguale (la linea resta al posto giusto)
        _, pezzi = CAT.scrematura_da(tt, tieni)
    elif riga is not None:
        tieni, pezzi = CAT.scrematura(da, a, riga)
    if riga is not None and not pezzi:
        if msg is not False:
            scrivi("In quel tratto non c'e'.")
        return
    k = f"{da:%Y%m%d%H%M%S}:{a:%Y%m%d%H%M%S}"
    # Telegram li ha gia' (file_id): il pulsante risponde subito. VIDEO_V cambia se cambia il disegno.
    chiave, pronti = f"{VIDEO_V}:{k}:{int(pulito)}:{riga}" + ("" if fonte == "a21s" else f":{fonte}"), leggi_json(F("video_pronti.json"))
    voce = pronti.get(chiave)
    if not voce or not (voce.get("file_id") or os.path.exists(voce.get("mp4", ""))):
        cart = F("video_pronti"); os.makedirs(cart, exist_ok=True)
        base = os.path.join(cart, chiave.replace(":", "_"))
        audio = audio_tratto(da, a, pulito, base + ".m4a", pezzi, fonte)
        if not audio:
            if msg is not False:
                scrivi("Audio di quel tratto non disponibile.")
            return
        n = len(tieni) if tieni is not None else len(tt)
        zoom = min(10, 16000 // max(n, 1)) if n * 10 > 1080 - CAT.SX else None  # ponytail: PNG <= 16000 px di larghezza
        if len(tt):
            png, geo = CAT.disegna(da, a, base + ".png", con_geo=True, tieni=tieni, zoom=zoom)
        else:
            zoom = None
            png, geo = grafici.clip(audio, None, f"{da.day} {MESI[da.month - 1]}", f"{da:%H:%M} · {fonte.upper()}", base + ".png")
        mp4 = (grafici.clip_scorre if zoom else grafici.clip_video)(png, audio, geo, base + ".mp4")
        voce = {"mp4": mp4, **dim_video(png, 1080 if zoom else None)}
        pronti = leggi_json(F("video_pronti.json")); pronti[chiave] = voce; scrivi_json(F("video_pronti.json"), pronti)
    if msg is False:  # prepara_video: solo pronto sul telefono, niente invio
        return
    nome = "pause del respiro" if riga == "pause" else R[riga][0].lower() if riga is not None else ""
    cosa = "tutto" if riga is None else f"solo {nome}, {len(tieni) * 5 // 60} min su {int((a - da).total_seconds() // 60)}"
    if riga == "pause":
        cosa += f" ({len(pz)} pause, la piu' lunga {max(d for _, d in pz):.0f} s)"
    testo = f"Dalle {da:%H:%M} alle {a:%H:%M} · {cosa} · {'pulito, volume alzato' if pulito else 'audio originale'}"
    # callback tr:<da>:<a>:<pulito>[:<riga>[:<fonte>]] (riga vuota = tutto il tratto; fonte assente = A21s)
    cb = lambda pu, ri, fo=fonte: f"tr:{k}:{int(pu)}" + (f":{'' if ri is None else ri}:{fo}" if fo != "a21s" else f":{ri}" if ri is not None else "")
    s = cb(pulito, riga)[len(f"tr:{k}:{int(pulito)}"):]
    blu = lambda si: "primary" if si else None  # il pulsante scelto e' blu (prima: "> " davanti)
    solo = [("Solo " + n.split(" ")[0].lower(), cb(pulito, r), blu(r == riga)) for r, (n, _, _) in enumerate(R)]
    if pz:
        solo.append(("Solo pause", cb(pulito, "pause"), blu(riga == "pause")))
    fonti = [("A21s", cb(pulito, riga, "a21s"), blu(fonte == "a21s")), ("PC", cb(pulito, riga, "pc"), blu(fonte == "pc"))]         if copre(da, a, "pc") else []
    tasti = kb([("Originale", cb(False, riga), blu(not pulito)), ("Pulito", cb(True, riga), blu(pulito))], fonti,
               *[solo[i:i + 3] for i in range(0, len(solo), 3)],
               [("Tutto il tratto", cb(pulito, None), blu(riga is None))])
    extra = dict(width=voce["width"], height=voce["height"], supports_streaming=True)
    fid, m = voce.get("file_id"), None
    if msg:
        try:
            m = (api("editMessageMedia", chat_id=CHAT, message_id=msg, reply_markup=tasti,
                     media={"type": "video", "media": fid, "caption": testo, **extra}) if fid
                 else cambia_media(msg, "video", voce["mp4"], testo, tasti, **extra))
        except Exception as e:
            log(f"tratto stessa scheda: {e}")
    if not m:
        m = (api("sendVideo", chat_id=CHAT, video=fid, caption=testo, reply_markup=tasti, disable_notification=True, **extra)
             if fid else multipart("sendVideo", {"chat_id": CHAT, "disable_notification": "true", "caption": testo,
                                                 "reply_markup": json.dumps(tasti), **{x: str(v).lower() for x, v in extra.items()}},
                                   "video", voce["mp4"], "video/mp4"))
    if not fid and isinstance(m.get("result"), dict) and m["result"].get("video"):
        pronti = leggi_json(F("video_pronti.json"))
        pronti.setdefault(chiave, voce)["file_id"] = m["result"]["video"]["file_id"]
        scrivi_json(F("video_pronti.json"), pronti)


VIDEO_V = "v1"  # cambia quando cambia il disegno dei video: quelli pronti si rifanno


def prepara_video(day):
    """
    originale + pause della notte, gia' pronti la mattina. Niente invio (msg=False)."""
    try:
        r = analizza(day)
        sys.path.insert(0, HOME)
        import categorie as CAT
        da, a = r["inizio"] - timedelta(hours=1), r["fine"] + timedelta(hours=1)
        for n, x, y in sorted(CAT.tratti(da, a), key=lambda z: z[0] != "Russare")[:1]:
            tratto(x, y, True, False); tratto(x, y, False, False)
        tratto(da, a, True, False, "pause")
    except Exception as e:
        log(f"prepara_video: {e}")


def firma_scheda(testo, tasti, png):
    """(nota rimossa)"""
    import hashlib
    h = hashlib.md5((testo + json.dumps(tasti, sort_keys=True)).encode())
    if png and os.path.exists(png):
        h.update(open(png, "rb").read())
    return h.hexdigest()


IN_FONDO = [False]  # True mentre si risponde al tasto Notte del menu: la scheda va riportata in fondo alla chat


def scheda_notte(testo, tasti, day, msg=None, png=None):
    """Una scheda principale persistente; nessuna grafica alternativa al renderer approvato."""
    st = leggi_json(F("scheda_notte.json"))
    precedente = st.get("msg")
    fi = firma_scheda(testo, tasti, png)
    if IN_FONDO[0] and precedente:
        prova("deleteMessage", chat_id=CHAT, message_id=precedente)
        st, precedente, msg = {}, None, None
    if st.get("day") == day and st.get("firma") == fi and precedente and msg in (None, precedente):
        return precedente  # identica a quella che c'e' gia' in chat
    # mai -> notte nuova = scheda nuova in fondo alla chat; modifica fallita = scheda nuova, mai report perso
    msg = msg or (precedente if st.get("day") == day else None)
    fatto = False
    if msg and msg == precedente and (st.get("foto") or not png):
        try:
            if png:
                cambia_media(msg, "photo", png, testo, tasti)
            elif st.get("foto"):
                didascalia(msg, testo, tasti)
            else:
                modifica(msg, testo, tasti)
            fatto = True
        except Exception as e:
            log(f"scheda_notte stessa scheda: {e}")
    if not fatto:
        nuovo = foto(png, testo, tasti) if png else scrivi(testo, tasti)
        if precedente:
            prova("editMessageReplyMarkup", chat_id=CHAT, message_id=precedente,
                  reply_markup={"inline_keyboard": []})
        msg = nuovo
        st["foto"] = bool(png)
    st.update(msg=msg, day=day, firma=fi, testo=testo, tasti=json.dumps(tasti, sort_keys=True))
    scrivi_json(F("scheda_notte.json"), st)
    return msg


def voto_di(day):
    v = [x["voto"] for x in leggi_csv(DIARIO) if x["day"] == day]
    return v[-1] if v else None


def conferma_tua(day):
    """(nota rimossa)"""
    v = [n["valore"] for n in note() if n["tipo"] == "notte" and n["valore"].startswith((f"{day}:durata_ok", f"{day}:inizio:"))]
    return ("durata" if v[-1].endswith(":durata_ok") else "inizio") if v else ""  # l'ultima conferma vince


def applica_inizio(r, day):
    """(nota rimossa)"""
    sc = [n["valore"].split(":")[2] for n in note() if n["tipo"] == "notte" and n["valore"].startswith(f"{day}:inizio:")]
    if not (r and r.get("blocco") and sc):
        return r
    k = r["inizio"].replace(hour=int(sc[-1][:2]), minute=int(sc[-1][2:]))
    k -= timedelta(days=1) if k > r["fine"] else timedelta()
    return dict(r, inizio=k, durata=(r["fine"] - k).total_seconds() / 3600 - r.get("pausa", 0) / 60)


def russa_sonno(r):
    """(nota rimossa)"""
    g = giudizi()
    c = [p for p in tutte_clip() if os.path.basename(p).startswith("russa_")
         and r["inizio"] <= quando_clip(os.path.basename(p)) <= r["fine"]]
    return c, sum(os.path.basename(p) in g for p in c)


def periodi_russare(r):
    """MAPPA DEL RUSSARE (priorita' n.1 dell'utente): [(da, a)] dei periodi in cui ha russato, dentro la notte, dal JSON che
    il PC copia in ~/sonno_bot/mappe/ (sonno_tex/mappa_russare.py sul PC). Solo certezza >= 2 (un modello, PANNs/EfficientAT
    d'accordo, o tuo giudizio): 'solo YAMNet' resta nel JSON ma non nel report. Nessun file = niente riga.
    ponytail: max 8 periodi (i piu' sicuri, poi i piu' lunghi), in ordine di orario."""
    try:
        J = json.load(open(F(f"mappe/mappa_{r['day']}.json"), encoding="utf-8"))
        per = [(datetime.fromisoformat(p["da"]), datetime.fromisoformat(p["a"]), p["certezza"], p["minuti"]) for p in J["periodi"]
               if p["certezza"] >= 2]
    except (OSError, ValueError, KeyError):
        return []
    per = [p for p in per if p[1] > r["inizio"] and p[0] < r["fine"]]
    return sorted(p[:2] for p in sorted(per, key=lambda p: (-p[2], -p[3]))[:8])


_INIZI = {}  # (cartella, day) -> inizio del sonno o None; le notti passate non cambiano


def letto_prev(r, day):
    """
    ponytail: cache per processo; il primo giro analizza 13 notti (minuti() legge tutti i csv): lento sull'A21s una volta."""
    via, g0, inizi = tolte(), datetime.strptime(day, "%Y%m%d"), [(0, r["inizio"])] if r.get("blocco") and r.get("durata", 0) >= 3 else []
    for g in range(1, 14):
        d = (g0 - timedelta(days=g)).strftime("%Y%m%d")
        if (D, d) not in _INIZI:
            x = notte.analizza(D, d, pc_fn=uso_fn)
            _INIZI[(D, d)] = x["inizio"] if x and x.get("blocco") and not x.get("vuota") and x.get("durata", 0) >= 3 else None
        if _INIZI[(D, d)] and d not in via:
            inizi.append((g, _INIZI[(D, d)]))
    return notte.previsione_letto(inizi)


def testo_report(r, day, in_corso=False):
    r = applica_inizio(r, day)
    if not in_corso and r.get("blocco"):
        fu = fonti_uso()
        r = dict(r, sveglie=notte.risvegli_uniti(r.get("risvegli", []), r.get("brevi", []),
                                                 lambda k: "PC" if fu.get(k) == "pc" else "telefono"),
                 letto_prev=letto_prev(r, day))
    c, g = russa_sonno(r)
    per = periodi_russare(r)
    t = TX.notte_report(r, len(c), g, dubbi(r), in_corso, conferma_tua(day),
                        TX.ui("rep_periodi", periodi=", ".join(f"{a:%H:%M}-{b:%H:%M}" for a, b in per)) if per else "")
    if not c and r.get("russa") and not in_corso:  # colpi nell'audio ma nessuna clip: lo dice, non "non rilevato"
        t = t.replace(TX.ui("rep_russa_no"), TX.ui("rep_russa_min", m=r["russa"]))
    if not in_corso and r.get("blocco"):
        try:
            import musica
            mus = musica.riassunto_notte(F("media_a56.csv"), F("musica_eventi.csv"), r["inizio"], r["fine"])
        except Exception as e:  # noqa: BLE001
            log(f"riga musica: {e}")
            mus = ""
        if mus:
            righe = t.split("\n")
            righe.insert(len(righe) - 1 if r.get("letto_prev") and len(righe) > 1 else len(righe), mus)
            t = "\n".join(righe)
    return t


def mappa_png(day):
    """(percorso, firma) del PNG della mappa del russare che il PC copia in ~/sonno_bot/mappe/ (mappa_russare.py); (None, "") se non c'e'."""
    p = F(f"mappe/mappa_{day}.png")
    if not os.path.exists(p):
        return None, ""
    return p, hashlib.md5(open(p, "rb").read()).hexdigest()


def manda_notte(r, day, msg=None, in_corso=False):
    """Un solo messaggio per notte (scheda_notte lo aggiorna; identica = non si tocca): orari veri, risvegli brevi."""
    r = applica_inizio(r, day)
    didasc = testo_report(r, day, in_corso)
    tasti_ = kb() if in_corso else tastiera_report(day, r=r)
    st = leggi_json(F("scheda_notte.json"))
    mp, mfi = mappa_png(day) if not in_corso else (None, "")
    if not IN_FONDO[0] and st.get("day") == day and st.get("msg") and msg in (None, st["msg"]) and st.get("testo") == didasc \
            and st.get("tasti") == json.dumps(tasti_, sort_keys=True) and st.get("mappa", "") == mfi:
        return st["msg"]  # stessa cosa gia' in chat: niente disegno, niente invio (resta zitta se si riaddormenta)
    if mp:  # mappa del russare approvata (stile righe): al posto della linea, STESSA scheda (editMessageMedia, sendPhoto mai documento)
        m = scheda_notte(didasc, tasti_, day, msg, mp)
        st = leggi_json(F("scheda_notte.json")); st["mappa"] = mfi; scrivi_json(F("scheda_notte.json"), st)
        return m
    png = F("notte.png")
    if "mattino_linea" in APPROVATE:
        try:
            from concept.notte.notte_bot import disegna
            disegna(r, fonti_uso(), png)
        except Exception as e:
            log(f"grafico mattino: {e}")
        else:
            return scheda_notte(didasc, tasti_, day, msg, png)
    return scheda_notte(didasc, tasti_, day, msg)


def curiosita(r, day):
    """UNA cosa notata stanotte, con quanto e' provata (🧪 teoria, 🔬 in prova, ✅ provato). Ruota per giorno tra
    quelle che hanno dati; None se non c'e' niente di vero da dire (allora resta la domanda del voto)."""
    if not r or not r.get("blocco"):
        return None
    M, a, z = r["M"], r["inizio"], r["fine"]
    idee = []
    usati = [k for k in sorted(M) if M[k].get("pc") and a - timedelta(hours=3) <= k < a]
    if usati:  # telefono -> sonno: segnale certo (uso) ma la regola e' ancora da vedere su molte notti
        idee.append(TX.t("cur_telefono", mat=TX.MATURITA["prova"], m=int((a - usati[-1]).total_seconds() // 60)))
    ore = ore_russate(r)
    if ore:
        h, m = max(ore.items(), key=lambda x: x[1])
        idee.append(TX.t("cur_russa_ora", mat=TX.MATURITA["prova"], h=f"{h:02d}", m=m))
    if r.get("diff") is not None and abs(r["diff"]) >= 0.75:  # orari: e' solo aritmetica sugli orari = provato
        idee.append(TX.t("cur_solito", mat=TX.MATURITA["provato"], h=f"{abs(r['diff']):.1f}h".replace(".", ","),
                         verso="dopo" if r["diff"] > 0 else "prima del"))
    mus = sum(1 for k in M if a <= k <= z and M[k]["russa"] and M[k]["esterno_top"] == "tv_musica")
    if mus >= 3:  # russare vs musica: pura teoria finche' non separiamo le due cose (beamforming)
        idee.append(TX.t("cur_musica", mat=TX.MATURITA["teoria"], m=mus))
    if not idee:
        return None
    return idee[int(day) % len(idee)]


def conto(*tipi):
    """(nota rimossa)"""
    g = n = 0
    for t in tipi:
        a, b = verificati(t); g += a; n += b
    return f" · {TX.t('verificato', g=g, n=n)}" if n else ""


def testo_dettagli(r, day):
    """Quattro righe; gli orari dei singoli eventi restano nei pulsanti."""
    telefono = testo_notte_telefono(day)
    if telefono:
        return telefono
    if not r:
        return TX.ui("dettagli_vuoti")
    if not r.get("blocco"):
        return TX.ui("dettagli_sonno")
    dub = dubbi(r)
    motivi = [dub[k] for k in ("musica", "buco", "vuota", "corta") if k in dub]
    testo = TX.ui("dettagli_riga", inizio=f"{r['inizio']:%H:%M}", fine=f"{r['fine']:%H:%M}",
                  durata=TX.durata(r["durata"]), audio=TX.durata(r["ore_audio"]), russa=r["russa"],
                  fiducia="bassa" if motivi else "stima da audio",
                  dubbi="; ".join(motivi[:2]) or TX.ui("dettagli_limite"))
    return testo + conto("sonno", "sveglio", "letto", "alzato", "russa", "musica", "respiro")


def intervalli(minuti):
    """(nota rimossa)"""
    out = []
    for k in minuti:
        if out and k - out[-1][1] <= timedelta(minutes=2):
            out[-1][1] = k
        else:
            out.append([k, k])
    return [f"{a:%H:%M}" + (f"–{b:%H:%M}" if b > a else "") for a, b in out]


# ---------------------------------------------------------------- verifica per punti
PUNTI = {"ora": "cosa si sente", "letto": "a letto", "alzato": "in piedi", "sonno": "addormentato", "sveglio": "sveglio", "risveglio": "svegliato",
         "mosso": "mosso", "russa": "russa", "respiro": "respiro", "musica": "musica", "esterno": "rumore", "buco": "buco",
         "voce": "voce", "tosse": "tosse"}
VERIFICHE = F("verifiche.csv")


def fonti_uso():
    """{minuto: 'pc'|'a56'} da uso.csv (il PC la scrive; righe vecchie senza fonte = 'a56')."""
    out = {}
    if os.path.exists(USO):
        for l in open(USO):
            p = l.strip().split(",")
            try:
                out[datetime.fromisoformat(p[0])] = p[1] if len(p) > 1 else "a56"
            except ValueError:
                pass
    return out


def letto(r, fonte=False):
    """A letto = dopo l'ultimo uso del PC (scrivania) prima di addormentarsi, entro 4h; se il PC non c'e', dopo
    l'ultimo uso del telefono (che pero' si usa anche a letto). Deduzione: 🔬. fonte=True -> (istante, 'pc'|'a56')."""
    f = fonti_uso()
    u = [k for k in sorted(f) if r["inizio"] - timedelta(hours=4) <= k < r["inizio"]]
    pc = [k for k in u if f[k] == "pc"]
    k = (pc or u or [None])[-1]
    t = k + timedelta(minutes=1) if k else None
    return (t, "pc" if pc else "a56") if fonte else t


def alzato(r):
    """In piedi = primo uso del PC dopo il risveglio (entro 3h). Il telefono no: si usa anche a letto."""
    f = fonti_uso()
    pc = [k for k in sorted(f) if f[k] == "pc" and r["fine"] <= k <= r["fine"] + timedelta(hours=3)]
    return pc[0] if pc else None


SOGLIA_MOV = 50


def movimenti(r):
    """{minuto: mov} dall'accelerometro del telefono nel letto (A56), se il PC l'ha mandato; se no {}."""
    out = {}
    for x in leggi_csv(F("movimenti.csv")):
        try:
            k = datetime.fromisoformat(x["t"])
        except (ValueError, KeyError):
            continue
        if r["inizio"] <= k <= r["fine"]:
            out[k] = float(x["mov"])
    return out


def mossi(r):
    """Mosso = movimento BREVE che non e' un risveglio. Regola sua: movimenti continui = sveglio, pochi ogni tanto
    = mosso ma dorme. Se c'e' l'accelerometro (A56 nel letto) uso quello, se no i picchi dell'audio."""
    mv = movimenti(r)
    if mv:
        su = {k for k, v in mv.items() if v > SOGLIA_MOV}
        return sorted(k for k in su if not ({k - timedelta(minutes=1), k + timedelta(minutes=1)} & su))
    M = r["M"]
    dentro = [k for k in sorted(M) if r["inizio"] <= k <= r["fine"]]
    return [k for k in dentro if M[k]["picchi"] >= 4 and not M[k]["sveglio"]] or \
        [k for k in dentro if M[k]["picchi"] >= 2 and not M[k]["sveglio"]]


def punti(r):
    """I punti della notte da poter riascoltare: [(istante, tipo)] — uno per risultato e uno per classe di suono,
    cosi' giudica se ho classificato bene (russa, respiro, musica, rumori esterni) e se ha senso quando dico letto/mosso."""
    if not r or not r.get("blocco"):
        return []
    M, a, z = r["M"], r["inizio"], r["fine"]
    dentro = [k for k in sorted(M) if a <= k <= z]
    out = [(a, "sonno"), (z, "sveglio")] + [(k, "risveglio") for k in r["risvegli"][:1]]
    if letto(r):
        out.append((letto(r), "letto"))
    if alzato(r):
        out.append((alzato(r), "alzato"))
    if mossi(r):
        out.append((mossi(r)[0], "mosso"))
    if dentro and max(M[k]["respiro"] for k in dentro) > 0:
        out.append((max(dentro, key=lambda k: M[k]["respiro"]), "respiro"))
    mus = [k for k in dentro if M[k]["esterno_top"] == "tv_musica"]
    if mus:
        out.append((mus[0], "musica"))
    est = [k for k in dentro if M[k]["esterno_top"] and M[k]["esterno_top"] != "tv_musica"]
    if est:
        out.append((est[0], "esterno"))
    rus = sorted(k for k in r["M"] if r["inizio"] <= k <= r["fine"] and r["M"][k]["russa"])
    if rus:
        h = max(ore_russate(r).items(), key=lambda x: x[1])[0]
        out.append((next(k for k in rus if k.hour == h), "russa"))
    b = MM.buco(r) if MM else None
    if b:
        out.append((b[0], "buco"))
    return sorted(out)[:10]


def verificati(tipo):
    """(giusti, totale) delle sue verifiche su quel tipo di punto: la fiducia misurata sui risultati."""
    v = [x for x in leggi_csv(VERIFICHE) if x["tipo"] == tipo]
    return sum(x["giusto"] == "1" for x in v), len(v)


def pezzo_a(t, secondi=20):
    """20 s di audio VERO attorno all'istante t, dai pezzi interi da 30' (~/rec/interi) o dal blocco in corso."""
    fs = sorted(glob.glob(os.path.join(D, "interi", "2*.m4a")) + glob.glob(os.path.join(D, "2*.m4a")),
                key=os.path.basename)
    scelto = None
    for f in fs:
        t0 = datetime.strptime(os.path.basename(f)[:15], "%Y%m%d_%H%M%S")
        if t0 <= t:
            scelto = (f, t0)
    if not scelto or (t - scelto[1]).total_seconds() > 31 * 60:
        return None
    out = F("punto.m4a")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(max((t - scelto[1]).total_seconds() - 5, 0)), "-t",
                    str(secondi), "-i", scelto[0], "-c", "copy", out], capture_output=True)
    return out if os.path.exists(out) and os.path.getsize(out) > 1000 else None


def dividi(path):
    """Divisione secondo per secondo col modello della notte (sonno_tel, stesso di tutte le clip)."""
    try:
        sys.path.insert(0, HOME)
        import sonno_tel
        c = sonno_tel.classifica(path)
        return sonno_tel.pezzi([sonno_tel.etichetta_frame(c[5], c[0], j) for j in range(len(c[0]))]) if c else ""
    except Exception as e:
        log(f"divisione: {e}")
        return ""


def con_categorie(p, txt):
    """
    (YAMNet) si aggiungono quelle di EfficientAT calcolate sulla clip stessa (C:/sonno_tex/categorie.py)."""
    try:
        sys.path.insert(0, HOME)
        import categorie as CAT
        return " · ".join(x for x in (txt, CAT.divisione_file(p)) if x)
    except Exception as e:
        log(f"categorie clip: {e}")
        return txt


def livelli_categorie(p, txt):
    """
    basso (YAMNet, .txt) grigio chiaro, medio (EfficientAT sulla clip) grigio scuro sopra. Colori da modelli.json."""
    n = os.path.basename(p)
    alto = ""
    try:
        sys.path.insert(0, HOME)
        import categorie as CAT
        alto = CAT.divisione_file(p)
    except Exception as e:
        log(f"categorie clip: {e}")
    DUE_LIVELLI.discard(n)
    if txt and alto:
        DUE_LIVELLI.add(n)
    return [(txt, LIV["YAMNet"][1]), (alto, LIV["EfficientAT"][1])]


PUNTO_SUONO = ("ora", "russa", "respiro", "musica", "esterno", "voce", "tosse")  # punti che chiedono "che suono e'?"; gli altri (letto, sonno...) sono stati: si/no


def clip_punto(t, tipo, p, div):
    """I 20 s del punto come CLIP vera (punto_AAAAMMGG_HHMM.m4a + .tipo + .txt): stessa card, stessa tastiera completa
    """
    out = os.path.join(D, f"punto_{t:%Y%m%d_%H%M}.m4a")
    shutil.copy(p, out)
    open(out[:-4] + ".tipo", "w", encoding="utf-8").write(tipo)
    if div:
        open(out[:-4] + ".txt", "w", encoding="utf-8").write(div)
    PRONTA.pop(os.path.basename(out), None)
    return out


def manda_punto(t, tipo):
    p = pezzo_a(t)
    ora = f"{t:%H:%M}"
    if not p:
        scrivi(TX.t("punto_manca", ora=ora)); return
    div = dividi(p)
    if tipo in PUNTO_SUONO:
        return mostra_clip(clip_punto(t, tipo, p, div))
    g, n = verificati(tipo)
    fid = TX.fiducia("forse", TX.MOTIVI["musica"]) if "musica" in div else TX.fiducia("quasi")
    png, geo = grafici.clip(p, con_categorie(p, div) or None, f"{t.day} {MESI[t.month - 1]}", f"{ora} · {PUNTI[tipo]}?", F("punto.png"),
                            TX.t("verificato", g=g, n=n) if n else None, fid_parole(fid))
    mp4 = grafici.clip_video(png, p, geo, F("punto.mp4"))
    testo = TX.t("punto", ora=ora, cosa=PUNTI[tipo]) + " " + fid
    tasti = kb([(TX.b("punto_si"), f"pv:{tipo}:1:{t:%Y%m%d%H%M}", "success"), (TX.b("punto_no"), f"pv:{tipo}:0:{t:%Y%m%d%H%M}", "danger")])
    if mp4:
        manda_file("sendVideo", "video", mp4, {"caption": testo, "parse_mode": "HTML", "reply_markup": tasti,
                                               **dim_video(png), "supports_streaming": True}, "video/mp4")
    else:
        foto(png, testo, tasti)


def tastiera_punti(r):
    b = [(TX.ui("punto", ora=f"{t:%H:%M}", cosa=PUNTI[tipo]), f"pt:{t:%Y%m%d%H%M}:{tipo}") for t, tipo in punti(r)]
    return [b[i:i + 2] for i in range(0, len(b), 2)]


def tastiera_dettagli(r, day):
    return kb(*tastiera_punti(r), [(TX.ui("notte"), f"nt:{day}")],
              [(TX.ui("settimana"), "set"), (TX.ui("non_era_notte"), f"nn:{day}")])


def dettagli(day, msg=None):
    """Stessa scheda della notte, poche righe; orari consultabili sui pulsanti."""
    r = analizza(day)
    return scheda_notte(testo_dettagli(r, day), tastiera_dettagli(r, day), day, msg)


def testo_notte_telefono(day):
    r = next((x for x in storico() if x["day"] == day and x.get("fonte") == "A56/SAA/uso"), None)
    if r:
        return TX.t("notte_telefono", durata=TX.durata(float(r["durata"])),
                    inizio=r["inizio"][11:16], fine=r["fine"][11:16])
    return ""


def settimana(q=None):
    st = storico()
    if len(st) < 3:
        return TX.toast("settimana_poche") if q else scrivi(TX.toast("settimana_poche"))
    if any(x.get("fonte") == "A56/SAA/uso" for x in st[-7:]):
        rs = st[-7:]
        scrivi(TX.t("settimana_mista", n=len(rs),
                    media=TX.durata(sum(float(x["durata"]) for x in rs)/len(rs))))
        return ""  # grafici audio/SRI non rappresentano i buchi del telefono
    testo, _ = MM.settimana(st) if MM else (messaggi.trend(st, grafici.sri(st) if grafici else None), None)
    if "settimana" not in APPROVATE:
        scrivi(TX.ascii_(testo))
        return ""
    try:
        png = GM.cartolina(st, F("settimana.png"), stato_mondo()) if GM else grafici.trend(st, F("settimana.png"), 7)
        foto(png, testo, kb([(TX.b("mese"), "mese")]) if "mese" in APPROVATE else None)
    except Exception as e:
        log(f"settimana: {e}")
        scrivi(testo)
    return ""


def pausa_nella_notte(day):
    end = datetime.strptime(day, "%Y%m%d").replace(hour=16)
    return in_pausa() or any(n["tipo"] in ("pausa", "fuori") and end - timedelta(hours=40) <= datetime.fromisoformat(n["ts"]) < end
                             for n in note())


def pisolino(r):
    """Sonno che INIZIA di giorno (08-18) e dura < 5 h: pisolino (o stanza vuota), non una notte -> niente mattino
    """
    return bool(r and r.get("blocco") and 8 <= r["inizio"].hour < 18 and r["durata"] < 5)


def candidati_inizio(r):
    """
    non digita): ultimo uso telefono/PC, fine della voce, silenzio (stima del bot), Sleep as Android (live.json)."""
    a, M, out = r["inizio"], r["M"], []
    f = fonti_uso()
    u = [k for k in f if a - timedelta(hours=3) <= k < a]
    if u:
        out.append((max(u), TX.ui("cand_pc" if f[max(u)] == "pc" else "cand_telefono")))
    v = [k for k in M if a - timedelta(hours=1) <= k < a and M[k]["voce"] >= 10]
    if v:
        out.append((max(v), TX.ui("cand_voce")))
    out.append((a, TX.ui("cand_stima")))
    for ts, ev in leggi_json(F("live.json")).get("saa", []):
        t = datetime.fromisoformat(ts).replace(second=0)
        if ev == "deep_sleep" and a - timedelta(minutes=30) <= t <= a + timedelta(minutes=90):
            out.append((t, TX.ui("cand_saa"))); break
    visti, res = set(), []
    for t, p in sorted(out):
        if f"{t:%H%M}" not in visti:
            visti.add(f"{t:%H%M}"); res.append((t, p))
    return res[:5]


def tre_suoni(r):
    """
    ne sono, il tipo piu' frequente) non giudicate; 1) la piu' sicura per i modelli, 2) una dove i modelli litigano
    (fid 'forse'), 3) la piu' lontana nel tempo dalle altre. Nomi file."""
    if not r or not r.get("blocco"):
        return []
    g = giudizi()
    c = [p for p in tutte_clip() if r["inizio"] <= quando_clip(os.path.basename(p)) <= r["fine"]]
    tipi = [os.path.basename(p).split("_")[0] for p in c]
    tipo = "russa" if "russa" in tipi else max(set(tipi), key=tipi.count, default=None)
    c = [p for p in c if os.path.basename(p).startswith(tipo or "-") and os.path.basename(p) not in g]
    conf = lambda p: max(_num(p, ".eff") or 0, _num(p, ".panns") or 0)
    scelte = sorted(c, key=conf, reverse=True)[:1]
    scelte += [p for p in c if p not in scelte and "forse" in fid_clip(p)[1]][:1]
    resto = [p for p in c if p not in scelte]
    if resto and scelte:  # la piu' lontana (minimo scarto) dalle scelte
        scelte.append(max(resto, key=lambda p: min(abs((quando_clip(os.path.basename(p)) - quando_clip(os.path.basename(x))).total_seconds())
                                                  for x in scelte)))
    return [os.path.basename(p) for p in (scelte or resto)[:3]]


def report_automatico():
    """Notte finita da >=45': foto + voto (muto). Notti senza dati: regola a 3 casi (ALLINEAMENTO punto 1)."""
    fatti, mandati = {x["day"]: x for x in storico()}, leggi_json(MANDATI)
    archivio = leggi_json(F("notti_telefono.json"))
    archivio.update({d:r for d,r in fatti.items() if r.get("fonte") == "A56/SAA/uso"})
    if archivio:
        scrivi_json(F("notti_telefono.json"), archivio)
    for d in (datetime.now() - timedelta(days=1), datetime.now()):
        day = d.strftime("%Y%m%d")
        r = analizza(day)
        chiusa = datetime.now() >= datetime.strptime(day, "%Y%m%d").replace(hour=16)
        if pisolino(r):
            continue
        if r and r.get("blocco") and not sospetta(r):
            if day in fatti and r["durata"] - float(fatti[day]["durata"]) < 1:
                # gia' mandata (una notte a pezzi con un sonno piu' lungo di >=1h si rimanda); il resto dell'audio
                # arrivato dopo ("Elaborato fino a") aggiorna la STESSA scheda, solo se il testo cambia
                vecchio = mandati.get("el_" + day)  # l'ultimo "elaborato fino a" mostrato
                if vecchio and vecchio != r["elaborato"].isoformat() and r["fine"] - datetime.fromisoformat(vecchio) > timedelta(minutes=2):
                    manda_notte(r, day); mandati["el_" + day] = r["elaborato"].isoformat(); scrivi_json(MANDATI, mandati)
                elif mappa_png(day)[1] != leggi_json(F("scheda_notte.json")).get("mappa", "") and leggi_json(F("scheda_notte.json")).get("day") == day:
                    manda_notte(r, day)  # e' arrivata (o cambiata) la mappa del russare: la scheda si aggiorna sul posto
                continue
            if r["confermata"]:  # veglia sostenuta vista da PC/telefono: la notte e' finita, bastano 5'
                if datetime.now() - r["fine"] < timedelta(minutes=5):
                    continue
            elif datetime.now() - r["fine"] < timedelta(minutes=45) or \
                    (max(r["M"]) - r["fine"] < timedelta(minutes=30) and not chiusa):
                # notte non ancora finita. Dopo un risveglio breve (>=2h di sonno prima) la scheda dice "in corso",
                # una volta; se si riaddormenta resta zitta (firma uguale = nessuna modifica)
                if r["brevi"] and r["brevi"][0] - r["inizio"] >= timedelta(hours=2) and day not in mandati:
                    manda_notte(dict(r, durata=(r["brevi"][0] - r["inizio"]).total_seconds() / 3600), day, in_corso=True)
                continue
            manda_notte(r, day)
            mandati["el_" + day] = r["elaborato"].isoformat()
            import threading  # video principali pronti prima che li apra (ponytail: json condiviso senza lock)
            threading.Thread(target=prepara_video, args=(day,), daemon=True).start()
            salva_notte(r)  # DOPO l'invio: se manca la rete ci riprova al giro dopo
            mandati[day] = "notte"
            if d.weekday() == 0 and not mandati.get("sett_" + day):  # lunedi': la cartolina della settimana
                settimana(); mandati["sett_" + day] = 1
            scrivi_json(MANDATI, mandati)
            continue
        if not chiusa or day in mandati or day in fatti:
            continue
        if pausa_nella_notte(day):
            mandati[day] = "pausa"
        elif r is None:
            # Decisione 5: l'assenza dati la gestisce freschezza, dopo recupero e con limite orario.
            mandati[day] = "no_audio"
        else:  # audio ma niente sonno, o notte sospetta: MAI il grafico finto, una domanda
            testo = TX.t("notte_sospetta", day)
            tasti = kb([(TX.b(f"nd_{x}"), f"nd:{day}:{x}") for x in ("fuori", "bianco", "dormito")])
            try:
                png = GM.disegna("stato_vuoto", None, storico(), stato_mondo(), F("vuota.png"),
                                 quando=datetime.strptime(day, "%Y%m%d"), sotto="audio sì, nessun sonno vero")
                foto(png, testo, tasti)
            except Exception as e:
                log(f"card vuota: {e}")
                scrivi(testo, tasti)
            mandati[day] = "sospetta"
        scrivi_json(MANDATI, mandati)


# ---------------------------------------------------------------- rocchetto (🔊 Ascolta): card clip ◀️▶️
CLIP_SILENZIO = ("20260930_0855", "20261001_2210")  # microfono silenziato da Android = silenzio digitale: non si mostra
FINESTRA_S = 19  # durata vera >= 19 s = finestra da ~20 s (taglio fisso vecchio o voce al tetto); sotto = tagliata sull'evento
DURATE = F("durate_clip.json")  # cache ffprobe {clip: secondi}
_dur = {"v": None, "sporca": False}


def durata_clip(p):
    """Secondi veri del file (ffprobe), in cache su disco: non si rifa' a ogni giro. None = ffprobe non risponde."""
    n = os.path.basename(p)
    if _dur["v"] is None:
        _dur["v"] = leggi_json(DURATE)
    if n not in _dur["v"]:
        try:
            _dur["v"][n] = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p],
                                                capture_output=True, text=True, timeout=20).stdout)
            _dur["sporca"] = True
        except (ValueError, OSError, subprocess.SubprocessError):
            return None
    return _dur["v"][n]


def finestra(p):
    """True = clip da ~20 s (l'utente mette i suoni in ORDINE); False = tagliata sull'evento (un tasto)."""
    if os.path.basename(p).startswith("finestra_"):
        return True  # finestra_AAAAMMGG_HHMMSS.m4a: 20 s dai periodi candidati della mappa (preparate da un altro agente)
    if os.path.basename(p).startswith("punto_"):
        return False  # un punto della notte e' UN evento: un tasto (come le clip tagliate sull'evento)
    d = durata_clip(p)
    return d >= FINESTRA_S if d is not None else os.path.basename(p).split("_", 1)[1][:13] < "20260929_1500"


def tutte_clip():
    """(nota rimossa)"""
    c = [p for t in TIPI_CLIP for p in glob.glob(f"{D}/{t}_*.m4a")
         if not CLIP_SILENZIO[0] <= os.path.basename(p).split("_", 1)[1][:13] < CLIP_SILENZIO[1]]
    for p in c:
        finestra(p)
    if _dur["sporca"]:
        _dur["sporca"] = False
        scrivi_json(DURATE, _dur["v"])
    return sorted(c, key=lambda p: os.path.basename(p).split("_", 1)[1], reverse=True)


SESS = {"foto": None}


def coda_fresca():
    """
    dentro ciascun gruppo dalla piu' recente. `tutte_clip()` (anche le giudicate) resta per "Classificate" e il resto."""
    g = giudizi()
    c, ESCLUSE["telefono"], ESCLUSE["sveglio"] = [], 0, 0
    liv = livelli_minuti()
    for p in tutte_clip():
        n = os.path.basename(p)
        if n in g:
            continue
        m = motivo_esclusa(n)
        if m:
            ESCLUSE[m] += 1
        else:
            c.append(p)
    # l'ordine di tutte_clip() = le piu' recenti prima (sort stabile). Precise/finestre non contano piu': conta cosa dicono i modelli.
    r = {os.path.basename(p): rango_clip(p, liv) for p in c}
    VERIFICARE[0] = sum(v == 3 for v in r.values())
    return sorted(c, key=lambda p: -r[os.path.basename(p)])


ESCLUSE = {"telefono": 0, "sveglio": 0}  # conteggio dell'ultima coda_fresca(): le clip NON giudicate tenute fuori dalla coda
MEDIA_CSV, USO_CSV, STORIA_CSV = F("media_a56.csv"), F("uso.csv"), os.path.join(HOME, "stato_storia.csv")
LIV = SG.livelli(F("modelli.json"))  # {modello: (livello, colore)}: basso YAMNet / medio EfficientAT / preciso PANNs


def motivo_esclusa(n):
    """'telefono' (un telefono suonava: TikTok...) | 'sveglio' (sveglio certo: PC/A56 in uso o storico stato) | None.
    """
    if n.startswith("punto_"):
        return None
    try:
        media = SG.leggi(MEDIA_CSV)
        if SG.sorgente_clip(os.path.join(D, n), media, intervalli=SG.leggi_intervalli(MEDIA_CSV))[0] == "telefono":
            return "telefono"
        if SG.sveglio_certo(SG.minuto_clip(n), SG.leggi_uso(USO_CSV), SG.leggi_storia(STORIA_CSV), media):
            return "sveglio"
    except Exception as e:
        log(f"motivo_esclusa {n}: {e}")
    return None


VERIFICARE = [0]  # clip non giudicate (e non escluse) dove PANNs dice russare: l'ultimo conteggio di coda_fresca()
MAPPE_DIR = F("mappe")
_LIV = {}  # {file mappa: (mtime, {minuto ISO: livello 1-3})}


def livelli_minuti():
    """{minuto 'AAAA-MM-GGTHH:MM': 3 PANNs / 2 EfficientAT / 1 YAMNet} che dicono russare, da TUTTE le mappe copiate dal PC
    (mappe/mappa_*.json, corsie per minuto di modelli.json: livello PRECISO/MEDIO/BASSO)."""
    out = {}
    for f in glob.glob(os.path.join(MAPPE_DIR, "mappa_*.json")):
        mt = os.path.getmtime(f)
        if _LIV.get(f, (0,))[0] != mt:
            v = {}
            try:
                for c in leggi_json(f).get("corsie", []):
                    r_ = {"PRECISO": 3, "MEDIO": 2, "BASSO": 1}.get(c.get("livello"), 0)
                    for k, cats in (c.get("celle") or {}).items():
                        if r_ and "russa" in cats:
                            v[k] = max(v.get(k, 0), r_)
            except (AttributeError, TypeError):
                pass
            _LIV[f] = (mt, v)
        for k, r_ in _LIV[f][1].items():
            out[k] = max(out.get(k, 0), r_)
    return out


def rango_clip(p, liv):
    """Valore di una clip da categorizzare: il livello piu' alto che dice russare nel suo minuto (mappa) o sulla clip stessa
    (.panns/.eff > 0,2); 1 se il suo tipo e' russa (YAMNet l'ha tagliata); 0 altrimenti."""
    n = os.path.basename(p)
    r = liv.get(f"{SG.minuto_clip(n):%Y-%m-%dT%H:%M}", 0)
    for ext, v in ((".panns", 3), (".eff", 2)):
        x = _num(p, ext)
        if x is not None and x > 0.2:
            r = max(r, v)
    return max(r, 1 if tipo_di(n) == "russa" else 0)


def riga_escluse():
    """'🔬 russa PANNs: N da verificare · 🎵 N clip dal telefono escluse · 👁️ N clip da sveglio escluse' (solo > 0), '' se niente."""
    return " · ".join(([TX.t("da_verificare", n=VERIFICARE[0])] if VERIFICARE[0] else []) + [TX.t("esc_" + k, n=v) for k, v in ESCLUSE.items() if v])


def coda_cat():
    """La coda STABILE della sessione: l'ordine fotografato da `ascolta()` (meno le giudicate nel frattempo); le clip nate
    dopo la foto (si registra di notte) vanno IN CODA, mai davanti. Senza sessione = la coda fresca."""
    fresca = coda_fresca()
    if SESS["foto"] is None:
        return fresca
    pos = {n: i for i, n in enumerate(SESS["foto"])}
    vecchie = sorted((p for p in fresca if os.path.basename(p) in pos), key=lambda p: pos[os.path.basename(p)])
    if SESS.get("solo"):
        return vecchie  # sessione ristretta: niente clip nate dopo
    return vecchie + [p for p in fresca if os.path.basename(p) not in pos]


SCALDA = {}


def scalda_durate():
    """tutte_clip() in un thread nice: l'ffprobe delle clip appena nate non blocca la risposta ai tocchi (cache DURATE)."""
    if SCALDA.get("t") and SCALDA["t"].is_alive():
        return

    def lavoro():
        try:
            os.nice(10)
        except (AttributeError, OSError):
            pass
        try:
            tutte_clip()
        except Exception as e:
            log(f"scalda_durate: {e}")
    SCALDA["t"] = threading.Thread(target=lavoro, daemon=True)
    SCALDA["t"].start()


def lista_nav(n):
    """Dove scorrono le frecce partendo da n: la coda; se n e' gia' giudicata (aperta da Classificate) tutte le clip."""
    c = coda_cat()
    return c if n in [os.path.basename(p) for p in c] else tutte_clip()


GIUD_COLS = ["clip", "detto", "giusto", "era", "sequenza", "ora"]


def giudizi():
    """{clip: riga} — giudizi.csv con colonne 'era' e 'sequenza' (migra il file vecchio: righe vecchie, colonne vuote)."""
    righe = leggi_csv(GIUDIZI)
    if righe and "sequenza" not in righe[0]:
        with open(GIUDIZI, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=GIUD_COLS); w.writeheader()
            w.writerows({k: x.get(k) or "" for k in GIUD_COLS} for x in righe)
    return {x["clip"]: x for x in leggi_csv(GIUDIZI)}


def quando_clip(n):
    t = datetime.strptime(n.split("_", 1)[1][:13], "%Y%m%d_%H%M")
    return t


def fid_clip(p):
    txt = open(p[:-4] + ".txt").read() if os.path.exists(p[:-4] + ".txt") else ""
    if "musica" in txt:
        return txt, TX.fiducia("forse", TX.MOTIVI["musica"])
    pn = p[:-4] + ".panns"
    if os.path.basename(p).startswith("russa_") and os.path.exists(pn):
        try:
            mx = float(open(pn).read().split(",")[0])
        except ValueError:
            mx = -1
        if 0 <= mx <= 0.2:
            return txt, TX.fiducia("forse", TX.MOTIVI["panns_no"])
    return txt, TX.fiducia("quasi")


def fid_parole(fid):
    """Nelle IMMAGINI la fiducia resta a parole (il font delle card non ha '━'); nei messaggi e' la cucitura."""
    return fid.replace("━━━", "sicuro").replace("- - -", "quasi sicuro").lstrip("· ").strip()


def _num(p, ext):
    try:
        return float(open(p[:-4] + ext).read().split(",")[0])
    except (OSError, ValueError):
        return None


COMPOSTE = {"tiktok": ["voce_media", "musica"]}
SOTTO_DEFAULT = {"tiktok": ["voce", "musica", "entrambe"]}


def cat_da_cartella(lab):
    """Cartella Drive -> categorie suggerite ("Muoversi e russare" = movimento + russa). Solo un SUGGERIMENTO, non la verita'."""
    ids = {"russ": "russa", "muov": "movimento", "toss": "tosse", "voce": "voce", "parl": "voce", "resp": "respiro"}
    c = [ids[w[:4]] for w in pulisci(lab).split("_") if w[:4] in ids]
    return list(dict.fromkeys(c))


def tipo_di(n):
    """Il tipo che il modello aveva visto: il prefisso del nome; per un punto della notte (punto_*) quello scritto accanto (.tipo)."""
    t = n.split("_")[0]
    if t == "finestra":
        return "russa"  # nata dai periodi candidati di russare
    if t == "punto":
        try:
            return open(os.path.join(D, n[:-4] + ".tipo"), encoding="utf-8").read().strip()
        except OSError:
            return ""
    return t


_CAT = {}  # {file mappa: (mtime, {minuto ISO: (rango, livello, [categorie])})} del modello piu' preciso per minuto


def cat_precisa(n):
    """(livello, [categorie]) del modello PIU' PRECISO che ha analizzato i minuti della clip n (mappe/mappa_*.json, anche
    """
    t = quando_clip(n)
    chiavi = {f"{t:%Y-%m-%dT%H:%M}", f"{t + timedelta(seconds=19):%Y-%m-%dT%H:%M}"}
    best = None
    for f in glob.glob(os.path.join(MAPPE_DIR, "mappa_*.json")):
        mt = os.path.getmtime(f)
        if _CAT.get(f, (0,))[0] != mt:
            v = {}
            try:
                for c in leggi_json(f).get("corsie", []):
                    r_ = c.get("rango") or {"PRECISO": 3, "MEDIO": 2, "BASSO": 1}.get(c.get("livello"), 0)
                    if not r_ or c.get("nome") == "Tue etichette":
                        continue
                    for k, cats in (c.get("celle") or {}).items():
                        if r_ > v.get(k, (0,))[0]:  # analizzato anche senza categorie = silenzio sentito dal piu' preciso
                            v[k] = (r_, c.get("livello", ""), list(cats or []))
            except (AttributeError, TypeError):
                pass
            _CAT[f] = (mt, v)
        for k in chiavi:
            x = _CAT[f][1].get(k)
            if x and (best is None or x[0] > best[0]):
                best = x
    if not best:
        return None
    cats = sorted({c for k in chiavi for f in _CAT for x in [_CAT[f][1].get(k)] if x and x[0] == best[0] for c in x[2]})
    return best[1], cats


def suggerimento(p):
    """(categorie suggerite, riga 🤖) della clip: cartella Drive (se e' un audio "dormire") e/o cosa sentiva il modello
    (nome file = YAMNet, .panns/.eff = i due altri orecchi, con la loro confidenza). Mai presentato come SUA scelta."""
    n = os.path.basename(p)
    tipo, lab = tipo_di(n), cartella_drive(n)
    sugg = [c for c in cat_da_cartella(lab) if c in suoni()] if lab else []
    if not sugg and tipo in suoni():
        sugg = [tipo]
    pezzi = [TX.t("sugg_cartella", lab=lab)] if lab else []
    ore = [(nome, _num(p, ext)) for nome, ext in (("EfficientAT", ".eff"), ("PANNs", ".panns")) if _num(p, ext) is not None and _num(p, ext) >= 0]
    pezzi.append((TX.t("sugg_punto", cat=PUNTI.get(tipo, tipo)) if n.startswith("punto_") else TX.t("sugg_modello", liv=LIV["YAMNet"][0], cat=TX.mostra(tipo))) + "".join(
        " · " + TX.t("sugg_orecchio", liv=LIV[nome][0], esito=TX.t("sugg_ok" if v > 0.2 else "sugg_no"))
        for nome, v in ore))
    cp = cat_precisa(n) if not n.startswith("punto_") else None
    if cp and cp[0] == "PRECISO":  # il giudice preciso (PANNs, anche Kaggle notte intera) comanda il suggerimento
        liv = next((v[0] for k, v in LIV.items() if k.startswith("PANNs")), "preciso")
        sugg = [c for c in cp[1] if c in suoni()] or (["silenzio"] if "silenzio" in suoni() else [])
        pezzi.insert(0, TX.t("sugg_modello", liv=liv, cat=" + ".join(TX.mostra(c) for c in cp[1]) or TX.mostra("silenzio")))
    return sugg, " · ".join(pezzi)


_MIN = {}  # {file minuti_*.csv: (mtime, {minuto: riga})}
_ST_ORA = {"k": None, "c": {}}


def info_clip(p):
    """
    (TV/musica...). "" se il minuto non c'e'. Dati: minuti_AAAAMMGG.csv (db, base, esterni, esterno_top) e stato_clip()."""
    n = os.path.basename(p)
    k = quando_clip(n).replace(second=0, microsecond=0)
    f = os.path.join(D, f"minuti_{k:%Y%m%d}.csv")
    if not os.path.exists(f):
        return ""
    mt = os.path.getmtime(f)
    if f not in _MIN or _MIN[f][0] != mt:
        _MIN[f] = (mt, {r["t"][:16]: r for r in leggi_csv(f) if r.get("t")})
    r = _MIN[f][1].get(f"{k:%Y-%m-%dT%H:%M}")
    pezzi = []
    chiave = max(glob.glob(f"{D}/minuti_*.csv"), key=os.path.getmtime, default=None)
    if _ST_ORA["k"] != (chiave, os.path.getmtime(chiave) if chiave else 0):  # i giorni analizzati si rifanno solo se i minuti cambiano
        _ST_ORA["k"], _ST_ORA["c"] = (chiave, os.path.getmtime(chiave) if chiave else 0), {}
    try:
        st = stato_clip(n, _ST_ORA["c"])
    except Exception as e:
        log(f"info_clip stato: {e}"); st = "?"
    if st in ("dorme", "sveglio"):
        pezzi.append(TX.t("info_" + st))
    try:
        if r:
            d = round(float(r["db"]) - float(r["base"]))
            pezzi.append(TX.t("info_db", db=f"{d:+d}"))
            if int(r.get("esterni") or 0) >= 3 and r.get("esterno_top"):
                pezzi.append(TX.t("info_ext", cosa=TX.EXT_NOMI.get(r["esterno_top"], r["esterno_top"].replace("_", " "))))
    except (KeyError, ValueError):
        pass
    return " · ".join(pezzi)


FIRMA = {}


def firma(p):
    """Tutto cio' che cambia cosa dice una card: .txt/.panns/.eff (arrivano 10-20 s DOPO la clip, i due ultimi dal PC),
    didascalia (letta dopo) 'PANNs: no' -> testo e video diversi. Card e didascalia devono avere la stessa firma."""
    s = []
    for e in (".txt", ".panns", ".eff"):
        try:
            st = os.stat(p[:-4] + e)
            s.append((st.st_mtime_ns, st.st_size))
        except OSError:
            s.append(None)
    return (tuple(s), finestra(p))


GRAF = threading.Lock()  # matplotlib non e' thread-safe: la card della clip dopo si prepara in un thread


def card_clip(p, riga=None, pronto=None):
    """(png, geo, didascalia, tastiera) della clip p. pronto = {png, geo} gia' disegnati dal thread di preparazione."""
    n = os.path.basename(p)
    tipo, t = n.split("_")[0], quando_clip(n)
    nome_img = TX.t("clip_img_punto", nome=PUNTI.get(tipo_di(n), "...")) if tipo == "punto" else TX.t("clip_img_modello", nome=NOME_CLIP[tipo])
    txt, fid = fid_clip(p)
    timbro = None
    png = F("clip.png") if threading.current_thread() is threading.main_thread() else F(f"clip_prep_{n[:-4]}.png")
    fin = finestra(p)
    if pronto:
        png, geo = pronto["png"], pronto["geo"]
    else:
        with GRAF:
            png, geo = grafici.clip(p, livelli_categorie(p, txt), f"{t.day} {MESI[t.month - 1]}",
                                    f"{t:%H:%M} · " + ("finestra da 20 s" if fin else nome_img), png, timbro,
                                    TX.t("clip_fiducia", fid=fid_parole(fid)))
    testo = testo_clip(p, riga)
    if fin:  # finestra: la card chiede la sequenza, i tasti sono i suoni
        return png, geo, testo, tasti_finestra(n)
    return png, geo, testo, tasti_precisa(n)


def freccia_cat(n):
    """Categoria del modello che ▶️ senza tocchi terrebbe come giudizio ('' se non vale: finestra, gia' toccata/giudicata, niente 🤖)."""
    p = os.path.join(D, n)
    if finestra(p) or sel(n) or n in giudizi():
        return ""
    return next(iter(suggerimento(p)[0]), "")


def testo_clip(p, riga=None):
    n = os.path.basename(p)
    if finestra(p):
        t = testo_finestra(n)
    else:  # max 3 righe corte: ora, cosa diceva il modello (NON la sua scelta), info per decidere
        t = suggerimento(p)[1]
        i = salvato(n) or info_clip(p)  # la SUA scelta salvata al posto delle info
        t += f"\n{i}" if i else ""
        t += "\n" + TX.t("sugg_freccia") if freccia_cat(n) else ""
        if GRUPPO.get(n):
            t += "\n" + riga_gruppo(n)
    s = riga_sorgente(p)
    t += f"\n{s}" if s else ""
    if n in DUE_LIVELLI and not finestra(p):  # legenda minima delle due tinte della card
        t += "\n" + TX.t("legenda_liv", chiaro=LIV["YAMNet"][0], scuro=LIV["EfficientAT"][0])
    return t + (f"\n{riga}" if riga else "")


DUE_LIVELLI = set()  # clip la cui card ha disegnato i due livelli (basso chiaro + medio scuro): serve alla legenda


def riga_sorgente(p):
    """(nota rimossa)"""
    n = os.path.basename(p)
    try:
        k, app = SG.sorgente_clip(p, SG.leggi(MEDIA_CSV), salva=n not in giudizi(), intervalli=SG.leggi_intervalli(MEDIA_CSV))
    except Exception as e:
        log(f"riga_sorgente {n}: {e}")
        return ""
    return TX.t("sorg_telefono", app=app) if k == "telefono" else TX.t("sorg_io") if k == "io" else ""


CTX_S = (10, 30)
CTX = {}  # clip -> livello mostrato (1 = CTX_S[0], 2 = CTX_S[1]); assente = clip corta


def riga_nav(n):
    """I tasti contesto (le frecce stanno ai lati delle categorie, vedi tasti_sequenza): [🔍 Contesto]; col contesto aperto [↩️ Clip] [🔍 ±30 s]."""
    l = CTX.get(n, 0)
    ctx = ([(TX.b("contesto"), f"kx:1:{n}")] if contesto_possibile(n) else []) if not l else \
        [(TX.b("ctx_clip"), f"kx:0:{n}")] + ([(TX.b("ctx_piu", s=CTX_S[1]), f"kx:2:{n}")] if l == 1 else [])
    return ctx


def _pcm(path, ss=0, t=None):
    import numpy as np
    cmd = ["ffmpeg", "-v", "error", "-ss", str(ss)] + (["-t", str(t)] if t else []) + ["-i", path, "-f", "s16le", "-ac", "1", "-ar", "8000", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True).stdout, dtype="int16").astype("float64")


def _dove(clip, blocco, da, a):
    """(secondo in cui la clip comincia nel blocco, somiglianza 0-1): correlazione normalizzata sul tratto [da, a] s.
    Serve perche' il nome della clip ha solo il MINUTO (sonno_tel.py), non il secondo."""
    import numpy as np
    c, r_ = _pcm(clip), _pcm(blocco, da, a - da)
    if len(c) < 800 or len(r_) < len(c):
        return da, 0.0
    k = len(r_) - len(c) + 1
    N = 1 << (len(r_) + len(c)).bit_length()
    cor = np.fft.irfft(np.fft.rfft(r_, N) * np.conj(np.fft.rfft(c, N)), N)[:k]
    e = np.concatenate([[0.0], np.cumsum(r_ * r_)])
    pun = cor / np.sqrt(np.maximum(e[len(c):] - e[:k], 1e-9)) / (np.linalg.norm(c) + 1e-9)
    i = int(pun.argmax())
    return da + i / 8000, float(pun[i])


INTERI_DA = "20260930_2331"  # primo blocco intero mai salvato in rec/interi: prima di allora l'audio intero non esiste
CTX_VICINE = (60, 120)  # ponytail: ±s entro cui cercare le clip vicine da cucire quando manca il blocco (1o e 2o tocco)
BUCO_S = 0.3  # bip leggero che segna ogni buco nell'audio cucito
_DUR_F = {}


def _dur_file(f):
    if f not in _DUR_F:
        try:
            _DUR_F[f] = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f],
                                             capture_output=True, text=True, timeout=20).stdout)
        except (ValueError, OSError, subprocess.SubprocessError):
            _DUR_F[f] = 0.0
    return _DUR_F[f]


def _cuci(pezzi, out):
    """pezzi = [(file, da_s, durata_s) | None]; None = buco (BUCO_S di bip leggero). ffmpeg concat -> aac mono."""
    cmd, filt = ["ffmpeg", "-v", "error", "-y"], []
    for i, x in enumerate(pezzi):
        if x is None:
            cmd += ["-f", "lavfi", "-t", str(BUCO_S), "-i", "sine=frequency=880:sample_rate=44100"]
            filt.append(f"[{i}:a]volume=0.15,aformat=channel_layouts=mono[a{i}]")
        else:
            cmd += ["-ss", f"{x[1]:.2f}", "-t", f"{x[2]:.2f}", "-i", x[0]]
            filt.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=mono[a{i}]")
    filt.append("".join(f"[a{i}]" for i in range(len(pezzi))) + f"concat=n={len(pezzi)}:v=0:a=1[o]")
    subprocess.run(cmd + ["-filter_complex", ";".join(filt), "-map", "[o]", "-c:a", "aac", "-b:a", "64k", out], capture_output=True)
    return out if os.path.exists(out) and os.path.getsize(out) > 1000 else None


def clip_vicine(n, entro):
    """Le clip (qualsiasi tipo, n compresa) entro ±`entro` s dal minuto di n, in ordine di tempo."""
    m = quando_clip(n)
    return [p for p in sorted(tutte_clip(), key=lambda p: os.path.basename(p).split("_", 1)[1])
            if abs((quando_clip(os.path.basename(p)) - m).total_seconds()) <= entro]


def _interi():
    return sorted(glob.glob(os.path.join(D, "interi", "2*.m4a")) + glob.glob(os.path.join(D, "2*.m4a")), key=os.path.basename)


def _t0(f):
    return datetime.strptime(os.path.basename(f)[:15], "%Y%m%d_%H%M%S")


def _blocchi_di(n):
    m = quando_clip(n)
    return [(f, _t0(f)) for f in _interi() if _t0(f) <= m + timedelta(seconds=59) and (m - _t0(f)).total_seconds() < 31 * 60][-2:]


def contesto_possibile(n):
    """Il tasto 🔍 Contesto c'e' se un blocco intero o clip vicine lo permettono; clip dopo INTERI_DA con blocco archiviato:
    c'e' (il toast spiega); clip prima di INTERI_DA senza blocco ne' vicine: niente tasto (audio intero mai salvato)."""
    if n.split("_", 1)[1][:13] >= INTERI_DA:
        return True
    return len(clip_vicine(n, CTX_VICINE[1])) > 1 or bool(_blocchi_di(n))


def contesto(n, livello):
    """La clip n allargata di CTX_S[livello-1] s prima e dopo, ritagliata dal blocco intero rec/interi che la contiene
    (vicino all'inizio/fine del blocco: il pezzo mancante dal blocco adiacente, buco segnato col bip). Senza blocco (mai
    salvato prima di INTERI_DA, o archiviato dopo 48 h): CUCITE le clip vicine ±CTX_VICINE s, un bip per buco; il nome del
    file porta il numero di clip (contesto_<n>_<l>_c<N>.m4a). None = niente da mostrare."""
    p, pad = os.path.join(D, n), CTX_S[livello - 1]
    for x in glob.glob(F(f"contesto_{n[:-4]}_{livello}*.m4a")):
        if os.path.getsize(x) > 1000:
            return x
    out = F(f"contesto_{n[:-4]}_{livello}.m4a")
    m, fs, cand = quando_clip(n), _interi(), _blocchi_di(n)
    if cand and os.path.exists(p):
        dur = durata_clip(p) or 20
        best = None
        for f, t0 in cand:  # ponytail: l'ultimo blocco che parte entro il minuto, o quello prima: vince chi somiglia di piu'
            off = (m - t0).total_seconds()
            try:
                ini, sc = _dove(p, f, max(off - 2, 0), off + 62 + dur)
            except Exception as e:  # senza numpy / ffmpeg: tutto il minuto
                log(f"contesto: {e}"); ini, sc = max(off, 0), 0.0
            if best is None or sc > best[2]:
                best = (f, ini, sc, max(off, 0))
        f, ini, sc, off = best
        if sc < 0.5:  # non si e' ritrovata: tutto il minuto del nome
            ini, dur = off, 60 + dur
        a, b, bd = ini - pad, ini + dur + pad, _dur_file(f)
        i, pezzi = fs.index(f), []
        if a < 0 and i > 0 and (_t0(f) - _t0(fs[i - 1])).total_seconds() - _dur_file(fs[i - 1]) < 30:  # blocco prima, contiguo
            pd_ = _dur_file(fs[i - 1])
            pezzi += [(fs[i - 1], max(pd_ + a, 0), min(-a, pd_)), None]
        pezzi.append((f, max(a, 0), (min(b, bd) if bd else b) - max(a, 0)))
        if bd and b > bd and i + 1 < len(fs) and (_t0(fs[i + 1]) - _t0(f)).total_seconds() - bd < 30:  # blocco dopo, contiguo
            pezzi += [None, (fs[i + 1], 0, min(b - bd, _dur_file(fs[i + 1]) or b - bd))]
        if len(pezzi) == 1:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{max(a, 0):.2f}", "-t", f"{dur + 2 * pad:.2f}", "-i", f,
                            "-c", "copy", out], capture_output=True)
            r = out if os.path.exists(out) and os.path.getsize(out) > 1000 else None
        else:
            r = _cuci(pezzi, out)
        if r:
            return r
    vic = clip_vicine(n, CTX_VICINE[livello - 1])
    if len(vic) < 2:
        return None
    pezzi = []
    for x in vic:
        pezzi += ([None] if pezzi else []) + [(x, 0, durata_clip(x) or 20)]
    return _cuci(pezzi, F(f"contesto_{n[:-4]}_{livello}_c{len(vic)}.m4a"))


def mostra_contesto(n, livello, msg):
    """🔍 Contesto: la STESSA card diventa l'audio allargato (editMessageMedia); ↩️ Clip la riporta com'era."""
    p = os.path.join(D, n)
    if not livello:
        CTX.pop(n, None)
        return mostra_clip(p, msg)
    f = contesto(n, livello)
    if not f:
        return TX.toast("contesto_manca" if n.split("_", 1)[1][:13] >= INTERI_DA else "contesto_non_salvato")
    CTX[n] = livello
    k = os.path.basename(f)[:-4].rpartition("_c")[2]
    titolo = f"Da {k} clip vicine, buchi segnati" if k.isdigit() else f"Contesto ±{CTX_S[livello - 1]} s"
    cambia_media(msg, "audio", f, testo_clip(p), tasti_clip(n), title=titolo, performer="Toppa")


def marcati(n):
    """Le categorie spuntate = la selezione SALVATA in giudizi.csv (stessa fonte della didascalia: vedi = salvato)."""
    return {x.split("/")[0] for e in seq_salvata(n) for x in (e if isinstance(e, list) else [e])}


def riga_gruppo_tasti(n):
    return [(TX.b("chiudi_gruppo" if GRUPPO.get(n) else "insieme"), f"ci:{n}", "primary" if GRUPPO.get(n) else None)]


def tasti_cat(n, pref):
    """Tasti categoria + "➕ nuova". Con sottocategorie il tocco apre la riga delle sotto (cm:), senza = pref (1 tocco)."""
    sub = sotto()
    sg = suggerimento(os.path.join(D, n))[0] if pref == "cp" else []  # sempre: l'ordine dei tasti non cambia sotto il dito
    mk = marcati(n)
    conta = {}
    for e_ in seq_salvata(n):
        for x_ in (e_ if isinstance(e_, list) else [e_]):
            conta[x_.split("/")[0]] = conta.get(x_.split("/")[0], 0) + 1
    ele = sorted(enumerate(suoni()), key=lambda x: (sg.index(x[1]) if x[1] in sg else len(sg), x[0]))
    def et(s_):
        q = TX.mostra(s_) + (TX.b("sugg") if s_ in sg and s_ not in mk else "")  # spuntata: niente "?" in piu'
        x = TX.b("con_sotto", cat=q) if sub.get(s_) else q
        if s_ not in mk:
            return x
        k = conta[s_]  # quante volte e' nella sequenza
        m = TX.b("marcato", cat=x)
        return m.replace(" ", f"{k} ", 1) if k > 1 else m
    tasti = [(j, s_, (et(s_), f"cm:{j}:{n}" if sub.get(s_) else f"{pref}:{j}:{n}")) for j, s_ in ele]
    # usate (almeno una riga piena), le spuntate e la suggerita. L'ordine dei tasti visibili non cambia.
    rare = poco_usate([s_ for _, s_, _ in tasti], frequenze(), tenere=set(mk) | set(sg) | set(conta))
    aperto = n in ALTRI
    vis = [t_ for j, s_, t_ in tasti if s_ not in rare or aperto]
    return vis + ([(TX.b("meno" if aperto else "altri", n=len(rare)), f"ao:{n}")] if rare else []) + [(TX.b("nuova"), f"cn:-:{n}")]


ALTRI = set()  # clip con "altri…" aperto (in memoria: chiude da solo al riavvio)
RIGA_PIENA, MIN_USI = 3, 2  # ponytail: tasti per riga; sotto MIN_USI scelte una categoria e' "poco usata" (a occhio)


def frequenze():
    """{categoria principale: quante volte l'ha scelta} da giudizi.csv (colonna 'sequenza')."""
    f = {}
    for g in giudizi().values():
        for e in (g.get("sequenza") or "").replace("[", "").replace("]", "").replace(">", "+").split("+"):
            if e:
                f[e.split("/")[0]] = f.get(e.split("/")[0], 0) + 1
    return f


def poco_usate(cats, uso, tenere=()):
    """Le categorie da raccogliere in "altri…": le piu' usate restano (almeno una riga piena), le altre vanno sotto solo se
    usate < MIN_USI volte; mai quelle in `tenere`. Meno di 2 candidate: niente "altri" (un tasto per uno non serve)."""
    ordine_ = sorted(cats, key=lambda c: -uso.get(c, 0))
    visibili = set(ordine_[:RIGA_PIENA]) | set(tenere) | {c for c in cats if uso.get(c, 0) >= MIN_USI}
    rare = [c for c in cats if c not in visibili]
    return set(rare) if len(rare) >= 2 else set()


def tasti_precisa(n):
    return tasti_sequenza(n, "cp")


def tasti_clip(n):
    return (tasti_finestra if finestra(os.path.join(D, n)) else tasti_precisa)(n)


def tastiera_sotto(n, j):
    """La STESSA card, solo i tasti cambiano: sottocategorie di suoni()[j], quella generica, indietro, nuova."""
    cat = suoni()[j]
    b = [(TX.mostra(x), f"cq:{j}:{k}:{n}") for k, x in enumerate(sotto().get(cat, []))]
    return kb(*[b[k:k + 3] for k in range(0, len(b), 3)], [(TX.b("sotto_generico", cat=TX.mostra(cat)), f"cq:{j}:-:{n}")],
              [(TX.b("sotto_indietro"), f"cr:{n}"), (TX.b("nuova"), f"cn:{j}:{n}")])


def cambia_tasti(msg, tastiera):
    prova("editMessageReplyMarkup", chat_id=CHAT, message_id=msg, reply_markup=tastiera)


GRUPPO = {}
SEQ = {}  # clip -> [[etichetta, doppio], ...] tocchi in ordine (ponytail: in memoria; se il bot riparte a meta' si ricomincia)
ULTIMO = {}  # clip -> istante dell'ultimo tocco
SOGLIA_DOPPIO = 1.2  # ponytail: 1,2 s a occhio (latenza Telegram: il 2o tocco arriva con ritardo variabile); tarare sull'uso


def adesso():
    return time.time()


SEQ_SIG = {}  # clip -> la riga "sequenza" che ho scritto per ultima (se il csv cambia da fuori, la memoria si butta)


def sel(n):
    """SEQ[n] = la selezione della clip; la prima volta parte da quella salvata (riaperta, ripasso)."""
    g = giudizi().get(n)
    if n in SEQ_SIG and SEQ_SIG[n] != (g or {}).get("sequenza", ""):
        SEQ.pop(n, None)  # il csv e' cambiato fuori da qui: vale il salvato
    if n not in SEQ:
        SEQ[n] = [[y, False] + ([f"s{i}"] if isinstance(x, list) else []) for i, x in enumerate(seq_salvata(n))
                  for y in (x if isinstance(x, list) else [x])]
    return SEQ[n]


def tocca(n, e):
    """Un tocco di `e` ('cat' o 'cat/sotto') AGGIUNGE in fondo alla sequenza. Stesso tasto entro SOGLIA_DOPPIO = il 2o tocco
    trasforma il 1o in 'doppio' (contemporaneo); 🔗 Insieme apre un gruppo."""
    s, t = sel(n), adesso()
    rec = bool(s) and len(s[-1]) == 2 and s[-1][0] == e and not s[-1][1] and t - ULTIMO.get(n, -9) < SOGLIA_DOPPIO and not GRUPPO.get(n)
    if rec:
        s[-1][1] = True
    elif GRUPPO.get(n):  # gruppo aperto: ogni tocco entra nel gruppo, a prescindere dal tempo
        s.append([e, False, GRUPPO[n]])
    else:
        s.append([e, False])
    ULTIMO[n] = t


def togli_ultimo(n):
    """Annulla l'ultimo TOCCO: se era il 2o di un doppio torna semplice, altrimenti toglie l'elemento."""
    s = sel(n)
    if s:
        if len(s[-1]) == 2 and s[-1][1]:
            s[-1][1] = False
        else:
            s.pop()


def ordine(n):
    """Sequenza in ordine: etichetta oppure [a, b, ...] (gruppo di contemporanei). Gruppo = tocchi di un 🔗 (stesso id) oppure
    """
    out, run, k0 = [], [], None

    def chiudi():
        g = list(dict.fromkeys(run))
        out.extend([g] if len(g) > 1 else run)
        run.clear()
    for e, d, *g in SEQ.get(n, []):
        k = g[0] if g else "d" if d else None
        if k is None:
            chiudi(); out.append(e)
        else:
            if k != k0:
                chiudi()
            run.append(e)
        k0 = k
    chiudi()
    return out


def principali(o):
    """Le categorie principali (prima della '/') di una sequenza `ordine`, gruppi appiattiti."""
    return [x.split("/")[0] for e in o for x in (e if isinstance(e, list) else [e])]


def salva_sel(n):
    """Scrive SUBITO la selezione di n in giudizi.csv: UNA riga per clip, sovrascritta sul posto (resta il 1o 'ora'; selezione
    vuota = giudizio tolto). Finestra: 'a>[b+c]>d'; precisa: 'a+b' (insieme). 'giusto' come sempre: 1 solo il tipo del modello,
    parte = c'e' anche il suo, 0 = altro."""
    o, tipo = ordine(n), tipo_di(n)
    m = list(dict.fromkeys(principali(o)))
    giusto = "1" if m == [tipo] else "parte" if tipo in m else "0"
    seq = ">".join("[" + "+".join(e) + "]" if isinstance(e, list) else e for e in o)
    giudizi()  # migra il formato vecchio
    righe, nuova, fatto = leggi_csv(GIUDIZI), [], False
    era = m[0].replace(",", " ") if m and giusto == "0" else ""
    for x in righe:
        if x["clip"] != n:
            nuova.append(x)
        elif not fatto and o:
            fatto = True
            nuova.append(dict(x, detto=tipo, giusto=giusto, era=era, sequenza=seq.replace(",", " ")))
    if o and not fatto:
        nuova.append(dict(clip=n, detto=tipo, giusto=giusto, era=era, sequenza=seq.replace(",", " "),
                          ora=f"{datetime.now():%Y-%m-%dT%H:%M}"))
    tmp = GIUDIZI + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=GIUD_COLS); w.writeheader()
        w.writerows({k: x.get(k) or "" for k in GIUD_COLS} for x in nuova)
    for k in range(20):  # Windows: un thread che sta leggendo il file blocca il replace (sul telefono non succede)
        try:
            os.replace(tmp, GIUDIZI); break
        except PermissionError:
            if k == 19:
                raise
            time.sleep(0.05)
    SEQ_SIG[n] = seq.replace(",", " ") if o else ""


def fmt_seq(o):
    return " → ".join("[" + " + ".join(TX.mostra_em(x) for x in e) + "]" if isinstance(e, list) else TX.mostra_em(e) for e in o)


def seq_salvata(n):
    """La sequenza salvata in giudizi.csv come lista `ordine` ('a>[b+c]>d' -> ['a', ['b','c'], 'd']); [] se non giudicata."""
    g = giudizi().get(n)
    if not g or not g.get("sequenza"):
        return []
    return [x.strip("[]").split("+") if "+" in x else x for x in g["sequenza"].split(">")]  # 'a+b' (precisa) e '[a+b]' = insieme


def riga_gruppo(n):
    if not GRUPPO.get(n):
        return ""
    ora = [e for e, d, *g in SEQ.get(n, []) if g and g[0] == GRUPPO[n]]
    return TX.t("clip_gruppo", seq=" + ".join([TX.mostra(x) for x in dict.fromkeys(ora)] + ["…"]))


def salvato(n):
    """'Salvato: respiro + russa ✓' dal giudizi.csv ('' se non c'e'): la didascalia mostra SOLO quello che e' scritto."""
    sv = seq_salvata(n)
    if not sv:
        return ""
    return TX.t("clip_salvato", seq=fmt_seq(sv))


def testo_finestra(n):
    g = "\n" + riga_gruppo(n) if GRUPPO.get(n) else ""
    return (salvato(n) if seq_salvata(n) else TX.t("clip_finestra")) + g


def tasti_finestra(n):
    return tasti_sequenza(n, "cs")


def tasti_sequenza(n, pref):
    """(nota rimossa)"""
    b = tasti_cat(n, pref)
    nuova = b.pop()
    r = [b[k:k + 3] for k in range(0, len(b), 3)] or [[]]
    m = len(r) // 2
    r[m] = [(TX.b("prec"), f"c<:{n}")] + r[m] + [(TX.b("succ"), f"c>:{n}")]
    mod = [(TX.b("modifica"), f"cz:{n}")] if seq_salvata(n) else []
    return kb(riga_gruppo_tasti(n), *r, [(TX.b("clip_togli"), f"cu:{n}"), nuova], mod + riga_nav(n))


def applica(n, e, msg):
    """Tocco su `e` ('cat' o 'cat/sotto') sulla clip n (precisa o finestra): toggle della spunta, salvataggio immediato,
    stessa card aggiornata (spunte + didascalia). In giudizi.csv era = categoria principale, sequenza = la selezione."""
    tocca(n, e)
    salva_sel(n)  # SUBITO su disco: la card NON avanza da sola, il tasto avanti passa
    aggiorna_finestra(n, msg)
    return TX.toast("clip_ok", cat=TX.mostra(e)[:40])


def aggiorna_finestra(n, msg):
    p = os.path.join(D, n)
    if FIRMA.get(n, firma(p)) != firma(p) and not CTX.get(n):  # i dati sono cambiati dopo il disegno: l'immagine non e' piu' quella del testo
        return mostra_clip(p, msg)
    didascalia(msg, testo_clip(p), tasti_clip(n))


def dim_video(png, larghezza=None):
    """Dimensioni vere del video (clip_video allarga col bordo fino a MAX_ALTEZZA): Telegram le usa per l'anteprima.
    larghezza: video che scorre (clip_scorre) -> la finestra, non tutta l'immagine."""
    from PIL import Image
    w, h = Image.open(png).size
    w = larghezza or w
    h += 2 * grafici.MARGINE_VIDEO
    return dict(width=max(w, -(-int(h / grafici.MAX_ALTEZZA) // 2) * 2), height=h)


#   inattivo --entra--> entrato --2 tocchi in USO_ATTIVO s--> attivo --4 tocchi in USO_INTENSO s--> intenso
#   qualunque stato --USO_INATTIVO_S s senza entrata ne' tocchi--> inattivo (il giro principale scarta il preparato: uso_pulisci)
#   profondita' (clip dopo la corrente, con card+video+contesto +-10 s): inattivo 0 · entrato 1 · attivo 2 · intenso 4
#   Lo stato si ricava SOLO dai timestamp (adesso()), niente timer; il lavoro e' in un thread nice, mai nella risposta al tocco.
USO_PROF = {"inattivo": 0, "entrato": 1, "attivo": 2, "intenso": 4}
USO_ATTIVO, USO_INTENSO, USO_INATTIVO_S = (2, 180), (4, 45), 300  # ponytail: (tocchi, secondi) a occhio, da tarare sull'uso
USO_ST = {}  # servizio -> {"entrata": t, "tocchi": [t, ...]}


def uso_entra(servizio="ascolta"):
    USO_ST[servizio] = {"entrata": adesso(), "tocchi": []}


def uso_tocco(servizio="ascolta"):
    t = adesso()
    u = USO_ST.setdefault(servizio, {"entrata": t, "tocchi": []})
    u["tocchi"] = [x for x in u["tocchi"] if t - x < USO_ATTIVO[1]] + [t]


def stato_uso(servizio="ascolta"):
    u, t = USO_ST.get(servizio), adesso()
    if not u or t - max([u["entrata"]] + u["tocchi"]) > USO_INATTIVO_S:
        return "inattivo"
    n = lambda w: sum(t - x < w for x in u["tocchi"])
    return "intenso" if n(USO_INTENSO[1]) >= USO_INTENSO[0] else "attivo" if n(USO_ATTIVO[1]) >= USO_ATTIVO[0] else "entrato"


def uso_pulisci():
    """Dal giro principale: inattivo = scarta card/video/contesti preparati e mai usati. Mai bloccante: se il thread di
    preparazione lavora ancora, riprova al giro dopo."""
    if stato_uso() != "inattivo" or PREP.get("thread") and PREP["thread"].is_alive():
        return
    for n in list(PRONTA):
        scarta_pronta(n)
    for f in glob.glob(F("contesto_*.m4a")) + glob.glob(F("pronta_*")):
        os.remove(f)
    PREP.pop("corso", None)


PRONTA, PREP, PREP_LOCK = {}, {}, threading.RLock()  # rientrante: coda e singola clip condividono il lock


def scarta_pronta(n):
    x = PRONTA.pop(n, None)
    for f in (x or {}).get("png"), (x or {}).get("mp4"):
        if f and os.path.exists(f):
            os.remove(f)


def prepara_clip(n):
    """Card + video (ffmpeg) della clip n. Un giro = un lock: chi vuole la clip appena preparata aspetta al massimo una clip.
    Riusa solo se n e' ancora da giudicare."""
    with PREP_LOCK:
        try:
            p = os.path.join(D, n)
            if n in PRONTA or n in giudizi() or not os.path.exists(p):
                return
            f0 = firma(p)  # PRIMA di disegnare: se i dati arrivano a meta', la card risulta vecchia e si rifa'
            png, geo, _, _ = card_clip(p)
            png = shutil.move(png, F(f"pronta_{n[:-4]}.png"))
            PRONTA[n] = dict(png=png, geo=geo, firma=f0, mp4=grafici.clip_video(png, p, geo, F(f"pronta_{n[:-4]}.mp4")))
        except Exception as e:
            log(f"prepara_clip: {e}")


def prepara_coda(nomi, corrente=None, generazione=None):
    """Thread a bassa priorita' (nice: l'ffmpeg figlio la eredita'): prepara in ordine le clip `nomi`, scarta le pronte non piu' attese."""
    try:
        os.nice(10)
    except (AttributeError, OSError):
        pass
    with PREP_LOCK:
        if generazione is not None and generazione != PREP.get('generazione'):
            return
        for n in [x for x in PRONTA if x not in nomi]:
            scarta_pronta(n)
        tieni = [corrente] + list(nomi)
        for f in glob.glob(F("contesto_*.m4a")):
            if not any(os.path.basename(f).startswith(f"contesto_{x[:-4]}_") for x in tieni if x):
                os.remove(f)
    for n in [corrente] + list(nomi):
        with PREP_LOCK:
            if generazione is not None and generazione != PREP.get('generazione'):
                return
            if n and n != corrente:
                prepara_clip(n)
            try:
                n and contesto(n, 1)
            except Exception as e:
                log(f"contesto {n}: {e}")


CLIP_TASTI = ("ci:", "cp:", "cs:", "cu:", "cf:", "cq:", "cm:", "cr:", "cn:", "cz:", "c<:", "c>:", "kx:")  # pulsanti della card clip (n ultimo)
MOSTRATA = {}


def stantio(q):
    d = q.get("data", "")
    m = MOSTRATA.get(q["message"]["message_id"])
    return d.startswith(CLIP_TASTI) and m is not None and d.rsplit(":", 1)[-1] != m


def mostra_clip(p, msg=None, riga=None):
    with PREP_LOCK:
        PREP['generazione'] = PREP.get('generazione', 0) + 1
        generazione = PREP['generazione']
    v = _mostra_clip(p, msg, riga)
    if v:
        MOSTRATA[v] = os.path.basename(p)
    for e_ in ("png", "mp4"):
        f_ = F(f"pronta_{os.path.basename(p)[:-4]}.{e_}")
        if os.path.basename(p) not in PRONTA and os.path.exists(f_):
            os.remove(f_)
    if grafici and os.path.basename(p) not in giudizi():
        lista = [os.path.basename(x) for x in lista_nav(os.path.basename(p))]
        i = lista.index(os.path.basename(p)) if os.path.basename(p) in lista else -1
        nomi = lista[i + 1:i + 1 + USO_PROF[stato_uso()]] if i >= 0 else []
        if nomi:
            PREP["corso"] = set(nomi)
            PREP["thread"] = threading.Thread(target=prepara_coda, args=(nomi, os.path.basename(p), generazione), daemon=True)
            PREP["thread"].start()


def _mostra_clip(p, msg=None, riga=None):
    """UNA clip = UN video (card + audio + linea che scorre): vedi e senti insieme, pulsanti sotto, ◀️▶️ cambiano il
    video nello STESSO messaggio (ux/FASTIDIO_VANTAGGIO.md: 1 messaggio invece di 6). Se ffmpeg non fa il video:
    foto + audio m4a separati, come fallback."""
    n = os.path.basename(p)
    CTX.pop(n, None)
    if not grafici:  # senza matplotlib: audio + pulsanti
        return manda_file("sendAudio", "audio", p, {"caption": TX.t("clip", ora=f"{quando_clip(n):%H:%M}", nome=NOME_CLIP[n.split('_')[0]]),
                                                    "parse_mode": "HTML", "reply_markup": card_tasti_semplici(n)}, "audio/mp4")
    if n in PREP.get("corso", ()) and n not in PRONTA:
        with PREP_LOCK:  # la sta preparando il thread: aspetto che finisca la clip in corso, non la rifaccio
            pass
    pr = dict(PRONTA[n]) if n in PRONTA and PRONTA[n].get("mp4") and os.path.exists(PRONTA[n]["mp4"]) and n not in giudizi() else None  # mp4 None = clip_video fallito
    if pr and pr.get("firma") != firma(p):
        scarta_pronta(n); pr = None
    PRONTA.pop(n, None)  # i file li toglie mostra_clip dopo l'invio
    for _ in range(2):  # i dati possono arrivare mentre si disegna (~3 s): se la firma cambia si ridisegna una volta
        f0 = pr["firma"] if pr else firma(p)
        png, geo, testo, tasti = card_clip(p, riga, pr)
        if pr or firma(p) == f0:
            break
    FIRMA[n] = f0
    mp4 = pr["mp4"] if pr else grafici.clip_video(png, p, geo, F("clip.mp4"))
    st = leggi_json(ROCCHETTO)
    if mp4:
        extra = dict(**dim_video(png), supports_streaming=True)
        if msg:  # qualsiasi card clip si aggiorna sul posto (anche un punto della notte), non solo l'ultima del rocchetto
            try:
                cambia_media(msg, "video", mp4, testo, tasti, **extra)
                return msg
            except Exception as e:
                log(f"video rocchetto: {e}")
        st = dict(video=manda_file("sendVideo", "video", mp4, {"caption": testo, "parse_mode": "HTML",
                                                               "reply_markup": tasti, **extra}, "video/mp4"))
    else:
        titolo = dict(title=f"{NOME_CLIP[n.split('_')[0]]} {quando_clip(n):%d/%m %H:%M}", performer="Toppa")
        st = dict(video=foto(png, testo, tasti), audio=manda_file("sendAudio", "audio", p, titolo, "audio/mp4"))
    scrivi_json(ROCCHETTO, st)
    return st.get("video")


def clip_notte(day):
    return [p for p in tutte_clip() if quando_clip(os.path.basename(p)).strftime("%Y%m%d") in
            (day, (datetime.strptime(day, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d"))]


def card_tasti_semplici(n):
    return kb([(TX.b("clip_si"), f"cg:1:{n}"), (TX.b("clip_no"), f"cg:0:{n}")])


def ascolta(inizio=None, solo=None):
    """🔊 Ascolta: parte dalla prima clip NON giudicata (o da `inizio`, nome file). solo = nomi: la coda e' ristretta
    a quelle (report del mattino: 3 suoni / tutta la notte)."""
    uso_entra()  # entrare in Ascolta fa partire la preparazione (mostra_clip, qui sotto)
    SESS["solo"] = solo; SESS.pop("rip", None)
    SESS["foto"] = solo or [os.path.basename(p) for p in coda_fresca()]  # la coda non cambia sotto le dita finche' non rientra
    scalda_durate()
    c = tutte_clip()
    if not c:
        scrivi(TX.t("clip_vuoto")); return
    nomi = [os.path.basename(p) for p in c]
    coda = coda_cat()
    if inizio in nomi:
        mostra_clip(c[nomi.index(inizio)])
    elif coda:
        mostra_clip(coda[0])
    else:
        scrivi(TX.t("clip_finite") + (f"\n{riga_escluse()}" if riga_escluse() else ""))


def ripasso():
    """/ripasso: le clip giudicate OGGI, nell'ordine in cui le ha giudicate, con la sua etichetta gia' spuntata (aggiunge le
    spunte mancanti, avanti passa). Sessione a parte da Ascolta: la coda delle non giudicate non cambia."""
    g, oggi = giudizi(), f"{datetime.now():%Y-%m-%d}"
    nomi = [n for n in ordine_giudizi() if g.get(n, {}).get("ora", "").startswith(oggi)]
    if not nomi:
        scrivi(TX.t("ripasso_vuoto")); return
    uso_entra()
    SESS["rip"] = nomi
    mostra_clip(os.path.join(D, nomi[0]))


def notte_di(n):
    """La clip appartiene alla notte che finisce quel giorno (dopo le 18 = notte del giorno dopo)."""
    t = quando_clip(n)
    return f"{t + timedelta(days=1) if t.hour >= 18 else t:%Y%m%d}"


STATO_EM = {"dorme": "💤", "sveglio": "👁️", "?": "❔"}


def stato_clip(n, cache):
    """
    quello che notte.analizza sa gia' (minuto agitato / telefono o PC usati = sveglio, dentro il blocco di sonno = dorme).
    ponytail: fuori dal blocco ma calmo = "?" (pisolino o sdraiato sveglio: non si sa); la fusione vera di tutti i
    sensori e' il compito ux/nuvola/COMPITO_FUSIONE.md. `cache` = dict per giorno, vive una sola chiamata."""
    day = notte_di(n)
    if day not in cache:
        cache[day] = analizza(day)
    r, k = cache[day], quando_clip(n).replace(second=0, microsecond=0)
    if not r or k not in r["M"]:
        return "?"
    if r["M"][k]["sveglio"]:
        return "sveglio"
    return "dorme" if r["blocco"] and r["blocco"][0] <= k <= r["blocco"][1] else "?"


def cartella_drive(n):
    """
    rec/etichette_drive.csv: inizio_audio,cartella. ponytail: la clip sta entro 30' dall'inizio del suo audio."""
    f = os.path.join(D, "etichette_drive.csv")
    if not os.path.exists(f):
        return None
    t = quando_clip(n)
    for r in open(f, encoding="utf-8").read().split("\n"):
        if "," in r:
            s, lab = r.split(",", 1)
            if timedelta(0) <= t - datetime.strptime(s[:13], "%Y%m%d_%H%M") <= timedelta(minutes=30):
                return lab
    return None


def valutate(tipo=None, msg=None, solo_dorme=False):
    """
    accedere alle clip valutate"; etichette guardabili trasversalmente). Un messaggio, un pulsante per riaprirle."""
    via = tolte()
    cache = {}
    if tipo == "drive":  # le clip dagli audio Drive, con la sua cartella come etichetta
        g, c = giudizi(), {os.path.basename(p): p for p in tutte_clip() if cartella_drive(os.path.basename(p))}
        g = {**g, **{n: {"clip": n, "giusto": "📁 " + cartella_drive(n)} for n in c if n not in g}}
    else:
        g, c = giudizi(), {os.path.basename(p): p for p in tutte_clip() if (not tipo or os.path.basename(p).startswith(tipo + "_"))
                           and notte_di(os.path.basename(p)) not in via}
    st = {n: stato_clip(n, cache) for n in c}
    # lo stato e' un'etichetta, il filtro "solo 💤" e' una scelta sua
    if solo_dorme:
        c = {n: p for n, p in c.items() if st[n] == "dorme"}
    def num(p, ext):
        try:
            return float(open(p[:-4] + ext).read().split(",")[0])
        except (OSError, ValueError):
            return -1.0

    def disaccordo(n):
        a, b = num(c[n], ".panns"), num(c[n], ".eff")
        return a >= 0 and b >= 0 and (a > 0.2) != (b > 0.2)
    if tipo != "drive":
        c = {n: p for n, p in c.items() if datetime.now() - quando_clip(n) <= timedelta(days=7)}
    ordine = sorted(c, key=lambda n: n.split("_", 1)[1], reverse=True)  # solo per data (prima i disaccordi: confondeva)
    ult = [g.get(n, {"clip": n, "giusto": "-"}) for n in ordine][:10]
    s = ":d" if solo_dorme else ""
    blu = lambda si: "primary" if si else None  # scelto = blu (test cieco: niente "> " e simboli)
    filtro = [((NOME_CLIP[t] if t else "tutte").capitalize(), f"vl:{t or ''}{s}", blu(t == tipo)) for t in ("russa", "voce", "tosse", None)] + \
             [("Drive", "vl:drive", blu(tipo == "drive"))]
    sveglio_b = [("Solo quando dormivi", f"vl:{tipo or ''}:d", blu(solo_dorme)), ("Anche da sveglio", f"vl:{tipo or ''}", blu(not solo_dorme))]
    if not ult:
        scrivi(TX.ascii_(TX.t("valutate_vuoto"))); return

    def orecchio(p, ext):
        try:
            v = float(open(p[:-4] + ext).read().split(",")[0])
        except (OSError, ValueError):
            return "-"
        return "-" if v < 0 else f"{v:.2f}".replace(".", ",")
    tu = {"1": "si", "0": "no", "parte": "in parte", "musica": "musica"}
    righe = [TX.t("valutate_titolo", n=len(ult))] + [
        TX.t("valutate_riga", quando=f"{quando_clip(x['clip']):%d/%m %H:%M}", nome=NOME_CLIP[x["clip"].split("_")[0]],
             tu=f" - hai detto: {tu[x['giusto']]}" if x["giusto"] in tu else "",
             dubbio=" - i due controlli non sono d'accordo" if disaccordo(x["clip"]) else "")
        for x in ult]
    em = {"russa": "🟥", "voce": "🗣️", "tosse": "🤧", "sbuffo": "🟪"}
    b = [(f"{NOME_CLIP[x['clip'].split('_')[0]].capitalize()} {quando_clip(x['clip']):%d/%m %H:%M}", f"cv:{x['clip']}")
         for x in ult]
    tasti = kb(filtro, sveglio_b, *[b[i:i + 2] for i in range(0, len(b), 2)])
    if msg:
        modifica(msg, TX.ascii_("\n".join(righe)), tasti)
    else:
        scrivi(TX.ascii_("\n".join(righe)), tasti)


def ascolta_ora(day, hh):
    g = [p for p in tutte_clip() if f"{quando_clip(os.path.basename(p)):%H}" == hh
         and abs((quando_clip(os.path.basename(p)).date() - datetime.strptime(day, "%Y%m%d").date()).days) <= 1]
    ascolta(os.path.basename(g[0]) if g else None)


def ordine_giudizi():
    """Clip giudicate in ordine di ULTIMO giudizio (righe del csv): ◀️ ci torna, un nuovo giudizio sovrascrive il vecchio."""
    o = {}
    for x in leggi_csv(GIUDIZI):
        o.pop(x["clip"], None); o[x["clip"]] = 1
    return [n for n in o if os.path.exists(os.path.join(D, n))]


def vicina(n, passo):
    """◀️ (-1) = l'ultima giudicata prima di n (e cosi' via all'indietro); ▶️ (+1) = la successiva giudicata, poi la coda."""
    rip = SESS.get("rip")
    if rip and n in rip:  # ripasso: solo le clip di oggi, nell'ordine in cui le ha giudicate
        j = rip.index(n) + passo
        return os.path.join(D, rip[j]) if 0 <= j < len(rip) else None
    og, c = ordine_giudizi(), coda_cat()
    nomi = [os.path.basename(p) for p in c]
    if n in og:
        j = og.index(n) + passo
        if 0 <= j < len(og):
            return os.path.join(D, og[j])
        return next((p for p in c if os.path.basename(p) != n), None) if passo > 0 else None
    if passo < 0:
        return os.path.join(D, og[-1]) if og else None
    j = (nomi.index(n) if n in nomi else -1) + 1
    return c[j] if j < len(c) else None


CLIP_AL_GIORNO = 3  # ponytail: ogni 3 giudizi il flusso "passa subito" si ferma su "Altre clip" (regola di prima del TikTok: chiedere se tenerla)


def leggi_csv_giudizi_senza(n):
    return [x for x in leggi_csv(GIUDIZI) if x["clip"] != n]


def giudica(n, giusto, msg, era="", seq=None):
    """seq = suoni in ordine (finestra); clip a tasto singolo: un elemento (la categoria scelta)."""
    era, tipo = era.replace(",", " "), tipo_di(n)
    SEQ.pop(n, None); GRUPPO.pop(n, None); ULTIMO.pop(n, None)
    punto = n.startswith("punto_")
    c = coda_cat()  # la prossima si sceglie PRIMA di scrivere: dopo, n non e' piu' in coda
    nomi = [os.path.basename(p) for p in c]
    i = nomi.index(n) if n in nomi else -1
    dopo = c[i + 1] if i + 1 < len(c) else next((p for p in c if os.path.basename(p) != n), None)
    if punto:  # il punto resta li' col suo timbro: non si passa alla coda di Ascolta
        dopo = os.path.join(D, n)
    seq = seq or [{"1": tipo, "parte": tipo, "musica": "musica"}.get(giusto) or era or "?"]
    if n in giudizi():
        resto = leggi_csv_giudizi_senza(n)  # PRIMA di aprire in "w" (tronca il file)
        with open(GIUDIZI, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=GIUD_COLS); w.writeheader()
            w.writerows({k: x.get(k) or "" for k in GIUD_COLS} for x in resto)
    aggiungi_riga(GIUDIZI, ",".join(GIUD_COLS), f"{n},{tipo},{giusto},{era},{'>'.join(seq).replace(',', ' ')},{datetime.now():%Y-%m-%dT%H:%M}")
    MOSTRATA[msg] = ""  # la card non mostra piu' n (se c'e' una prossima, mostra_clip lo riscrive): un 2o tocco su n e' stantio
    tot = len(giudizi())
    riga = MM.clip_giudicata(giusto != "0", tot)[0] if MM else ""
    oggi = sum(x["ora"].startswith(f"{datetime.now():%Y-%m-%d}") for x in giudizi().values() if not x["clip"].startswith("punto_"))
    if dopo and not punto and oggi >= CLIP_AL_GIORNO and oggi % CLIP_AL_GIORNO == 0:
        didascalia(msg, TX.t("clip_basta", n=oggi) + (f"\n{riga}" if riga else ""),
                   kb([(TX.b("clip_altri"), f"ca:{os.path.basename(dopo)}")]))
    elif dopo:
        mostra_clip(dopo, msg, riga)
    else:
        didascalia(msg, TX.t("clip_finite") + (f"\n{riga}" if riga else "") + (f"\n{riga_escluse()}" if riga_escluse() else ""))
    return TX.toast("clip_ok", cat="›".join(TX.mostra(x) for x in seq)[:40])


def chiedi_era(n, msg):
    """❌ -> "cos'era?" con i tipi (senza quello che avevo detto), poi avanti (ALLINEAMENTO punto 2)."""
    tipo = tipo_di(n)
    b = [(TX.mostra(s), f"ce:{s}:{n}") for s in suoni() if s != tipo]
    righe = [b[i:i + 3] for i in range(0, len(b), 3)] + [[(TX.b("clip_altro"), f"ce:?:{n}")]]
    t = quando_clip(n)
    didascalia(msg, TX.t("clip_cosera", ora=f"{t:%H:%M}"), kb(*righe))


AV = {"t": 0, "png": None, "lavoro": None}  # cache 5 minuti: l'immagine si rifa' in un thread, mai nella risposta al tocco
AV_CACHE_S = 300
ARCHIVIATI_N = os.path.join(HOME, "archiviati_n.txt")  # opzionale: lo scrive il PC (n. blocchi gia' su Drive); se manca la riga Drive sparisce


def dati_avanzamento(ora=None):
    """Numeri veri dal telefono. Per notte (ultime 7): clip giudicate / da fare precise / da fare finestre / escluse
    (microfono silenziato o notte tolta). Analisi: blocchi in rec/interi = analizzati, 2*.m4a in rec = in coda.
    Archivio: spazio libero e (se c'e' ~/archiviati_n.txt) blocchi su Drive."""
    ora = ora or datetime.now()
    g, via = giudizi(), tolte()
    notti = [f"{(ora + timedelta(days=1 if ora.hour >= 18 else 0) - timedelta(days=k)):%Y%m%d}" for k in range(6, -1, -1)]
    righe = {d: dict(fatte=0, precise=0, finestre=0, escluse=0) for d in notti}
    for t in TIPI_CLIP:
        for p in glob.glob(f"{D}/{t}_*.m4a"):
            n = os.path.basename(p); d = notte_di(n)
            if d not in righe:
                continue
            r = righe[d]
            if d in via or CLIP_SILENZIO[0] <= n.split("_", 1)[1][:13] < CLIP_SILENZIO[1]:
                r["escluse"] += 1
            elif n in g:
                r["fatte"] += 1
            else:
                r["finestre" if finestra(p) else "precise"] += 1
    interi = len(glob.glob(os.path.join(D, "interi", "2*.m4a")))
    coda = len(glob.glob(os.path.join(D, "2*.m4a")))
    df = os.statvfs(HOME)
    try:
        drive = int(open(ARCHIVIATI_N).read().split()[0])
    except (OSError, ValueError, IndexError):
        drive = None
    return dict(notti=righe, analizzati=interi, coda=coda, libero=df.f_bavail * df.f_frsize, totale=df.f_blocks * df.f_frsize, drive=drive)


def disegna_avanzamento(dati, out):
    """Immagine 1080x1080 in stile giornale (palette 'carta e denim'): barre orizzontali, colore = significato, testo >= 20 pt,
    niente torte/3D/heatmap. Ritorna (png, sovrapposizioni): coppie di testi i cui riquadri si toccano (deve essere [])."""
    P, plt = grafici.P, grafici.plt
    M, L, T = grafici.MARGINE, grafici.LARGO, grafici.TESTO
    fig = grafici._fig(grafici.W)
    ax = grafici._tela(fig)
    testi = []

    def tx(x, y, s_, **k):
        k.setdefault("fontsize", T); k.setdefault("va", "center"); k.setdefault("color", P["inchiostro"])
        t_ = ax.text(x, y, s_, **k); testi.append(t_); return t_

    def barra(y, parti, tot, x0, x1, h=0.036):
        x = x0
        for v, c in parti:
            w = (x1 - x0) * v / tot if tot else 0
            if w > 0:
                ax.add_patch(plt.Rectangle((x, y - h / 2), w, h, color=c, lw=0))
            x += w
        ax.add_patch(plt.Rectangle((x0, y - h / 2), x1 - x0, h, fill=False, ec=P["griglia"], lw=1.5))

    # griglia verticale: testo 20 pt = ~0.052 di altezza, righe a passo 0.056 -> niente riquadri che si toccano
    tx(M, 0.93, "Avanzamento", fontsize=36, va="baseline", color=P["inchiostro"])
    tx(M, 0.865, "Clip per notte", fontsize=24)
    voci = [(P["sonno"], "giudicate"), (P["sveglio"], "da fare: 1 tasto"), (P["sonno_chiaro"], "da fare: 20 s"), (P["griglia"], "escluse")]
    for i, (c, nome) in enumerate(voci):
        x = M + L * (i % 2) / 2; y = 0.79 - 0.057 * (i // 2)
        ax.add_patch(plt.Rectangle((x, y - 0.012), 0.024, 0.024, color=c, lw=0)); tx(x + 0.035, y, nome, color=P["grigio"])
    righe = list(dati["notti"].items())
    mx = max([sum(r.values()) for _, r in righe] + [1])
    x0, x1 = M + 0.17, 1 - M - 0.21
    for i, (d, r) in enumerate(righe):
        y = 0.655 - i * 0.056
        dd = datetime.strptime(d, "%Y%m%d")
        tx(M, y, f"{grafici.GG[dd.weekday()]} {dd.day}", color=P["grigio"])
        barra(y, [(r["fatte"], P["sonno"]), (r["precise"], P["sveglio"]), (r["finestre"], P["sonno_chiaro"]), (r["escluse"], P["griglia"])], mx, x0, x1)
        da = r["precise"] + r["finestre"]
        tx(1 - M, y, f"{r['fatte']}/{r['fatte'] + da}" if r["fatte"] + da else "-", ha="right", color=P["sonno"] if not da else P["inchiostro"])
    # telefono: stesse colonne delle notti (nome | barra | numero)
    tx(M, 0.255, "Telefono", fontsize=24)
    tot_a = dati["analizzati"] + dati["coda"]
    tx(M, 0.19, "analisi", color=P["grigio"])
    barra(0.19, [(dati["analizzati"], P["sonno"]), (dati["coda"], P["sveglio"])], max(tot_a, 1), x0, x1)
    tx(1 - M, 0.19, f"{dati['analizzati']}/{tot_a}", ha="right", color=P["sveglio"] if dati["coda"] else P["sonno"])
    tx(M, 0.134, "liberi", color=P["grigio"])
    barra(0.134, [(dati["libero"], P["sonno_chiaro"])], dati["totale"] or 1, x0, x1)
    tx(1 - M, 0.134, f"{dati['libero'] / 2**30:.0f} GB", ha="right")
    if dati["drive"] is not None:
        tx(M, 0.078, "Drive", color=P["grigio"])
        tx(x0, 0.078, f"{dati['drive']} blocchi archiviati")
    fig.canvas.draw()
    r_ = fig.canvas.get_renderer()
    bb = [(t_.get_text(), t_.get_window_extent(r_)) for t_ in testi]
    tocchi = [(a[0], b[0]) for i, a in enumerate(bb) for b in bb[i + 1:] if a[1].overlaps(b[1])]
    fig.savefig(out, dpi=grafici.DPI, facecolor=P["carta"])
    plt.close(fig)
    return out, tocchi


def avanzamento_pronto():
    """(png | None): l'immagine in cache se ha meno di 5 minuti; se no ne parte la rigenerazione in un thread nice."""
    if AV["png"] and os.path.exists(AV["png"]) and time.time() - AV["t"] < AV_CACHE_S:
        return AV["png"]
    if not (AV["lavoro"] and AV["lavoro"].is_alive()):
        def lavoro():
            try:
                os.nice(10)
            except (AttributeError, OSError):
                pass
            try:
                with GRAF:
                    png, tocchi = disegna_avanzamento(dati_avanzamento(), F("avanzamento.png"))
                if tocchi:
                    log(f"avanzamento: testi sovrapposti {tocchi}", rumore=True)
                AV["png"], AV["t"] = png, time.time()
            except Exception as e:
                log(f"avanzamento: {e}")
        AV["lavoro"] = threading.Thread(target=lavoro, daemon=True)
        AV["lavoro"].start()
    return None


def mostra_avanzamento(msg=None):
    """📊 dal tasto in /stato: la prima volta una foto nuova, ⟳ la cambia sullo STESSO messaggio. Il disegno e' in un thread."""
    def consegna():
        png = avanzamento_pronto()  # (se serve parte il disegno in un altro thread nice)
        for _ in range(120):  # fino a ~60 s di attesa, qui nel thread: i tocchi non aspettano
            if png or not (AV["lavoro"] and AV["lavoro"].is_alive()):
                break
            time.sleep(0.5)
        png = png or AV["png"]
        if not png:
            return scrivi(TX.t("av_errore"))
        tasti = kb([(TX.b("av_aggiorna"), "av:1")])
        testo = TX.t("av_card", ora=f"{datetime.now():%H:%M}")
        if msg:
            cambia_media(msg, "photo", png, testo, tasti)
        else:
            unico("av", foto(max_4_5(png), testo, tasti))
    threading.Thread(target=consegna, daemon=True).start()


# ---------------------------------------------------------------- ⚙️ /stato: card (foto) dopo il testo, disegnata in un thread
SC = {"lavoro": None}


def dati_stato_card(ora=None):
    """Tutto da file/telefono, niente rete. Persona: stato.json (<10'), riposo dichiarato; dispositivi: dispositivi.json."""
    ora = ora or datetime.now()
    s = leggi_json(os.path.join(HOME, "stato.json"))
    try:
        fresco = 0 <= (ora - datetime.fromisoformat(s["t"])).total_seconds() <= 600
    except (KeyError, ValueError, TypeError):
        fresco = False
    j = s.get("utente") if fresco else "?"
    persona = dict(stato={"dorme": "Dorme", "sveglio": "Sveglio"}.get(j, "Incerto"), fiducia=s.get("fiducia") if fresco and j in ("dorme", "sveglio") else None)
    if riposo_fino():
        persona = dict(stato="Riposo", fiducia=None, fino=riposo_fino())
    d = leggi_json(F("dispositivi.json"))
    df = os.statvfs(HOME)
    try:
        bat = json.loads(subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=10).stdout or "{}").get("percentage")
    except Exception:
        bat = None
    def eta(iso):
        try:
            return int((ora - datetime.fromisoformat(iso)).total_seconds() // 60)
        except (ValueError, TypeError):
            return None
    s56 = d.get("a56_sleep") or []
    pc_ok = eta(d.get("pc"))
    reg_pc = bool(d.get("pc_rec")) and eta(d["pc_rec"]) is not None and eta(d["pc_rec"]) < 40
    a21_reg = time.time() - ultimo_rec() < 120 and not in_pausa()
    libero = df.f_bavail * df.f_frsize / 2**30
    devs = [dict(nome="A21s", colore="verde" if a21_reg and libero >= 0.5 else "rosso" if libero < 0.5 else "giallo",
                 bat=bat, gb=libero, fa=0, adesso=a21_reg),
            dict(nome="A56", colore=None, bat=None, gb=None, fa=eta(d.get("a56")), adesso=bool(s56) and s56[1].endswith("started"))]
    if d.get("pc"):
        devs.append(dict(nome="PC", colore=None, bat=None, gb=d.get("pc_gb"), fa=pc_ok, adesso=reg_pc))
    for v in devs:
        v["colore"] = "verde" if v["adesso"] and (v["fa"] is None or v["fa"] <= 30) else "rosso"
    av = dati_avanzamento(ora)
    da_fare = sum(r["precise"] + r["finestre"] for r in av["notti"].values())
    lavori = [f"Analisi: {av['coda']} blocchi in coda" if av["coda"] else "Analisi: in pari",
              f"Clip da giudicare: {da_fare}" if da_fare else "Clip: tutte giudicate"]
    rec = s.get("rec") if fresco else None  # guardiano_dispositivi.py: esiti ok/muto/fermo per dispositivo
    if rec and any(rec.get(k, {}).get("esito") not in (None, "ok", "riavviato") for k in ("a21s", "a56")):
        lavori.insert(0, " · ".join(rec[k]["testo"] for k in ("a21s", "a56", "pc") if k in rec))
    lavori.append(riga_drive(leggi_json(F("stato_drive.json"))))
    lavori.append(riga_kaggle(leggi_json(F("stato_kaggle.json"))))
    ok, mot = puo_registrare()
    reg = "In pausa" if ok is None else "Stanotte registra" if ok else "NON registra: " + ", ".join(mot)
    mot_ora = ["in pausa"] if in_pausa() else ["microfono fermo"] if not a21_reg else []
    if mot_ora and persona["stato"] == "Sveglio":
        mot_ora.append("sei sveglio")
    adesso = "Adesso registra" if a21_reg else "Adesso NON registra: " + ", ".join(mot_ora)
    return dict(persona=persona, devs=devs, lavori=lavori, reg=reg, ok=ok, ora=f"{ora:%H:%M}", adesso=adesso, adesso_ok=a21_reg)


def firma_stato(dati):
    """Cosa fa cambiare la card da sola: stato persona + chi registra adesso (non l'ora, non i lavori)."""
    return [dati["persona"]["stato"], [[v["nome"], bool(v["adesso"])] for v in dati["devs"]]]


def _hm(iso):
    """(nota rimossa)"""
    try:
        t = datetime.fromisoformat(iso)
        return f"{t:%H:%M}" if t.date() == datetime.now().date() else f"{t:%d/%m %H:%M}"
    except (ValueError, TypeError):
        return "?"


def riga_drive(d):
    """stato_drive.json lo scrive il PC a fine giro di archivia_interi.py. Assente = non so."""
    if not d:
        return "Drive: non so"
    ok = f"ultimo ok {_hm(d['ultimo_ok'])}, {d.get('ultimo_ok_file')} file {str(d.get('ultimo_ok_gb')).replace('.', ',')} GB" if d.get("ultimo_ok") else "nessun archivio riuscito"
    return f"Drive: ERRORE ({d['errori']}), {ok}" if d.get("errori") and not d.get("file") else f"Drive: {ok}"


def riga_kaggle(d):
    """stato_kaggle.json lo scrive kaggle_mattino.py (in corso / ok / errore). Assente = non so."""
    if not d:
        return "Kaggle: non so"
    notte = f"{d['notte'][6:8]}/{d['notte'][4:6]}" if len(d.get("notte") or "") == 8 else "?"
    gpu = f", {d['gpu_min']} min GPU" if d.get("gpu_min") else ""
    return f"Kaggle: notte {notte} {d.get('esito', '?')} alle {_hm(d.get('t'))}{gpu}"


def disegna_stato_card(dati, out):
    """Card 1080x1080 (carta e denim): persona grande, una riga per dispositivo con pallino, lavori in basso. -> (png, sovrapposizioni)."""
    P, plt = grafici.P, grafici.plt
    M, T = grafici.MARGINE, grafici.TESTO
    fig = grafici._fig(grafici.W); ax = grafici._tela(fig); testi = []
    def tx(x, y, s_, **k):
        k.setdefault("fontsize", T); k.setdefault("va", "center"); k.setdefault("color", P["inchiostro"])
        t_ = ax.text(x, y, s_, **k); testi.append(t_); return t_
    pe = dati["persona"]
    col = {"Dorme": P["sonno"], "Sveglio": P["sveglio"], "Riposo": P["sonno_chiaro"]}.get(pe["stato"], P["grigio"])
    ax.add_patch(plt.Rectangle((M, 0.73), 0.016, 0.19, color=col, lw=0))
    tx(M + 0.04, 0.83, pe["stato"], fontsize=grafici.TESTO_GRANDE, va="baseline", color=col)
    sub = f"fino alle {pe['fino']}" if pe.get("fino") else f"fiducia {round(pe['fiducia'] * 100)}%, stima" if pe.get("fiducia") else "stima non sicura"
    tx(M + 0.04, 0.75, sub, color=P["grigio"])
    tx(1 - M, 0.83, dati["ora"], fontsize=grafici.TESTO_GRANDE, va="baseline", ha="right", color=P["inchiostro"])
    tx(M + 0.04, 0.69, dati["adesso"], color=P["musica"] if dati["adesso_ok"] else P["russa"])
    tx(M + 0.04, 0.635, dati["reg"], color={True: P["musica"], False: P["russa"]}.get(dati["ok"], P["grigio"]))
    verde, giallo, rosso = P["musica"], P["sveglio"], P["russa"]
    for i, v in enumerate(dati["devs"]):
        y = 0.58 - i * 0.085
        ax.add_patch(plt.Circle((M + 0.016, y), 0.017, color={"verde": verde, "giallo": giallo, "rosso": rosso}[v["colore"]], lw=0))
        tx(M + 0.06, y, v["nome"], fontsize=24)
        tx(0.31, y, f"{v['bat']}%" if isinstance(v["bat"], int) else "", color=P["grigio"])
        tx(0.45, y, f"{v['gb']:.0f} GB" if v["gb"] is not None else "", color=P["grigio"])
        tx(0.58, y, "rec" if v["adesso"] else "no rec", color=P["grigio"], fontsize=24)
        tx(1 - M, y, "adesso" if v["fa"] is not None and v["fa"] < 3 else f"{v['fa']}' fa" if v["fa"] is not None and v["fa"] < 90
           else f"{v['fa'] // 60}h fa" if v["fa"] is not None else "mai visto", ha="right")
    tx(M, 0.30, "In corso", fontsize=24)
    for i, riga in enumerate(dati["lavori"]):
        tx(M, 0.235 - i * 0.06, riga, color=P["grigio"])
    fig.canvas.draw()
    r_ = fig.canvas.get_renderer()
    bb = [(t_.get_text(), t_.get_window_extent(r_)) for t_ in testi if t_.get_text()]
    tocchi = [(a[0], b[0]) for i, a in enumerate(bb) for b in bb[i + 1:] if a[1].overlaps(b[1])]
    fig.savefig(out, dpi=grafici.DPI, facecolor=P["carta"])
    plt.close(fig)
    return out, tocchi


SCJ = lambda: F("stato_card.json")  # {"msg", "t", "firma", "ctl"}: l'ultima card, per aggiornarla da sola


def manda_copertura(day=None, msg=None, auto=False):
    """Una foto aggiuntiva: la scheda notte conserva mappa e comandi esistenti."""
    from mattino_card import disegna
    day = day or (datetime.now() - timedelta(days=int(datetime.now().hour < 12))).strftime('%Y%m%d')
    if not (len(day) == 8 and day.isdigit()):
        return
    dati = leggi_json(F(f'copertura_{day}.json'))
    if not dati:
        if not auto:
            return scrivi('Copertura non ancora disponibile: il PC la prepara dopo mezzogiorno.')
        return
    stato_ = leggi_json(F('coperture_inviate.json'))
    if auto and day in stato_:
        return
    with GRAF:
        png = disegna(dati, F(f'copertura_{day}.png'), grafici)
    cap = f"Cosa hai in mano · notte {day[6:8]}/{day[4:6]}"
    tasti = kb([(TX.b('av_aggiorna'), f'cop:{day}')], [(TX.b('cop_stato'), 'st')])
    if msg:
        cambia_media(msg, 'photo', png, cap, tasti)
        mid = msg
    else:
        mid = foto(png, cap, tasti)
    if auto and mid:
        stato_[day] = mid
        scrivi_json(F('coperture_inviate.json'), stato_)
    return mid


def copertura_automatica():
    manda_copertura(auto=True)


def manda_stato_card(msg=None, auto=False):
    """/stato = SOLO la foto (didascalia minima + tastiera di stato()), in un thread nice: il tocco non aspetta.
    msg = messaggio da aggiornare sul posto (tasto Aggiorna). Se il disegno fallisce: il vecchio testo, mai silenzio.
    auto=True: aggiornamento da solo (stato_card_auto): niente se la firma non e' cambiata, e mai un messaggio nuovo."""
    if SC["lavoro"] and SC["lavoro"].is_alive():
        return
    def lavoro():
        try:
            os.nice(10)
        except (AttributeError, OSError):
            pass
        testo, tasti = None, None
        try:
            dati = dati_stato_card()
            if auto and firma_stato(dati) == leggi_json(SCJ()).get("firma"):
                return
            testo, tasti = stato()
            with GRAF:
                png, tocchi = disegna_stato_card(dati, F("stato_card.png"))
            if tocchi:
                log(f"stato card: testi sovrapposti {tocchi}", rumore=True)
            cap = TX.t("st_card", ora=dati["ora"], cosa=dati["persona"]["stato"].lower())
            mid = msg
            if msg:
                cambia_media(msg, "photo", png, cap, tasti)
            else:
                mid = foto(max_4_5(png), cap, tasti)
                unico("stato", mid)
            scrivi_json(SCJ(), dict(msg=mid, t=time.time(), firma=firma_stato(dati), ctl=time.time()))
        except Exception as e:
            log(f"stato card: {e}")
            if testo and not auto:
                unico("stato", scrivi(testo, tasti))
    SC["lavoro"] = threading.Thread(target=lavoro, daemon=True)
    SC["lavoro"].start()


def stato_card_auto():
    """L'ULTIMA card /stato (< 12 h) si aggiorna sul posto (editMessageMedia) se cambia persona o chi registra.
    Controllo al massimo ogni 2 minuti; disegno nel thread nice di manda_stato_card, il giro principale non aspetta."""
    c = leggi_json(SCJ())
    if not c.get("msg") or time.time() - c["t"] > 12 * 3600 or time.time() - c.get("ctl", 0) < 120:
        return
    if SC["lavoro"] and SC["lavoro"].is_alive():
        return
    scrivi_json(SCJ(), dict(c, ctl=time.time()))
    manda_stato_card(c["msg"], auto=True)


# ---------------------------------------------------------------- loop / pausa / stato
def loop_vivo():
    return subprocess.run(["pgrep", "-f", "bash .*home/rec.sh"], capture_output=True).returncode == 0


def in_pausa():
    if not os.path.exists(PAUSA):
        return False
    scad = (open(PAUSA).read().splitlines() or [""])[0].strip()
    if scad and datetime.now() >= datetime.fromisoformat(scad):
        os.remove(PAUSA)  # pausa scaduta: si riparte da soli, e lo dico (S10: il menu torna ⏸️)
        nota("riprendi")
        prova("sendMessage", chat_id=CHAT, text=TX.t("pausa_finita", ora=scad[11:16]), parse_mode="HTML",
              reply_markup=menu(), disable_notification=True)
        return False
    return True


def ultimo_rec():
    rec = sorted(glob.glob(f"{D}/2*.m4a"))
    return os.path.getmtime(rec[-1]) if rec else 0


def puo_registrare():
    """
    Solo letture: batteria, file audio che cresce, spazio, microfono che sente. -> (True/False, [motivi]);
    (None, []) se in pausa (scelta sua, non e' un guasto). ponytail: soglie a occhio, tararle se danno falsi allarmi."""
    if in_pausa():
        return None, []
    mot = []
    try:
        bat = json.loads(subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=10).stdout or "{}")
        # Prima ogni stacco/riattacco del caricatore debole = 2 messaggi ("spam notifiche").
        if bat.get("plugged", "UNPLUGGED") == "UNPLUGGED" and int(bat.get("percentage", 100)) < 15:
            mot.append(TX.t("motivo_carica"))
    except Exception:
        pass  # batteria illeggibile: non e' un motivo per dire "non registra"
    if time.time() - ultimo_rec() > 120:
        mot.append(TX.t("motivo_fermo"))
    df = os.statvfs(HOME)
    if df.f_bavail * df.f_frsize < 0.5 * 2**30:  # ~15 MB ogni 30': 0,5 GB = una notte scarsa
        mot.append(TX.t("motivo_spazio"))
    mins = sorted(glob.glob(f"{D}/minuti_*.csv"))
    try:
        avvio = min(os.stat(f"/proc/{p}").st_mtime for p in
                    subprocess.run(["pgrep", "-f", "rec.sh"], capture_output=True, text=True).stdout.split())
    except Exception:
        avvio = time.time()  # avvio ignoto: meglio nessun allarme che uno falso
    if mins:  # microfono sordo = volume identico minuto dopo minuto (ultima mezz'ora analizzata dopo l'avvio)
        db = [r.split(",")[1] for r in open(mins[-1]).read().split()[1:]
              if datetime.fromisoformat(r.split(",")[0]).timestamp() >= avvio][-30:]
        if len(db) >= 10 and len(set(db)) <= 1:
            mot.append(TX.t("motivo_sordo"))
    return not mot, mot


def sorveglia_registrazione():
    """Grafo a 2 stati (puo' / non puo' registrare): avvisa SOLO al cambio, confermato da 2 controlli di fila
    (no falsi allarmi per un blocco che si chiude). Vale anche in silenzio: e' l'unico avviso che deve arrivare."""
    ok, mot = puo_registrare()
    if ok is None:
        return
    s = leggi_json(F("verdetto.json")) or {"ok": True, "dubbio": 0}
    if ok == s["ok"]:
        s["dubbio"] = 0
    else:
        s["dubbio"] = s.get("dubbio", 0) + 1
        ultimo = datetime.fromisoformat(s["da"]).timestamp() if s.get("da") else 0
        if s["dubbio"] >= 2 and time.time() - ultimo >= 2700:
            scrivi(TX.t("verdetto_ok") if ok else TX.t("verdetto_ko", motivi=", ".join(mot)), suono=not ok)
            s = {"ok": ok, "dubbio": 0, "da": datetime.now().isoformat(timespec="minutes")}
    scrivi_json(F("verdetto.json"), s)


def tieni_vivo_loop(avvisa=True):
    if TARATURA or in_pausa():
        return
    fermo = loop_vivo() and time.time() - ultimo_rec() > 300
    if fermo:
        for pid in subprocess.run(["pgrep", "-f", "bash .*home/rec.sh"], capture_output=True, text=True).stdout.split():
            subprocess.run(["kill", pid], capture_output=True)
        subprocess.run(["termux-microphone-record", "-q"], capture_output=True, timeout=20)
        log("loop fermo da 5' (nessun audio nuovo): riavvio")
    if not loop_vivo():
        subprocess.Popen(["setsid", "nohup", "bash", os.path.join(HOME, "rec.sh")], cwd=HOME,
                         stdout=open(os.path.join(HOME, "rec.log"), "a"), stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True)
        # nessun messaggio (FASTIDIO_VANTAGGIO: si ripara da solo = rumore); il buco si vede nel mattino ("⚠️ 14' senza audio")
        log("loop ripartito")


def controlla_freschezza():
    import threading
    import freschezza
    if TARATURA or in_pausa():
        return
    precedente = getattr(controlla_freschezza, "thread", None)
    if precedente and precedente.is_alive():
        return
    def esegui():
        try:
            freschezza.controlla(HOME, D, QUI, tieni_vivo_loop,
                                 lambda: scrivi(TX.t("all_freschezza")),
                                 sospeso=lambda: bool(TARATURA) or in_pausa())
        except Exception as e:
            log(f"freschezza: {type(e).__name__}")
    controlla_freschezza.thread = threading.Thread(target=esegui, daemon=True)
    controlla_freschezza.thread.start()


def ora_letto():
    """(quando, fonte): prossima ora a cui va a letto, dall'inizio notte (storico()) di IERI; se non c'e' (ultima notte
    """
    now = datetime.now()
    ini = [x["inizio"] if isinstance(x["inizio"], datetime) else datetime.fromisoformat(str(x["inizio"]))
           for x in storico() if x.get("inizio")][-7:]  # notti vere (senza le tolte), come settimana()
    if not ini:
        return None
    m = lambda t: (t.hour * 60 + t.minute - 720) % 1440
    ieri = now - ini[-1] < timedelta(hours=36)
    min_ = m(ini[-1]) if ieri else sum(map(m, ini)) // len(ini)
    base = now.replace(hour=12, minute=0, second=0, microsecond=0)
    if now < base:
        base -= timedelta(days=1)
    q = base + timedelta(minutes=min_)
    return (q if q > now else q + timedelta(days=1)), "ieri" if ieri else "media"


def pausa(fino, fuori=False):
    """fino: '1h' | '3h' | 'letto' | '20' | 'domani' | 'sempre' | datetime. fuori=True: dorme fuori (niente promemoria delle 22)."""
    now = datetime.now()
    if fino == "20":
        scad = now.replace(hour=20, minute=0, second=0, microsecond=0)
        if scad - now < timedelta(hours=2):
            scad += timedelta(days=1)  # S10: "fino alle 20" con meno di 2h = domani
    else:
        scad = {"1h": now + timedelta(hours=1), "3h": now + timedelta(hours=3), "sempre": None,
                "domani": (now if now.hour < 8 else now + timedelta(days=1)).replace(hour=8, minute=0, second=0, microsecond=0),
                "letto": (ora_letto() or (now + timedelta(hours=3),))[0]}.get(fino, fino)
    open(PAUSA, "w").write((scad.isoformat(timespec="minutes") if scad else "") + ("\nfuori" if fuori else ""))
    nota("pausa", scad.isoformat(timespec="minutes") if scad else "sempre")
    subprocess.run(["pkill", "-f", "^bash .*home/rec.sh"])
    subprocess.run(["termux-microphone-record", "-q"], capture_output=True)
    if not scad:
        return TX.t("pausa_sempre")
    return TX.t("pausa_fino_domani" if scad.date() > now.date() else "pausa_fino", ora=f"{scad:%H:%M}")


def riprendi():
    gia = not in_pausa()
    if os.path.exists(PAUSA):
        os.remove(PAUSA)
    nota("riprendi")
    tieni_vivo_loop(avvisa=False)
    return TX.t("riprendi_gia" if gia and loop_vivo() else "riprendi")


def promemoria_pausa():
    """Alle 22 se e' in pausa senza scadenza (e non dorme fuori): te lo ricordo (muto)."""
    oggi = datetime.now().strftime("%Y%m%d")
    f = F("promemoria.txt")
    righe = open(PAUSA).read().splitlines() if os.path.exists(PAUSA) else []
    if in_pausa() and not (righe[0].strip() if righe else "") and "fuori" not in righe and datetime.now().hour >= 22 \
            and (not os.path.exists(f) or open(f).read() != oggi):
        open(f, "w").write(oggi)
        scrivi(TX.t("pausa_promemoria"), kb([(TX.b("riprendi"), "pz:via")]))


RIPOSO = F("dichiarato.json")  # lo legge stato.osserva -> albero.stima: {"stato": "riposo", "da": ISO, "fino": ISO}


def riposo_fino():
    """'HH:MM' di fine del riposo dichiarato se ancora valido, se no ''. File rotto/scaduto = nessun riposo."""
    try:
        d = json.load(open(RIPOSO))
        if d.get("stato") == "riposo" and datetime.fromisoformat(d["fino"]) > datetime.now():
            return d["fino"][11:16]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        pass
    return ""


def riposo_inizia(minuti):
    ora = datetime.now()
    fino = ora + timedelta(minutes=minuti)
    scrivi_json(RIPOSO, dict(stato="riposo", da=f"{ora:%Y-%m-%dT%H:%M:%S}", fino=f"{fino:%Y-%m-%dT%H:%M:%S}"))
    return f"{fino:%H:%M}"


ZG = F("zona_grigia.json")
INCERTI = ("?", "dorme?", "sveglio?")


def dichiarato_valido(ora=None):
    """(nota rimossa)"""
    try:
        d = json.load(open(RIPOSO))
        return d["stato"] if datetime.fromisoformat(d["fino"]) > (ora or datetime.now()) else ""
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return ""


def dichiara(stato_, minuti, ora=None):
    ora = ora or datetime.now()
    scrivi_json(RIPOSO, dict(stato=stato_, da=f"{ora:%Y-%m-%dT%H:%M:%S}", fino=f"{ora + timedelta(minutes=minuti):%Y-%m-%dT%H:%M:%S}"))


def abitudine(ora):
    """(notti in cui a quest'ora dormiva gia', notti note) dagli inizi in cache di letto_prev (_INIZI)."""
    h = lambda t: t.hour + t.minute / 60 - (24 if t.hour >= 12 else 0)
    v = [k for k in _INIZI.values() if k]
    return sum(1 for k in v if h(k) <= h(ora)), len(v)


def zona_grigia(ora=None):
    """
    altri giorni alla stessa ora". Dalle 21 alle 7, stato in tempo reale incerto e fresco, niente gia' dichiarato,
    al massimo una domanda all'ora (muta). La risposta va in dichiarato.json e vince sulla deduzione (albero.DICHIARABILI)."""
    ora = ora or datetime.now()
    if not (ora.hour >= 21 or ora.hour < 7) or dichiarato_valido(ora):
        return None
    s = leggi_json(os.path.join(HOME, "stato.json")) or {}
    try:
        fresco = 0 <= (ora - datetime.fromisoformat(s.get("t", ""))).total_seconds() <= 600
        z = leggi_json(ZG) or {}
        if z.get("chiesto") and (ora - datetime.fromisoformat(z["chiesto"])).total_seconds() < 3600:
            return None
    except (ValueError, TypeError):
        return None
    if not fresco or s.get("livello") not in INCERTI:
        return None
    # Se non usa ne' telefono ne' PC da 20' non puo' rispondere e quasi certamente dorme: niente domanda.
    if not uso_fn(ora - timedelta(minutes=20), ora + timedelta(minutes=1)):
        return None
    n, tot = abitudine(ora)
    ab = "" if tot < 3 else (f"\nDi solito a quest'ora dormi gia' ({n} notti su {tot})." if 2 * n >= tot
                             else f"\nDi solito a quest'ora sei ancora sveglio ({tot - n} notti su {tot}).")
    m = scrivi("Non capisco se sei a letto." + ab, kb([("A letto", "zg:letto"), ("Sveglio", "zg:sveglio")]))
    scrivi_json(ZG, dict(chiesto=ora.isoformat(timespec="seconds"), msg=m))
    return m


def riposo_fine():
    if os.path.exists(RIPOSO):
        os.remove(RIPOSO)


def stato():
    """Riga 1 sempre; riga 2 SOLO se c'e' un problema, con il pulsante che lo risolve."""
    bat = json.loads(subprocess.run(["termux-battery-status"], capture_output=True, text=True).stdout or "{}")
    p = bat.get("percentage", "?")
    batt = TX.t("stato_batt_carica" if bat.get("plugged", "UNPLUGGED") != "UNPLUGGED" else
                "stato_batt_bassa" if isinstance(p, int) and p < 20 else "stato_batt", p=p)
    df = os.statvfs(HOME)
    gb_n = df.f_bavail * df.f_frsize / 2**30
    gb = f"{gb_n:.1f}".replace(".", ",")
    registra = time.time() - ultimo_rec() < 120
    if in_pausa():
        scad = (open(PAUSA).read().splitlines() or [""])[0].strip()
        r1 = TX.t("stato_pausa", fino=f"fino alle {scad[11:16]}" if scad else "", batt=batt, gb=gb)
    else:
        r1 = TX.t("stato_registra" if registra else "stato_fermo", batt=batt, gb=gb)
    tasti = [(TX.b("disp_b"), "disp"), (TX.b("prova_b"), "prova"), (TX.b("stile_b"), "stile")]
    r2 = ""
    tasti.insert(0, (TX.b("av_aggiorna"), "st:riprova"))  # sempre: rifa' il controllo e ridisegna la card sul posto
    if not in_pausa() and not registra and ultimo_rec():
        r2 = TX.t("stato_riga2_fermo", ora=datetime.fromtimestamp(ultimo_rec()).strftime("%H:%M"))
    elif gb_n < 1:
        r2 = TX.t("stato_riga2_spazio")
    else:
        mins = sorted(glob.glob(f"{D}/minuti_*.csv"))
        ultimo = open(mins[-1]).read().split()[-1].split(",")[0] if mins else ""
        if registra and ultimo and datetime.now() - datetime.fromisoformat(ultimo) > timedelta(minutes=75):
            r2 = TX.t("stato_riga2_indietro", ora=ultimo[11:16])  # "sto ascoltando, pronto verso…"
    from analisi.stato_corrente import riepilogo, memoria
    corrente = riepilogo(os.path.join(HOME, "stato.json"))
    corrente += "\n" + memoria(os.path.join(HOME, "memoria.json"))
    ok, mot = puo_registrare()
    if ok is not None:  # prima riga = la risposta alla domanda vera: stanotte registra?
        r1 = (TX.t("verdetto_si") if ok else TX.t("verdetto_no", motivi=", ".join(mot))) + "\n" + r1
    if riposo_fino():
        r1 += "\n" + TX.t("stato_riposo", ora=riposo_fino())
    return r1 + (f"\n{r2}" if r2 else "") + "\n" + corrente, kb(tasti, [(TX.b("suoni"), "su"), (TX.b("settimana"), "set")], [(TX.b("cop_stanotte"), "cop:oggi")])  # ponytail: tasto 📊 (av:0) spento finche' il thread di disegno non e' provato in prova_bot: riattivare aggiungendo [(TX.b("avanz_b"), "av:0")]


def fa(iso):
    """(nota rimossa)"""
    if not iso:
        return TX.t("disp_mai")
    m = int((datetime.now() - datetime.fromisoformat(iso)).total_seconds() // 60)
    return TX.t("disp_ora") if m < 3 else TX.t("disp_fa", t=f"{m}'" if m < 90 else f"{m // 60}h")


def dispositivi():
    """📡 ultimo segno di vita di ogni dispositivo (A21s = qui; A56 e PC dal file che manda il PC)."""
    d = leggi_json(F("dispositivi.json"))
    reg = lambda si: TX.t("disp_registra" if si else "disp_non_registra")
    df = os.statvfs(HOME)
    gb = df.f_bavail * df.f_frsize / 2**30
    interi = glob.glob(os.path.join(D, "interi", "*.m4a"))  # pezzi da 30': consumo vero al giorno
    mb_giorno = sum(map(os.path.getsize, interi)) / len(interi) * 48 / 2**20 if interi else 290
    giorni = int(gb * 1024 / max(mb_giorno, 1))
    righe = [TX.t("disp_a21", rec=reg(time.time() - ultimo_rec() < 120), gb=f"{gb:.1f}".replace(".", ","),
                  giorni=giorni, barra=TX.barra(min(giorni / 30, 1)))]  # rocchetto in testo: pieno = 30 giorni
    s = d.get("a56_sleep") or []
    sleep = TX.t("disp_sleep_mai") if not s else \
        TX.t("disp_sleep_on" if s[1].endswith("started") else "disp_sleep_off", ora=s[0][11:16])
    righe.append(TX.t("disp_a56", a56=fa(d.get("a56", "")), sleep=sleep))
    if d.get("pc"):
        pc_rec = bool(d.get("pc_rec")) and datetime.now() - datetime.fromisoformat(d["pc_rec"]) < timedelta(minutes=40)
        pc_gb = "?" if d.get("pc_gb") is None else f"{d['pc_gb']:.0f}"
        righe.append(TX.t("disp_pc", pc=fa(d["pc"]), gb=pc_gb, rec=reg(pc_rec)))
    return "\n".join(righe)


def mappa_vecchia():
    """Dopo /spostati la mappa (e gli errori di posizione) non valgono piu' finche' il PC non ne fa una nuova."""
    s, c = F("spostati.txt"), F("disposizione.png")
    return os.path.exists(s) and (not os.path.exists(c) or os.path.getmtime(c) < os.path.getmtime(s))


def card_dispositivi():
    """📡 fatta coi mattoni (concept/MATTONI.md): una riga per dispositivo, niente testo oltre ai nomi."""
    import componenti
    d = leggi_json(F("dispositivi.json"))
    err = {} if mappa_vecchia() else d.get("err", {})
    df = os.statvfs(HOME)
    interi = glob.glob(os.path.join(D, "interi", "*.m4a"))
    mb_giorno = sum(map(os.path.getsize, interi)) / len(interi) * 48 / 2**20 if interi else 290
    libero = df.f_bavail * df.f_frsize
    s = d.get("a56_sleep") or []
    pc_rec = bool(d.get("pc_rec")) and datetime.now() - datetime.fromisoformat(d["pc_rec"]) < timedelta(minutes=40)
    stati = [dict(nome="A21s", rec=time.time() - ultimo_rec() < 120, mem=libero / (df.f_blocks * df.f_frsize),
                  giorni=int(libero / 2**20 / max(mb_giorno, 1)), err=err.get("A21s")),
             dict(nome="A56", rec=bool(s) and s[1].endswith("started"), mem=None, err=err.get("tuo telefono"))]
    if d.get("pc"):
        stati.append(dict(nome="PC", rec=pc_rec, mem=d["pc_gb"] / d["pc_tot"] if d.get("pc_tot") else None, err=0.0))
    return componenti.dispositivi(stati, F("dispositivi.png"))


def prova_live():
    """🎤 prova dal vivo: 5 s dal microfono -> video 'cosa sento adesso' con la divisione vera (YAMNet di sonno_tel)."""
    msg = scrivi(TX.t("prova_via"))
    subprocess.run(["pkill", "-f", "^bash .*home/rec.sh"])
    subprocess.run(["termux-microphone-record", "-q"], capture_output=True)
    f = F("prova.m4a")
    if os.path.exists(f):
        os.remove(f)
    subprocess.run(["termux-microphone-record", "-e", "aac", "-b", "64", "-r", "16000", "-c", "1", "-l", "5", "-f", f],
                   capture_output=True)
    time.sleep(6)
    subprocess.run(["termux-microphone-record", "-q"], capture_output=True)
    tieni_vivo_loop(avvisa=False)
    div = ""
    try:
        sys.path.insert(0, HOME)
        import sonno_tel  # stessa divisione delle clip notturne
        c = sonno_tel.classifica(f)
        if c:
            div = sonno_tel.pezzi([sonno_tel.etichetta_frame(c[5], c[0], j) for j in range(len(c[0]))])
    except Exception as e:
        log(f"prova divisione: {e}")
    fid = TX.fiducia("forse", TX.MOTIVI["musica"]) if "musica" in div else TX.fiducia("quasi")
    png, geo = grafici.clip(f, div or None, f"{datetime.now():%H:%M:%S}", "Adesso",
                            F("prova.png"), None, TX.t("clip_fiducia", fid=fid_parole(fid)))
    mp4 = grafici.clip_video(png, f, geo, F("prova.mp4"))
    prova("deleteMessage", chat_id=CHAT, message_id=msg)
    if mp4:
        manda_file("sendVideo", "video", mp4, {"caption": TX.t("prova_card", fid=fid), "parse_mode": "HTML",
                                               **dim_video(png), "supports_streaming": True}, "video/mp4")
    else:
        foto(png, TX.t("prova_card", fid=fid))


def salva_foto(m):
    """📷 foto della disposizione dei telefoni: salvata, il PC la copia (sonno_audio.manda_al_bot) e Claude la guarda."""
    fid = max(m["photo"], key=lambda x: x.get("file_size", 0))["file_id"]
    path = api("getFile", file_id=fid)["result"]["file_path"]
    os.makedirs(F("foto"), exist_ok=True)
    dati = urllib.request.urlopen(f"https://api.telegram.org/file/bot{TOKEN}/{path}", timeout=60).read()
    open(os.path.join(F("foto"), f"{datetime.now():%Y%m%d_%H%M%S}.jpg"), "wb").write(dati)
    if m.get("caption"):
        aggiungi_riga(F("commenti.txt"), "", f"{datetime.now():%Y-%m-%d %H:%M} | foto | {m['caption']}")
    scrivi(TX.t("foto_ok"))


# ---------------------------------------------------------------- 🎙️ registra suoni
def voce(nome):
    """Conferma a voce dal telefono (~/r_<nome>.ogg, testi.VOCE preparati sul PC)."""
    p = os.path.join(HOME, f"r_{nome}.ogg")
    if os.path.exists(p) and not in_silenzio():
        # registrazione della notte -> 3 h e mezza senza audio. Ora parte in background e non puo' bloccare niente.
        try:
            subprocess.Popen(["termux-media-player", "play", p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
        except OSError as e:
            log(f"voce: {e}")


def scelta_suoni(ancora=None):
    b = [(TX.mostra(s), "s:" + s) for s in suoni()]
    righe = [b[i:i + 3] for i in range(0, len(b), 3)]
    if ancora:
        righe.insert(0, [(TX.b("ancora", cat=TX.mostra(ancora)), "s:" + ancora)])  # D13
    STATO_UI["registra"] = time.time()  # UX (c): un testo libero adesso = nome di un suono nuovo
    return kb(*righe, [(TX.b("categorie"), "m:menu"), (TX.b("suoni"), "su"), (TX.b("fatto"), "r:fine")])


def registra_inizio(lab, msg):
    if TARATURA:
        registra_fine(salva=True)
    subprocess.run(["pkill", "-f", "^bash .*home/rec.sh"])  # pausa registrazione notturna (riparte alla fine)
    subprocess.run(["termux-microphone-record", "-q"], capture_output=True)
    os.makedirs(CAL, exist_ok=True)
    etich = "ambiente" if lab == "silenzio" else lab  # nome della classe usato dal modello
    f = os.path.join(CAL, f"{etich}__tg__{datetime.now():%Y%m%d_%H%M%S}.m4a")
    voce("vai")
    time.sleep(1.2)  # la voce non deve finire nel pezzo
    subprocess.run(["termux-microphone-record", "-e", "aac", "-b", "64", "-r", "16000", "-c", "1", "-l", str(MAX_REG),
                    "-f", f], capture_output=True)
    TARATURA.update(file=f, lab=lab, t0=time.time(), msg=msg)
    modifica(msg, TX.t("reg_in_corso", cat=TX.mostra(lab), max=MAX_REG),
             kb([(TX.b("stop"), "r:stop"), (TX.b("cancella"), "r:canc")]))


def registra_fine(salva, auto=False):
    subprocess.run(["termux-microphone-record", "-q"], capture_output=True)
    lab, f, msg = TARATURA["lab"], TARATURA["file"], TARATURA["msg"]
    dur = min(time.time() - TARATURA["t0"], MAX_REG)
    TARATURA.clear()
    cat = TX.mostra(lab)
    if not salva or dur < 1.5:
        if os.path.exists(f):
            os.remove(f)
        voce("cancellato")
        testo = TX.t("reg_cancellato", cat=cat) if salva is False else TX.t("reg_corto", cat=cat)
    else:
        voce("preso")
        n = len(glob.glob(os.path.join(CAL, ("ambiente" if lab == "silenzio" else lab) + "__*")))
        testo = TX.t("reg_auto_stop" if auto else "reg_salvato", cat=cat, s=round(dur), n=n)
    tieni_vivo_loop(avvisa=False)  # riparte la registrazione notturna
    modifica(msg, testo, scelta_suoni(ancora=lab))


def tastiera_tipi():
    b = [(TX.b("togli", cat=s), "x:" + s) for s in suoni()]
    return kb(*[b[i:i + 3] for i in range(0, len(b), 3)], [(TX.b("aggiungi"), "m:add"), (TX.b("fatto"), "m:ok")])


def lista_audio(msg=None):
    fs = sorted(glob.glob(os.path.join(CAL, "*__tg__*.m4a")), key=os.path.getmtime)[-8:]
    if not fs:
        return (modifica(msg, TX.t("suoni_vuoto")) if msg else scrivi(TX.t("suoni_vuoto")))
    righe = []
    for p in reversed(fs):
        n = os.path.basename(p)
        quando = datetime.fromtimestamp(os.path.getmtime(p)).strftime("%d/%m %H:%M")
        righe.append([(TX.b("ascolta", cat=TX.mostra(n.split("__")[0]), quando=quando), "p:" + n),
                      (TX.b("cancella_icona"), "d:" + n)])
    (modifica(msg, TX.t("suoni_titolo"), kb(*righe)) if msg else scrivi(TX.t("suoni_titolo"), kb(*righe)))


def cancella_audio(n):
    p = os.path.join(CAL, n)
    if os.path.exists(p):
        os.remove(p)
    aggiungi_riga(os.path.join(CAL, "cancellati.txt"), "", n)  # il PC lo legge e cancella la sua copia


# ---------------------------------------------------------------- 📝 nota
CHIESTO_ENERGIA = F("dati/chiesto_energia.txt")
# memoria si perdeva a ogni riavvio del bot (molti deploy) -> in un file, e al massimo una domanda ogni 4 h


def chiesto_da_poco(ora, ore=4):
    try:
        return ora - datetime.fromisoformat(open(CHIESTO_ENERGIA).read().strip()) < timedelta(hours=ore)
    except (OSError, ValueError):
        return False


def promemoria_energia():
    """
    domanda muta con i 4 tasti, solo se nelle ultime 3h non ha gia' scritto e non e' in pausa.
    ponytail: per ora intera; se diventa fastidioso -> togliere dalla lista dei 10' in main()."""
    ora = datetime.now()
    if ora.hour < 8 or ora.hour not in NOTE.ore_tipiche(note(), ora) or chiesto_da_poco(ora) or in_pausa():
        return
    if any(n["tipo"] in ("energia", "umore") and ora - datetime.fromisoformat(n["ts"]) < timedelta(hours=3) for n in note()):
        return
    os.makedirs(os.path.dirname(CHIESTO_ENERGIA), exist_ok=True)
    open(CHIESTO_ENERGIA, "w").write(ora.isoformat(timespec="minutes"))
    api("sendMessage", chat_id=CHAT, text="Come stai?", disable_notification=True,
        reply_markup=kb([(t, "n:e" + v) for v, t in NOTE.ENERGIA.items()], [(t, "n:u" + v) for v, t in NOTE.UMORE.items()]))


# codice = un tipo di NOTE.TIPI (flussi suoi: farmaco, fuori...) oppure "" = tasto suo (salva nota("altro", etichetta)).
TASTI_JSON = F("dati/note_tasti.json")
PROPOSTA = [None]  # testo libero in attesa di "aggiungo ai tasti?"


def tasti_note():
    try:
        return json.load(open(TASTI_JSON, encoding="utf-8"))
    except Exception:
        return [[k, TX.b("nota_" + k)] for k in NOTE.TIPI]


def salva_tasti(l):
    os.makedirs(os.path.dirname(TASTI_JSON), exist_ok=True)
    json.dump(l, open(TASTI_JSON, "w", encoding="utf-8"), ensure_ascii=False)


def proponi_tasto(t):
    """(nota rimossa)"""
    t = t.strip()[:30]
    if not t or len(t.split()) > 3 or any(e.lower().endswith(t.lower()) for _, e in tasti_note()):
        return
    PROPOSTA[0] = t
    scrivi(f"Aggiungo «📌 {t}» ai tuoi tasti?", kb([("Sì", "n:add"), ("No", "n:noadd")]))


def tastiera_modifica():
    l = tasti_note()
    b = [("✖ " + e, f"n:x{i}") for i, (_, e) in enumerate(l)]
    return kb(*[b[i:i + 3] for i in range(0, len(b), 3)], [("➕ Aggiungi", "n:nuovo"), ("✅ Fatto", "n:menu")])


SCALE = {"e": ("energia", "ENERGIA"), "u": ("umore", "UMORE"), "m": ("mente", "MENTE"), "s": ("sonno", "SONNO")}


def scala_di(k):
    """'e'|'u'|'m'|'s' -> (tipo, {valore: etichetta}) o (None, None)."""
    t = SCALE.get(k)
    return (t[0], getattr(NOTE, t[1])) if t else (None, None)


def tastiera_note(ora=None):
    """(nota rimossa)"""
    h = (ora or datetime.now()).hour
    righe = ("m", "s") if h >= 18 or h < 6 else ("e", "u")
    b = [(e, "n:" + c if c else f"n:#{i}") for i, (c, e) in enumerate(tasti_note())] + [("⚙️ Modifica", "n:mod")]
    return kb(*[[(t, f"n:{r}{v}") for v, t in scala_di(r)[1].items()] for r in righe],
              *[b[i:i + 3] for i in range(0, len(b), 3)])


def dopo_nota(tipo, valore="1"):
    ora = f"{datetime.now():%H:%M}"
    scala = {"energia": NOTE.ENERGIA, "umore": NOTE.UMORE, "mente": NOTE.MENTE, "sonno": NOTE.SONNO}.get(tipo)
    voce_ = TX.b("nota_" + tipo) if tipo in NOTE.TIPI else scala.get(valore, valore) if scala else valore
    testo = TX.t("nota_fatta_n", voce=voce_, n=valore, ora=ora) if valore.isdigit() and int(valore) > 1 and not scala else \
        TX.t("nota_fatta", voce=voce_ if tipo != "farmaco" else TX.b("nota_farmaco_nome", nome=valore), ora=ora)
    return testo, kb([(TX.b("nota_annulla"), "n:undo"), (TX.b("nota_1h"), "n:-1h"), (TX.b("nota_ancora"), "n:menu")])


def chiedi(testo, ph, chiave, **ctx):
    """force_reply: la risposta vale SOLO se risponde a questo messaggio entro 5' (S2)."""
    r = api("sendMessage", chat_id=CHAT, text=testo, parse_mode="HTML", disable_notification=True,
            reply_markup={"force_reply": True, "input_field_placeholder": ph})
    STATO_UI[chiave] = dict(t=time.time(), msg=r["result"]["message_id"], **ctx)
    MENU_NASCOSTO[0] = True  # il force_reply toglie la tastiera fissa: alla prossima risposta si rimanda (loop update)


MENU_NASCOSTO = [False]


def gestisci_nota(k, msg):
    ora = f"{datetime.now():%H:%M}"
    if k == "menu":
        modifica(msg, TX.t("nota_chiedi", ora=ora), tastiera_note())
    elif k == "undo":
        NOTE.annulla(NOTE_CSV); modifica(msg, TX.t("nota_annullata")); return TX.toast("nota_annullata")
    elif k == "-1h":
        NOTE.indietro_1h(NOTE_CSV)
        return TX.toast("nota_1h", ora=note()[-1]["ts"][11:16]) if note() else ""
    elif k in ("farmaco", "altro"):
        chiedi(TX.t("nota_" + k), TX.t(f"nota_{k}_ph"), "nota", tipo=k)
    elif k == "pisolino":
        nota("pisolino"); modifica(msg, TX.t("pisolino_via", ora=ora), kb([(TX.b("pisolino_fine"), "n:sveglio")]))
    elif k == "sveglio":
        da = next((n["ts"] for n in reversed(note()) if n["tipo"] == "pisolino"), None)
        nota("pisolino_fine")
        if da:
            m = int((datetime.now() - datetime.fromisoformat(da)).total_seconds() // 60)
            modifica(msg, TX.t("pisolino_fine", da=da[11:16], a=ora, durata=TX.durata(m / 60)))
    elif k == "fuori":
        modifica(msg, TX.t("fuori_chiedi"), kb([(TX.b("fuori_casa"), "n:casa"), (TX.b("fuori_porto"), "n:porto")]))
    elif k == "casa":
        modifica(msg, TX.t("fuori_pausa", ora="14:00"), kb([(TX.b("fuori_si"), "fz:1"), (TX.b("fuori_2"), "fz:2"),
                                                            (TX.b("fuori_sempre"), "fz:0")]))
    elif k == "porto":
        nota("viaggio"); modifica(msg, TX.t("fuori_porto"), kb([(TX.b("tornato"), "n:tornato")]))
    elif k == "tornato":
        nota("tornato"); modifica(msg, TX.t("tornato"))
    elif k == "esame":
        modifica(msg, TX.t("esame_chiedi"), kb([(TX.b(f"esame_{x}"), f"ez:{g}") for x, g in
                                                (("oggi", 0), ("3", 3), ("7", 7), ("14", 14))]))
    elif k == "mod":
        modifica(msg, "Tocca un tasto per toglierlo, o aggiungine uno.", tastiera_modifica())
    elif k[:1] == "x" and k[1:].isdigit():
        l = tasti_note()
        if int(k[1:]) < len(l):
            via = l.pop(int(k[1:])); salva_tasti(l)
            modifica(msg, f"Tolto {via[1]}.", tastiera_modifica())
    elif k == "nuovo":
        chiedi("Che tasto aggiungo?", "es. camomilla", "nota", tipo="nuovo_tasto")
    elif k == "add" and PROPOSTA[0]:
        salva_tasti(tasti_note() + [["", "📌 " + PROPOSTA[0]]])
        modifica(msg, f"Aggiunto «📌 {PROPOSTA[0]}» ai tasti ✅"); PROPOSTA[0] = None
    elif k == "noadd":
        PROPOSTA[0] = None; modifica(msg, "Ok, resta solo come nota.")
    elif k[:1] == "#" and k[1:].isdigit() and int(k[1:]) < len(tasti_note()):  # tasto suo
        e = tasti_note()[int(k[1:])][1]
        nota("altro", e.removeprefix("📌 "))
        modifica(msg, TX.t("nota_fatta", voce=e, ora=ora), dopo_nota("altro")[1])
        return TX.toast("nota", emoji=e.split()[0], ora=ora)
    elif scala_di(k[:1])[1] and k[1:] in scala_di(k[:1])[1]:
        tipo, scala = scala_di(k[:1])
        nota(tipo, k[1:])
        testo, tasti = dopo_nota(tipo, k[1:])
        modifica(msg, testo, tasti)
        if tipo in ("mente", "sonno"):
            threading.Thread(target=commenta_ritmi, args=(msg, testo, tasti, tipo, int(k[1:])), daemon=True).start()
        return TX.toast("nota", emoji=scala[k[1:]].split()[0], ora=ora)
    elif k in NOTE.TIPI:
        nota(k)
        testo, tasti = dopo_nota(k)
        modifica(msg, testo, tasti)
        return TX.toast("nota", emoji=TX.b("nota_" + k).split()[0], ora=ora)
    return ""


# ---------------------------------------------------------------- pulsanti
def gestisci_pulsante(q):
    d, msg = q["data"], q["message"]["message_id"]
    if stantio(q):  # tocco accodato su una clip gia' passata (il bot era lento): niente salti a catena
        return TX.toast("gia_passato")
    if d.startswith(CLIP_TASTI):
        uso_tocco()  # un tocco sulla card clip = uso (stato_uso)
    risp = ""
    if d == "noop":
        pass
    elif d.startswith("v:"):
        _, day, v = d.split(":")
        aggiungi_riga(DIARIO, "day,voto,ora", f"{day},{v},{datetime.now():%Y-%m-%dT%H:%M}")
        r = analizza(day)
        prova("editMessageReplyMarkup", chat_id=CHAT, message_id=msg, reply_markup=tastiera_report(day, v))
        risp = TX.toast("voto", v=v)
        if MM and r and r.get("blocco") and MM.dopo_voto(int(v), r)[1] == "dubbio" and \
                not any(n["tipo"] == "dubbio" and n["valore"].startswith(day) for n in note()):
            scrivi(TX.t("dubbio", p=r["punteggio"]), kb([(TX.b(f"dubbio_{x}"), f"dq:{day}:{x}")
                                                        for x in ("orari", "leggero", "niente")]))
    elif d.startswith("dq:"):
        _, day, x = d.split(":")
        nota("dubbio", f"{day}:{x}"); modifica(msg, TX.t("dubbio_grazie"))
    elif d.startswith("nd:"):
        _, day, x = d.split(":")
        nota("notte", f"{day}:{x}"); didascalia(msg, TX.t("nd_" + x))
        if x == "fuori":
            mandati = leggi_json(MANDATI); mandati[day] = "fuori"; scrivi_json(MANDATI, mandati)
    elif d == "vl":  # 📋 clip classificate
        valutate()
    elif d.startswith("vl:"):  # filtro per categoria (":d" = solo quando dormiva), stesso messaggio
        t, _, s = d[3:].partition(":")
        valutate(t or None, msg, solo_dorme=s == "d")
    elif d == "rr:":  # [Ripassa le clip di oggi]
        ripasso()
    elif d == "as:":  # [Ascolta]: la coda delle non giudicate
        ascolta()
    elif d.startswith("cv:"):  # riapri una clip valutata
        p = os.path.join(D, os.path.basename(d[3:]))
        if os.path.exists(p):
            mostra_clip(p)
    elif d.startswith("nn:"):  # D5: non era una notte (pisolino, stanza vuota) -> fuori dallo storico, annullabile
        day = d[3:]
        nota("notte", f"{day}:tolta")
        didascalia(msg, TX.ascii_(TX.t("notte_tolta", data=f"{day[6:]}/{day[4:6]}")), kb([(TX.b("rimetti"), f"nr:{day}")]))
    elif d.startswith("nr:"):
        day = d[3:]
        nota("notte", f"{day}:rimessa")
        r = analizza(day)
        didascalia(msg, testo_dettagli(r, day)[:1024], tastiera_dettagli(r, day))
    elif d.startswith("pt:"):  # riascolta un punto della notte
        _, t, tipo = d.split(":")
        manda_punto(datetime.strptime(t, "%Y%m%d%H%M"), tipo)
    elif d.startswith("pv:"):  # la sua verifica: la fiducia si misura sui risultati
        _, tipo, giusto, t = d.split(":")
        aggiungi_riga(VERIFICHE, "ts,tipo,giusto,punto", f"{datetime.now():%Y-%m-%dT%H:%M},{tipo},{giusto},{t}")
        g, n = verificati(tipo)
        tt = datetime.strptime(t, "%Y%m%d%H%M")
        didascalia(msg, TX.t("punto_ok", ora=f"{tt:%H:%M}", cosa=PUNTI[tipo],
                             esito=TX.b("punto_si" if giusto == "1" else "punto_no")) + " · " + TX.t("verificato", g=g, n=n))
        risp = TX.toast("clip")
    elif d.startswith("sn:"):  # il suono della notte: la clip piu' dubbia di quella notte
        day = d[3:]
        c = [p for p in tutte_clip() if quando_clip(os.path.basename(p)).strftime("%Y%m%d") in
             (day, (datetime.strptime(day, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d"))]
        g = giudizi()
        c = sorted(c, key=lambda p: (os.path.basename(p) in g, "forse" not in fid_clip(p)[1]))
        ascolta(os.path.basename(c[0]) if c else None)
    elif d.startswith("dg:"):  # [Durata giusta]: diventa verita' sua (note.csv)
        day = d[3:]
        nota("notte", f"{day}:durata_ok")
        manda_notte(analizza(day), day, msg)
        risp = TX.ui("salvato", ora=f"{datetime.now():%H:%M}", giudizio="durata giusta")
    elif d.startswith("rc:"):  # [Correggi]: orari candidati con la prova accanto, sulla stessa scheda
        day = d[3:]
        r = analizza(day)
        if not (r and r.get("blocco") and r.get("inizio")):
            return "Non trovo ancora quando ti sei addormentato: riprova domattina."
        cand = candidati_inizio(r)
        scheda_notte(TX.ui("rep_quando") + "\n" + "\n".join(f"{t:%H:%M} {p}" for t, p in cand),
                     kb([(f"{t:%H:%M}", f"rk:{day}:{t:%H%M}") for t, _ in cand], [(TX.ui("rep_indietro"), f"nt:{day}")]),
                     day, msg)
    elif d.startswith("rk:"):
        _, day, hhmm = d.split(":")
        nota("notte", f"{day}:inizio:{hhmm}")
        manda_notte(analizza(day), day, msg)
        risp = TX.ui("salvato", ora=f"{datetime.now():%H:%M}", giudizio=f"inizio {hhmm[:2]}:{hhmm[2:]}")
    elif d.startswith("zg:"):  # risposta alla zona grigia: vince sulla deduzione (a letto 2 h, sveglio 1 h)
        letto = d == "zg:letto"
        dichiara("a_letto" if letto else "sveglio_detto", 120 if letto else 60)
        nota("stato", "a_letto" if letto else "sveglio")
        modifica(msg, "A letto: ne tengo conto e registro." if letto else "Sveglio: ok, ne tengo conto per un'ora.",
                 {"inline_keyboard": []})
        risp = "Salvato"
    elif d.startswith("mp:"):  # carosello della mappa: stessa scheda, cambia solo la foto
        _, day, pag = d.split(":")
        pg = pagine_mappa(day)
        pag = min(int(pag), len(pg)) if pg else 0
        if pag:
            cambia_media(msg, "photo", pg[pag - 1], leggi_json(F("scheda_notte.json")).get("testo"),
                         tastiera_report(day, r=None, pag=pag))
    elif d.startswith("s3:"):  # [Controlla 3 suoni]: carta/tastiera completa di Ascolta, coda = i 3
        c = tre_suoni(analizza(d[3:]))
        if c:
            ascolta(c[0], c)
        else:
            risp = TX.ui("rep_niente_suoni")
    elif d.startswith("tn:"):  # [Tutta la notte]: coda Ascolta filtrata sulla notte
        # TODO: ascolto a pezzi grandi (pezzi lunghi, ux/RISVEGLIO_02-10.md 2.6): passo successivo
        n = [os.path.basename(p) for p in coda_fresca() if notte_di(os.path.basename(p)) == d[3:]]
        if n:
            ascolta(n[0], n)
        else:
            risp = TX.ui("rep_niente_suoni")
    elif d.startswith("rh:"):
        _, day, hh = d.split(":")
        ascolta_ora(day, hh)
    elif d.startswith("det:"):
        dettagli(d[4:], msg)
    elif d.startswith("nr:"):
        notte_ricca(d[3:])
    elif d.startswith("ct:"):  # decisione 12: categorie ogni 5 s + momenti da ascoltare
        categorie_notte(d[3:], msg)
    elif d.startswith("tr:"):  # un tratto intero (video col cursore), originale o pulito
        _, x, y, p, *r = d.split(":")  # r = [riga, fonte]: video scremato / microfono
        tratto(datetime.strptime(x, "%Y%m%d%H%M%S"), datetime.strptime(y, "%Y%m%d%H%M%S"), p == "1", msg,
               int(r[0]) if r and r[0].isdigit() else "pause" if r and r[0] == "pause" else None,
               r[1] if len(r) > 1 and r[1] in ("a21s", "pc") else "a21s")
    elif d.startswith("nt:"):
        day = d[3:]
        r = analizza(day)
        if r and r.get("blocco"):
            manda_notte(r, day, msg)
        else:
            scheda_notte(testo_dettagli(r, day), tastiera_report(day, r=r), day, msg)
    elif d == "mese" and "mese" in APPROVATE:  # la coperta: una toppa per notte, colore = durata, bottone = ora in cui crolli
        import componenti
        unico("mese", foto(componenti.mese(storico(), F("mese.png")), TX.b("mese")))
    elif d == "set":
        risp = settimana(q)
    elif d.startswith("av:"):  # 📊 Avanzamento (0 = nuova foto, 1 = aggiorna sul posto); il disegno gira in un thread
        if grafici:
            if d == "av:1":
                AV["t"] = 0 if time.time() - AV["t"] > 20 else AV["t"]  # aggiorna davvero, ma non piu' di una volta ogni 20 s
            mostra_avanzamento(msg if d == "av:1" else None)
    elif d == "st":
        manda_stato_card()
    elif d.startswith('cop:'):
        manda_copertura(None if d == 'cop:oggi' else d[4:], None if d == 'cop:oggi' else msg)
    elif d == "stile":
        cambia_stile("emoji" if TX.STILE[0] == "ascii" else "ascii")
    elif d == "disp":  # mattoni: ago (registra?) · rocchetto (memoria) · bottone (posizione); numeri in didascalia
        testo = dispositivi() + ("\n" + TX.t("disp_spostati") if mappa_vecchia() else "")
        tasti = kb([(TX.b("mappa_b"), "mappa")]) if "mappa" in APPROVATE and os.path.exists(F("disposizione.png")) \
            and not mappa_vecchia() else None
        if "dispositivi" not in APPROVATE:
            unico("disp", scrivi(testo, tasti))  # card non approvata: solo testo
            return risp
        try:
            unico("disp", foto(card_dispositivi(), testo, tasti))
        except Exception as e:
            log(f"card dispositivi: {e}")
            unico("disp", scrivi(testo, tasti))
    elif d == "mappa":  # la card della disposizione (la fa e la manda il PC: tecnica/array/card_disposizione.py)
        if "mappa" in APPROVATE and os.path.exists(F("disposizione.png")) and not mappa_vecchia():
            unico("mappa", foto(F("disposizione.png"), TX.b("mappa_b")))
    elif d == "prova":
        if grafici:
            prova_live()
    elif d == "st:riprova":
        tieni_vivo_loop(avvisa=False); time.sleep(3)
        manda_stato_card(msg)
    elif d.startswith(("c<:", "c>:")):
        c = freccia_cat(d[3:]) if d[1] == ">" else ""
        if c:  # ▶️ senza toccare niente: vale il suggerimento del modello, marcato giusto="freccia"
            aggiungi_riga(GIUDIZI, ",".join(GIUD_COLS), f"{d[3:]},{tipo_di(d[3:])},freccia,,{c.replace(',', ' ')},{datetime.now():%Y-%m-%dT%H:%M}")
            risp = TX.toast("clip_tenuto", cat=TX.mostra(c)[:40])
        GRUPPO.pop(d[3:], None); ULTIMO.pop(d[3:], None)  # tutto e' gia' salvato a ogni tocco: avanti passa e basta
        p = vicina(d[3:], -1 if d[1] == "<" else 1)
        if p:
            mostra_clip(p, msg)
        elif not c:
            risp = "—"
    elif d.startswith("ca:"):  # "Altre clip" dopo il limite giornaliero: la prossima della coda
        p = os.path.join(D, os.path.basename(d[3:]))
        if os.path.exists(p):
            mostra_clip(p, msg)
    elif d.startswith("cp:"):  # clip precisa: un tocco sulla categoria = giudizio
        j, _, n = d[3:].partition(":")
        sn = suoni()
        if int(j) < len(sn):
            risp = applica(n, sn[int(j)], msg)
    elif d.startswith("kx:"):  # 🔍 Contesto (1 = +-10 s, 2 = +-30 s) / ↩️ Clip (0)
        _, l, n = d.split(":", 2)
        risp = mostra_contesto(n, int(l), msg)
    elif d.startswith("cm:"):  # categoria con sottocategorie: stessa card, la riga delle sotto
        j, _, n = d[3:].partition(":")
        if int(j) < len(suoni()):
            cambia_tasti(msg, tastiera_sotto(n, int(j)))
    elif d.startswith("cr:"):  # indietro dalle sottocategorie
        cambia_tasti(msg, tasti_clip(d[3:]))
    elif d.startswith("cq:"):  # sottocategoria (k) o la generica ("-")
        _, j, k, n = d.split(":", 3)
        sn = suoni()
        if int(j) < len(sn):
            ss = sotto().get(sn[int(j)], [])
            if k == "-" or int(k) < len(ss):
                risp = applica(n, sn[int(j)] if k == "-" else f"{sn[int(j)]}/{ss[int(k)]}", msg)
    elif d.startswith("cn:"):  # ➕ nuova categoria (j="-") o sottocategoria: chiedo il nome, poi lo applico alla clip
        _, j, n = d.split(":", 2)
        sn = suoni()
        if j == "-" or int(j) < len(sn):
            chiedi(TX.t("cat_nuova_chiedi") if j == "-" else TX.t("sotto_nuova_chiedi", cat=TX.mostra(sn[int(j)])),
                   TX.t("cat_placeholder"), "nuova_cat", clip=n, j=j, card=msg)
    elif d.startswith("cg:") or d.startswith("g:"):  # g: = pulsanti delle clip vecchie in chat
        _, giusto, n = d.split(":", 2)
        if giusto == "0":
            chiedi_era(n, msg)
        else:
            risp = giudica(n, giusto, msg)
    elif d.startswith("ao:"):  # "altri…": apre / chiude le categorie poco usate (stessa card, cambiano solo i tasti)
        n = d[3:]
        ALTRI.symmetric_difference_update({n})
        aggiorna_finestra(n, msg)
    elif d.startswith("ci:"):  # 🔗 Insieme: apre / chiude il gruppo
        n = d[3:]
        if GRUPPO.get(n):
            GRUPPO.pop(n)
        else:
            GRUPPO[n] = adesso()  # id unico: i gruppi di una stessa clip non si fondono
        aggiorna_finestra(n, msg)
    elif d.startswith("cz:"):
        aggiorna_finestra(d[3:], msg)
    elif d.startswith(("cs:", "cu:", "cf:")):  # finestra da 20 s: aggiungi suono / togli ultimo / fatto
        k, _, r = d.partition(":")
        if k == "cs":
            j, _, n = r.partition(":")
            sn = suoni()
            if int(j) < len(sn):
                tocca(n, sn[int(j)]); salva_sel(n)
        else:
            n = r
            if k == "cu":
                togli_ultimo(n)
            elif k == "cf":  # vecchio "Fatto" (card rimaste in chat): passa alla prossima
                p = vicina(n, 1)
                if p:
                    mostra_clip(p, msg)
                return None
            salva_sel(n)
        aggiorna_finestra(n, msg)
    elif d.startswith("ce:"):
        _, era, n = d.split(":", 2)
        if era == "?":
            chiedi(TX.t("nota_altro"), TX.t("nota_altro_ph"), "era", clip=n, foto=msg)
        else:
            risp = giudica(n, "0", msg, era)
    elif d.startswith("n:"):
        risp = gestisci_nota(d[2:], msg)
    elif d.startswith("fz:"):
        g = int(d[3:])
        scad = (datetime.now() + timedelta(days=g)).replace(hour=14, minute=0, second=0, microsecond=0) if g else None
        nota("fuori", g)
        pausa(scad or "sempre", fuori=True)
        modifica(msg, TX.t("fuori_ok", quando=f"{scad:%d/%m alle %H:%M}" if scad else "quando torni"))
        scrivi("🏠", menu())  # aggiorna il menu fisso (⏸️ -> ▶️)
    elif d.startswith("ez:"):
        fino = date.today() + timedelta(days=int(d[3:]))
        nota("esame", fino.isoformat()); modifica(msg, TX.t("esame_ok", data=f"{fino:%d/%m}"))
    elif d == "m:menu":
        modifica(msg, TX.t("cat_titolo"), tastiera_tipi())
    elif d == "m:add":
        chiedi(TX.t("cat_chiedi_nome"), TX.t("cat_placeholder"), "aspetta_nome")
    elif d == "m:ok":
        modifica(msg, TX.t("reg_chiedi"), scelta_suoni())
    elif d.startswith("x:"):
        salva_suoni([s for s in suoni() if s != d[2:]])
        modifica(msg, TX.t("cat_tolta", cat=TX.mostra(d[2:])), tastiera_tipi())
    elif d == "su":
        lista_audio()
    elif d.startswith("p:") and os.path.exists(os.path.join(CAL, d[2:])):
        manda_voce(os.path.join(CAL, d[2:]), TX.mostra(d[2:].split("__")[0]))
    elif d.startswith("p:"):
        risp = TX.toast("suono_sparito")
    elif d.startswith("d:"):
        cancella_audio(d[2:]); lista_audio(msg); risp = TX.toast("cancellato_secco")
    elif d.startswith("s:"):
        registra_inizio(d[2:], msg)
    elif d in ("r:stop", "r:canc"):
        if TARATURA:
            registra_fine(salva=(d == "r:stop"))
        else:
            risp = TX.toast("scaduto")
    elif d == "r:fine":
        oggi = f"{datetime.now():%Y%m%d}"
        n = len(glob.glob(os.path.join(CAL, f"*__tg__{oggi}_*.m4a")))
        modifica(msg, TX.t("reg_fatto", n=n) if n else TX.t("reg_fatto_zero"))
        STATO_UI.pop("registra", None)
    elif d.startswith("rp:"):  # un'azione = un messaggio che si aggiorna
        if d == "rp:fine":
            riposo_fine()
            modifica(msg, TX.t("riposo_finito"))
        else:
            modifica(msg, TX.t("riposo_via", ora=riposo_inizia(int(d[3:]))), kb([(TX.b("riposo_fine"), "rp:fine")]))
    elif d.startswith("pz:"):
        testo = riprendi() if d == "pz:via" else pausa(d[3:])
        scrivi(testo)  # messaggio nuovo: aggiorna anche il menu fisso
    else:
        risp = TX.toast("vecchio")
    return risp


COMANDI = {v.lower(): k for k, v in list(TX.MENU.items()) + list(TX.MENU_ASCII.items())}  # funzionano entrambi gli stili
COMANDI.update({"🌙 stanotte": "stanotte", "/notte": "stanotte", "/ascolta": "clip", "/ripasso": "ripasso", "/registra": "registra", "/suoni": "suoni", "/pausa": "pausa",
                "/stato": "stato", "/riposo": "riposo", "/nota": "nota", "/settimana": "settimana", "/start": "start",
                "/ascii": "ascii", "/emoji": "emoji", "/spostati": "spostati"})


def attivo(chiave, minuti, rif_msg=None):
    """Contesto del testo libero ancora valido (e, se serve, risposta al messaggio giusto)."""
    c = STATO_UI.get(chiave)
    if not c:
        return None
    t = c["t"] if isinstance(c, dict) else c
    if time.time() - t > minuti * 60 or (isinstance(c, dict) and "msg" in c and rif_msg != c["msg"]):
        return None
    return c


def cambia_stile(stile):
    """Pulsanti emoji <-> ASCII: si salva (stile.txt) e il menu fisso si rimanda subito nel nuovo stile."""
    TX.STILE[0] = stile
    open(F("stile.txt"), "w").write(stile)
    unico("stile", scrivi(f"Aa {stile}"))


def gestisci_testo(t, rif="", rif_msg=None, vecchio=False, msg_id=None):
    """Le azioni partono SOLO dal testo esatto dei pulsanti/comandi ("sono stato male" e' una nota, S1).
    Il testo libero dipende dal contesto: nome di un suono (dopo 🎙️), farmaco/altro (force_reply), cos'era (❌),
    altrimenti diventa una 📝 nota. Comandi vecchi di >10' (bot giu') si saltano; note e commenti mai."""
    t = t.strip()
    azione = COMANDI.get(t.lower())
    import re
    m = re.fullmatch(r"(\d{1,2})[:.,](\d{2})", t)
    if m and not azione and int(m.group(1)) < 24 and int(m.group(2)) < 60:  # "5:12" -> l'audio di quel momento
        adesso = datetime.now()
        quando = adesso.replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
        if quando > adesso:
            quando -= timedelta(days=1)
        if msg_id:
            prova("deleteMessage", chat_id=CHAT, message_id=msg_id)
        manda_punto(quando, "ora")
        return
    if azione and vecchio:
        return
    if not azione:
        if attivo("nota", 5, rif_msg):
            c = STATO_UI.pop("nota")
            if c["tipo"] == "nuovo_tasto":  # ⚙️ Modifica -> ➕ Aggiungi
                salva_tasti(tasti_note() + [["", "📌 " + t.strip()[:30]]])
                scrivi(f"Aggiunto «📌 {t.strip()[:30]}» ✅", tastiera_note())
                return
            nota(c["tipo"], t.replace(",", " "))
            testo, tasti = dopo_nota(c["tipo"], t)
            scrivi(testo, tasti)
            if c["tipo"] == "altro":
                proponi_tasto(t)
        elif attivo("era", 5, rif_msg):
            c = STATO_UI.pop("era")
            nome = "".join(ch for ch in t.lower().replace(" ", "_") if ch.isalnum() or ch == "_")[:24]
            giudica(c["clip"], "0", c["foto"], nome)
        elif attivo("nuova_cat", 5, rif_msg):
            c = STATO_UI["nuova_cat"]
            nome, sn, sub = pulisci(t), suoni(), sotto()
            cat = None if c["j"] == "-" else sn[int(c["j"])]
            if not nome:
                scrivi(TX.t("nome_vuoto")); return
            if nome in (sn if cat is None else sub.get(cat, [])):
                scrivi(TX.t("nome_esiste", cat=TX.mostra(nome))); return
            STATO_UI.pop("nuova_cat")
            if cat is None:
                salva_suoni(sn + [nome])
            else:
                sub.setdefault(cat, []).append(nome)
                scrivi_json(F("sottocategorie.json"), sub)
            for m_ in (c["msg"], msg_id):  # il giro domanda+risposta non resta in chat
                if m_:
                    prova("deleteMessage", chat_id=CHAT, message_id=m_)
            applica(c["clip"], nome if cat is None else f"{cat}/{nome}", c["card"])
        elif attivo("aspetta_nome", 5, rif_msg) or (attivo("registra", 10) and not rif):
            STATO_UI.pop("aspetta_nome", None)
            nome = "".join(ch for ch in t.lower().replace(" ", "_") if ch.isalnum() or ch == "_")[:24]
            if not nome:
                scrivi(TX.t("cat_vuota")); return
            if nome in suoni():
                scrivi(TX.t("cat_esiste", cat=TX.mostra(nome)), scelta_suoni()); return
            salva_suoni(suoni() + [nome])
            scrivi(TX.t("reg_nome_libero", cat=t), scelta_suoni())
        else:  # commento/nota: lo salvo sempre per Claude (anche le risposte a una clip: etichette a parole)
            aggiungi_riga(F("commenti.txt"), "", f"{datetime.now():%Y-%m-%d %H:%M} | {rif} | {t}")
            tv = NOTE.da_testo(t)
            if tv and not rif:
                nota(*tv)
                testo, tasti = dopo_nota(*tv)
                scrivi(testo, tasti)
            else:
                if not rif:
                    nota("altro", t.replace(",", " ")[:120])
                scrivi(TX.t("nota_ok"))
                if not rif:
                    proponi_tasto(t)
        return
    STATO_UI.pop("registra", None)
    if rif_msg is None and msg_id:
        prova("deleteMessage", chat_id=CHAT, message_id=msg_id)
    if azione == "stanotte":
        day = datetime.now().strftime("%Y%m%d")
        r = analizza(day)
        if r and r.get("blocco") and not sospetta(r):
            ultimo = max(r["M"])
            if datetime.now() - ultimo < timedelta(minutes=15) and ultimo - r["fine"] < timedelta(minutes=30):
                k = "notte_in_corso_russa" if r["russa"] else "notte_in_corso"
                scrivi(TX.t(k, inizio=f"{r['inizio']:%H:%M}", durata=TX.durata(r["durata"]), m=r["russa"]))
            else:
                IN_FONDO[0] = True
                try:
                    manda_notte(r, day)
                finally:
                    IN_FONDO[0] = False
        else:
            scrivi(testo_notte_telefono(day) or TX.t("notte_non_iniziata"))
    elif azione == "nota":  # UN messaggio 📝 per volta: il nuovo toglie il vecchio e riassume le note di oggi
        ora, oggi = f"{datetime.now():%H:%M}", f"{date.today():%Y-%m-%d}"
        conta = {}
        for n in note():
            if n["ts"].startswith(oggi) and n["tipo"] in NOTE.TIPI:
                conta[n["tipo"]] = conta.get(n["tipo"], 0) + (int(n["valore"]) if n["valore"].isdigit() else 1)
        lista = " · ".join(TX.b("nota_" + k).split()[0] + (f"×{q}" if q > 1 else "") for k, q in conta.items())
        unico("nota", scrivi(TX.t("nota_oggi", lista=lista, ora=ora) if lista else TX.t("nota_chiedi", ora=ora),
                             tastiera_note()))
    elif azione == "clip":
        ascolta()
    elif azione == "ripasso":
        ripasso()
    elif azione == "registra":
        scrivi(TX.t("reg_chiedi"), scelta_suoni())
    elif azione == "suoni":
        lista_audio()
    elif azione == "pausa" and in_pausa():
        scrivi(riprendi())
    elif azione == "pausa":
        L = ora_letto()
        scrivi(TX.t("pausa_chiedi"), kb(*([[(TX.b("pausa_letto", ora=f"{L[0]:%H:%M}", fonte=L[1]), "pz:letto", "primary")]] if L else []),
                                        [(TX.b("pausa_1h"), "pz:1h"), (TX.b("pausa_3h"), "pz:3h")],
                                        [(TX.b("pausa_20"), "pz:20"), (TX.b("pausa_domani"), "pz:domani")],
                                        [(TX.b("pausa_sempre"), "pz:sempre")]))
    elif azione == "riprendi":
        scrivi(riprendi())
    elif azione == "riposo" and riposo_fino():
        scrivi(TX.t("riposo_via", ora=riposo_fino()), kb([(TX.b("riposo_fine"), "rp:fine")]))
    elif azione == "riposo":
        scrivi(TX.t("riposo_chiedi"), kb([(TX.b("riposo_45"), "rp:45"), (TX.b("riposo_90"), "rp:90", "primary"),
                                          (TX.b("riposo_120"), "rp:120")]))
    elif azione == "stato":
        manda_stato_card()
    elif azione == "settimana":
        settimana()
    elif azione == "spostati":  # telefoni spostati: la mappa vecchia non si mostra piu' (sarebbe falsa)
        open(F("spostati.txt"), "w").write(datetime.now().isoformat(timespec="minutes"))
        scrivi(TX.t("disp_spostati"))
    elif azione in ("ascii", "emoji"):
        cambia_stile(azione)
    elif azione == "start":
        scrivi(TX.t("start"))


# ---------------------------------------------------------------- manutenzione e main
def in_silenzio():
    """
    """
    ora = datetime.now()
    try:
        return any(datetime.fromisoformat(x) <= ora <= datetime.fromisoformat(y) for x, y in leggi_json(F("silenzio.json")) or [])
    except (TypeError, ValueError) as e:
        log(f"silenzio.json: {e}")
        return False


def pulizia():
    """Log con tetto 1 MB (tengo gli ultimi 200 KB). Le clip le pulisce sonno_tel.py (7 giorni); i punto_* li pulisco io."""
    for p in glob.glob(os.path.join(D, "punto_*")) + glob.glob(os.path.join(D, "finestra_*")):
        if time.time() - os.path.getmtime(p) > 7 * 86400:
            os.remove(p)
    for p in glob.glob(os.path.join(HOME, "*.log")) + glob.glob(os.path.join(QUI, "*.log")):
        if os.path.getsize(p) > 2**20:
            coda = open(p, "rb").read()[-200_000:]
            open(p, "wb").write(coda)


SUBITO = CLIP_TASTI + ("rr:", "as:", "av:", "cv:", "ca:", "vl", "pt:", "sn:", "det:", "tr:", "ct:", "nr:", "s3:", "tn:", "rc:", "rk:", "dg:", "cop:")


def tratta_callback(q):
    """
    prima di qualsiasi lavoro (card+video ~4 s). Sulla card clip il toast e' quello che gia' si sa (✓ categoria)."""
    d = q.get("data", "")
    if stantio(q):
        return prova("answerCallbackQuery", callback_query_id=q["id"], text=TX.toast("gia_passato"))
    if d.startswith(SUBITO):
        t = ""
        if d.startswith("cp:"):
            j = d[3:].partition(":")[0]
            t = TX.toast("clip_ok", cat=TX.mostra(suoni()[int(j)])) if j.isdigit() and int(j) < len(suoni()) else ""
        prova("answerCallbackQuery", callback_query_id=q["id"], text=t)
        gestisci_pulsante(q)
    else:
        prova("answerCallbackQuery", callback_query_id=q["id"], text=gestisci_pulsante(q) or "")


def main():
    if os.path.exists(F("stile.txt")):
        TX.STILE[0] = open(F("stile.txt")).read().strip() or "emoji"
    off = None  # NON salto i messaggi in attesa: voti/commenti scritti mentre il bot era giu' (bug UX)
    prova("setMyCommands", commands=[{"command": c, "description": d} for c, d in TX.COMANDI])
    ultimo_controllo = 0
    ultima_freschezza = ultimo_vivo = ultimo_verdetto = 0
    while True:
        if TARATURA and time.time() - TARATURA["t0"] > MAX_REG + 1:
            registra_fine(salva=True, auto=True)  # stop automatico
        if time.time() - ultimo_vivo > 60:
            ultimo_vivo = time.time()
            try:
                tieni_vivo_loop(avvisa=False)
            except Exception as e:
                log(f"tieni_vivo_loop: {e}")
        scalda_durate()  # no-op se gia' in corso; l'ffprobe delle clip nuove fuori dal thread dei tocchi
        try:
            uso_pulisci()  # inattivo: via il preparato non usato (ogni giro, e' economico)
        except Exception as e:
            log(f"uso_pulisci: {e}")
        if time.time() - ultimo_verdetto > 300:  # anche in silenzio: "non registra" deve arrivare
            ultimo_verdetto = time.time()
            try:
                sorveglia_registrazione()
            except Exception as e:
                log(f"sorveglia_registrazione: {e}")
        try:
            stato_card_auto()  # edit sul posto (muto), anche in silenzio
        except Exception as e:
            log(f"stato_card_auto: {e}")
        if in_silenzio():
            pass
        elif time.time() - ultima_freschezza > 300:  # margine sul TTL stato/uso di 10 minuti
            ultima_freschezza = time.time()
            try:
                controlla_freschezza()
            except Exception as e:
                log(f"freschezza: {e}")
        if time.time() - ultimo_controllo > 600 and not in_silenzio():  # ogni 10': report, promemoria, pulizia
            ultimo_controllo = time.time()
            try:
                zona_grigia()
            except Exception as e:
                log(f"zona_grigia: {e}")
            for f in (report_automatico, copertura_automatica, promemoria_pausa, pulizia):
                try:
                    f()
                except Exception as e:
                    tb = [x for x in traceback.extract_tb(e.__traceback__) if x.filename.endswith("bot.py")][-3:]
                    log(f"{f.__name__}: {e} @ " + " <- ".join(f"{x.lineno} {x.name}" for x in reversed(tb)))
        try:
            ups = api("getUpdates", timeout=5 if TARATURA else 50, **({"offset": off} if off else {})).get("result", [])
        except Exception:
            time.sleep(10); continue
        for u in ups:
            off = u["update_id"] + 1
            try:
                q = u.get("callback_query")
                if q:
                    if str(q["message"]["chat"]["id"]) != CHAT:
                        continue
                    tratta_callback(q)
                    continue
                m = u.get("message") or {}
                ULTIMO.clear()
                if str(m.get("chat", {}).get("id")) != CHAT:
                    continue
                if m.get("photo"):
                    salva_foto(m)
                    continue
                r = m.get("reply_to_message") or {}
                rif = (r.get("caption") or r.get("text") or "")[:40].replace("\n", " ")
                gestisci_testo(m.get("text") or "", rif, r.get("message_id"), vecchio=time.time() - m.get("date", 0) > 600,
                               msg_id=m.get("message_id"))
                if MENU_NASCOSTO[0]:
                    MENU_NASCOSTO[0] = False
                    scrivi("🏠")
            except Exception as e:
                errore("update", e)


def una_copia():
    """
    due bot = messaggi doppi che si cancellano a vicenda e tocchi presi dall'altro (Notte 'non va').
    Lucchetto del sistema: la seconda copia esce. Il kernel lo libera da solo se il bot muore."""
    import fcntl
    fd = open(F("bot.lock"), "w")  # non ereditabile dai figli (PEP 446)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    return fd


if __name__ == "__main__":
    _LUCCHETTO = una_copia()
    if _LUCCHETTO is None:
        sys.exit("bot gia' attivo: esco")
    main()
