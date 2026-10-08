# Manda su @IlTuoBot il materiale da valutare (dal PC): foto una per una con didascalia corta + riepiloghi.
import json, os, urllib.parse, urllib.request, uuid

env = dict(l.strip().split("=", 1) for l in open(os.path.expanduser(r"~\.env"), encoding="utf-8", errors="ignore")
           if "=" in l and not l.lstrip().startswith("#"))
TOKEN, CHAT = env["TELEGRAM_SONNO_TOKEN"].strip(), env["TELEGRAM_CHAT"].strip().strip("\"'")
URL = f"https://api.telegram.org/bot{TOKEN}/"
C = r"C:\sonno_bot\concept"


def testo(t):
    d = urllib.parse.urlencode({"chat_id": CHAT, "text": t, "parse_mode": "HTML"}).encode()
    urllib.request.urlopen(URL + "sendMessage", data=d, timeout=60)


def file(metodo, campo, path, didasc):
    b = uuid.uuid4().hex
    campi = {"chat_id": CHAT, "caption": didasc, "parse_mode": "HTML"}
    corpo = b"".join(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in campi.items())
    corpo += (f"--{b}\r\nContent-Disposition: form-data; name=\"{campo}\"; filename=\"{os.path.basename(path)}\"\r\n"
              f"Content-Type: application/octet-stream\r\n\r\n").encode() + open(path, "rb").read() + f"\r\n--{b}--\r\n".encode()
    urllib.request.urlopen(urllib.request.Request(URL + metodo, data=corpo,
                           headers={"Content-Type": f"multipart/form-data; boundary={b}"}), timeout=120)


if __name__ == "__main__":  # solo se lanciato: importarlo per le funzioni NON deve rimandare tutto
    testo("🧵 <b>Da valutare</b>: 6 immagini + 2 riepiloghi. Rispondi a ognuna: ok / no / cosa cambiare.")
    FOTO = [
        (rf"{C}\avatar_512.png", "A · <b>Toppa</b>, l'avatar del bot (toppa di utente con mascherina)"),
        (rf"{C}\espressioni.png", "B · Toppa: notte, buona, storta, russa, allarme"),
        (os.path.join(os.environ.get("CLAUDE_JOB_DIR", ""), "tmp", "prova_tel3.png"),
         "C · <b>Mattino</b> (fatto dal telefono, notte finta). Didascalia vera:\n☀️ <b>8h 46</b> · 84/100 — Tiene: si riparte bene.\n🟥 russato <b>70'</b> · 🟪 1 sbuffo"),
        (rf"{C}\esempi\trend_7.png", "D · Ultime 7 notti (ogni lunedì)"),
        (rf"{C}\esempi\trend_30.png", "E · Ultime 30 notti: si vede quanto balla l'orario"),
        (rf"{C}\esempi\confronto.png", "F · Tu vs gli altri (regolarità, una volta al mese)"),
    ]
    for p, d in FOTO:
        if os.path.exists(p):
            file("sendPhoto", "photo", p, d)
            print("ok", os.path.basename(p))
    file("sendDocument", "document", rf"{C}\RIEPILOGO.md", "G · concept: personaggio, voce, palette, lessico")
    file("sendDocument", "document", r"C:\sonno_bot\ux\RIEPILOGO.md", "H · esperienza d'uso: flusso, un tocco, comodino")
    print("fatto")
