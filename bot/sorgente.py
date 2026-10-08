"""
Dato (stato_live.py sul PC, ogni 2'): media_a56.csv = t,dev,suona,app,uscita  (dev = a56|a21s; t = minuto ISO; suona = si|no; uscita = altoparlante|cuffie: con cuffie/Bluetooth il suono NON e' nella stanza = non e' 'telefono').
  PC: C:/sonno_audio/media_a56.csv (originale)   telefono: ~/sonno_bot/media_a56.csv (copia, la legge il bot)
Intervalli ESATTI (stesso file, righe da 7 colonne: t_inizio_s,dev,si,app,uscita,t_fine_s,tipo; tipo = primo_piano | player):
  primo_piano = app media in primo piano (usagestats, al secondo) -> con audio non in cuffia = "telefono" possibile;
  player = player audio started..stopped dal log di dumpsys audio -> "telefono". Esatto: orari e durata di primo piano/player
  (finche' il log del telefono arriva: ~1-3 giorni di usagestats, il log audio e' corto). Stimato: l'uscita (cuffie/altoparlante)
  e' quella del momento del campionamento, il silenzio di un video in primo piano, l'app di un player (= quella in primo piano).
Sulla clip: solo "telefono" e' una prova -> si scrive accanto alla clip, <clip>.sorgente = 'telefono|TikTok' (il resto si
Stdlib pura: gira sul telefono (bot) e sul PC (mappa_russare)."""
import csv, os
from datetime import datetime, timedelta

TOL_MIN = 2        # il campione e' ogni 2': un suono dura piu' di un campione, quindi vale +-2 minuti attorno alla clip
PIU_FORTE_DB = 6   # un dispositivo e' "piu' vicino" se sente +6 dB degli altri (stessa soglia di mappa_russare)
_C = {}            # path -> (mtime, righe)


def leggi(path):
    """[(minuto datetime, dev, suona bool, app, uscita)]; file assente/illeggibile = []."""
    try:
        m = os.stat(path).st_mtime_ns
        if _C.get(path, (0,))[0] == m:
            return _C[path][1]
        r = []
        for x in csv.reader(open(path, encoding="utf-8")):
            if len(x) >= 7:
                continue  # riga di intervallo esatto: la legge leggi_intervalli
            try:
                r.append((datetime.fromisoformat(x[0]), x[1], x[2] == "si", x[3] if len(x) > 3 else "", x[4] if len(x) > 4 else ""))
            except (ValueError, IndexError):
                pass  # intestazione o riga rotta
        _C[path] = (m, r)
        return r
    except OSError:
        return []


def leggi_intervalli(path):
    """[(inizio, fine, dev, app, uscita, tipo)] dalle righe esatte; assente = []."""
    try:
        k, m = (path, "i"), os.stat(path).st_mtime_ns
        if _C.get(k, (0,))[0] != m:
            r = []
            for x in csv.reader(open(path, encoding="utf-8")):
                try:
                    if len(x) >= 7:
                        r.append((datetime.fromisoformat(x[0]), datetime.fromisoformat(x[5]), x[1], x[3], x[4], x[6]))
                except ValueError:
                    pass
            _C[k] = (m, r)
        return _C[k][1]
    except OSError:
        return []


def telefono_intervallo(iv, t, durata_s=60, margine_s=10):
    """app se un intervallo esatto (player, o app media in primo piano) tocca [t, t+durata] e l'audio non era in cuffia."""
    for a, b, _, app, uscita, tipo in iv:
        if uscita != "cuffie" and a <= t + timedelta(seconds=durata_s + margine_s) and b >= t - timedelta(seconds=margine_s):
            return app or "?"
    return None


def telefono_suona(media, t, tol=TOL_MIN):
    """app (str, anche '') se un telefono suonava entro +-tol minuti da t, altrimenti None."""
    for m, _, si, app, uscita in media:
        if si and uscita != "cuffie" and abs((m - t).total_seconds()) <= tol * 60 + 30:
            return app or "?"
    return None


