"""LANCIO (dal PC, telefono A21s collegato in adb):  python voce_sessione.py   (da C:/sonno_tex)
Termux va in primo piano da solo (serve per non avere il microfono silenziato); a fine sessione il loop notturno riparte.
Taratura A VOCE, con risposte del telefono a ogni comando.
  <suono> (russa, respiro, tosse, movimento, voce, sbuffo, silenzio) o "inizia" (= ultimo suono) -> "Vai", apre un pezzo
  "stop" / "ferma"      -> "Preso", chiude il pezzo
  "cancella"/"annulla"  -> "Cancellato", butta l'ultimo pezzo
  "fine"                -> chiude, taglia i pezzi, allena, dice cosa ha sentito
Registrazione continua Ogg/Opus letta ogni 3s mentre cresce; Vosk (offline, solo parole chiave) trova i tempi.
I momenti in cui parla il telefono vengono tolti dai pezzi.
   python voce_sessione.py   -> C:\\sonno_audio\\cal\\<suono>__voce__<ora>_<n>.wav, poi cal_train
"""
import json, os, subprocess, sys, time
from datetime import datetime
import numpy as np, soundfile as sf, vosk
sys.path.insert(0, r"C:\sonno_tex")
from sonno_audio import adb, device, load, tg
from cal_sessione import T, riavvia_loop, registra

vosk.SetLogLevel(-1)
MODELLO = vosk.Model(r"C:\sonno_tex\vosk\vosk-model-small-it-0.22")
SUONI = {"russa": "russa", "russo": "russa", "respiro": "respiro", "respira": "respiro", "voce": "voce",
         "parlo": "voce", "tosse": "tosse", "tossisco": "tosse", "movimento": "movimento", "muovo": "movimento",
         "sbuffo": "sbuffo", "ambiente": "ambiente", "silenzio": "ambiente"}
STOP, FINE, CANC, INIZIA = {"stop", "ferma", "basta"}, {"fine"}, {"cancella", "annulla"}, {"inizia"}
GRAMMATICA = json.dumps(sorted(SUONI) + sorted(STOP | FINE | CANC | INIZIA) + ["[unk]"])
PH, CAL, SR, MAX_MIN = "/sdcard/Recordings/sonno_cal", r"C:\sonno_audio\cal", 16000, 30
TMP = os.environ["TEMP"]
# risposte SENZA parole chiave (se no Vosk le sente dal telefono stesso)
RISPOSTE = {"vai": "Vai.", "preso": "Preso.", "cancellato": "Cancellato.", "boh": "Non ho capito quale suono."}


def sintetizza(testo, nome):
    """Voce italiana di Windows (Elsa) -> ogg nella home di Termux. Ritorna la durata in secondi."""
    wav, ogg = os.path.join(TMP, nome + ".wav"), os.path.join(TMP, nome + ".ogg")
    ps = ("Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
          "$s.SelectVoice('Microsoft Elsa Desktop'); $s.Rate=1; "
          f"$s.SetOutputToWaveFile('{wav}'); $s.Speak('{testo.replace(chr(39), ' ')}'); $s.Dispose()")
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", wav, "-c:a", "libopus", ogg], capture_output=True)
    return sf.info(wav).duration, ogg


def carica(dev, ogg, nome):
    adb("push", ogg, f"/sdcard/Recordings/tmp_{nome}.ogg", dev=dev)
    adb("shell", f"cat /sdcard/Recordings/tmp_{nome}.ogg | run-as com.termux sh -c 'cat > files/home/{nome}.ogg' "
                 f"&& rm /sdcard/Recordings/tmp_{nome}.ogg", dev=dev)


def suona(dev, nome):
    T(dev, f"timeout 15 termux-media-player play $HOME/{nome}.ogg")  # ritorna subito, il suono continua


def parla(dev, testo):
    """Frase nuova (inizio/fine): la genero, la carico, la suono e ASPETTO che finisca."""
    dur, ogg = sintetizza(testo, "frase")
    carica(dev, ogg, "frase")
    suona(dev, "frase")
    time.sleep(dur + 0.7)


def parole(w):
    """Parole chiave con tempi (s) nell'audio w (float32 16k) — usato anche nei test."""
    rec = vosk.KaldiRecognizer(MODELLO, SR, GRAMMATICA)
    rec.SetWords(True)
    pcm = (np.clip(w, -1, 1) * 32767).astype("<i2").tobytes()
    out = []
    for i in range(0, len(pcm), 8000):
        if rec.AcceptWaveform(pcm[i:i + 8000]):
            out += json.loads(rec.Result()).get("result", [])
    out += json.loads(rec.FinalResult()).get("result", [])
    return [(x["word"], x["start"], x["end"]) for x in out if x["word"] != "[unk]" and x.get("conf", 1) > 0.8]


def buone(res):
    return [(x["word"], x["start"], x["end"]) for x in json.loads(res).get("result", [])
            if x["word"] != "[unk]" and x.get("conf", 1) > 0.8]


