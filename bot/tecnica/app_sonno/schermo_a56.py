"""Segnali CERTI di veglia dal SUO telefono (A56, adb wireless): schermo acceso/spento/sbloccato -> CSV sul PC.
   python schermo_a56.py   -> aggiunge gli eventi nuovi a C:\\sonno_audio\\a56_schermo.csv (t, evento)
Chiamato anche da sonno_audio.py sync (ogni 30'). Se il telefono non risponde non fa niente (riprova al giro dopo).
adb: porta fissa 5555 (adb tcpip) finche' il telefono non si riavvia; dopo, si ritrova via mDNS se il Debug
wireless e' acceso (la chiave del PC e' gia' associata: niente codice).
"""
import csv, os, re, subprocess

IP, OUT = "192.0.2.54", r"C:\sonno_audio\a56_schermo.csv"
EVENTI = {"SCREEN_INTERACTIVE": "acceso", "SCREEN_NON_INTERACTIVE": "spento", "KEYGUARD_HIDDEN": "sbloccato"}


def adb(*a, dev=None, timeout=30):
    return subprocess.run(["adb", *(["-s", dev] if dev else []), *a], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout,
                          creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def collega():
    if "connected" in adb("connect", f"{IP}:5555").stdout:
        return f"{IP}:5555"
    m = re.search(rf"_adb-tls-connect\._tcp\s+({re.escape(IP)}:\d+)", adb("mdns", "services").stdout)
    if m and "connected" in adb("connect", m.group(1)).stdout:
        adb("tcpip", "5555", dev=m.group(1))  # di nuovo porta fissa
        return m.group(1)
    return None


def eventi(testo):
    """Righe di 'dumpsys usagestats' -> [(t, evento)] solo schermo/sblocco."""
    return [(t, EVENTI[e]) for t, e in re.findall(r'time="([^"]+)" type=(\w+) package=android', testo) if e in EVENTI]


def main():
    dev = collega()
    if not dev:
        return print("A56 non raggiungibile")
    nuovi = eventi(adb("shell", "dumpsys usagestats", dev=dev, timeout=120).stdout)
    visti = set()
    if os.path.exists(OUT):
        visti = {tuple(r) for r in csv.reader(open(OUT, encoding="utf-8"))}
    righe = sorted(set(nuovi) - visti)
    with open(OUT, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(righe)
    print(f"A56: {len(righe)} eventi schermo nuovi")
    # eventi di Sleep as Android (webhooks -> sonno_webhook.py sul telefono): copia intera, e' piccolo
    adb("pull", "/sdcard/Documents/sonno/eventi.csv", r"C:\sonno_audio\a56_eventi_sleep.csv", dev=dev)
    pausa_se_dorme(dev)


def dorme_ora(righe, adesso=None):
    """Stessa regola del telefono (sonno_webhook.py): la PAUSA solo se il telefono ha gia' abbassato la musica
    dopo l'ultimo risveglio/inizio, e l'ultimo evento (ultime 3 h) e' sonno."""
    from datetime import datetime, timedelta
    adesso = adesso or datetime.now()
    abbassata = False
    for t, ev, *_ in reversed(righe):
        if ev == "claude_musica_abbassata":
            abbassata = True
        elif ev in ("awake", "sleep_tracking_started"):
            return False  # dopo l'abbassamento si e' svegliato (o abbassamento mai avvenuto): non tocco
        elif ev in ("deep_sleep", "light_sleep", "rem"):
            if adesso - datetime.fromisoformat(t) >= timedelta(hours=3):
                return False
            if abbassata:
                return True
    return False


def pausa_se_dorme(dev):
    """
    Sul telefono sonno_webhook.py abbassa gia' il volume; questo ferma davvero il lettore."""
    f = r"C:\sonno_audio\a56_eventi_sleep.csv"
    if not os.path.exists(f) or not dorme_ora(list(csv.reader(open(f, encoding="utf-8")))):
        return
    if "PLAYING" in adb("shell", "dumpsys media_session | grep -m3 'state=PlaybackState'", dev=dev).stdout:
        adb("shell", "input keyevent KEYCODE_MEDIA_PAUSE", dev=dev)
        print("A56: dorme e suonava -> pausa")


if __name__ == "__main__":
    assert eventi('time="2026-09-27 04:34:15" type=SCREEN_NON_INTERACTIVE package=android flags=0x0 '
                  'time="2026-09-27 04:34:17" type=KEYGUARD_SHOWN package=android') == [("2026-09-27 04:34:15", "spento")]
    main()
