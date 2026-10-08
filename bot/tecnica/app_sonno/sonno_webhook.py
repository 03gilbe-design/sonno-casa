"""Sul SUO telefono (A56, Termux, servizio sv 'sonnowebhook'): riceve i webhooks di Sleep as Android
(Impostazioni -> Servizi -> Automazione -> Webhooks, URL http://127.0.0.1:8765) e scrive ogni evento in
~/storage/shared/Documents/sonno/eventi.csv (t, evento, value1, value2). Eventi: sleep_tracking_started/stopped,
awake, not_awake, deep_sleep, light_sleep, rem, alarm_alert_start/dismiss, ...
"""
import csv, json, os, subprocess, threading, time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

OUT = os.path.expanduser("~/storage/shared/Documents/sonno/eventi.csv")
DORME = ("deep_sleep", "light_sleep", "rem")  # Sleep as Android: stai dormendo
# --- MUSICA CHE SI SPEGNE (modulo musica, vedi tecnica\musica\RIEPILOGO.md) --- regolabili:
MINUTI_SONNO_STABILE = 20
MINUTI_DISCESA = 2         # il volume scende piano, per non svegliarlo
# appena ripartito) non abbassava MAI finche' non arrivava un "awake" -> all'avvio si parte da "sveglio adesso".
stato = {"sveglio": datetime.now(), "abbassata": False, "abbassata_t": None, "rispetta": None}
RISPETTA_MINUTI = 90


def volume_musica():
    v = json.loads(subprocess.run(["termux-volume"], capture_output=True, text=True, timeout=20).stdout)
    return next(x["volume"] for x in v if x["stream"] == "music")


def abbassa_musica():
    """
    Solo il canale MUSICA: sveglie e suonerie non si toccano. Non la rialza al risveglio (spari nelle orecchie)."""
    if os.path.exists(os.path.expanduser("~/NO_MUSICA_GIU")):
        riga([datetime.now().isoformat(timespec="seconds"), "claude_non_abbasso", "interruttore NO_MUSICA_GIU", ""])
        return
    try:
        cur = volume_musica()
        for liv in range(cur - 1, -1, -1):
            if liv < cur - 1 and volume_musica() > liv + 1:
                stato["rispetta"] = datetime.now() + timedelta(minutes=RISPETTA_MINUTI)
                riga([datetime.now().isoformat(timespec="seconds"), "claude_non_abbasso", "l'hai alzato tu durante la discesa", ""])
                return
            subprocess.run(["termux-volume", "music", str(liv)], timeout=20)
            time.sleep(MINUTI_DISCESA * 60 / max(cur, 1))
        riga([datetime.now().isoformat(timespec="seconds"), "claude_musica_abbassata", cur, 0])
    except Exception as e:  # mai far cadere il ricevitore per questo
        riga([datetime.now().isoformat(timespec="seconds"), "claude_errore_musica", str(e)[:80], ""])


def recente(ora):
    """(nota rimossa)"""
    return stato["abbassata_t"] is not None and ora - stato["abbassata_t"] < timedelta(hours=3)


def riga(r):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "a", newline="") as f:
        csv.writer(f).writerow(r)


class H(BaseHTTPRequestHandler):
    def _salva(self, d):
        ev, ora = d.get("event", ""), datetime.now()
        riga([ora.isoformat(timespec="seconds"), ev, d.get("value1", ""), d.get("value2", "")])
        if ev in ("sleep_tracking_started", "awake"):
            # inizio o risveglio: si riparte da zero (se si sveglia e rialza la musica, non gliela rispengo subito)
            stato.update(sveglio=ora, abbassata=False)
        elif ev in DORME and stato["rispetta"] and ora < stato["rispetta"]:
            riga([ora.isoformat(timespec="seconds"), "claude_non_abbasso", f"l'hai rialzato tu: fino alle {stato['rispetta']:%H:%M}", ""])
        elif (ev in DORME and not stato["abbassata"] and stato["sveglio"]
              and ((ev == "deep_sleep" and not recente(ora)) or ora - stato["sveglio"] >= timedelta(minutes=MINUTI_SONNO_STABILE))):
            try:
                alta = volume_musica() > 0
            except Exception:
                alta = False
            if recente(ora) and alta:
                stato["rispetta"] = ora + timedelta(minutes=RISPETTA_MINUTI)
                riga([ora.isoformat(timespec="seconds"), "claude_non_abbasso", f"l'hai rialzato tu: fino alle {stato['rispetta']:%H:%M}", ""])
            else:
                stato.update(abbassata=True, abbassata_t=ora)
                threading.Thread(target=abbassa_musica, daemon=True).start()
        elif ev in DORME:
            perche = "gia' abbassata" if stato["abbassata"] else                 f"sonno da {int((ora - stato['sveglio']).total_seconds() // 60)}' < {MINUTI_SONNO_STABILE}'"
            riga([ora.isoformat(timespec="seconds"), "claude_non_abbasso", perche, ""])
        self.send_response(200); self.end_headers(); self.wfile.write(b"ok")

    def do_POST(self):
        corpo = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode("utf-8", "replace")
        try:
            d = json.loads(corpo)
        except ValueError:
            d = {k: v[0] for k, v in parse_qs(corpo).items()}
        self._salva(d)

    def do_GET(self):
        self._salva({k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()})

    def log_message(self, *a):
        pass


def _prova():
    """(nota rimossa)"""
    global volume_musica, abbassa_musica
    fatti = []
    volume_musica = lambda: 7
    abbassa_musica = lambda: fatti.append("giu")
    riga_vera = globals()["riga"]; globals()["riga"] = lambda r: fatti.append(r[1])
    h = H.__new__(H); h.send_response = h.end_headers = lambda *a: None; h.wfile = type("W", (), {"write": lambda s, b: None})()
    t0 = datetime.now()
    stato.update(sveglio=t0 - timedelta(hours=1), abbassata=False, abbassata_t=t0 - timedelta(minutes=40), rispetta=None)
    stato["abbassata"] = False  # c'e' stato un "awake" dopo l'abbassamento
    h._salva({"event": "deep_sleep"})
    assert "giu" not in fatti, fatti  # deep_sleep da solo dopo un abbassamento recente: no
    stato["sveglio"] = t0 - timedelta(minutes=30); h._salva({"event": "light_sleep"})
    assert "giu" not in fatti and stato["rispetta"], (fatti, stato)
    globals()["riga"] = riga_vera
    print("ok")


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["prova"]:
        _prova(); sys.exit()
    HTTPServer(("127.0.0.1", 8765), H).serve_forever()  # solo dal telefono stesso, non dalla rete