def main():
    dev = device()
    T(dev, 'pkill -f "^bash .*home/rec.sh"; termux-microphone-record -q')  # sospendo il loop notturno
    adb("shell", f"mkdir -p {PH}", dev=dev)
    os.makedirs(CAL, exist_ok=True)
    durate = {}
    for k, frase in RISPOSTE.items():  # risposte pronte sul telefono: partono subito
        durate[k], ogg = sintetizza(frase, "r_" + k)
        carica(dev, ogg, "r_" + k)
    tg("🗣️ <b>Taratura a voce</b>: suono → \"Vai\" · stop → \"Preso\" · cancella → \"Cancellato\" · fine")
    parla(dev, "Dimmi il nome del suono e fallo. Stop quando hai finito. Cancella per buttare l'ultimo. "
               "Fine per chiudere. Ti ascolto.")
    nome = f"sessione_{datetime.now():%H%M%S}.ogg"
    registra(dev, f"-e opus -r 16000 -c 1 -l 0 -f {PH}/{nome}")
    loc = os.path.join(TMP, nome)
    rec = vosk.KaldiRecognizer(MODELLO, SR, GRAMMATICA)
    rec.SetWords(True)
    fatti, t0 = 0, time.time()
    aperto, ultimo, pezzi, muti, finito = None, None, [], [], False

    def rispondi(k):
        pos = fatti / SR + 0.3  # il suono parte ~adesso nella registrazione
        suona(dev, "r_" + k)
        muti.append((pos - 0.2, pos + durate[k] + 0.8))

    def gestisci(p, a, b):
        nonlocal aperto, ultimo, finito
        if p in SUONI or p in INIZIA:
            lab = SUONI.get(p, ultimo)
            if aperto:
                pezzi.append((aperto[0], aperto[1], a - 0.3))
            if lab is None:
                aperto = None; rispondi("boh"); return
            aperto, ultimo = (lab, b + 0.4), lab
            rispondi("vai")
        elif p in STOP:
            if aperto:
                pezzi.append((aperto[0], aperto[1], a - 0.3)); aperto = None
            rispondi("preso")
        elif p in CANC:
            if aperto:
                aperto = None
            elif pezzi:
                pezzi.pop()
            rispondi("cancellato")
        elif p in FINE:
            if aperto:
                pezzi.append((aperto[0], aperto[1], a - 0.3)); aperto = None
            finito = True

    while not finito and time.time() - t0 < MAX_MIN * 60:
        time.sleep(3)
        adb("pull", f"{PH}/{nome}", loc, dev=dev)
        w = load(loc) if os.path.exists(loc) else np.zeros(0, np.float32)
        if len(w) <= fatti:
            continue
        pcm = (np.clip(w[fatti:], -1, 1) * 32767).astype("<i2").tobytes()
        fatti = len(w)
        if rec.AcceptWaveform(pcm):
            nuove = buone(rec.Result())
        else:  # parola non ancora "chiusa": guardo il parziale solo per sapere se c'e' gia' qualcosa
            continue
        # ignoro cio' che sento mentre parla il telefono (se no "Preso" diventa "silenzio"/"basta": effetto a catena)
        nuove = [(p, a, b) for p, a, b in nuove if not any(ma <= a <= mb for ma, mb in muti)]
        for p, a, b in nuove:
            gestisci(p, a, b)
        if nuove:
            tg("👂 " + " · ".join(f"{p} {int(a) // 60}:{int(a) % 60:02d}" for p, a, _ in nuove))
    T(dev, "termux-microphone-record -q")
    time.sleep(1)
    adb("pull", f"{PH}/{nome}", loc, dev=dev)
    adb("shell", f"rm -f {PH}/{nome}", dev=dev)
    tutto = load(loc) if os.path.exists(loc) else np.zeros(0, np.float32)
    if aperto:
        pezzi.append((aperto[0], aperto[1], len(tutto) / SR))
    np.save(loc + ".muti.npy", np.array(muti))  # per poter ri-tagliare dopo
    pezzi = pezzi_whisper(loc, muti) or pezzi  # Whisper (frasi intere) se trova qualcosa, se no quelli di Vosk
    chiudi(dev, salva_pezzi(tutto, pezzi, muti))


