"""Tocca le voci sullo schermo del SUO telefono (A56) cercandole per testo: uiautomator dump + input tap.
   python tocca.py "Impostazioni" "Servizi|Services"   -> tocca in ordine (regex, maiuscole indifferenti)
   python tocca.py --vedi                              -> elenca i testi visibili
"""
import contextlib, re, subprocess, sys, time
from datetime import datetime

DEV = "192.0.2.54:5555"
AZIONI = r"C:\sonno_audio56_azioni.csv"


@contextlib.contextmanager
def azione(nome):
    """Segna in a56_azioni.csv (inizio,fine,azione) i comandi del PC che possono accendere lo schermo: non e' uso suo."""
    t0 = datetime.now()
    try:
        yield
    finally:
        with open(AZIONI, "a", encoding="utf-8") as f:
            f.write(f"{t0:%Y-%m-%dT%H:%M:%S},{datetime.now():%Y-%m-%dT%H:%M:%S},{nome}" + chr(10))


def sh(cmd):
    return subprocess.run(["adb", "-s", DEV, "shell", cmd], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=60).stdout


def schermo():
    """[(testo, x, y)] delle voci visibili."""
    xml = sh("uiautomator dump /sdcard/ui.xml >/dev/null && cat /sdcard/ui.xml")
    out = []
    for n in re.finditer(r'<node [^>]*>', xml):
        a = dict(re.findall(r'(\w[\w-]*)="([^"]*)"', n.group(0)))
        t = a.get("text") or a.get("content-desc")
        b = re.findall(r"\d+", a.get("bounds", ""))
        if t and len(b) == 4:
            x1, y1, x2, y2 = map(int, b)
            out.append((t, (x1 + x2) // 2, (y1 + y2) // 2))
    return out


PERMESSE = ("com.android.settings", "com.urbandroid.sleep", "com.google.android.gms", "com.samsung.android")


def primo_piano():
    return sh("dumpsys window | grep -m1 mCurrentFocus")


def tocca(regex, scorri=6):
    with azione("tocca"):
        return _tocca(regex, scorri)


def _tocca(regex, scorri):
    fp = primo_piano()
    if not any(p in fp for p in PERMESSE):
        raise SystemExit(f"NON tocco: in primo piano c'e' {fp.strip()}")
    for _ in range(scorri):
        for t, x, y in schermo():
            if re.search(regex, t, re.I):
                sh(f"input tap {x} {y}"); time.sleep(1.5)
                return t
        sh("input swipe 540 1800 540 700 300"); time.sleep(1)  # non c'e': scorro giu'
    raise SystemExit(f"non trovato: {regex}")


if __name__ == "__main__":
    if sys.argv[1:] == ["--vedi"]:
        print("\n".join(t for t, _, _ in schermo()))
    else:
        for r in sys.argv[1:]:
            print("toccato:", tocca(r))
