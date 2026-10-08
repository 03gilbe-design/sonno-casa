"""
A ogni giro della catena (rec.sh -> conferma.py) scrive ~/stato.json:
  a21s:   registra, batteria, in carica, temperatura, arretrato del dataset
e decide quanti blocchi elaborare in questo giro. Pesi ordinali, non probabilita calibrate.
Albero veto: silenzio senza presenza resta ?. SAA letto solo se disponibile e fresco.
   python stato.py        -> stampa lo stato
   python stato.py prova  -> self-check della decisione
"""
import csv, glob, json, math, os, subprocess, sys
from pathlib import Path
from datetime import datetime, timedelta

HOME = os.path.expanduser("~")
D = os.environ.get("SONNO_DIR", os.path.join(HOME, "rec"))


PESI = dict(pc=10, russa_jeans=8, russa_modello=6, camera_muta=6, a56=2, saa=0.5)


def repo_bot():
    if os.environ.get("SONNO_BOT_DIR"):
        return Path(os.environ["SONNO_BOT_DIR"])
    fratello = Path(__file__).resolve().parent.parent / "sonno_bot"
    return fratello if (fratello / "analisi/albero.py").exists() else Path(HOME) / "sonno_bot"


def recente(t, ora, minuti=10):
    try:
        return 0 <= (ora - datetime.fromisoformat(t)).total_seconds() <= minuti * 60
    except (ValueError, TypeError):
        return False


def leggi_csv(path, intestazione=True):
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f) if intestazione else csv.reader(f))
    except OSError:
        return []


def leggi_live(path, adesso, validita=600):
    """live.json scritto da stato_live.py (PC): {t, pc:{attivo,t}, a56:{attivo,t}, saa:[[ts,ev],..], saa_t}. Piu' vecchio di
    10' o illeggibile -> {} (nessun effetto). Ritorna pc/a56 = attivo adesso, *_t = minuto del controllo, eta = secondi."""
    try:
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        out, eta = {}, {}
        for k in ("pc", "a56"):
            c = d.get(k) or {}
            e = (adesso - datetime.fromisoformat(c["t"])).total_seconds()
            if 0 <= e <= validita:
                eta[k] = round(e)
                out[k], out[k + "_t"] = c.get("attivo") is True, c["t"][:16]
        if d.get("saa_t") and 0 <= (adesso - datetime.fromisoformat(d["saa_t"])).total_seconds() <= validita:
            eta["saa"] = round((adesso - datetime.fromisoformat(d["saa_t"])).total_seconds())
            out["saa"] = [r[:2] for r in d.get("saa", []) if isinstance(r, list) and len(r) >= 2]
        out["eta"] = eta
        return out if eta else {}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {}


def tempo_clip(nome):
    try:
        parti = Path(nome).stem.split("_")
        return datetime.strptime(parti[1] + parti[2][:4], "%Y%m%d%H%M").isoformat()
    except (ValueError, IndexError):
        return ""


