"""Archivia su Google Drive i blocchi audio del telefono (e i flac del PC), poi libera spazio.
Uso: python archivia_interi.py [--prova] [--max N] [--tieni-ore 48]
Regola: si cancella SOLO dopo verifica su Drive (dimensione + md5). Ogni errore = non cancellare."""
import senza_finestre  # noqa: F401  (niente finestre dei processi figli: va importato per primo)
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time
import a21
from datetime import datetime

RCLONE = r"~\AppData\Local\Microsoft\WinGet\Packages\Rclone.Rclone_Microsoft.Winget.Source_8wekyb3d8bbwe\rclone-v1.75.1-windows-amd64\rclone.exe"
def ssh(host):
    return ["ssh", "-p", "8022", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15",
            "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3", host]


NL = chr(10)
A56 = "192.0.2.54"
DEADLINE = time.time() + 45 * 60  # uscita pulita prima del limite 1h dello scheduler
CSV_A56 = r"C:\sonno_audio\archiviati_a56.csv"
CSV_CLIP = r"C:\sonno_audio\archiviati_clip.csv"
SCP = ["scp", "-P", "8022", "-o", "HostKeyAlias=[192.0.2.184]:8022", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3"]
TEL = a21.ip()
TMP = r"C:\sonno_audio\_archivia_tmp"
LOG = r"C:\sonno_audio\archivia.log"
PC_DIR = r"C:\sonno_audio\tre_dispositivi"
OK_PC = r"C:\sonno_audio\archivia_pc_ok.json"
CSV = r"C:\sonno_audio\archiviati.csv"  # nome,size: blocchi telefono verificati su Drive
MIN_LIBERO = 1 << 20      # KB: sotto 1 GB liberi sul telefono si cancella anche prima del limite ore
SKIP_S = 35 * 60         # file toccato negli ultimi 35' = in scrittura
PC_ETA = 2 * 86400        # i flac locali si cancellano solo se piu' vecchi di 2 giorni


STAT = dict(ok=0, mb=0.0, errori=0, ultimo_errore="")  # di questo giro: lo scrive stato_drive()


def log(nome, mb, esito):
    if esito.startswith("OK"):
        STAT["ok"] += 1; STAT["mb"] += mb
    elif esito.startswith("ERRORE"):
        STAT["errori"] += 1; STAT["ultimo_errore"] = f"{nome}: {esito}"[:120]
    riga = f"{datetime.now():%Y-%m-%d %H:%M:%S}\t{nome}\t{mb:.1f} MB\t{esito}"
    print(riga, flush=True)
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(riga + "\n")


def run(cmd, **kw):
    if cmd[0] == RCLONE:
        cmd = cmd[:2] + ["--timeout", "120s", "--contimeout", "60s", "--low-level-retries", "8", "--tpslimit", "3", "--tpslimit-burst", "1", "--transfers", "2"] + cmd[2:]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=kw.pop("timeout", 900), **kw)


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def data_da_nome(nome):
    m = re.search(r"(\d{4})(\d{2})(\d{2})_\d{4}", nome)
    return f"{m[1]}-{m[2]}-{m[3]}" if m else None


def su_drive_ok(remoto, size, h):
    """True se su Drive c'e' con stessa dimensione e (se disponibile) stesso md5."""
    for _ in range(4):  # rate limit Drive: ritenta con pausa
        r = run([RCLONE, "lsjson", "--hash", "--files-only", remoto])
        if r.returncode == 0:
            break
        time.sleep(15)
    else:
        return False
    try:
        e = json.loads(r.stdout)[0]
    except (ValueError, IndexError):
        return False
    if e["Size"] != size:
        return False
    drive_md5 = (e.get("Hashes") or {}).get("md5")
    return drive_md5 is None or drive_md5.lower() == h  # ponytail: se Drive non da' md5 vale solo la size


