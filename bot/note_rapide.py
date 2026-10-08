"""
sull'A56 (Termux) una pagina locale http://127.0.0.1:8090 con pulsanti grandi; un tocco = una riga in ~/note_rapide.csv
(ora, nota). Il PC la recupera via ssh. Solo 127.0.0.1: nessun altro in rete la vede.
python note_rapide.py            (sull'A56; parte da ~/.termux/boot)"""
import csv
import html
import os
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

FILE = os.path.expanduser("~/note_rapide.csv")
NOTE = ["🛏️ a letto", "😴 mi addormento", "👀 sveglio (risveglio breve)", "☀️ sveglio (mi alzo)", "🥱 stanco",
        "🧠 mente sveglia", "💤 sonno forte", "☕ caffè/tè", "🎵 musica accesa", "🤧 tosse/naso", "🍽️ mangiato", "🚶 uscito"]


def ultime(n=8):
    try:
        return list(csv.reader(open(FILE, encoding="utf-8")))[-n:][::-1]
    except OSError:
        return []


def pagina(fatto=""):
    bt = "".join(f'<form method="post"><button name="n" value="{html.escape(x)}">{html.escape(x)}</button></form>' for x in NOTE)
    st = "".join(f"<li>{html.escape(t[11:16])} · {html.escape(n)}</li>" for t, n in ultime())
    return f"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Note rapide</title><style>body{{margin:0;padding:12px;background:#0f1219;color:#e9ebf2;font:16px system-ui}}
.g{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}button{{width:100%;min-height:72px;font-size:17px;border-radius:14px;
border:1px solid #2b3248;background:#1e2332;color:#e9ebf2}}button:active{{background:#6cb0ff;color:#000}}
.ok{{color:#5fd39c;min-height:22px}}ul{{color:#8b92a8;padding-left:18px}}</style>
<h3>Note rapide (A56, senza internet)</h3><div class="ok">{html.escape(fatto)}</div><div class="g">{bt}</div><ul>{st}</ul>"""


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _r(self, corpo):
        b = corpo.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        self._r(pagina())

    def do_POST(self):
        n = urllib.parse.parse_qs(self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()).get("n", [""])[0]
        if n in NOTE:  # solo i pulsanti previsti: niente testo libero da salvare
            with open(FILE, "a", encoding="utf-8", newline="") as f:
                csv.writer(f).writerow([datetime.now().isoformat(timespec="seconds"), n])
        self._r(pagina(f"✓ {n} · {datetime.now():%H:%M}" if n in NOTE else ""))


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8090), H).serve_forever()
