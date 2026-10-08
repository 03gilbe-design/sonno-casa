"""Test di UN microfono, guidato a voce dal telefono (TTS): ambiente, russa, respiro.
   python mic_test.py NOME     -> pezzi in C:\\sonno_audio\\cal\\<suono>__NOME__<ora>.m4a, poi classifica
"""
import os, sys, time
from datetime import datetime
sys.path.insert(0, r"C:\sonno_tex")
from sonno_audio import adb, device, tg
from cal_sessione import T, ingressi
import mic_confronto

PH, CAL = "/sdcard/Recordings/sonno_cal", r"C:\sonno_audio\cal"
PASSI = [("ambiente", "Silenzio. Resta fermo e zitto", 15),
         ("russa", "Russa adesso, come di notte", 20),
         ("respiro", "Respira normale, come se dormissi", 15)]


def parla(dev, testo):
    tg(f"🎙️ {testo}")  # la voce (termux-tts-speak) si blocca se lanciata da run-as: uso Telegram, 1 riga


def main(nome):
    dev = device()
    print("microfoni visti da Android:", ", ".join(ingressi(dev)))
    T(dev, 'pkill -f "^bash .*home/rec.sh"; termux-microphone-record -q')  # sospendo il loop notturno
    adb("shell", f"mkdir -p {PH}", dev=dev)
    os.makedirs(CAL, exist_ok=True)
    parla(dev, f"Test microfono {nome}. Si parte tra tre secondi")
    time.sleep(3)
    for lab, frase, sec in PASSI:
        parla(dev, frase)
        f = f"{lab}__{nome}__{datetime.now():%Y%m%d_%H%M%S}.m4a"
        T(dev, f"termux-microphone-record -e aac -b 64 -r 16000 -c 1 -l {sec} -f {PH}/{f}")
        time.sleep(sec + 1)
        T(dev, "termux-microphone-record -q")
        parla(dev, "Stop")
        time.sleep(1)
        adb("pull", f"{PH}/{f}", os.path.join(CAL, f), dev=dev)
    parla(dev, "Finito. Puoi cambiare cuffia")
    print(mic_confronto.classifica().replace("<b>", "").replace("</b>", ""))


if __name__ == "__main__":
    main(sys.argv[1])