def osserva(adesso, cartella=None, bot_dir=None):
    cartella = Path(cartella or D)
    bot_dir = Path(bot_dir or os.path.join(HOME, "sonno_bot"))
    uso = leggi_csv(bot_dir / "uso.csv", False)
    live = leggi_live(bot_dir / "live.json", adesso)
    uso += [[live[k + "_t"], k] for k in ("pc", "a56") if live.get(k)]
    s = dict(pc=False, a56=False, russa_jeans=False, russa_modello=False,
             camera_muta=False, saa="", audio="ignoto", respiro_regolare=False, uso_sessione_min=0,
             mov_continuo=False, luce_accesa=False, russa_modello_n=0)
    fonti = {}
    def fonte(nome, path, tempi, ttl=10):
        validi = []
        for t in tempi:
            try:
                eta = (adesso - datetime.fromisoformat(t)).total_seconds()
                validi.append((eta, t))
            except (ValueError, TypeError):
                pass
        passati = [v for v in validi if v[0] >= 0]
        eta, t = min(passati or validi, default=(None, None))
        fonti[nome] = dict(file=str(path), t=t, eta_secondi=eta, soglia_secondi=ttl*60,
                           stato="assente" if eta is None else "futuro" if eta < 0 else
                           "fresco" if eta <= ttl*60 else "vecchio")
    for nome in ("pc", "a56"):
        fonte(nome, bot_dir / "uso.csv", [r[0] for r in uso if len(r) >= 2 and r[1] == nome])
    for r in uso:
        if len(r) >= 2 and r[1] in ("pc", "a56") and recente(r[0], adesso):
            s[r[1]] = True
    # uso). albero.stima ci ricava la latenza d'addormentamento (~1h dopo un uso intenso).
    try:
        mu = sorted({datetime.fromisoformat(r[0][:16]) for r in uso if len(r) >= 2 and r[1] in ("pc", "a56")} - {None})
        mu = [m for m in mu if m <= adesso]
        if mu:
            s["uso_sessione_min"] = sum(1 for m in mu if timedelta(0) <= mu[-1] - m <= timedelta(minutes=90))
    except ValueError:
        pass
    # Sensori OPZIONALI dell'A56 nel letto (sensori_minuti.py -> movimenti.csv: t,mov,luce,n). Arrivano a tratti.
    mv = [r for r in leggi_csv(bot_dir / "movimenti.csv") if r.get("t")]
    fonte("mov", bot_dir / "movimenti.csv", [r["t"] for r in mv], 3)
    try:
        ultimi = [r for r in mv if 0 <= (adesso - datetime.fromisoformat(r["t"])).total_seconds() <= 600]
        ultima = max(ultimi, key=lambda r: r["t"], default=None)
        if ultima and recente(ultima["t"], adesso, 3):
            s["mov_continuo"] = sum(float(r["mov"]) > 50 for r in ultimi) >= 6   # 50 = SOGLIA_MOV di bot.py
            s["luce_accesa"] = float(ultima["luce"]) > 5
    except (ValueError, KeyError, TypeError):
        pass
    # Deduplica minuti, ignora futuro e buchi: due ore mute richiedono 120 minuti consecutivi.
    minuti = {}
    tempi_audio = []
    for giorno in (adesso - timedelta(days=1), adesso):
        for r in leggi_csv(cartella / f"minuti_{giorno:%Y%m%d}.csv"):
            tempi_audio.append(r.get("t"))
            if recente(r.get("t"), adesso, 130):
                minuti[r["t"][:16]] = r
    ultimo = max(minuti, default="")
    if ultimo and recente(ultimo, adesso, 2):
        def muto(r):
            try:
                return all(float(r[k]) == 0 for k in ("voce", "colpi_russa", "respiro", "picchi_miei"))
            except (KeyError, ValueError, TypeError):
                return False
        fine = datetime.fromisoformat(ultimo)
        sequenza = [minuti.get((fine - timedelta(minutes=i)).isoformat(timespec="minutes")) for i in range(120)]
        s["camera_muta"] = all(r is not None and muto(r) for r in sequenza)
        s["audio"] = "silenzio" if muto(minuti[ultimo]) else "rumore"
    # il blocco): la finestra e' sui 10 minuti che finiscono all'ULTIMA riga, valida se l'ultima riga ha < 45' (albero.eta
    # fa decadere la prova con l'eta' della fonte audio).
    if ultimo and recente(ultimo, adesso, 45):
        fine_a = datetime.fromisoformat(ultimo)
        ult10 = [minuti.get((fine_a - timedelta(minutes=i)).isoformat(timespec="minutes")) or {} for i in range(10)]

        def num(r, k):
            try:
                return float(r[k])
            except (KeyError, ValueError, TypeError):  # minuto mancante o scartato (vuoto): conta zero
                return 0.0
        # ponytail: soglie a occhio. respiro: >=15 frame su 125, niente voce, picchi<4, in 6 minuti su 10. russa: un minuto
        # "russa" = >=3 colpi (come notte.py); russa_modello_n = quanti dei 10. Tarare sui minuti_*.csv con russare confermato.
        s["respiro_regolare"] = sum(num(r, "respiro") >= 15 and num(r, "voce") == 0 and num(r, "picchi_miei") < 4
                                    for r in ult10) >= 6
        s["russa_modello_n"] = sum(num(r, "colpi_russa") >= 3 for r in ult10)
    giudizi = {r.get("clip"): r for r in leggi_csv(bot_dir / "giudizi.csv")}
    clips = list(cartella.glob("russa_*.m4a"))
    fonte("audio", cartella / "minuti_*.csv", tempi_audio, 2)
    fonte("clip", cartella / "russa_*.m4a", [tempo_clip(c.name) for c in clips])
    for clip in clips:
        if not recente(tempo_clip(clip.name), adesso):
            continue
        g = giudizi.get(clip.name, {})
        if g.get("giusto") == "1":
            s["russa_jeans"] = True
            s["audio"] = "russa"
        elif g.get("giusto") == "0":
            continue
        else:
            try:
                valore = float(clip.with_suffix(".panns").read_text().split(",")[0])
                s["russa_modello"] |= 0.2 < valore <= 1
            except (OSError, ValueError):
                pass
    # copiato qui ogni 2'): ha preso il telefono in mano = sveglio. albero.stima lo fa decadere con l'eta' della fonte.
    sv = [r["t"] for r in leggi_csv(bot_dir / "musica_eventi.csv") if r.get("evento") == "sveglio_volume" and r.get("t")]
    fonte("volume", bot_dir / "musica_eventi.csv", sv)
    s["sveglio_volume"] = any(recente(t, adesso, 60) for t in sv)
    eventi = leggi_csv(bot_dir / "a56_eventi_sleep.csv", False) + live.get("saa", [])
    fonte("saa", bot_dir / "a56_eventi_sleep.csv", [r[0] for r in eventi if len(r) >= 2])
    validi = [r for r in eventi if len(r) >= 2 and recente(r[0], adesso)]
    if validi:
        s["saa"] = max(validi, key=lambda r: r[0])[1]
    s["adesso"] = adesso.isoformat(timespec="seconds")
    try:
        d = json.loads((bot_dir / "dichiarato.json").read_text(encoding="utf-8"))
        if isinstance(d, dict):
            s["dichiarato"] = d
    except (OSError, ValueError):
        pass
    s["fonti"] = fonti
    s["live"] = live.get("eta", {})   # eta' (s) dell'ULTIMO CONTROLLO di pc/a56/saa, anche se non erano in uso
    return s