def carica(locale, remoto, size):
    """copyto + verifica. Ritorna stringa errore o None se ok."""
    h = md5(locale)
    for _ in range(3):
        r = run([RCLONE, "copyto", locale, remoto])
        if r.returncode == 0:
            break
        time.sleep(30)
    if r.returncode != 0:
        return "rclone copyto: " + r.stderr.strip()[-150:]
    if not su_drive_ok(remoto, size, h):
        return "verifica Drive fallita"
    return None


def carica_csv(csv):
    try:
        return {n: int(z) for n, z in (l.strip().split(",") for l in open(csv) if "," in l)}
    except FileNotFoundError:
        return {}


def blocchi(host, rdir, dest, csv, max_n, prova, tieni_ore, glob="*.m4a", min_libero=0):
    """Carica+verifica i blocchi nuovi (registra in CSV). Cancella dal telefono solo i verificati
    piu' vecchi di tieni_ore (il bot ritaglia 'contesto' dai blocchi locali), o i piu' vecchi
    se lo spazio libero e' < 1 GB."""
    try:
        r = run(ssh(host) + [f"stat -c '%s %Y %n' ~/{rdir}/{glob}; date +%s; df -k ~ | tail -1"])
    except subprocess.TimeoutExpired:
        log(host, 0, "ERRORE ssh elenco: timeout")
        return 0
    if r.returncode != 0:
        log(host, 0, "ERRORE ssh elenco: " + r.stderr.strip()[-100:])
        return 0
    righe = r.stdout.strip().splitlines()
    libero_kb = int(righe[-1].split()[3])
    ora = int(righe[-2])
    files = []
    for l in righe[:-2]:
        size, mt, path = l.split(" ", 2)
        files.append((os.path.basename(path), int(size), int(mt)))
    files.sort()
    if files and host == TEL:
        files = files[:-1]  # il piu' recente e' in scrittura
    files = [f for f in files if ora - f[2] > SKIP_S]
    ok = carica_csv(csv)
    n = 0
    os.makedirs(TMP, exist_ok=True)
    for nome, size, _ in files:
        if ok.get(nome) == size or n >= max_n or time.time() > DEADLINE:
            continue
        mb = size / 1e6
        data = data_da_nome(nome)
        if not data:
            log(nome, mb, "SALTATO nome non valido")
            continue
        loc = os.path.join(TMP, nome)
        try:
            for _ in range(3):  # il telefono a volte rifiuta la connessione: 3 tentativi
                r = run(SCP + [f"{host}:{rdir}/{nome}", loc])
                if r.returncode == 0 and os.path.exists(loc) and os.path.getsize(loc) == size:
                    break
                time.sleep(10)
            else:
                log(nome, mb, "ERRORE copia dal telefono: " + r.stderr.strip()[-100:])
                continue
            err = carica(loc, f"gdrive:sonno/{dest}/{data}/{nome}", size)
            if err:
                log(nome, mb, "ERRORE " + err)
                continue
            ok[nome] = size
            with open(csv, "a") as f:
                f.write(f"{nome},{size}\n")
            log(nome, mb, "OK verificato su Drive")
            n += 1
        except Exception as e:  # qualunque errore: non registrare, passa oltre
            log(nome, mb, f"ERRORE {type(e).__name__}: {e}")
        finally:
            if os.path.exists(loc):
                os.remove(loc)
    # cancellazione: solo verificati (CSV, stessa size sul telefono), dal piu' vecchio
    for nome, size, mt in files:
        if ok.get(nome) != size:
            continue
        vecchio = ora - mt > tieni_ore * 3600
        poco_spazio = libero_kb < min_libero
        if not (vecchio or poco_spazio):
            continue
        motivo = f"vecchio >{tieni_ore}h" if vecchio else "spazio libero basso"
        if prova:
            log(nome, size / 1e6, f"PROVA: cancellerei dal telefono ({motivo})")
            continue
        d = run(ssh(host) + [f"rm -- ~/{rdir}/{nome}"])
        if d.returncode == 0:
            libero_kb += size // 1024
            log(nome, size / 1e6, f"cancellato dal telefono ({motivo})")
        else:
            log(nome, size / 1e6, "ERRORE rm: " + d.stderr.strip()[-80:])
    return n


