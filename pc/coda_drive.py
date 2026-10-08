"""
Aspetta in Downloads lo zip/cartella *dormire*, copia gli audio sull'A21s (~/drive_in) e li mette in ~/rec come
2AAAAMMGG_HHMMSS.m4a: il loop normale (sonno_tel.py analizza + conferma.py, un lavoro alla volta col lucchetto) li
   python coda_drive.py          (gira finche' trova la cartella, poi finisce)
   python coda_drive.py prova    (self-check della data dal nome)
"""
import senza_finestre  # noqa: F401  (niente finestre dei processi figli: va importato per primo)
import glob, os, re, subprocess, sys, time, zipfile
import a21
from datetime import datetime

DL = os.path.expanduser(r"~\Downloads")
DEST = os.path.join(DL, "dormire_drive")
SSH = ["ssh", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-p", "8022", a21.ip()]
AUDIO = (".m4a", ".mp3", ".wav", ".ogg", ".opus", ".flac", ".aac", ".3gp", ".amr")


def data_da(nome, mtime):
    """Data dal nome (20260915_031200, 2026-09-15 03.12...) se c'e', se no la data del file. ponytail: 2 formati."""
    mesi = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"]
    m = re.search(r"(\d{1,2}) ([A-Za-z]{3})\w* (20\d\d) (\d\d)\.(\d\d)\.(\d\d)", nome)
    if m and m.group(2).lower() in mesi:
        g, me, a, h, mi, s = m.groups()
        return datetime(int(a), mesi.index(me.lower()) + 1, int(g), int(h), int(mi), int(s))
    m = re.search(r"(20\d\d)[-_]?(\d\d)[-_]?(\d\d)[ _T-]?(\d\d)[.:_-]?(\d\d)(?:[.:_-]?(\d\d))?", nome)
    if m:
        try:
            return datetime(*(int(x or 0) for x in m.groups()))
        except ValueError:
            pass
    return datetime.fromtimestamp(mtime)


def trova():
    zips = [z for z in glob.glob(os.path.join(DL, "*ormire*.zip"))]
    for z in zips:
        with zipfile.ZipFile(z) as f:
            f.extractall(DEST)
    cart = [c for c in glob.glob(os.path.join(DL, "*ormire*")) if os.path.isdir(c)]
    return [p for c in cart for p in glob.glob(os.path.join(c, "**", "*"), recursive=True) if p.lower().endswith(AUDIO)]


def main():
    while True:
        audio = trova()
        if audio:
            break
        time.sleep(120)
    subprocess.run(SSH + ["mkdir -p ~/drive_in"], timeout=60)
    fatti = 0
    for p in sorted(audio):
        while int((subprocess.run(SSH + ["df -k ~ | tail -1 | awk '{print $4}'"], capture_output=True, text=True,
                                  timeout=60).stdout.strip() or 0)) < 1_500_000:
            print("A21s sotto 1,5 GB liberi: aspetto", flush=True); time.sleep(1800)
        t = data_da(os.path.basename(p), os.path.getmtime(p))
        ext = os.path.splitext(p)[1].lower()
        nome = f"{t:%Y%m%d_%H%M%S}{ext}"
        subprocess.run(["scp", "-q", "-P", "8022", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", p, f"{a21.ip()}:drive_in/{nome}"], timeout=600)
        # sul telefono: converte (nice 19) in ~/rec con lo stesso nome dei blocchi -> il loop lo analizza come una notte
        cmd = (f"cd ~/drive_in && nice -n 19 ffmpeg -v error -y -i {nome} -ac 1 -ar 16000 -c:a aac -b:a 48k "
               f"~/rec/.{nome[:15]}.m4a && mv ~/rec/.{nome[:15]}.m4a ~/rec/{nome[:15]}.m4a && rm {nome}")
        r = subprocess.run(SSH + [cmd], capture_output=True, text=True, timeout=1800)
        fatti += r.returncode == 0
        print(nome, "ok" if r.returncode == 0 else "ERRORE " + r.stderr[-200:], flush=True)
    print(f"in coda sull'A21s: {fatti}/{len(audio)} audio")


if __name__ == "__main__":
    if sys.argv[1:] == ["prova"]:
        assert data_da("rec 20260915_031200.m4a", 0) == datetime(2026, 9, 15, 3, 12, 0)
        assert data_da("2026-09-15 03.12.m4a", 0) == datetime(2026, 9, 15, 3, 12)
        assert data_da("Sleep Noise 27 Giu 2026 14.30.16.m4a", 0) == datetime(2026, 6, 27, 14, 30, 16)
        assert data_da("russo.m4a", 0) == datetime.fromtimestamp(0)
        print("ok")
    else:
        main()
