"""
Un comando = una cosa. Dal PC, in C:\\sonno_bot:
   python sonno.py stato          -> A21s (registra? batteria, spazio, bot vivo), A56 (raggiungibile, sensori), PC
   python sonno.py prova          -> prova completa del bot sul PC (niente Telegram): python prova_bot.py
   python sonno.py installa       -> copia bot + concept + testi sull'A21s e riavvia il bot (deploy.py albero)
   python sonno.py sync           -> dati al bot (uso telefono/PC, dispositivi, mappa) e foto dal bot
   python sonno.py confronto      -> scarica PNG e risultati dall'A21s in C:\\sonno_audio\\confronto e stampa risultati
   python sonno.py mattino [GIORNO] -> manda ADESSO al bot il mattino di quella notte (AAAAMMGG, default oggi)
   python sonno.py punto HH:MM    -> manda al bot 20 s di audio vero di quel momento (come scrivere 5:12 in chat)
   python sonno.py log            -> ultimi errori del bot e del loop di registrazione
   python sonno.py lista          -> cosa resta da fare (voci [ ] di LISTA.md)
"""
import os, subprocess, sys

QUI = os.path.dirname(os.path.abspath(__file__))
TEX = r"C:\sonno_tex"
sys.path.insert(0, TEX)
import a21


def tel(cmd):
    """Comando nella home di Termux dell'A21s (run-as), output come testo."""
    from sonno_audio import device
    from cal_sessione import T
    d = device()
    if not d:
        # chiave del PC) resta su -> seconda strada indipendente
        r = subprocess.run(["ssh", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-p", "8022", a21.ip(), cmd],
                           capture_output=True, text=True, timeout=120)
        return r.stdout if r.returncode == 0 else "A21s NON raggiungibile (ne' adb ne' SSH)"
    return T(d, cmd)


def sul_bot(codice):
    """Esegue due righe di python DENTRO il bot sull'A21s (stesso codice, stessi dati, manda davvero in chat)."""
    from sonno_audio import device
    from deploy import copia
    from cal_sessione import T
    f = os.path.join(QUI, "_cmd_tel.py")
    open(f, "w", encoding="utf-8").write("import bot\n" + codice + "\n")
    d = device()
    copia(d, f, "sonno_bot/_cmd_tel.py")
    os.remove(f)
    return T(d, "cd ~/sonno_bot && timeout 250 python -W ignore _cmd_tel.py 2>&1 | tail -5; rm -f _cmd_tel.py")


def main(a):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # console Windows cp1252: le emoji della LISTA la rompevano
    c = a[0] if a else "aiuto"
    if c == "stato":
        print(tel('termux-battery-status | grep -E "percentage|plugged"; termux-microphone-record -i | grep isRec; '
                  'pgrep -f "^python .*bot[.]py" >/dev/null && echo "bot: vivo" || echo "bot: FERMO"; '
                  'pgrep -f "bash .*rec.sh" >/dev/null && echo "loop: vivo" || echo "loop: FERMO"; df -h ~ | tail -1'))
        out = tel("cd ~/rec; echo coda $(ls 2*.m4a 2>/dev/null | wc -l); "
                  "echo senza_conferma $(for f in russa_*.m4a; do [ -e ${f%.m4a}.eff ] || echo x; done | wc -l); "
                  "grep 'tempo yamnet' ~/analizza.log | tail -5 | awk '{print $NF}' | tr -d s | tr '\\n' ' '")
        v = out.split()
        try:
            coda, conf = int(v[1]) - 1, int(v[3])  # -1: l'ultimo blocco e' quello in registrazione
            t = [int(x) for x in v[4:]]
            yam = sum(t) / len(t) if t else None
            print(f"analisi: {max(coda, 0)} blocchi in coda" + (f" (~{max(coda, 0) * yam / 60:.0f}' YAMNet, {yam:.0f} s a blocco)"
                  if yam else " (tempo per blocco non ancora misurato)") + f", {conf} clip da confermare (~{conf * 16 / 60:.0f}')")
        except (IndexError, ValueError):
            print("analisi: stima non disponibile", out[:80])
        a56 = subprocess.run(["adb", "-s", "192.0.2.54:5555", "shell", "run-as com.termux ls files/home/notte_sensori"],
                             capture_output=True, text=True)
        print("A56:", f"raggiungibile, sensori: {a56.stdout.split()[-2:]}" if a56.returncode == 0 else "NON raggiungibile")
        import shutil
        print(f"PC: {shutil.disk_usage('C:/').free / 2**30:.1f} GB liberi")
    elif c == "prova":
        subprocess.run([sys.executable, "-W", "ignore", os.path.join(QUI, "prova_bot.py")] + a[1:])
    elif c == "installa":
        subprocess.run([sys.executable, os.path.join(TEX, "deploy.py"), "albero"])
    elif c == "sync":
        import sonno_audio
        sonno_audio.manda_al_bot(sonno_audio.device()); print("fatto")
    elif c == "confronto":
        from sonno_audio import device
        d = device()
        if not d:
            print("A21s NON raggiungibile (adb)")
            return
        dest = r"C:\sonno_audio\confronto"
        os.makedirs(dest, exist_ok=True)
        for f in tel("ls -1 ~/confronto/*.png").splitlines():
            nome = os.path.basename(f)
            if not nome.endswith(".png"):
                continue
            png = subprocess.run(["adb", "-s", d, "exec-out",
                                  f'run-as com.termux cat "files/home/confronto/{nome}"'],
                                 capture_output=True, check=True)
            with open(os.path.join(dest, nome), "wb") as out:
                out.write(png.stdout)
        risultati = tel("cat ~/confronto/risultati.txt")
        with open(os.path.join(dest, "risultati.txt"), "w", encoding="utf-8") as out:
            out.write(risultati)
        print(risultati)
    elif c == "mattino":
        from datetime import date
        g = a[1] if len(a) > 1 else f"{date.today():%Y%m%d}"
        print(sul_bot(f'bot.manda_notte(bot.analizza("{g}"), "{g}"); print("mandato")'))
    elif c == "punto" and len(a) > 1:
        print(sul_bot(f'bot.gestisci_testo("{a[1]}"); print("mandato")'))
    elif c == "log":
        print(tel("tail -8 ~/sonno_bot/errori.log; echo ---; tail -5 ~/rec.log"))
    elif c == "lista":
        for l in open(os.path.join(QUI, "LISTA.md"), encoding="utf-8"):
            if l.startswith("- [ ]"):
                print(l.rstrip()[:150])
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