def sorgente(media, t, db_io=None, db_fuori=None, intervalli=()):
    """('telefono', app) | ('io', '') | ('fuori', '') | ('non so', ''). db_io = livello sull'A21s (comodino), db_fuori = su
    PC/finestra: solo se entrambi noti; senza dati multi-dispositivo resta la sola regola del media."""
    app = telefono_suona(media, t)
    if app is None:
        app = telefono_intervallo(intervalli, t)  # fonte esatta retroattiva: un TikTok di 30 s tra due campioni non si perde
    if app is not None:
        return "telefono", app
    if db_io is not None and db_fuori is not None:
        if db_io - db_fuori >= PIU_FORTE_DB:
            return "io", ""
        if db_fuori - db_io >= PIU_FORTE_DB:
            return "fuori", ""
    return "non so", ""


def minuto_clip(nome):
    """russa_20261002_0423.m4a / finestra_20261002_042310.m4a -> datetime al minuto."""
    return datetime.strptime(nome.split("_", 1)[1][:13], "%Y%m%d_%H%M")


def sorgente_clip(p, media, salva=True, intervalli=()):
    """Come `sorgente` per una clip; 'telefono' si salva in <clip>.sorgente e poi vale per sempre."""
    s = p[:-4] + ".sorgente"
    try:
        a, _, b = open(s, encoding="utf-8").read().strip().partition("|")
        return a, b
    except OSError:
        pass
    r = sorgente(media, minuto_clip(os.path.basename(p)), intervalli=intervalli)
    if r[0] == "telefono" and salva:
        try:
            open(s, "w", encoding="utf-8").write("|".join(r))
        except OSError:
            pass
    return r


