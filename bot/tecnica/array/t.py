"""
   python t.py prova [nome] -> TUTTO in ~35 s: rumore, sweep annunciati, bip insieme, mappa + distanze + chi non ha suonato
   python t.py stato     -> A21s/A56: registra? volume, muto, pausa
   python t.py bip        -> prova distanze 10 bip (ripetuti.py)
   python t.py analizza   -> rifa' solo l'analisi dell'ultima prova
   python t.py canale     -> mappa canale X->Y: 7 toni lunghi 150 Hz-10 kHz da A56, A21s, PC (perdita, deformazione, rumore)
   python t.py mappa     -> salva tutte le impostazioni A21s in app_sonno\MAPPA_A21s\<data>
   python t.py ripristina -> A21s: toglie pausa, riavvia loop, volume 12, suoni come prima
"""
import subprocess, sys
import ripetuti as r
from ripetuti import b, SSH


def stato():
    d = b.device()
    print("A21s", d, b.T(d, "termux-microphone-record -i | grep isRec; termux-volume | tr -d ' \\n' | grep -o 'music\",\"volume\":[0-9]*'; "
                     "ls ~/sonno_bot/PAUSA 2>/dev/null").strip().replace("\n", " | "),
          "| all_sound_off", b.adb("shell", "settings get system all_sound_off", dev=d).stdout.strip())
    print("A56 ", subprocess.run(SSH + ["termux-microphone-record -i | grep isRec; pgrep -f '^python .*sonno_webhook' >/dev/null && echo webhook_ok"],
                                 capture_output=True, text=True, timeout=20).stdout.strip().replace("\n", " | "))


def ripristina():
    d = b.device(); b.T(d, "termux-volume music 12"); r.a21s_registra_ok(d); stato()


def mappa():
    """
    Poi: confronta due mappe con `fc` per vedere cosa cambia toccando un'impostazione."""
    import os, time
    d = b.device(); out = os.path.join(r"C:\sonno_bot\tecnica\app_sonno\MAPPA_A21s", time.strftime("%Y%m%d_%H%M"))
    os.makedirs(out, exist_ok=True)
    for nome, cmd in (("system", "settings list system"), ("secure", "settings list secure"),
                      ("global", "settings list global"), ("audio", "dumpsys audio"),
                      ("audio_policy", "dumpsys media.audio_policy"), ("pacchetti", "pm list packages")):
        with open(os.path.join(out, nome + ".txt"), "w", encoding="utf-8") as f:
            f.write(b.adb("shell", cmd, dev=d).stdout)
    print("mappa in", out)


def uscite():
    """Quale modo di suonare funziona sull'A21s? Il PC dice il numero a voce, poi l'A21s suona in quel modo.
    """
    import time
    d = b.device(); f = "/sdcard/Recordings/sonno_cal/m_A21s.wav"
    muto = b.adb("shell", "settings get system all_sound_off", dev=d).stdout.strip()
    b.adb("shell", "settings put system all_sound_off 0", dev=d)
    b.T(d, f"cp ~/m_A21s_1.0.wav {f}")
    modi = [("play-audio", lambda: b.T(d, "play-audio ~/m_A21s_1.0.wav")),
            ("termux-media-player", lambda: b.T(d, "termux-media-player play ~/m_A21s_1.0.wav")),
            ("voce termux", lambda: b.T(d, "termux-tts-speak -l it 'prova tre'")),
            ("app lettore di sistema", lambda: b.adb("shell", f"am start -a android.intent.action.VIEW -d file://{f} -t audio/wav", dev=d)),
            ("notifica con suono", lambda: b.T(d, "termux-notification --sound -t prova5 -c prova5"))]
    parla = lambda s: subprocess.run(["powershell", "-c", "Add-Type -AssemblyName System.Speech; "
                                      f"(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{s}')"])
    try:
        for i, (nome, fa) in enumerate(modi, 1):
            print(i, nome); parla(f"metodo {i}"); time.sleep(0.5); fa(); time.sleep(3)
    finally:
        if muto in ("0", "1"):
            b.adb("shell", f"settings put system all_sound_off {muto}", dev=d)
        b.T(d, "termux-notification-remove prova5")


def canale():
    import canale as c; c.registra(); c.analizza()


def parla(s):
    subprocess.run(["powershell", "-c", "Add-Type -AssemblyName System.Speech; "
                    f"(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{s}')"])


def con_avviso(f):
    """(nota rimossa)"""
    def g():
        import time
        parla("silenzio, test fra 5 secondi"); time.sleep(5)
        try:
            f()
        finally:
            parla("fine test")
    return g


def mostra():
    """
    voce -> ognuno 3 bip DA SOLO (PC, A56, A21s), poi tutti e tre INSIEME."""
    import os, time, winsound
    import numpy as np
    d = b.device(); vol_pc = b.volume_pc(1.0)
    vol56 = subprocess.run(SSH + ["termux-volume | tr -d ' \\n' | grep -o '\"music\",\"volume\":[0-9]*' | grep -o '[0-9]*$'"],
                           capture_output=True, text=True, timeout=30).stdout.strip() or "9"
    subprocess.run(SSH + ["termux-volume music 15"], timeout=30)
    f = {}
    for chi, x in r.BOCCHE.items():
        tre = np.tile(np.concatenate([x, np.zeros(int(0.3 * b.SR), np.float32)]), 3)
        f[chi] = os.path.join(b.OUT, f"mostra_{chi}.wav"); b.scrivi_wav(f[chi], tre, pausa_prima=0.1)
    subprocess.run(["scp", "-q", "-P", "8022", f["A56"], f"{b.A56}:mostra_A56.wav"], check=True)
    sys.path.insert(0, r"C:\sonno_tex"); from deploy import copia; copia(d, f["A21s"], "mostra_A21s.wav")
    suona = {"PC": lambda: winsound.PlaySound(f["PC"], winsound.SND_FILENAME | winsound.SND_ASYNC),
             "A56": lambda: subprocess.Popen(SSH + ["play-audio mostra_A56.wav"]),
             "A21s": lambda: b.T(d, "termux-media-player play ~/mostra_A21s.wav")}
    try:
        for chi, nome in (("PC", "computer"), ("A56", "telefono personale"), ("A21s", "A 21 esse")):
            parla(nome); suona[chi](); time.sleep(3.5)
        parla("tutti insieme")
        for chi in ("A21s", "A56", "PC"):
            suona[chi]()
        time.sleep(4)
    finally:
        b.volume_pc(vol_pc); subprocess.run(SSH + [f"termux-volume music {vol56}"], timeout=30)


def sweep():
    import sweep as s; s.canale.registra(s.segnale(), nome="sweep", pref="sweep"); s.analizza(sys.argv[2] if len(sys.argv) > 2 else "tavolo")


def prova():
    import prova as p; nome = sys.argv[2] if len(sys.argv) > 2 else "prova"; p.registra(); p.analizza(nome); p.RIPRISTINO.join()


COMANDI = {"prova": con_avviso(prova), "sweep": con_avviso(sweep), "mostra": mostra, "canale": con_avviso(canale), "uscite": uscite, "mappa": mappa, "stato": stato, "bip": lambda: (r.registra(), r.analizza()), "analizza": r.analizza,
           "sorgenti": r.prova_sorgenti, "ripristina": ripristina}

if __name__ == "__main__":
    COMANDI.get(sys.argv[1] if sys.argv[1:] else "", lambda: print(__doc__))()