def valuta(s):
    """Pesi ordinali non calibrati: fiducia NON e' una probabilita clinica."""
    punti = dict(sveglio=0., dorme=0., fuori=0.)
    motivi = []
    for chiave, esito in (("pc", "sveglio"), ("russa_jeans", "dorme"),
                          ("russa_modello", "dorme"), ("camera_muta", "fuori"), ("a56", "sveglio")):
        if s.get(chiave):
            # Due conferme sullo stesso audio non sono prove indipendenti.
            if chiave == "russa_modello" and s.get("russa_jeans"):
                continue
            punti[esito] += PESI[chiave]
            motivi.append(chiave)
    if s.get("saa") in ("deep_sleep", "light_sleep", "rem", "not_awake", "awake"):
        punti["sveglio" if s["saa"] == "awake" else "dorme"] += PESI["saa"]
        motivi.append("saa")
    candidato = max(punti, key=punti.get)
    massimo = punti[candidato]
    j = candidato if massimo >= 6 else "?"
    # PC vince sui segnali acustici, telefono aperto non vince sul russare confermato.
    if s.get("pc"):
        j = candidato = "sveglio"
    fiducia = round(min(.95, punti[candidato] / (sum(punti.values()) + 1)), 2) if j != "?" else 0.
    try:
        # PC: repo fratello. A21s: ~/sonno_bot. Claude copia anche analisi/.
        repo = repo_bot()
        if str(repo.parent) not in sys.path:
            sys.path.insert(0, str(repo.parent))
        if str(repo) not in sys.path:
            sys.path.insert(0, str(repo))
        from analisi.albero import controlla_stato
        controllo = controlla_stato(s)
        if controllo["indistinguibile"] or j not in controllo["stati"]:
            j, fiducia = "?", 0.
            motivi.append("albero: scenari indistinguibili/incompatibili")
        elif j != "?":
            fiducia = max(fiducia, controllo["fiducia"])
    except ImportError:
        controllo = dict(errore="analisi.albero non disponibile")
        j, fiducia = "?", 0.
        motivi.append("albero assente: nessuna decisione certa")
    conflitto = bool((s.get("pc") or s.get("a56")) and
                     (s.get("russa_jeans") or s.get("russa_modello") or
                      s.get("saa") in ("deep_sleep", "light_sleep", "rem", "not_awake")))
    return dict(stato=j, fiducia=fiducia, candidato=candidato if massimo else "?",
                conflitto=conflitto, stanza="sconosciuta", fiducia_tipo="euristica non calibrata",
                punti=punti, motivi=motivi, segnali=s, albero=controllo)