def minuti_telefono(media, a, z, intervalli=()):
    """Insieme dei minuti (datetime) in [a, z] in cui suonava un telefono (per la mappa del russare)."""
    a = a.replace(second=0, microsecond=0)
    return {a + timedelta(minutes=i) for i in range(int((z - a).total_seconds() // 60) + 1)
            if sorgente(media, a + timedelta(minutes=i), intervalli=intervalli)[0] == "telefono"}


def leggi_uso(path):
    """Minuti ('AAAA-MM-GGTHH:MM') in cui PC o A56 erano in uso (uso.csv: t,dev); file assente = vuoto."""
    try:
        m = os.stat(path).st_mtime_ns
        if _C.get(path, (0,))[0] != m:
            _C[path] = (m, {x[0][:16] for x in csv.reader(open(path, encoding="utf-8")) if len(x) >= 2 and x[1] in ("pc", "a56")})
        return _C[path][1]
    except OSError:
        return set()


def leggi_storia(path):
    """[(datetime, registra bool)] di stato_storia.py (registra=0 SOLO se sveglio al 100%); assente = []."""
    try:
        out = []
        for x in csv.reader(open(path, encoding="utf-8")):
            try:
                out.append((datetime.fromisoformat(x[0]), x[1].strip() != "0"))
            except (ValueError, IndexError):
                pass
        return out
    except OSError:
        return []


def sveglio_certo(t, uso, storia, media, validita=5):
    """True se in quel minuto era sveglio con certezza (>= 0,95): lo STORICO stato (registra=0) se ha un campione entro
    """
    vicini = [(abs((m - t).total_seconds()), reg) for m, reg in storia if abs((m - t).total_seconds()) <= validita * 60]
    if vicini:
        return not min(vicini)[1]
    return any(f"{t + timedelta(minutes=d):%Y-%m-%dT%H:%M}" in uso for d in (-1, 0, 1)) or \
        any(dev == "a56" and si and abs((m - t).total_seconds()) <= TOL_MIN * 60 + 30 for m, dev, si, _, _ in media)


def livelli(path, default=None):
    """{nome modello: (livello in minuscolo, colore)} dal registro modelli.json (basso/medio/preciso: i modelli attivi)."""
    import json
    try:
        return {m["nome"]: (m["livello"].lower(), m["colore"]) for m in json.load(open(path, encoding="utf-8"))["modelli"]
                if m.get("attivo")}
    except (OSError, ValueError, KeyError):
        return default or {"YAMNet": ("basso", "#9AA3B2"), "EfficientAT": ("medio", "#5B6B86"), "PANNs": ("preciso", "#2A3350")}


if __name__ == "__main__":  # self-check con dati finti
    t0 = datetime(2026, 10, 3, 1, 0)
    md = [(t0, "a56", True, "TikTok", "altoparlante"), (t0 + timedelta(minutes=2), "a56", False, "", "altoparlante"),
          (t0 + timedelta(minutes=10), "a21s", True, "Spotify", "altoparlante"), (t0 + timedelta(minutes=30), "a56", True, "TikTok", "cuffie")]
    assert sorgente(md, t0 + timedelta(minutes=30)) == ("non so", "")             # cuffie: il suono non e' nella stanza
    assert sorgente(md, t0 + timedelta(minutes=30), -50, -60) == ("io", "")
    assert sorgente(md, t0) == ("telefono", "TikTok")
    assert sorgente(md, t0 + timedelta(minutes=2)) == ("telefono", "TikTok")      # campione vicino
    assert sorgente(md, t0 + timedelta(minutes=5)) == ("non so", "")              # nessun dato vicino
    assert sorgente(md, t0 + timedelta(minutes=5), -50, -60) == ("io", "")        # piu' forte sul comodino
    assert sorgente(md, t0 + timedelta(minutes=5), -60, -50) == ("fuori", "")
    assert sorgente(md, t0 + timedelta(minutes=5), -52, -50) == ("non so", "")    # differenza piccola
    assert sorgente(md, t0, -50, -60)[0] == "telefono"                             # il media vince sui dB
    assert sorgente([], t0) == ("non so", "")
    assert minuti_telefono(md, t0, t0 + timedelta(minutes=12)) == {t0 + timedelta(minutes=i) for i in (0, 1, 2, 8, 9, 10, 11, 12)}
    assert minuto_clip("finestra_20261002_042310.m4a") == datetime(2026, 10, 2, 4, 23)
    iv = [(t0 + timedelta(minutes=20, seconds=5), t0 + timedelta(minutes=20, seconds=35), "a56", "TikTok", "altoparlante", "primo_piano"),
          (t0 + timedelta(minutes=40), t0 + timedelta(minutes=41), "a56", "YouTube", "cuffie", "player")]
    assert sorgente([], t0 + timedelta(minutes=20), intervalli=iv) == ("telefono", "TikTok")       # 30 s tra due campioni: trovato
    assert sorgente([], t0 + timedelta(minutes=19), intervalli=iv) == ("telefono", "TikTok")       # margine 10 s: la clip del minuto prima
    assert sorgente([], t0 + timedelta(minutes=21), intervalli=iv) == ("non so", "")
    assert sorgente([], t0 + timedelta(minutes=40), intervalli=iv) == ("non so", "")               # in cuffia
    assert minuti_telefono([], t0 + timedelta(minutes=18), t0 + timedelta(minutes=23), iv) == {t0 + timedelta(minutes=m) for m in (19, 20)}
    # sveglio certo: storico se c'e', altrimenti uso PC/A56
    uso = {"2026-10-03T13:00"}
    assert sveglio_certo(t0, uso, [], []) and sveglio_certo(t0 + timedelta(minutes=1), uso, [], [])
    assert not sveglio_certo(t0 + timedelta(minutes=5), uso, [], [])
    assert sveglio_certo(t0 + timedelta(minutes=10), set(), [], [(t0 + timedelta(minutes=10), "a56", True, "TikTok", "cuffie")])
    assert not sveglio_certo(t0 + timedelta(minutes=10), set(), [], [(t0 + timedelta(minutes=10), "a21s", True, "x", "")])
    assert sveglio_certo(t0 + timedelta(minutes=3), set(), [(t0 + timedelta(minutes=2), False)], [])      # registra=0 = sveglio
    assert not sveglio_certo(t0, uso, [(t0, True)], [])
    assert livelli("/non/esiste")["PANNs"][0] == "preciso"
    print("ok")
