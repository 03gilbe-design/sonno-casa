"""Provvisorio: manda su @IlTuoBot i pezzi di russamento di una notte (quelli dove YAMNet sente davvero russare),
come vocali con ✅/❌ — i tocchi li gestisce il bot sul telefono (giudizi.csv).
   python manda_russamenti.py AAAAMMGG HHMM HHMM   (es. 20260928 0451 0832)
"""
import json, os, subprocess, sys
import numpy as np, onnxruntime as ort
sys.path.insert(0, r"C:\sonno_tex"); sys.path.insert(0, r"C:\sonno_bot")
from sonno_audio import device, load, MODEL
from manda_valutazione import testo, file

giorno, da, a = sys.argv[1], sys.argv[2], sys.argv[3]
dev = device()
TMP = os.path.join(os.environ.get("TEMP", "."), "russamenti")
os.makedirs(TMP, exist_ok=True)
nomi = subprocess.run(["adb", "-s", dev, "shell", "run-as com.termux ls files/home/rec"], capture_output=True,
                      text=True).stdout.split()
scelti = sorted(n for n in nomi if n.startswith(f"russa_{giorno}_") and da <= n[15:19] <= a)
sess = ort.InferenceSession(MODEL)
buoni = []
for n in scelti:
    loc = os.path.join(TMP, n)
    open(loc, "wb").write(subprocess.run(["adb", "-s", dev, "exec-out", "run-as", "com.termux", "cat",
                                          f"files/home/rec/{n}"], capture_output=True).stdout)
    m = float(sess.run(None, {"waveform": load(loc)})[0][:, 38].max())
    print(n, f"russa max {m:.2f}")
    if m >= 0.3:  # dentro c'e' davvero russamento (i pezzi vecchi tagliati male sono silenzio)
        buoni.append(n)
testo(f"🔊 <b>Russamenti di stanotte</b> ({da[:2]}:{da[2:]}→{a[:2]}:{a[2:]}): {len(buoni)} pezzi su {len(scelti)} "
      f"(gli altri erano tagliati male). Ascolta e tocca ✅ o ❌.")
for n in buoni:
    ogg = os.path.join(TMP, n[:-4] + ".ogg")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(TMP, n), "-c:a", "libopus", "-b:a", "32k", ogg])
    kb = {"inline_keyboard": [[{"text": "✅ Giusto", "callback_data": "g:1:" + n}, {"text": "❌ No", "callback_data": "g:0:" + n}]]}
    # sendVoice con pulsanti: riuso file() aggiungendo reply_markup nella didascalia non basta -> chiamata diretta
    import manda_valutazione as mv, uuid, urllib.request
    b = uuid.uuid4().hex
    campi = {"chat_id": mv.CHAT, "caption": f"Russa {n[15:17]}:{n[17:19]} — è russamento?", "disable_notification": "true",
             "reply_markup": json.dumps(kb)}
    corpo = b"".join(f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode() for k, v in campi.items())
    corpo += (f"--{b}\r\nContent-Disposition: form-data; name=\"voice\"; filename=\"{os.path.basename(ogg)}\"\r\n"
              f"Content-Type: audio/ogg\r\n\r\n").encode() + open(ogg, "rb").read() + f"\r\n--{b}--\r\n".encode()
    urllib.request.urlopen(urllib.request.Request(mv.URL + "sendVoice", data=corpo,
                           headers={"Content-Type": f"multipart/form-data; boundary={b}"}), timeout=120)
print("mandati", len(buoni))