def pezzi_whisper(path, muti):
    """Taglio preciso a fine sessione: Whisper capisce frasi intere ("russare con testa inclinata, dal naso") con il
    tempo di ogni parola. Frase con un suono = inizio pezzo (+ descrizione); stop/basta/ferma o frase nuova = fine."""
    from faster_whisper import WhisperModel
    m = WhisperModel("small", device="cpu", compute_type="int8")
    seg, _ = m.transcribe(path, language="it", word_timestamps=True, vad_filter=True)
    parole_w = [(x.word.strip(" .,!?").lower(), x.start, x.end) for s in seg for x in (s.words or [])]
    # via la voce del telefono: per tempo (muti) e per testo (le sue risposte)
    parole_w = [p for p in parole_w if p[0] and p[0] not in {"vai", "preso", "cancellato"}
                and not any(ma <= p[1] <= mb for ma, mb in muti)]
    RADICI = [("russ", "russa"), ("respir", "respiro"), ("toss", "tosse"), ("muov", "movimento"),
              ("moviment", "movimento"), ("gir", "movimento"), ("parl", "voce"), ("sbuff", "sbuffo"),
              ("silenz", "ambiente"), ("ambient", "ambiente")]
    out, aperto, desc = [], None, []
    for i, (w, a, b) in enumerate(parole_w):
        lab = next((l for r, l in RADICI if w.startswith(r)), None)
        if w in STOP | FINE | CANC or lab:
            if aperto and not (lab and desc and a - desc[-1][2] < 1.5):  # frase nuova (non continuazione)
                out.append((aperto[0], aperto[1], a - 0.3, " ".join(d[0] for d in desc)))
                aperto = None
            if w in CANC and out:
                out.pop()
            if lab:
                desc = [(w, a, b)]
                aperto = (lab, b + 0.4)
        elif aperto and a - (desc[-1][2] if desc else 0) < 1.5:  # parole che continuano la frase = descrizione
            desc.append((w, a, b)); aperto = (aperto[0], b + 0.4)
    if aperto:
        out.append((aperto[0], aperto[1], parole_w[-1][2] + 60 if parole_w else aperto[1], " ".join(d[0] for d in desc)))
    return out


def salva_pezzi(tutto, pezzi, muti):
    """Scrive i pezzi (tolti i momenti in cui parlava il telefono, tratti >= 1s) + descrizione in descrizioni.csv."""
    salvati, righe, ora = {}, [], datetime.now().strftime("%Y%m%d_%H%M")
    for lab, a, b, *desc in pezzi:
        b = min(b, len(tutto) / SR)
        tratti = [(a, b)]
        for ma, mb in muti:
            tratti = [t for x, y in tratti for t in ((x, min(y, ma)), (max(x, mb), y)) if t[1] - t[0] > 0]
        for x, y in tratti:
            if y - x >= 1.0:
                n = salvati.get(lab, 0) + 1; salvati[lab] = n
                nome = f"{lab}__voce__{ora}_{n}.wav"
                sf.write(os.path.join(CAL, nome), tutto[int(x * SR):int(y * SR)], SR)
                righe.append(f"{nome},{lab},{y - x:.1f},{(desc[0] if desc else '').replace(',', ' ')}")
    with open(os.path.join(CAL, "descrizioni.csv"), "a", encoding="utf-8") as f:
        f.write("".join(r + "\n" for r in righe))
    print("pezzi:", "; ".join(righe))
    return salvati, righe


def chiudi(dev, esito):
    salvati, righe = esito
    riass = ", ".join(f"{k} {v}" for k, v in salvati.items()) or "nessun pezzo"
    tg(f"✂️ {riass}\n" + "\n".join(f"• {r.split(',')[1]} {r.split(',')[2]}s {r.split(',')[3]}" for r in righe[:12]))
    parla(dev, "Finito. Ho salvato: " + (", ".join(f"{v} {k}" for k, v in salvati.items()) or "niente") + ".")
    riavvia_loop(dev)  # loop notturno di nuovo attivo (funziona anche a schermo bloccato)
    classi = {f.split("__")[0] for f in os.listdir(CAL) if f.endswith((".m4a", ".wav"))}
    if len(classi) < 2:
        tg(f"🧠 per allenare servono almeno 2 suoni diversi (ora: {', '.join(sorted(classi)) or 'nessuno'})")
        return
    import contextlib, io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        import cal_train
    t = buf.getvalue(); print(t)
    rus = [l.split("russamento:")[1].split(",")[0].strip() for l in t.splitlines() if "russamento:" in l]
    acc = next((l.split()[1] for l in t.splitlines() if l.strip().startswith("accuracy")), "?")
    if cal_train.MIGLIORA:
        adb("push", cal_train.OUT, "/sdcard/Recordings/tmp_modello.npz", dev=dev)
        adb("shell", "cat /sdcard/Recordings/tmp_modello.npz | run-as com.termux sh -c "
                     "'cat > files/home/modello_personale.npz' && rm /sdcard/Recordings/tmp_modello.npz", dev=dev)
    tg(f"🧠 accuratezza {acc} · russa YAMNet {rus[0] if rus else '?'} vs tuo {rus[1] if len(rus) > 1 else '?'} · "
       + ("installato ✅" if cal_train.MIGLIORA else "resta YAMNet"))


if __name__ == "__main__":
    if sys.argv[1:2] == ["ritaglia"]:  # rifai i pezzi da una registrazione salvata: ritaglia FILE.ogg
        p = sys.argv[2]
        muti = [tuple(x) for x in np.load(p + ".muti.npy")] if os.path.exists(p + ".muti.npy") else []
        salvati, righe = salva_pezzi(load(p), pezzi_whisper(p, muti), muti)
        print("\n".join(righe))
    else:
        main()
