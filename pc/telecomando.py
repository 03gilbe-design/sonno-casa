"""Telecomando Telegram per taratura e test microfoni: decide l'utente, un tocco = 10s registrati ed etichettati.
   pythonw telecomando.py   (resta in ascolto finche' non tocca Fine; il loop notturno e' sospeso nel frattempo)
File: C:\\sonno_audio\\cal\\<etichetta>__<mic>__<ora>.m4a  -> cal_train.py (modello) e mic_confronto.py (classifica).
"""
import contextlib, io, json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime
import numpy as np, onnxruntime as ort
sys.path.insert(0, r"C:\sonno_tex")
from sonno_audio import adb, device, load, MODEL, log
from cal_sessione import T, ingressi, riavvia_loop

env = dict(l.strip().split("=", 1) for l in open(os.path.expanduser(r"~\.env"), encoding="utf-8", errors="ignore")
           if "=" in l and not l.lstrip().startswith("#"))
TOKEN, CHAT = env["TELEGRAM_BOT_TOKEN"].strip("\"'"), env["TELEGRAM_CHAT"].strip("\"'")
URL = f"https://api.telegram.org/bot{TOKEN}/"
CAL, PH = r"C:\sonno_audio\cal", "/sdcard/Recordings/sonno_cal"
INBOX = r"C:\sonno_audio\tg_messaggi_utente.log"  # testi dell'utente al bot: salvati prima di confermarli
SUONI = ["russa", "respiro", "voce", "tosse", "movimento", "sbuffo", "ambiente"]
MIC = ["interno", "cuffia1", "cuffia2", "cuffia3"]
nomi = [l.split(",", 2)[2].strip().strip('"') for l in open(r"C:\sonno_tex\yamnet\yamnet_class_map.csv")][1:]
sess = ort.InferenceSession(MODEL)


def api(m, **k):
    d = urllib.parse.urlencode({a: json.dumps(v) if isinstance(v, (dict, list)) else v for a, v in k.items()}).encode()
    return json.load(urllib.request.urlopen(URL + m, data=d, timeout=70))


def pannello(mic, testo, rec=False):
    kb = ([[{"text": "⏹️ STOP", "callback_data": "x"}]] if rec else []) + [
          [{"text": s.capitalize(), "callback_data": "s:" + s} for s in SUONI[:4]],
          [{"text": s.capitalize(), "callback_data": "s:" + s} for s in SUONI[4:]],
          [{"text": ("🎧 " if m == mic else "") + m, "callback_data": "m:" + m} for m in MIC],
          [{"text": "📊 Classifica", "callback_data": "c"}, {"text": "🧠 Allena", "callback_data": "a"},
           {"text": "⏹️ Fine", "callback_data": "f"}]]
    api("sendMessage", chat_id=CHAT, text=testo, parse_mode="HTML", reply_markup={"inline_keyboard": kb})


def avvia(dev, lab, mic):
    nome = f"{lab}__{mic}__{datetime.now():%Y%m%d_%H%M%S}.m4a"
    T(dev, f"termux-microphone-record -e aac -b 64 -r 16000 -c 1 -l 0 -f {PH}/{nome}")  # -l 0 = finche' STOP
    return nome, time.time()


def ferma(dev, nome, t0):
    T(dev, "termux-microphone-record -q")
    time.sleep(0.5)
    lab, mic = nome.split("__")[:2]
    if time.time() - t0 < 1.2:
        adb("shell", f"rm -f {PH}/{nome}", dev=dev)
        return f"⚠️ {lab}: troppo corto (serve almeno 1s), scartato"
    loc = os.path.join(CAL, nome)
    adb("pull", f"{PH}/{nome}", loc, dev=dev)
    if not os.path.exists(loc):
        return f"⚠️ {lab}: registrazione non arrivata"
    w = load(loc)
    sc, emb, _ = sess.run(None, {"waveform": w})
    top = np.argsort(sc.max(0))[::-1][:2]
    yam = " · ".join(f"{nomi[i]} {sc[:, i].max():.1f}" for i in top)
    mio = ""
    if os.path.exists(r"C:\sonno_tex\modello_personale.npz"):
        P = np.load(r"C:\sonno_tex\modello_personale.npz")
        z = ((emb - P["mu"]) / P["sd"]) @ P["W"].T + P["b"]
        voti = P["classi"][z.argmax(1)]
        k, n = np.unique(voti, return_counts=True)
        mio = f" · mio: {k[n.argmax()]} {n.max() / len(voti):.0%}"
    return f"✅ <b>{lab}</b> {len(w) / 16000:.0f}s [{mic}] — YAMNet: {yam}{mio}"


