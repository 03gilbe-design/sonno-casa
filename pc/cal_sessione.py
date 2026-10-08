"""Sessione di taratura guidata via Telegram: l'utente rifa' i singoli suoni, il telefono li registra etichettati.
   python cal_sessione.py        -> file in C:\\sonno_audio\\cal\\<etichetta>__<variante>__<data>.m4a
"""
import os, subprocess, sys, time
from datetime import datetime
sys.path.insert(0, r"C:\sonno_tex")
from sonno_audio import adb, device, tg, TG

TERMUX = ("run-as com.termux /data/data/com.termux/files/usr/bin/bash -c 'export PATH=/data/data/com.termux/files/usr/bin "
          "HOME=/data/data/com.termux/files/home PREFIX=/data/data/com.termux/files/usr "
          "LD_PRELOAD=/data/data/com.termux/files/usr/lib/libtermux-exec.so; {}'")
CAL_PHONE, CAL_PC = "/sdcard/Recordings/sonno_cal", r"C:\sonno_audio\cal"
# (etichetta, variante, istruzione, secondi). Stessa etichetta = stessa classe per il modello.
PASSI = [
    ("ambiente", "notte", "Lascia la stanza COME DI NOTTE (finestra, ventilatore, rumori di fuori). Tu immobile e zitto, "
     "respira pianissimo. Da qui in poi tieni sempre questo sottofondo", 60),
    ("respiro", "calmo", "Respira come se dormissi, bocca chiusa, normale", 50),
    ("respiro", "bocca", "Respira come se dormissi ma a bocca aperta, senza russare", 40),
    ("russa", "naso", "Russa DAL NASO, come fai di notte", 45),
    ("russa", "bocca", "Russa DALLA BOCCA", 45),
    ("russa", "forte", "Russa FORTE", 35),
    ("russa", "leggero", "Russa LEGGERO, appena appena", 45),
    ("russa", "misto", "Russa in TUTTI i modi che ti capitano di notte, cambiando tipo ogni tanto", 60),
    ("russa", "fianco", "Girati sul fianco e russa come ti viene in quella posizione", 45),
    ("movimento", "letto", "Girati nel letto, muovi coperte e cuscino, come quando ti agiti", 45),
    ("tosse", "varia", "Tossisci ogni 3-4 secondi, tossi diverse", 35),
    ("voce", "sonno", "Parla/mormora come nel sonno, anche parole a caso", 35),
    ("sbuffo", "respiro_ripreso", "Trattieni il respiro 8 secondi e poi riprendi di colpo con uno sbuffo/rantolo. Ripeti", 50),
]


# Test microfono: stesse 3 prove per ogni cuffietta, SEMPRE stessa distanza/posizione -> confronto giusto
PASSI_MIC = [
    ("ambiente", "notte", "Zitto e immobile, stanza come di notte", 20),
    ("russa", "test", "Russa come di notte, SEMPRE dalla stessa posizione (testa sul cuscino)", 25),
    ("respiro", "test", "Respira come se dormissi, normale, stessa posizione", 20),
]


def T(dev, cmd):
    return adb("shell", TERMUX.format(cmd), dev=dev).stdout


def primo_piano(dev):
    """Termux in primo piano: su Android 12 un microfono avviato da un processo in background viene SILENZIATO
    """
    for c in ("input keyevent KEYCODE_WAKEUP", "wm dismiss-keyguard", "am start -n com.termux/.app.TermuxActivity"):
        adb("shell", c, dev=dev)
    time.sleep(2)


def silenziato(dev):
    """True/False dal dumpsys audio (silenced:true = file pieno di zeri); None = nessun client MIC attivo."""
    out = adb("shell", "dumpsys audio | grep 'source client=MIC'", dev=dev).stdout
    return None if not out.strip() else "silenced:true" in out


def registra(dev, args):
    """Avvia termux-microphone-record <args> in primo piano e verifica silenced:false (un nuovo tentativo, poi errore)."""
    for _ in range(2):
        primo_piano(dev)
        T(dev, f"termux-microphone-record {args}")
        time.sleep(2)
        if silenziato(dev) is False:
            return
        T(dev, "termux-microphone-record -q")
    raise RuntimeError("microfono SILENZIATO anche in primo piano (silenced:true o nessun client MIC): registrazione inutile")


def _loop_vivo(dev):
    return "rec.sh" in T(dev, "pgrep -af rec.sh")


def riavvia_loop(dev):
    """Rilancia il loop notturno digitandolo nella sessione Termux in primo piano, verifica silenced:false, spegne lo schermo."""
    for tentativo in range(2):
        T(dev, 'pkill -f "^bash .*home/rec.sh"; termux-microphone-record -q')
        time.sleep(2)
        primo_piano(dev)
        adb("shell", "input text 'bash%s~/rec.sh'", dev=dev)
        adb("shell", "input keyevent KEYCODE_ENTER", dev=dev)
        time.sleep(8)  # rec.sh: battery-status + avvio registrazione
        ok = silenziato(dev) is False and _loop_vivo(dev)
        if ok:
            break
    adb("shell", "input keyevent KEYCODE_SLEEP", dev=dev)
    if not ok:
        raise RuntimeError("loop notturno NON ripartito o microfono silenziato: controllare l'A21s")


