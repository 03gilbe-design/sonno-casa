"""Watchdog locale A21s. Nessun deploy, nessun PC, nessuna cancellazione audio."""
import csv
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from datetime import datetime, timedelta


def recente(t, ora, secondi):
    try:
        return 0 <= (ora - datetime.fromisoformat(t)).total_seconds() <= secondi
    except (ValueError, TypeError):
        return False


def leggi(p):
    try:
        d = json.loads(Path(p).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def salva(p, d):
    p = Path(p)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(d), encoding="utf-8")
    tmp.replace(p)


def comando(args):
    return subprocess.run(args, capture_output=True, text=True, timeout=8, check=True).stdout


def osserva(home, rec, bot, ora):
    stato = leggi(home / "stato.json")
    try:
        registra = json.loads(comando(["termux-microphone-record", "-i"]))["isRecording"]
    except (OSError, subprocess.SubprocessError, ValueError, KeyError):
        registra = None
    try:
        b = json.loads(comando(["termux-battery-status"]))
        attesa = b["plugged"] != "UNPLUGGED" or b["percentage"] > 20
    except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError):
        b = {}
        attesa = None
    ultimo = ""
    for giorno in (ora - timedelta(days=1), ora):
        try:
            with (rec / f"minuti_{giorno:%Y%m%d}.csv").open(encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    t = r.get("t", "")
                    if recente(t, ora, 172800):
                        ultimo = max(ultimo, t)
        except OSError:
            pass
    guasti = []
    if attesa is not False:
        if registra is not True:
            guasti.append("registrazione")
        # Blocchi da 30 minuti: non pretendere un CSV al minuto.
        if not recente(ultimo, ora, 75 * 60):
            guasti.append("minuti")
    if not recente(stato.get("t"), ora, 10 * 60):
        guasti.append("stato")
    try:
        eta = ora.timestamp() - (bot / "uso.csv").stat().st_mtime
        uso_ok = 0 <= eta <= 600 and recente(leggi(bot / "uso_a56.json").get("raccolto"), ora, 600)
    except OSError:
        uso_ok = False
    if not uso_ok:
        guasti.append("uso")
    temperatura = b.get("temperature")
    sicura = attesa is True and isinstance(temperatura, (int, float)) and 0 <= temperatura < 42
    return dict(guasti=guasti, registra=registra, attesa=attesa, stato=stato, minuto=ultimo,
                analisi_sicura=sicura)


def sync_a56(bot, ora):
    """Solo file sonno via SSH; heartbeat vecchio non rende fresco uso.csv."""
    script = ("import json,pathlib; p=pathlib.Path.home()/'storage/shared/Documents/sonno'; "
              "print(json.dumps({n:((p/n).read_text() if (p/n).exists() else '') for n in "
              "['uso_recente.json','uso.csv','eventi.csv']}))")
    raw = comando(["ssh", "-p", "8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                   "192.0.2.54", "python -c " + shlex.quote(script)])
    d = json.loads(raw)
    heartbeat = json.loads(d["uso_recente.json"])
    if heartbeat.get("fonte") != "a56_locale" or not recente(heartbeat.get("raccolto"), ora, 120):
        raise ValueError("A56 senza heartbeat fresco")
    righe = list(csv.reader(io.StringIO(d["uso.csv"])))
    if any(len(r) != 2 or r[1] != "a56" or not recente(r[0], ora, 8*86400) for r in righe):
        raise ValueError("uso A56 invalido")
    try:
        with (bot / "uso.csv").open(encoding="utf-8") as f:
            righe += [r for r in csv.reader(f) if len(r) == 2 and r[1] == "pc" and recente(r[0], ora, 8*86400)]
    except FileNotFoundError:
        pass
    # Conserva PC; l'A56 resta fonte autorevole dei propri minuti.
    for nome, testo in (("uso.csv", "".join(",".join(r)+"\n" for r in sorted(set(map(tuple, righe))))),
                        ("a56_eventi_sleep.csv", d["eventi.csv"])):
        tmp = bot / (nome + ".sync.tmp")
        tmp.write_text(testo, encoding="utf-8")
        tmp.replace(bot / nome)
    salva(bot / "uso_a56.json", heartbeat)


def rimedia(guasti, snap, home, bot, riavvia):
    if "registrazione" in guasti and snap["attesa"] is True:
        # Non interrompere mai una registrazione attiva o di stato ignoto.
        if snap["registra"] is False:
            subprocess.run(["pkill", "-f", "^bash .*home/rec.sh"], capture_output=True, timeout=5)
        riavvia(avvisa=False)
    if "stato" in guasti:
        comando([sys.executable, str(home / "stato.py")])
    if "uso" in guasti:
        sync_a56(bot, datetime.now())
    if "minuti" in guasti and snap.get("analisi_sicura") is True:
        # Stesso lucchetto di rec.sh: mai analisi concorrenti, nessun riavvio audio.
        with (home / "analizza.log").open("a") as log:
            subprocess.Popen(["flock", "-n", str(home / ".analisi.lock"), "nice", "-n", "19",
                              sys.executable, str(home / "sonno_tel.py"), "analizza"],
                             stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                             start_new_session=True)


FACOLTATIVI = ("uso",)  # A56 personale: puo' mancare senza che i dati del sonno manchino


def controlla(home, rec, bot, riavvia, avvisa, ora=None, sospeso=False):
    """Un tentativo, verifica successiva dopo grazia; stato persistente tra riavvii."""
    fermo = sospeso if callable(sospeso) else lambda: sospeso
    if fermo():
        return
    home, rec, bot = map(Path, (home, rec, bot))
    tempo_reale = ora is None
    ora = ora or datetime.now()
    p = bot / "freschezza.json"
    memoria = leggi(p)
    snap = osserva(home, rec, bot, ora)
    pendenti = memoria.get("pendenti", {})
    tentativi = memoria.get("tentativi", dict(pendenti))
    falliti = []
    for g in snap["guasti"]:
        if fermo():
            return
        grazia = 75*60 if g == "minuti" else 600
        if g in pendenti and not recente(pendenti[g], ora, grazia-1):
            falliti.append(g)
        if g not in pendenti:
            pendenti[g] = ora.isoformat()
        if g not in tentativi or not recente(tentativi[g], ora, 3600):
            tentativi[g] = ora.isoformat()
            try:
                rimedia([g], snap, home, bot, riavvia)
            except (OSError, subprocess.SubprocessError, ValueError, KeyError, TypeError) as e:
                memoria["ultimo_errore"] = type(e).__name__ + ": " + str(e)[:120]
    # Verifica reale dopo rimedio: exit 0 non basta.
    if tempo_reale:
        ora = datetime.now()
    dopo = osserva(home, rec, bot, ora)
    memoria["pendenti"] = {g:t for g,t in pendenti.items() if g in dopo["guasti"]}
    memoria["tentativi"] = {g:t for g,t in tentativi.items() if g in dopo["guasti"]}
    falliti = [g for g in falliti if g in dopo["guasti"]]
    stato = dopo["stato"]
    # Notte interamente silenziosa: anche uno stato vecchio non autorizza a svegliarlo.
    silenzio = ora.hour >= 22 or ora.hour < 8 or stato.get("utente") == "dorme"
    # nella scheda Stato). Per gli altri guasti: lo stesso guasto al massimo una volta al giorno.
    oggi = ora.strftime("%Y-%m-%d")
    giorno = memoria.get("avvisati", {})
    da_dire = [g for g in falliti if g not in FACOLTATIVI and giorno.get(g) != oggi]
    if da_dire and not fermo() and not silenzio and not recente(memoria.get("avviso"), ora, 3599):
        memoria["avviso"] = ora.isoformat()
        memoria["avvisati"] = dict(giorno, **{g: oggi for g in da_dire})
        salva(p, memoria)  # riserva prima dell'invio, evita raffiche dopo errori/restart
        avvisa()
    salva(p, memoria)