def utente(adesso=None, cartella=None, bot_dir=None):
    return valuta(osserva(adesso or datetime.now(), cartella, bot_dir))


def a21s():
    try:
        b = json.loads(subprocess.run(["termux-battery-status"], capture_output=True, text=True, timeout=20).stdout)
    except Exception:
        b = {}
    try:
        reg = "true" in subprocess.run(["termux-microphone-record", "-i"], capture_output=True, text=True, timeout=20).stdout
    except Exception:
        reg = None
    fatti = {os.path.basename(p)[:-4] for p in glob.glob(os.path.join(D, "dataset", "*.csv"))}
    arretrato = sum(os.path.basename(p)[:-4] not in fatti for p in glob.glob(os.path.join(D, "interi", "*.m4a")))
    return dict(registra=reg, batteria=b.get("percentage"), carica=b.get("plugged") not in (None, "UNPLUGGED"),
                temperatura=b.get("temperature"), arretrato=arretrato)


def blocchi(j, d):
    """(nota rimossa)"""
    if any(not isinstance(d.get(k), (int, float)) or isinstance(d.get(k), bool)
           or not math.isfinite(d[k]) for k in ("temperatura", "batteria")):
        return 0  # sicurezza non misurabile: registrazione indipendente, niente nuovo carico
    if not 0 <= d["batteria"] <= 100 or not isinstance(d.get("carica"), bool):
        return 0
    if (d.get("temperatura") or 0) >= 42 or (not d.get("carica") and d.get("batteria") is not None and d["batteria"] <= 20):
        return 0                      # caldo o batteria bassa: fermo
    if j == "sveglio":
        return 12
    if j in ("sveglio?", "?"):
        return 6
    return 2                          # dorme: piano, la registrazione viene prima


# ponytail: costanti a occhio. Tarare guardando quante volte un cambio e' stato visto in ritardo (stato_storia/log).
INTERVALLO_CORTO, INTERVALLO_LUNGO = 120, 600   # secondi
CERTO, STABILE_MIN = 0.95, 20                    # fiducia e minuti nello stesso livello


def intervallo(precedente, livello, fiducia, adesso):
    """-> (stabile_da ISO, secondi al prossimo ricalcolo). Qualsiasi cambio di livello azzera la stabilita'."""
    da = adesso
    try:
        if precedente.get("livello") == livello and precedente.get("stabile_da"):
            da = datetime.fromisoformat(precedente["stabile_da"])
    except (ValueError, TypeError, AttributeError):
        pass
    stabile = (adesso - da) >= timedelta(minutes=STABILE_MIN)
    lungo = livello != "?" and fiducia >= CERTO and stabile
    return da.isoformat(timespec="seconds"), INTERVALLO_LUNGO if lungo else INTERVALLO_CORTO


def aggiorna():
    j, d = utente(), a21s()
    adesso = datetime.now()
    try:
        prec = json.load(open(os.path.join(HOME, "stato.json")))
    except (OSError, ValueError):
        prec = {}
    liv = (j.get("albero") or {}).get("livello", j["stato"])
    stabile_da, secondi = intervallo(dict(livello=prec.get("livello"), stabile_da=prec.get("stabile_da")), liv, j["fiducia"], adesso)
    s = dict(t=adesso.isoformat(timespec="seconds"), utente=j["stato"], fiducia=j["fiducia"], livello=liv,
             stabile_da=stabile_da, intervallo_s=secondi,
             jeans_dettaglio=j, a21s=d, blocchi=blocchi(j["stato"], d))
    try:
        s["rec"] = json.load(open(os.path.join(HOME, "guardiano_rec.json")))
    except (OSError, ValueError):
        pass
    json.dump(s, open(os.path.join(HOME, "stato.json.tmp"), "w"))
    os.replace(os.path.join(HOME, "stato.json.tmp"), os.path.join(HOME, "stato.json"))
    return s


