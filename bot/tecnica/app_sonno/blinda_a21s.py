"""
Cause viste stasera: doze (app in background sospese) + wifi a riposo a schermo spento (porte in timeout).
   python blinda_a21s.py          -> aspetta che l'A21s risponda (fino a 60 min), poi applica e verifica
Applica: Termux/Termux:API esenti da doze e dall'ottimizzazione batteria, background sempre consentito,
wifi mai a riposo, e in crontab un ping al router ogni minuto (traffico = il wifi resta sveglio).
"""
import subprocess, sys, time

IP = "192.0.2.184"
SSH = ["ssh", "-p", "8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", IP]
ADB = f"{IP}:5555"


def sh(cmd):
    try:
        return subprocess.run(SSH + [cmd], capture_output=True, text=True, timeout=30).stdout
    except Exception:
        return ""


def adb(*a):
    return subprocess.run(["adb", "-s", ADB, "shell", *a], capture_output=True, text=True, timeout=30)


def aspetta(minuti=60):
    for _ in range(minuti * 2):
        if "ok" in sh("echo ok"):
            return True
        time.sleep(30)
    return False


def blinda():
    subprocess.run(["adb", "connect", ADB], capture_output=True, timeout=20)
    for pkg in ("com.termux", "com.termux.api", "com.termux.boot"):
        adb("dumpsys", "deviceidle", "whitelist", f"+{pkg}")                 # niente doze
        adb("cmd", "appops", "set", pkg, "RUN_ANY_IN_BACKGROUND", "allow")    # background sempre ok
        adb("cmd", "appops", "set", pkg, "RUN_IN_BACKGROUND", "allow")
    adb("settings", "put", "global", "wifi_sleep_policy", "2")               # wifi mai a riposo
    # ping al router ogni minuto: senza traffico la scheda wifi va a riposo e le porte vanno in timeout
    riga = "* * * * * ping -c1 -W2 192.0.2.3 >/dev/null 2>&1"
    sh(f"(crontab -l 2>/dev/null | grep -v 'ping -c1 -W2 192.0.2.3'; echo '{riga}') | crontab -; "
       "pgrep crond >/dev/null || crond; termux-wake-lock")


def verifica():
    wl = adb("dumpsys", "deviceidle", "whitelist").stdout
    print("doze esente:", all(p in wl for p in ("com.termux", "com.termux.api")))
    print("wifi_sleep_policy:", adb("settings", "get", "global", "wifi_sleep_policy").stdout.strip())
    print("cron ping:", "192.0.2.3" in sh("crontab -l"), "| crond:", bool(sh("pgrep crond").strip()))
    print("registra:", '"isRecording": true' in sh("termux-microphone-record -i"))


if __name__ == "__main__":
    if not aspetta():
        sys.exit("A21s ancora irraggiungibile dopo 60 min: serve toccare lo schermo")
    blinda(); verifica()
