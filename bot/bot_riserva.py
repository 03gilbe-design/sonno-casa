"""
l'A21s e' spento (Mini App/bot morti). Lo accende/spegne il guardiano del PC con il file ~/riserva_on (mai insieme al
bot dell'A21s: due getUpdates si rubano i messaggi). Token in ~/.env_IlTuoBot (copiato dall'A21s, chmod 600).
Ogni messaggio -> pulsanti; un tocco -> riga in ~/note_rapide.csv (ora, nota) e conferma sullo stesso messaggio."""
import csv
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime

HOME = os.path.expanduser("~")
ON, ENV, NOTE_F = HOME + "/riserva_on", HOME + "/.env_IlTuoBot", HOME + "/note_rapide.csv"
NOTE = ["🛏️ a letto", "😴 mi addormento", "👀 risveglio breve", "☀️ mi alzo", "🥱 stanco", "🧠 mente sveglia",
        "💤 sonno forte", "☕ caffè/tè", "🎵 musica", "🤧 tosse/naso", "🍽️ mangiato", "🚶 uscito"]
env = dict(l.strip().split("=", 1) for l in open(ENV, encoding="utf-8") if "=" in l)
TOK = next(v for k, v in env.items() if "TOKEN" in k).strip("\"'")
CHAT = env["TELEGRAM_CHAT"].strip("\"'")


def api(metodo, **p):
    d = urllib.parse.urlencode({k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in p.items()}).encode()
    return json.load(urllib.request.urlopen(f"https://api.telegram.org/bot{TOK}/{metodo}", d, timeout=70))


def tastiera():
    return {"inline_keyboard": [[{"text": NOTE[i + j], "callback_data": str(i + j)} for j in (0, 1)] for i in range(0, len(NOTE), 2)]}


def main():
    off = 0
    while os.path.exists(ON):
        try:
            for u in api("getUpdates", offset=off, timeout=50).get("result", []):
                off = u["update_id"] + 1
                m, cb = u.get("message"), u.get("callback_query")
                if m and str(m["chat"]["id"]) == CHAT:
                    api("sendMessage", chat_id=CHAT, text="🟠 <b>A21s spento</b>: note dal bot di riserva (A56). Tocca:",
                        parse_mode="HTML", reply_markup=tastiera())
                elif cb and str(cb["message"]["chat"]["id"]) == CHAT and cb.get("data", "").isdigit():
                    n = NOTE[int(cb["data"]) % len(NOTE)]
                    with open(NOTE_F, "a", encoding="utf-8", newline="") as f:
                        csv.writer(f).writerow([datetime.now().isoformat(timespec="seconds"), n])
                    api("answerCallbackQuery", callback_query_id=cb["id"], text=f"✓ {n}")
                    api("editMessageText", chat_id=CHAT, message_id=cb["message"]["message_id"],
                        text=f"✓ {n} · {datetime.now():%H:%M}\nAltra nota:", reply_markup=tastiera())
        except Exception:  # noqa: BLE001 - rete a singhiozzo: si riprova
            time.sleep(10)


if __name__ == "__main__":
    main()
