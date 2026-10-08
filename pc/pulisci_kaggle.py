"""Libera il disco C dalle COPIE audio scaricate da Drive per Kaggle (C:\\sonno_audio\\kaggle\\<notte>\\ds e i file
con la stessa dimensione (regola: in locale si cancella solo cio' che e' verificato su Drive). Salta la notte di oggi.
"""
import glob, json, os, re, subprocess, sys
from datetime import datetime

RCL = r"~\AppData\Local\Microsoft\WinGet\Packages\Rclone.Rclone_Microsoft.Winget.Source_8wekyb3d8bbwe\rclone-v1.75.1-windows-amd64\rclone.exe"
K = r"C:\sonno_audio\kaggle"


def remoto(nome):
    """a21s_20261003_045457.m4a -> ('interi/2026-10-03', '20261003_045457.m4a'); a56_notte_...m4a -> ('a56', 'notte_...m4a')."""
    m = re.search(r"21s_((\d{4})(\d{2})(\d{2})_\d{6}\.m4a)$", nome)  # anche "ds?21s_" (bug \a)
    if m:
        return f"interi/{m[2]}-{m[3]}-{m[4]}", m[1]
    m = re.search(r"a56_(.+\.m4a)$", nome)
    return ("a56", m[1]) if m else (None, None)


def su_drive(cartella, cache={}):
    """{nome: size} di gdrive:sonno/<cartella> (ricorsivo per a56)."""
    if cartella not in cache:
        r = subprocess.run([RCL, "lsjson", "-R", "--files-only", f"gdrive:sonno/{cartella}/"], capture_output=True, text=True, timeout=300)
        cache[cartella] = {x["Name"]: x["Size"] for x in json.loads(r.stdout or "[]")} if r.returncode == 0 else {}
    return cache[cartella]


def pulisci(prova=False):
    oggi, liberati = datetime.now().strftime("%Y%m%d"), 0
    for d in sorted(glob.glob(K + r"\2026*")):
        if os.path.basename(d) == oggi:
            continue
        for p in glob.glob(d + r"\ds\*.m4a") + glob.glob(d + r"\ds?21s_*.m4a"):
            cart, nome = remoto(os.path.basename(p))
            sz = os.path.getsize(p)
            if cart and su_drive(cart).get(nome) == sz:
                if not prova:
                    os.remove(p)
                liberati += sz
    return liberati


if __name__ == "__main__":
    assert remoto("a21s_20261003_045457.m4a") == ("interi/2026-10-03", "20261003_045457.m4a")
    assert remoto("dsX21s_20261003_045457.m4a")[1] == "20261003_045457.m4a" and remoto("a56_notte_20261003_020922.m4a") == ("a56", "notte_20261003_020922.m4a")
    mb = pulisci("--prova" in sys.argv) / 2**20
    print(f"{'liberabili' if '--prova' in sys.argv else 'liberati'}: {mb:.0f} MB")
