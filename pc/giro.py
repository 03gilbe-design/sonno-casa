"""
   python giro.py         -> stato + avvia conferma.py sotto il lucchetto (se libero), torna subito
   python giro.py stato   -> solo lo stato (~/stato.json aggiornato)
"""
import subprocess, sys
import a21

SSH = ["ssh", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-p", "8022", a21.ip()]
AVVIA = ("cd ~ && (flock -n 9 || { echo 'lucchetto occupato: gira gia qualcosa'; exit 0; }; "
         "nice -n 19 python -W ignore conferma.py >> ~/conferma.log 2>&1) 9>~/.analisi.lock </dev/null >/dev/null 2>&1 &")

print(subprocess.run(SSH + ["cd ~ && python -W ignore stato.py"], capture_output=True, text=True, timeout=60).stdout)
if sys.argv[1:] != ["stato"]:
    subprocess.run(SSH + [AVVIA], timeout=30)
    print("giro avviato (in background sull'A21s)")
