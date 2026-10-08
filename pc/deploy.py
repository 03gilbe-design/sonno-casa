"""Copia file sull'A21s (home di Termux via run-as, che NON vede /sdcard) e riavvia bot o loop.
   python deploy.py bot                      -> ~/sonno_bot/bot.py + riavvio bot
   python deploy.py tel                      -> ~/sonno_tel.py (lo usa il loop al prossimo blocco)
   python deploy.py rec                      -> ~/rec.sh + riavvio loop
   python deploy.py albero                   -> bot + concept/ copy/ ux/ (stessa struttura del PC), backup dati, riavvio
   python deploy.py FILE_PC DEST_HOME [bot|loop]   -> qualsiasi file
"""
import senza_finestre  # noqa: F401  (niente finestre dei processi figli: va importato per primo)
import os, subprocess, sys, time
import a21
sys.path.insert(0, r"C:\sonno_tex")
from sonno_audio import adb, device
from cal_sessione import T as T_adb, riavvia_loop

SSH = ["ssh", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-p", "8022", a21.ip()]


def T(dev, cmd):
    if dev != "ssh":
        return T_adb(dev, cmd)
    return subprocess.run(SSH + [cmd], capture_output=True, text=True, timeout=120).stdout


def scegli():
    try:
        if subprocess.run(SSH + ["echo ok"], capture_output=True, text=True, timeout=20).stdout.strip() == "ok":
            return "ssh"
    except subprocess.TimeoutExpired:
        pass
    return device()

NOTI = {"bot": (r"C:\sonno_bot\bot.py", "sonno_bot/bot.py", "bot"),
        "tel": (r"C:\sonno_tex\sonno_tel.py", "sonno_tel.py", None),
        "rec": (r"C:\sonno_tex\rec.sh", "rec.sh", "loop")}


def copia(dev, src, dst):
    """src PC -> ~/dst sul telefono. Scrive su .new e poi mv: un bash in esecuzione tiene il vecchio file."""
    if dev == "ssh":
        subprocess.run(["scp", "-q", "-P", "8022", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", src, f"{a21.ip()}:{dst}.new"], timeout=120)
    else:
        adb("push", src, "/sdcard/Recordings/tmp_deploy", dev=dev)
        adb("shell", f"cat /sdcard/Recordings/tmp_deploy | run-as com.termux sh -c 'cat > files/home/{dst}.new'", dev=dev)
        adb("shell", "rm /sdcard/Recordings/tmp_deploy", dev=dev)
    T(dev, f"mv ~/{dst}.new ~/{dst}" + (" && chmod +x ~/" + dst if dst.endswith(".sh") else ""))
    ok = os.path.getsize(src) == int(T(dev, f"stat -c %s ~/{dst}").strip() or -1)
    print(f"{dst}: {'ok' if ok else 'DIMENSIONE DIVERSA!'}")
    return ok


def riavvia_bot(dev):
    T(dev, 'pkill -f "^python .*bot[.]py"')  # pattern ancorato: non uccide questa shell
    T(dev, "cd ~/sonno_bot && (nohup setsid python ~/sonno_bot/bot.py >> ~/sonno_bot/bot.log 2>&1 < /dev/null &)")
    time.sleep(5)
    print("bot:", T(dev, 'pgrep -f "^python .*bot[.]py" || echo NON GIRA').strip())


ALBERO = ["bot.py", "notte.py", "freschezza.py", "notti_telefono.py", "copy/testi.py", "ux/uso_quotidiano/note.py", "concept/grafici.py",
          "concept/messaggi.py", "concept/componenti.py", "concept/palette.json", "concept/fonts/DMSerifDisplay-Regular.ttf",
          "concept/fonts/BarlowCondensed-Medium.ttf", "concept/fonts/BarlowCondensed-SemiBold.ttf",
          "concept/mondo/messaggi_mondo.py", "concept/mondo/grafici_mondo.py", "concept/mondo/personaggi.py",
          "analisi/stato_corrente.py", "concept/notte/notte_bot.py",
          "miniapp.py", "miniapp.html", "grafo_stati.html", "analisi/presenza.csv"]


def albero(dev):
    """Bot con la STESSA struttura di cartelle del PC (bot.py mette concept/, copy/, ux/ nel path). Prima salva sul PC
    i dati del bot (csv, commenti) in C:\sonno_audio\bot_backup\<ora>."""
    import datetime
    bk = os.path.join(r"C:\sonno_audio", "bot_backup", f"{datetime.datetime.now():%Y%m%d_%H%M}")
    os.makedirs(bk, exist_ok=True)
    for n in T(dev, "cd ~/sonno_bot && ls *.csv *.txt *.json 2>/dev/null").split():
        p = subprocess.run(SSH + [f"cat ~/sonno_bot/{n}"] if dev == "ssh" else
                           ["adb", "-s", dev, "exec-out", "run-as", "com.termux", "cat", f"files/home/sonno_bot/{n}"],
                           capture_output=True, timeout=120)
        open(os.path.join(bk, n), "wb").write(p.stdout)
    print("backup:", bk, os.listdir(bk))
    T(dev, "mkdir -p ~/sonno_bot/concept/notte ~/sonno_bot/analisi ~/sonno_bot/copy ~/sonno_bot/ux/uso_quotidiano ~/sonno_bot/concept/fonts ~/sonno_bot/concept/mondo")
    ok = all(copia(dev, os.path.join(r"C:\sonno_bot", f), "sonno_bot/" + f) for f in ALBERO)
    T(dev, 'pkill -f "[p]ython .*miniapp.py"')  # il supervisore miniapp_run.sh lo rialza in 15 s
    return ok and all(copia(dev, rf"C:\sonno_tex\{m}", m) for m in ("categorie.py", "respiro.py", "conferma.py", "audioset_ontology.json"))


def riavvia(dev, cosa):
    if cosa == "bot":
        riavvia_bot(dev)
    elif cosa == "loop" and dev == "ssh":
        print("loop: riavvio solo via adb (riavvia_loop), fallo con il telefono sbloccato")
    elif cosa == "loop":
        T(dev, 'pkill -f "^bash .*home/rec.sh"; termux-microphone-record -q')
        riavvia_loop(dev); time.sleep(8)
        print("loop:", T(dev, "termux-microphone-record -i | grep isRec").strip())


TEST = [(r"C:\sonno_bot", "prova_bot.py"), (r"C:\sonno_bot", "prova_miniapp.py"), (r"C:\sonno_tex", "test_guardiano.py"),
        (r"C:\sonno_tex", "test_scenari_tempo.py"), (r"C:\sonno_bot\ux\uso_quotidiano", "note.py"), (r"C:\sonno_bot", "prova_notte_media.py")]


def test_verdi():
    """(nota rimossa)"""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    for cwd, f in TEST:
        r = subprocess.run([sys.executable, f], cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900, env=env,
                           creationflags=0x40)
        if r.returncode:
            print(f"TEST ROSSO, deploy annullato: {f}\n{(r.stdout + r.stderr)[-1500:]}")
            return False
    print("test verdi:", ", ".join(f for _, f in TEST))
    return True


if __name__ == "__main__":
    if "--senza-test" not in sys.argv and not test_verdi():
        sys.exit(1)
    sys.argv = [a for a in sys.argv if a != "--senza-test"]
    dev = scegli()
    print("via:", dev)
    if sys.argv[1] == "albero":
        if albero(dev):
            riavvia(dev, "bot")
        sys.exit()
    if sys.argv[1] in NOTI:
        src, dst, dopo = NOTI[sys.argv[1]]
    else:
        src, dst, dopo = sys.argv[1], sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else None)
    if copia(dev, src, dst) and dopo:
        riavvia(dev, dopo)
