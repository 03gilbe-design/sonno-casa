#!/usr/bin/env python3
"""Monitora il kernel, scarica i dati, genera markdown, video e messaggio Telegram."""
import json
import pathlib
import subprocess
import time
import sys
import os

KERNEL_NAME = "utente/sonno-qwen-descrizione-audio-03-10"
OUTPUT_DIR = pathlib.Path(r"C:\sonno_audio")
KERNEL_OUTPUT = OUTPUT_DIR / "sonno-qwen-descrizione-audio-03-10"
KAGGLE_PY = r"~\AppData\Local\Programs\Python\Python312\Scripts\kaggle.exe"

def check_and_download():
    """Controlla lo stato del kernel e scarica i risultati."""
    print("[*] Controllando lo stato del kernel...")

    for attempt in range(45):  # Massimo 45 * 4 = 3 ore
        try:
            result = subprocess.run(
                [KAGGLE_PY, "kernels", "status", KERNEL_NAME],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'}
            )
            status = result.stdout.strip()
            print(f"[{attempt+1}/45] {status}")

            if "COMPLETE" in status.upper():
                print("[OK] Kernel completato. Scaricamento...")
                try:
                    subprocess.run(
                        [KAGGLE_PY, "kernels", "output", KERNEL_NAME, "-p", str(OUTPUT_DIR)],
                        check=True,
                        timeout=120,
                        env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'}
                    )
                    print(f"[OK] Output scaricato.")
                    return True
                except Exception as e:
                    print(f"[ERROR] Errore nel download: {e}")
                    return False

            if "ERROR" in status.upper() or "FAILED" in status.upper():
                print(f"[ERROR] Kernel fallito: {status}")
                return False

        except Exception as e:
            print(f"[WARN] Errore nel check ({e}), riprovo...")

        if attempt < 44:
            time.sleep(240)  # 4 minuti

    print("[TIMEOUT] Kernel non completato entro 3 ore.")
    return False

def process_qwen_output():
    """Processa qwen.json e genera markdown."""
    qwen_file = KERNEL_OUTPUT / "qwen.json"
    if not qwen_file.exists():
        print(f"[ERROR] {qwen_file} non trovato.")
        return None

    print(f"[*] Caricando {qwen_file}")
    with open(qwen_file, encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    print(f"[*] Elaborando {len(items)} tratti...")

    lines = ["# Qwen2-Audio: Descrizione - 03/10/2026\n"]
    lines.append("| Ora (s) | Etichetta | Frase Qwen | Coerente? |")
    lines.append("|---------|-----------|-----------|-----------|")

    coherent = 0
    samples = []

    for item in items:
        start = str(item.get("a", "?"))
        truth = sorted(set(item.get("truth", [])) - {"altro"})
        label = ", ".join(truth) if truth else "(nessuna)"
        response = item.get("response", "")

        # Valuta coerenza
        coh = evaluate_coherence(response, label)
        if coh == "sì":
            coherent += 1

        # Raccogli 2 frasi
        if len(samples) < 2 and response:
            samples.append(response[:90])

        # Accorcia per markdown
        short = (response[:65] + "...") if len(response) > 65 else response
        lines.append(f"| {start} | {label} | {short} | {coh} |")

    lines.append(f"\n**Risultati**: {coherent}/{len(items)} coerenti.\n")

    # Salva markdown
    md_file = OUTPUT_DIR / "QWEN_DESCRIVE_03-10.md"
    md_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] Markdown: {md_file}")

    # Crea messaggio Telegram (max 3 righe per testo, poi video)
    tg_msg = f"Qwen: {coherent}/{len(items)} coerenti.\n{samples[0] if samples else ''}\n{samples[1] if len(samples) > 1 else ''}"

    return {
        "coherent": coherent,
        "total": len(items),
        "samples": samples,
        "tg_msg": tg_msg,
        "md_file": md_file,
        "items": items
    }

def generate_video(processed):
    """Genera il video con video.py."""
    print(f"[*] Generando video...")

    # Copia i file necessari
    video_py = pathlib.Path(r"C:\sonno_tex\kaggle_lab\contesto_0310\video.py")
    core_py = pathlib.Path(r"C:\sonno_tex\kaggle_lab\contesto_0310\core.py")

    if not video_py.exists() or not core_py.exists():
        print(f"[ERROR] File necessari non trovati.")
        return None

    # Per ora, il video richiede la struttura completa di run_kaggle.
    # Qui facciamo un comando semplice per testare.
    # In realtà, il video.py di Kaggle ha bisogno di tutti i dati di records/outputs.
    # Poiché non li abbiamo qui, creiamo un video minimalista o saltiamo.

    print(f"[SKIP] Generazione video richiede la struttura completa di Kaggle.")
    return None

def send_telegram(processed, video_path=None):
    """Invia messaggio Telegram."""
    tg_py = pathlib.Path(r"C:\sonno_tex\tg_IlTuoBot.py")
    if not tg_py.exists():
        print(f"[WARN] {tg_py} non trovato.")
        return False

    print(f"[*] Inviando messaggio Telegram...")
    try:
        cmd = [r"~\AppData\Local\Programs\Python\Python312\Scripts\python.exe",
               str(tg_py)]

        if video_path:
            cmd.extend(["--video", str(video_path), processed["tg_msg"]])
        else:
            cmd.append(processed["tg_msg"][:200])  # Limita a 200 caratteri

        subprocess.run(cmd, check=True, timeout=30)
        print("[OK] Telegram inviato.")
        return True
    except Exception as e:
        print(f"[WARN] Errore Telegram: {e}")
        return False

def evaluate_coherence(response, label):
    """sì / parziale / no"""
    if not response or not label or label == "(nessuna)":
        return "no"

    resp_l = response.lower()
    label_l = label.lower()

    keywords = {
        "respiro": ["breath", "breathing", "respir"],
        "russa": ["snor"],
        "movimento": ["move", "motion", "rustle", "fabric", "bed"],
        "silenzio": ["quiet", "silence", "silent"],
    }

    matches = 0
    for cat in label.split(","):
        cat = cat.strip()
        if cat in keywords and any(kw in resp_l for kw in keywords[cat]):
            matches += 1

    total = len([c for c in label.split(",") if c.strip()])
    if total == 0:
        return "no"
    elif matches >= total * 0.7:
        return "sì"
    elif matches > 0:
        return "parziale"
    else:
        return "no"

def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    if not check_and_download():
        print("[ERROR] Non è stato possibile scaricare i dati.")
        return 1

    processed = process_qwen_output()
    if not processed:
        print("[ERROR] Errore nell'elaborazione.")
        return 1

    video_path = generate_video(processed)

    send_telegram(processed, video_path)

    print("[DONE] Elaborazione completata.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
