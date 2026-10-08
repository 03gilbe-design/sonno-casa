"""Il SUO telefono (Samsung A56) via adb wireless: comandi pronti.
   python a56.py collega            -> adb su 192.0.2.54:5555 (o via mDNS dopo un riavvio, poi porta fissa)
   python a56.py avvia | ferma      -> Sleep as Android: inizia / ferma il tracciamento
   python a56.py apri               -> apre Sleep as Android (per tocca.py)
   python a56.py stato              -> schermo, carica, eventi webhook recenti
   python a56.py vedi               -> testi visibili sullo schermo
   python a56.py tocca "re1" "re2"  -> tocca in ordine le voci (regex)
   python a56.py scarica            -> eventi schermo + Sleep as Android sul PC (lo fa anche il sync ogni 30')
Modulo: a56.py (ingresso) + schermo_a56.py (adb, eventi) + tocca.py (schermo) + sonno_webhook.py e
sonno_app.sh (girano SUL telefono: ricevitore eventi, avvio notturno). I tocchi funzionano SOLO a telefono
sbloccato: il PIN non lo usiamo di proposito.
"""
import sys
import schermo_a56, tocca
from schermo_a56 import adb, collega

SAA = "com.urbandroid.sleep"


def intent(azione, dev):
    with tocca.azione(azione):
        return adb("shell", f"am broadcast -p {SAA} -a {SAA}.alarmclock.{azione}", dev=dev).stdout.strip()


if __name__ == "__main__":
    dev = collega()
    if not dev:
        sys.exit("A56 non raggiungibile: Debug wireless acceso? stesso Wi-Fi?")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stato"
    if cmd == "avvia":
        print(intent("START_SLEEP_TRACK", dev))
    elif cmd == "ferma":
        print(intent("STOP_SLEEP_TRACK", dev))
    elif cmd == "apri":
        with tocca.azione("apri"):
            adb("shell", f"monkey -p {SAA} -c android.intent.category.LAUNCHER 1", dev=dev)
    elif cmd == "vedi":
        print("\n".join(t for t, _, _ in tocca.schermo()))
    elif cmd == "tocca":
        for r in sys.argv[2:]:
            print("toccato:", tocca.tocca(r))
    elif cmd == "scarica":
        schermo_a56.main()
    elif cmd == "stato":
        print(adb("shell", "dumpsys power | grep -m1 mWakefulness; dumpsys battery | grep -m2 -E 'AC powered|level'; "
                  "tail -3 /sdcard/Documents/sonno/eventi.csv", dev=dev).stdout)
    print("collegato:", dev)
