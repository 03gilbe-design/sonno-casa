# notte_check.py        - un controllo: A21s (blocco nuovo? microfono silenziato?) + PC (flac che cresce) -> riga in notte_check.csv
# notte_check.py recap  - riepilogo della notte (dalle 21:00 di ieri) -> UN messaggio su @IlTuoBot + file
import senza_finestre  # noqa: F401  (niente finestre dei processi figli: va importato per primo)
import csv, glob, os, subprocess, sys
import a21
from datetime import datetime, timedelta

ADB = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Google.PlatformTools_Microsoft.Winget.Source_8wekyb3d8bbwe\platform-tools\adb.exe")
LOG = r"C:\sonno_audio\notte_check.csv"


def run(cmd, t=40):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=t).stdout
    except Exception:
        return ""


def controllo():
    ora = datetime.now()
    blocco = run(["ssh", "-p", "8022", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", a21.ip(),
                  "ls -t ~/rec/2*.m4a | head -1"]).strip().rsplit("/", 1)[-1]
    eta = ""
    if blocco[:15].replace("_", "").isdigit():
        eta = int((ora - datetime.strptime(blocco[:15], "%Y%m%d_%H%M%S")).total_seconds() // 60)
    run([ADB, "connect", f"{a21.ip()}:5555"], 15)
    au = run([ADB, "-s", f"{a21.ip()}:5555", "shell", "dumpsys audio | grep 'source client=MIC' | head -1"])
    mic = "silenziato" if "silenced:true" in au else "ok" if "silenced:false" in au else "nessuna_registrazione"
    flac = sorted(glob.glob(r"C:\sonno_audio\tre_dispositivi\*\pc_*.flac"), key=os.path.getmtime)
    pc = int((ora.timestamp() - os.path.getmtime(flac[-1])) // 60) if flac else ""
    nuovo = not os.path.exists(LOG)
    with open(LOG, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuovo:
            w.writerow(["ora", "a21s_blocco", "a21s_min_fa", "a21s_mic", "pc_min_da_ultimo_scritto"])
        w.writerow([ora.strftime("%Y-%m-%d %H:%M"), blocco or "IRRAGGIUNGIBILE", eta, mic, pc])


def recap():
    da = (datetime.now() - timedelta(days=1)).replace(hour=21, minute=0)
    righe = [r for r in csv.DictReader(open(LOG, encoding="utf-8")) if datetime.strptime(r["ora"], "%Y-%m-%d %H:%M") >= da]
    # blocco da 30': sano se nato da <40'; mic sano se "ok"; PC sano se ha scritto negli ultimi 10' (registra solo se sei fermo)
    a_ok = [r for r in righe if r["a21s_mic"] == "ok" and r["a21s_min_fa"] and int(r["a21s_min_fa"]) < 40]
    pc_ok = [r for r in righe if r["pc_min_da_ultimo_scritto"] and int(r["pc_min_da_ultimo_scritto"]) < 10]
    guai = [f"{r['ora'][11:]} A21s: {r['a21s_mic']}, blocco {r['a21s_min_fa'] or '?'}' fa" for r in righe if r not in a_ok]
    t = (f"🌅 <b>Controllo notte</b> ({len(righe)} controlli ogni 30')\n"
         f"A21s registra bene: <b>{len(a_ok)}/{len(righe)}</b>\nPC scriveva audio: {len(pc_ok)}/{len(righe)} (si ferma se usi il PC)")
    if guai:
        t += "\n⚠️ " + "\n⚠️ ".join(guai[:6])
    open(r"C:\sonno_audio\notte_check_recap.txt", "w", encoding="utf-8").write(t)
    subprocess.run([sys.executable, r"C:\sonno_tex\tg_IlTuoBot.py", t])


if __name__ == "__main__":
    recap() if sys.argv[1:] == ["recap"] else controllo()