if __name__ == "__main__":
    if sys.argv[1:] == ["prova"]:
        import tempfile
        assert valuta(dict(pc=True, russa_modello=True, saa="deep_sleep"))["stato"] == "sveglio"
        assert valuta(dict(a56=True, russa_jeans=True))["stato"] == "dorme"
        assert valuta(dict(a56=True, saa="deep_sleep"))["stato"] == "?"
        assert valuta(dict(camera_muta=True))["candidato"] == "fuori"
        assert valuta(dict(camera_muta=True, audio="silenzio"))["stato"] == "?"
        assert valuta(dict(russa_modello=True, a56=True))["stato"] == "?"
        assert not recente("2026-09-30T12:00", datetime(2026, 9, 29))
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            (p / "russa_20260928_0441.m4a").touch()
            (p / "giudizi.csv").write_text("clip,giusto\nrussa_20260928_0441.m4a,1\n")
            (p / "uso.csv").write_text("2026-09-28T16:41,a56\n")
            assert utente(datetime(2026, 9, 28, 4, 41), p, p)["stato"] == "dorme", "0441"
            (p / "giudizi.csv").write_text("clip,giusto\nrussa_20260928_0441.m4a,0\n")
            assert utente(datetime(2026, 9, 28, 4, 41), p, p)["stato"] == "?", "negativo avversariale"
            assert utente(datetime(2026, 9, 29), p, p)["stato"] == "?", "dati vecchi"
            ora = datetime(2026, 9, 29, 2)
            f = p / "minuti_20260929.csv"
            header = "t,voce,colpi_russa,respiro,picchi_miei\n"
            righe = [f"{ora-timedelta(minutes=i):%Y-%m-%dT%H:%M},0,0,0,0\n" for i in range(120)]
            f.write_text(header + "".join(righe))
            assert osserva(ora, p, p)["camera_muta"]
            assert utente(ora, p, p)["stato"] == "?", "silenzio non prova assenza"
            f.write_text(header + "".join(righe[:-1]) + righe[0])
            assert not osserva(ora, p, p)["camera_muta"], "duplicato non copre minuto mancante"
            f.write_text(header + "".join(righe))
            assert not osserva(ora+timedelta(minutes=3), p, p)["camera_muta"], "audio vecchio"
        repo = repo_bot()
        verita = leggi_csv(repo / "ux/nuvola/VERITA_JEANS.csv")
        assert len(verita) >= 4, "fixture VERITA_JEANS.csv assente"
        for r in verita:
            ora = datetime.fromisoformat(r["da"])
            s = osserva(ora, repo / "analisi", repo / "analisi")
            esito = valuta(s)["stato"]
            # Verita incerta non diventa un'etichetta certa; sola assenza uso non prova sonno.
            if "sveglio" in r["stato"]:
                assert esito == "sveglio", (r, esito)
            else:
                assert esito != "dorme", (r, esito)
            print(r["da"], r["stato"], "->", esito, "(replay solo uso; audio non incluso)")
        with tempfile.TemporaryDirectory() as tmp:  # live.json: PC attivo 1' fa -> sveglio; vecchio di 11' -> ignorato
            p = Path(tmp); ora = datetime(2026, 10, 2, 12, 0, 30)
            (p / "live.json").write_text(json.dumps(dict(pc=dict(attivo=True, t="2026-10-02T23:59:30"),
                                                         a56=dict(attivo=False, t="2026-10-02T23:59:30"))))
            o = osserva(ora, p, p)
            assert o["pc"] and not o["a56"] and o["live"] == dict(pc=60, a56=60), o["live"]
            assert o["fonti"]["pc"]["stato"] == "fresco"
            assert leggi_live(p / "live.json", ora + timedelta(minutes=11)) == {}, "live vecchio"
        assert blocchi("sveglio", dict(temperatura=30, carica=True, batteria=80)) == 12
        assert blocchi("dorme?", dict(temperatura=30, carica=True, batteria=80)) == 2
        assert blocchi("sveglio", dict(temperatura=45, carica=True, batteria=80)) == 0
        assert blocchi("sveglio", dict(temperatura=30, carica=False, batteria=15)) == 0
        assert blocchi("sveglio", dict(temperatura=30, carica=False, batteria=0)) == 0
        print("ok")
    else:
        print(json.dumps(aggiorna(), indent=1))