def ingressi(dev):
    """Microfoni che Android vede (per sapere se usa davvero la cuffietta)."""
    # solo la sezione "Available input devices" (finisce alla prossima riga "- ..." non indentata)
    out = adb("shell", "dumpsys media.audio_policy | sed -n '/Available input devices/,/^- [^A]/p' | grep 'type:'",
              dev=dev).stdout
    return sorted(set(x.split("AUDIO_DEVICE_IN_")[1].split()[0] for x in out.splitlines() if "AUDIO_DEVICE_IN_" in x))


def main(passi=PASSI, nome=None):
    global CAL_PHONE, CAL_PC
    if nome:  # test microfono: cartelle separate per cuffietta
        CAL_PHONE, CAL_PC = f"/sdcard/Recordings/sonno_mic/{nome}", rf"C:\sonno_audio\mic\{nome}"
    dev = device()
    if not dev:
        print("telefono non raggiungibile"); return
    ing = ingressi(dev)
    titolo = (f"🎧 TEST MICROFONO <{nome}>. Android vede: {', '.join(ing)}. " if nome else "🎙️ TARATURA: ")
    out = subprocess.run([sys.executable, os.path.join(TG, "telegram_chiedi_scelta_con_pulsanti.py"),
                          titolo + "Mettiti a letto come di notte, telefono al suo posto. "
                          f"{len(passi)} prove, ~{sum(p[3] for p in passi) // 60 + 1} minuti. "
                          "Ogni istruzione dura il tempo indicato: parti appena arriva. Pronto?",
                          "Pronto", "Annulla", "--aspetta", "1800"], capture_output=True, text=True).stdout
    if "SCELTA: Pronto" not in out:
        print("non pronto:", out[-200:]); return
    if nome:
        os.makedirs(CAL_PC, exist_ok=True)
        open(os.path.join(CAL_PC, "ingressi.txt"), "w").write(",".join(ingressi(dev)))
    # sospendi il loop notturno (lo rilancio alla fine)
    # "^bash " = solo il loop ("bash .../rec.sh"), non questa shell ("/data/.../bash -c ...") che contiene la stessa parola
    T(dev, 'pkill -f "^bash .*home/rec.sh"; termux-microphone-record -q')
    adb("shell", f"mkdir -p {CAL_PHONE}", dev=dev)
    oggi = datetime.now().strftime("%Y%m%d_%H%M")
    try:
        for i, (lab, var, istr, sec) in enumerate(passi, 1):
            tg(f"<b>{i}/{len(passi)} — {lab.upper()}</b> ({sec}s)\n{istr}\n<i>Parti ora.</i>")
            time.sleep(3)  # tempo di leggere
            registra(dev, f"-e aac -b 64 -r 16000 -c 1 -l {sec} -f {CAL_PHONE}/{lab}__{var}__{oggi}.m4a")
            time.sleep(sec + 2)
            T(dev, "termux-microphone-record -q")
            tg("⏸️ stop — prossimo tra poco" if i < len(passi) else "✅ Finito! Grazie.")
            time.sleep(4)
    finally:
        riavvia_loop(dev)
    os.makedirs(CAL_PC, exist_ok=True)
    for name in adb("shell", f"ls {CAL_PHONE}", dev=dev).stdout.split():
        adb("pull", f"{CAL_PHONE}/{name}", os.path.join(CAL_PC, name), dev=dev)
    print("\n".join(sorted(os.listdir(CAL_PC))))
    print("loop:", T(dev, "pgrep -af rec.sh"))
    if nome:
        import mic_confronto
        tg(mic_confronto.classifica())
    else:
        import contextlib, io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            import cal_train  # allena subito (stampa accuratezza su dati mai visti)
        testo = buf.getvalue()
        print(testo)
        tg("🧠 <b>Modello personale</b> (verifica su pezzi mai visti):\n<pre>"
           + testo.split("=== MODELLO PERSONALE")[1][:3000].replace("<", "&lt;") + "</pre>")
        if not cal_train.MIGLIORA:
            return
        # installa sul telefono (il loop lo usa dal prossimo blocco)
        adb("push", cal_train.OUT, "/sdcard/Recordings/tmp_modello.npz", dev=dev)
        adb("shell", "cat /sdcard/Recordings/tmp_modello.npz | run-as com.termux sh -c "
                     "'cat > files/home/modello_personale.npz' && rm /sdcard/Recordings/tmp_modello.npz", dev=dev)


if __name__ == "__main__":
    # python cal_sessione.py            -> taratura completa
    # python cal_sessione.py mic NOME   -> test microfono per la cuffietta NOME
    if sys.argv[1:2] == ["mic"]:
        main(PASSI_MIC, sys.argv[2])
    else:
        main()
