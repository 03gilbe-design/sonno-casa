# tg_leggi.py [N] - ultimi N messaggi ricevuti dal bot generico (~/.env TELEGRAM_BOT_TOKEN), SENZA consumare la coda
import json, os, sys, urllib.request
from datetime import datetime
env = dict(l.strip().split("=", 1) for l in open(os.path.expanduser("~/.env"), encoding="utf-8", errors="ignore")
           if "=" in l and not l.lstrip().startswith("#"))
tok = env["TELEGRAM_BOT_TOKEN"].strip('"\'')
u = json.load(urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/getUpdates?limit=100", timeout=30))["result"]
for x in u[-int(sys.argv[1]) if len(sys.argv) > 1 else -10:]:
    m = x.get("message") or x.get("edited_message") or {}
    if m:
        print(datetime.fromtimestamp(m["date"]).strftime("%d/%m %H:%M"), "|", m.get("text") or m.get("caption") or "[" + ",".join(k for k in m if k in ("voice", "audio", "photo", "document")) + "]")
