"""Prepara l'audio CON CONTESTO per video_respiri.py e lo manda a Kaggle (le curve si calcolano LI', mai sul PC).
Uso: contesto_respiri.py prepara | kaggle | tutto        (dati in C:\\sonno_audio\\ctx_respiri; blocchi scaricati uno alla volta e cancellati)
Per ogni clip giudicata: se esiste un blocco intero A21s (Drive gdrive:sonno/interi) che la contiene, la si cerca nel blocco (correlazione
normalizzata, esatta se > 0,9) e si ritaglia da 3 s prima a 3 s dopo; altrimenti si usa la clip com'e'. meta_ctx.json: file, pre (s di contesto
prima della clip), dur (durata clip), blocco."""
import ctypes, json, os, re, shutil, subprocess, sys, time
from datetime import datetime, timedelta
import numpy as np
from scipy.signal import fftconvolve
if sys.platform == "win32":
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)  # BELOW_NORMAL
D, CTX = r"C:\sonno_audio\test_finestre", r"C:\sonno_audio\ctx_respiri"
RCL = r"~\AppData\Local\Microsoft\WinGet\Packages\Rclone.Rclone_Microsoft.Winget.Source_8wekyb3d8bbwe\rclone-v1.75.1-windows-amd64\rclone.exe"
KAG = r"~\AppData\Local\Programs\Python\Python312\Scripts\kaggle.exe"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
LOCALI = r"C:\sonno_audio\mappe\_src\interi"
CONTESTO, BLOCCO, MAXD = 3.0, 1800.0, 10.0  # s di contesto; durata blocco; clip lunghe (20 s) tagliate a 10 s
run = lambda c, **k: subprocess.run(c, capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV, **k)


def pcm(p, ss=None, t=None):
    a = ["ffmpeg", "-v", "error"] + (["-ss", str(ss), "-t", str(t)] if ss is not None else []) + ["-i", p, "-ac", "1", "-ar", "16000", "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(a, capture_output=True).stdout, np.float32)


def nc(b, c):
    """correlazione normalizzata di c dentro b."""
    num = fftconvolve(b, c[::-1], "valid")
    return num / (np.sqrt(np.convolve(b ** 2, np.ones(len(c)), "valid") * np.sum(c ** 2)) + 1e-9)


def blocchi_drive():
    ini = {}
    for g in (datetime(2026, 9, 28) + timedelta(days=i) for i in range(6)):
        for n in run([RCL, "lsf", f"gdrive:sonno/interi/{g:%Y-%m-%d}/"]).stdout.split():
            if re.match(r"\d{8}_\d{6}\.m4a$", n):
                ini[n] = (datetime.strptime(n[:15], "%Y%m%d_%H%M%S"), f"gdrive:sonno/interi/{g:%Y-%m-%d}/{n}")
    return ini


def prepara():
    os.makedirs(CTX, exist_ok=True)
    tmp = os.path.join(CTX, "_blocco")
    os.makedirs(tmp, exist_ok=True)
    clips = [c for c in json.load(open(os.path.join(D, "clip.json"))) if not c["noseq"]]
    BL = blocchi_drive()
    pf = os.path.join(CTX, "progresso.json")  # ripartenza: clip gia ritagliate
    pos = json.load(open(pf)) if os.path.exists(pf) else {}
    for n, (s, _) in sorted(BL.items(), key=lambda kv: kv[1][0]):
        cs = [c for c in clips if "respiro" in c["cats"] and c["clip"] not in pos and (t := datetime.fromisoformat(c["t"])) and s - timedelta(seconds=75) <= t <= s + timedelta(seconds=BLOCCO)]
        if not cs:
            continue
        loc = os.path.join(LOCALI, n)
        if not os.path.exists(loc):
            loc = os.path.join(tmp, n)
            run([RCL, "copyto", BL[n][1], loc])
        for c in cs:
            if c["clip"] in pos:
                continue
            cp = os.path.join(D, "clip", c["clip"])
            x = pcm(cp if os.path.exists(cp) else os.path.join(D, c["clip"]))[:int(MAXD * 16000)]
            o = (datetime.fromisoformat(c["t"]) - s).total_seconds()
            a0 = max(0.0, o - 15)
            b = pcm(loc, a0, 100 + len(x) / 16000)
            if len(b) <= len(x):
                continue
            r = nc(b, x)
            i = int(r.argmax())
            print(c["clip"], n, f"{a0 + i / 16000:.2f}", f"{r[i]:.3f}", flush=True)
            if r[i] > 0.9:  # trovata: ritaglia subito (il blocco e' gia qui)
                off, dur = a0 + i / 16000, min(c["dur"], MAXD)
                pre = min(CONTESTO, off)
                tot = pre + dur + min(CONTESTO, BLOCCO - off - dur)
                f = os.path.splitext(c["clip"])[0] + ".flac"
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(off - pre), "-t", str(tot), "-i", loc, "-ac", "1", "-ar", "48000", "-c:a", "flac", os.path.join(CTX, f)], check=True)
                pos[c["clip"]] = dict(clip=c["clip"], file=f, pre=pre, dur=dur, blocco=n)
                json.dump(pos, open(pf, "w"))
        if loc.startswith(tmp):
            os.remove(loc)
    meta = []
    for c in clips:
        if c["clip"] in pos:
            meta.append(pos[c["clip"]])
            continue
        cp = os.path.join(D, "clip", c["clip"])
        cp = cp if os.path.exists(cp) else os.path.join(D, c["clip"])
        f = os.path.splitext(c["clip"])[0] + ".flac"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-t", str(MAXD), "-i", cp, "-ac", "1", "-ar", "48000", "-c:a", "flac", os.path.join(CTX, f)], check=True)
        meta.append(dict(clip=c["clip"], file=f, pre=0.0, dur=min(c["dur"], MAXD), blocco=None))
    json.dump(meta, open(os.path.join(CTX, "meta_ctx.json"), "w"))
    shutil.rmtree(tmp, ignore_errors=True)
    print(len(meta), "clip,", sum(m["blocco"] is not None for m in meta), "con contesto")


def kaggle():
    json.dump({"title": "sonno respiri ctx", "id": "utente/sonno-respiri-ctx", "licenses": [{"name": "CC0-1.0"}], "isPrivate": True}, open(os.path.join(CTX, "dataset-metadata.json"), "w"))
    st = run([KAG, "datasets", "status", "utente/sonno-respiri-ctx"]).stdout
    print(run([KAG, "datasets", "version" if "ready" in st else "create", "-p", CTX, "-r", "zip", *(["-m", "ctx"] if "ready" in st else [])]).stdout[-200:])
    for _ in range(60):
        if "ready" in run([KAG, "datasets", "status", "utente/sonno-respiri-ctx"]).stdout:
            break
        time.sleep(10)
    out = os.path.join(r"C:\sonno_tex\kaggle_lab\out_esp", "curve-respiri")
    sys.argv = ["esp_run.py", r"curve_respiri.py", "utente/sonno-respiri-ctx,utente/sonno-test-finestre-tmp"]
    exec(compile(open(r"C:\sonno_tex\kaggle_lab\esp_run.py", encoding="utf-8").read(), "esp_run.py", "exec"), {"__file__": r"C:\sonno_tex\kaggle_lab\esp_run.py", "__name__": "__main__"})
    print(out)


if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else "tutto"
    if m in ("prepara", "tutto"):
        prepara()
    if m in ("kaggle", "tutto"):
        kaggle()
