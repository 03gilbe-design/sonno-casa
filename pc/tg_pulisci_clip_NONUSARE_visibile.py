# tg_pulisci_clip.py DA A [quanti_indietro] - cancella da @IlTuoBot le clip audio (titolo "HH:MM tipo GG/MM")
# temporanea), legge il titolo e cancella la copia. Tocca SOLO messaggi audio con quel formato di titolo.
import json, re, sys, urllib.parse, urllib.request
import tg_IlTuoBot as T  # riusa token/chat
extra = sys.argv[1:]


def api(m, **p):
    try:
        return json.load(urllib.request.urlopen(f"https://api.telegram.org/bot{T.tok}/{m}",
                                                urllib.parse.urlencode(p).encode(), timeout=30))
    except urllib.error.HTTPError as e:
        return json.load(e)


da, a = extra[0], extra[1]
n = int(extra[2]) if len(extra) > 2 else 60
solo = extra[3] if len(extra) > 3 else None  # es. "voce": tiene solo quel tipo; toglie anche le mie intestazioni 🎧
if len(extra) > 4:  # id di partenza esplicito: niente sonda (ogni inoltro consuma id, le clip finiscono piu' indietro)
    sonda = int(extra[4]) + 1
else:
    sonda = api("sendMessage", chat_id=T.chat, text="…", disable_notification="true")["result"]["message_id"]
    api("deleteMessage", chat_id=T.chat, message_id=sonda)
tolte = tenute = 0
for mid in range(sonda - 1, sonda - 1 - n, -1):
    f = api("forwardMessage", chat_id=T.chat, from_chat_id=T.chat, message_id=mid, disable_notification="true")
    if not f.get("ok"):
        continue
    api("deleteMessage", chat_id=T.chat, message_id=f["result"]["message_id"])
    if solo and (f["result"].get("text") or "").startswith("🎧"):
        tolte += api("deleteMessage", chat_id=T.chat, message_id=mid).get("ok", False)
        continue
    m = re.match(r"(\d\d:\d\d) (\w+) \d\d/\d\d$", (f["result"].get("audio") or {}).get("title", ""))
    if not m:
        continue
    if da <= m[1] <= a and (not solo or m[2] == solo):
        tenute += 1
    elif api("deleteMessage", chat_id=T.chat, message_id=mid).get("ok"):
        tolte += 1
print(f"cancellate {tolte}, tenute {tenute}")