def clip(host=TEL):
    """Copia (mai cancella) clip ~/rec/{tipo}_* e file accanto su gdrive:sonno/clip/AAAA-MM-GG/."""
    r = run(ssh(host) + ["cd ~/rec && stat -c '%s %n' russa_* tosse_* voce_* 2>/dev/null"])
    ok = carica_csv(CSV_CLIP)
    nuovi = []
    for l in r.stdout.splitlines():
        size, nome = l.split(" ", 1)
        if ok.get(nome) != int(size) and data_da_nome(nome):
            nuovi.append((nome, int(size)))
    if not nuovi:
        return
    tmp = os.path.join(TMP, "clip")
    os.makedirs(tmp, exist_ok=True)
    for i in range(0, len(nuovi), 100):
        if time.time() > DEADLINE:
            return
        lotto = nuovi[i:i + 100]
        try:
            p = subprocess.run(ssh(host) + ["cd ~/rec && tar cf - -T -"], input=NL.join(n for n, _ in lotto).encode(),
                               capture_output=True, timeout=900)
            subprocess.run(["tar", "xf", "-", "-C", tmp], input=p.stdout, check=True, timeout=300)
            for d in {data_da_nome(n) for n, _ in lotto}:
                os.makedirs(os.path.join(tmp, d), exist_ok=True)
            for n, z in lotto:
                f = os.path.join(tmp, n)
                if os.path.getsize(f) != z:
                    raise RuntimeError("size diversa " + n)
                os.replace(f, os.path.join(tmp, data_da_nome(n), n))
            c = run([RCLONE, "copy", tmp, "gdrive:sonno/clip", "--size-only", "--tpslimit", "10", "--transfers", "4", "--max-duration", "10m"])
            if c.returncode != 0:
                raise RuntimeError(c.stderr.strip()[-150:])
            with open(CSV_CLIP, "a") as f:
                f.writelines(f"{n},{z}"+NL for n, z in lotto)
            log("clip", sum(z for _, z in lotto) / 1e6, f"OK {len(lotto)} file su Drive")
        except Exception as e:
            log("clip", 0, f"ERRORE {type(e).__name__}: {e}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            os.makedirs(tmp, exist_ok=True)


def dati(host=TEL):
    """Copia aggiornata dei file di dati su gdrive:sonno/dati (copy, mai sync)."""
    tmp = os.path.join(TMP, "dati")
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    try:
        r = run(SCP + [f"{host}:rec/minuti_*.csv", f"{host}:sonno_bot/*.csv", f"{host}:sonno_bot/commenti.txt",
                       f"{host}:stato.json", tmp])
        c = run([RCLONE, "copy", tmp, "gdrive:sonno/dati", "--checksum"])
        log("dati", 0, f"OK {len(os.listdir(tmp))} file" if c.returncode == 0 else "ERRORE " + c.stderr.strip()[-120:])
    except Exception as e:
        log("dati", 0, f"ERRORE {type(e).__name__}: {e}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def pc(max_n):
    """Carica i flac nuovi (stato in OK_PC); cancella solo se piu' vecchi di PC_ETA e ri-verificati su Drive."""
    try:
        ok = set(json.load(open(OK_PC)))
    except Exception:
        ok = set()
    ora = time.time()
    cand = sorted(os.path.join(d, f) for d, _, fs in os.walk(PC_DIR) for f in fs
                  if f.lower().endswith(".flac") and ora - os.path.getmtime(os.path.join(d, f)) > SKIP_S)
    n = 0
    for p in cand:
        nome = os.path.basename(p)
        data = data_da_nome(nome)
        if time.time() > DEADLINE:
            break
        vecchio = ora - os.path.getmtime(p) > PC_ETA
        if not data or (nome in ok and not vecchio) or (nome not in ok and n >= max_n):
            continue
        try:
            size = os.path.getsize(p)
            remoto = f"gdrive:sonno/pc/{data}/{nome}"
            if nome in ok:  # vecchio: ri-verifica su Drive prima di cancellare
                err = None if su_drive_ok(remoto, size, md5(p)) else "non verificato su Drive"
            else:
                err = carica(p, remoto, size)
                n += 1
            if err:
                ok.discard(nome)
                log(nome, size / 1e6, "ERRORE " + err + " (nessuna cancellazione)")
            elif vecchio:
                os.remove(p)
                log(nome, size / 1e6, "OK su Drive, cancellato dal PC (>2 giorni)")
            else:
                ok.add(nome)
                log(nome, size / 1e6, "OK su Drive, tenuto sul PC (<2 giorni)")
        except Exception as e:
            log(nome, 0, f"ERRORE {type(e).__name__}: {e}")
    json.dump(sorted(ok), open(OK_PC, "w"))
    return n


def stato_drive():
    """stato_drive.json sul telefono (lo legge /stato): ultimo giro, ultimo archivio riuscito, errori. Mai bloccante."""
    try:
        f = r"C:\sonno_audio\stato_drive.json"
        try:
            prec = json.load(open(f))
        except (OSError, ValueError):
            prec = {}
        ora = datetime.now().isoformat(timespec="seconds")
        d = dict(t=ora, file=STAT["ok"], gb=round(STAT["mb"] / 1024, 2), errori=STAT["errori"], ultimo_errore=STAT["ultimo_errore"],
                 ultimo_ok=ora if STAT["ok"] else prec.get("ultimo_ok"),
                 ultimo_ok_file=STAT["ok"] if STAT["ok"] else prec.get("ultimo_ok_file"),
                 ultimo_ok_gb=round(STAT["mb"] / 1024, 2) if STAT["ok"] else prec.get("ultimo_ok_gb"))
        json.dump(d, open(f, "w"))
        subprocess.run(SCP + [f, f"{TEL}:sonno_bot/stato_drive.json"], capture_output=True, timeout=60)
    except Exception as e:
        log("stato_drive", 0, f"ERRORE {type(e).__name__}: {e}")


def sicuro(f, *args, **kw):
    try:
        return f(*args, **kw)
    except Exception as e:  # una fase che salta non deve fermare le altre
        log(f.__name__, 0, f"ERRORE fase: {type(e).__name__}: {e}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prova", action="store_true", help="non cancella dal telefono")
    ap.add_argument("--max", type=int, default=20, help="max file per giro (telefono)")
    ap.add_argument("--tieni-ore", type=float, default=48, help="ore minime prima di cancellare dal telefono")
    ap.add_argument("--solo-telefono", action="store_true")
    ap.add_argument("--pc-ore", type=float, default=48, help="ore minime prima di cancellare i flac del PC (gia' su Drive)")
    a = ap.parse_args()
    PC_ETA = a.pc_ore * 3600
    T0 = time.time()  # ogni fase ha la sua fetta di tempo: uscita pulita entro ~50' (limite scheduler 1h)
    DEADLINE = T0 + 28 * 60
    t = blocchi(TEL, "rec/interi", "interi", CSV, a.max, a.prova, a.tieni_ore, min_libero=MIN_LIBERO)
    if not a.solo_telefono:
        DEADLINE = T0 + 38 * 60
        sicuro(blocchi, A56, "rec_a56", "a56", CSV_A56, a.max, a.prova, a.tieni_ore)
        DEADLINE = T0 + 44 * 60
        sicuro(clip)
        sicuro(dati)
        DEADLINE = T0 + 50 * 60
        sicuro(pc, a.max)
    print("archiviati dal telefono:", t)
    if not a.prova:
        stato_drive()