def allena():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        import importlib, cal_train
        importlib.reload(cal_train)
    t = buf.getvalue()
    acc = next((l.split()[1] for l in t.splitlines() if l.strip().startswith("accuracy")), "?")
    rus = [l.split("russamento:")[1].split(",")[0].strip() for l in t.splitlines() if "russamento:" in l]
    esito = "installato ✅" if cal_train.MIGLIORA else "non migliore, resta YAMNet"
    if cal_train.MIGLIORA:
        dev = device()
        adb("push", cal_train.OUT, "/sdcard/Recordings/tmp_modello.npz", dev=dev)
        adb("shell", "cat /sdcard/Recordings/tmp_modello.npz | run-as com.termux sh -c "
                     "'cat > files/home/modello_personale.npz' && rm /sdcard/Recordings/tmp_modello.npz", dev=dev)
    return f"🧠 accuratezza {acc} · russa YAMNet {rus[0] if rus else '?'} vs mio {rus[1] if len(rus) > 1 else '?'} · {esito}"


def main():
    os.makedirs(CAL, exist_ok=True)
    dev = device()
    T(dev, 'pkill -f "^bash .*home/rec.sh"; termux-microphone-record -q')  # sospendo il loop notturno
    adb("shell", f"mkdir -p {PH}", dev=dev)
    mic = "interno"
    pannello(mic, f"🎛️ <b>Telecomando</b> — tocca un suono = parte, ⏹️ STOP = fine. Mic: <b>{mic}</b> "
                  f"(Android: {', '.join(ingressi(dev))})")
    off, rec = None, None  # rec = (nome file, ora inizio) mentre registra
    for u in api("getUpdates", timeout=0).get("result", []):  # tocchi vecchi (sessioni precedenti): li salto
        off = u["update_id"] + 1
        if "message" in u:
            with open(INBOX, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now():%Y-%m-%d %H:%M} {u['message'].get('text', '')}\n")
    while True:
        try:
            ups = api("getUpdates", timeout=50, **({"offset": off} if off else {})).get("result", [])
        except Exception as e:
            log(f"telecomando getUpdates: {e}"); time.sleep(5); continue
        for u in ups:
            off = u["update_id"] + 1
            if "message" in u:  # testo scritto al bot: non lo perdo
                with open(INBOX, "a", encoding="utf-8") as f:
                    f.write(f"{datetime.now():%Y-%m-%d %H:%M} {u['message'].get('text', '')}\n")
                continue
            q = u.get("callback_query")
            if not q:
                continue
            try:
                api("answerCallbackQuery", callback_query_id=q["id"])
            except Exception:
                pass  # tocco scaduto: Telegram rifiuta la risposta, l'azione la faccio lo stesso
            d = q["data"]
            try:
                if d.startswith("s:") or d == "x":
                    esito = ferma(dev, *rec) + "\n" if rec else ""
                    rec = None
                    if d != "x":
                        rec = avvia(dev, d[2:], mic)
                        esito += f"🔴 <b>{d[2:]}</b> — registra… tocca STOP quando vuoi"
                    pannello(mic, esito, rec=bool(rec))
                elif d.startswith("m:"):
                    esito = ferma(dev, *rec) + "\n" if rec else ""
                    rec, mic = None, d[2:]
                    pannello(mic, esito + f"🎧 mic: <b>{mic}</b> · Android vede: {', '.join(ingressi(dev))}")
                elif d == "c":
                    import importlib, mic_confronto
                    importlib.reload(mic_confronto)
                    pannello(mic, mic_confronto.classifica())
                elif d == "a":
                    pannello(mic, allena())
                elif d == "f":
                    if rec:
                        ferma(dev, *rec)
                    riavvia_loop(dev)
                    api("sendMessage", chat_id=CHAT, text="⏹️ Fine. Registrazione notturna ripartita.")
                    api("getUpdates", offset=off, timeout=0)
                    return
            except Exception as e:
                log(f"telecomando {d}: {e}")
                api("sendMessage", chat_id=CHAT, text=f"⚠️ errore: {str(e)[:150]}")


if __name__ == "__main__":
    main()
