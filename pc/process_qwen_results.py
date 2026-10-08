#!/usr/bin/env python3
"""Elabora i risultati di Qwen e crea l'output."""
import json
import subprocess
import pathlib
import time
import sys

OUTPUT_DIR = pathlib.Path(r"C:\sonno_audio")
OUTPUT_DIR.mkdir(exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / "QWEN_DESCRIVE_03-10.md"

def download_qwen_results():
    """Scarica qwen.json dal kernel Kaggle."""
    kernel_name = "utente/sonno-qwen-descrizione-audio-03-10"
    print(f"[INFO] Aspettando il completamento del kernel {kernel_name}...")

    # Attendi il completamento del kernel
    max_wait = 3600  # 1 ora
    check_interval = 60  # 60 secondi
    elapsed = 0

    while elapsed < max_wait:
        try:
            # Controlla lo stato del kernel
            result = subprocess.run(
                [r"~\AppData\Local\Programs\Python\Python312\Scripts\kaggle.exe",
                 "kernels", "status", kernel_name],
                capture_output=True,
                text=True,
                timeout=30,
                env={**dict(os.environ), 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'}
            )

            if "complete" in result.stdout.lower():
                print("[OK] Kernel completato.")
                break
            elif "error" in result.stdout.lower() or "failed" in result.stdout.lower():
                print("[ERROR] Il kernel è fallito.")
                print(result.stdout)
                return False
            else:
                print(f"[{elapsed}s] Status: {result.stdout.strip()[:60]}...")
        except Exception as e:
            print(f"[WARN] Errore nel check dello stato: {e}")

        time.sleep(check_interval)
        elapsed += check_interval

    if elapsed >= max_wait:
        print("[TIMEOUT] Kernel non completato entro 1 ora.")
        return False

    # Scarica l'output
    print("[INFO] Scaricando output...")
    try:
        subprocess.run(
            [r"~\AppData\Local\Programs\Python\Python312\Scripts\kaggle.exe",
             "kernels", "output", kernel_name, "-p", str(OUTPUT_DIR.parent)],
            check=True,
            timeout=120,
            env={**dict(os.environ), 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'}
        )
        return True
    except Exception as e:
        print(f"[ERROR] Errore nel download: {e}")
        return False

def process_qwen_json(qwen_data):
    """Processa qwen.json e genera il markdown."""
    lines = []
    lines.append("# Qwen2-Audio: Descrizione audio - 03/10/2026\n")
    lines.append("| Ora (s) | Etichetta | Frase Qwen | Coerente? |")
    lines.append("|---------|-----------|-----------|-----------|")

    coherent_count = 0
    phrases_sample = []

    for i, item in enumerate(qwen_data.get("items", []), 1):
        start = item.get("a", "?")
        label = ", ".join(item.get("truth", []))
        response = item.get("response", "")

        # Decidi la coerenza leggendo la risposta
        coerenza = evaluate_coherence(response, label)
        if coerenza == "sì":
            coherent_count += 1

        # Prendi 2 frasi esempio
        if len(phrases_sample) < 2:
            phrases_sample.append(response[:100] if response else "(vuota)")

        # Accorcia la frase per il markdown
        short_response = (response[:80] + "...") if len(response) > 80 else response

        lines.append(f"| {start} | {label} | {short_response} | {coerenza} |")

    lines.append(f"\n**Risultati**: {coherent_count}/18 tratti coerenti.\n")
    lines.append(f"**Frasi esempio**:\n")
    for j, phrase in enumerate(phrases_sample, 1):
        lines.append(f"  {j}. {phrase}\n")

    return "\n".join(lines), coherent_count, phrases_sample

def evaluate_coherence(response, label):
    """Valuta se la risposta è coerente con l'etichetta."""
    response_lower = response.lower()
    label_lower = label.lower()

    # Semplice valutazione: controlla se la risposta contiene parole chiave dall'etichetta
    keywords = {
        "respiro": ["breath", "breathing", "respir"],
        "russa": ["snor"],
        "movimento": ["move", "motion", "rustle", "fabric", "bed"],
        "silenzio": ["quiet", "silence", "silent", "no sound"],
    }

    found_count = 0
    for cat, keys in keywords.items():
        if cat.lower() in label_lower:
            if any(key in response_lower for key in keys):
                found_count += 1

    # Valutazione semplice
    if found_count >= len(label.split(", ")) * 0.7:
        return "sì"
    elif found_count > 0:
        return "parziale"
    else:
        return "no"

def main():
    import os

    # Attendi i risultati da Kaggle
    if not download_qwen_results():
        print("[ERROR] Non è possibile scaricare i risultati da Kaggle.")
        sys.exit(1)

    # Leggi il file qwen.json
    qwen_path = OUTPUT_DIR.parent / "sonno-qwen-descrive-03-10" / "qwen.json"
    if not qwen_path.exists():
        print(f"[ERROR] File non trovato: {qwen_path}")
        sys.exit(1)

    with open(qwen_path, encoding="utf-8") as f:
        qwen_data = json.load(f)

    # Processa e salva il markdown
    md_content, coherent, samples = process_qwen_json(qwen_data)
    OUTPUT_FILE.write_text(md_content, encoding="utf-8")
    print(f"[OK] Markdown salvato: {OUTPUT_FILE}")

    # Crea il messaggio Telegram
    tg_message = (
        f"Qwen su {len(qwen_data.get('items', []))} tratti:\n"
        f"{coherent} coerenti, {len(qwen_data.get('items', [])) - coherent} discordanti.\n\n"
        f"Es. 1: {samples[0] if samples else 'N/A'}\n"
        f"Es. 2: {samples[1] if len(samples) > 1 else 'N/A'}"
    )

    # Salva il messaggio Telegram
    tg_file = OUTPUT_DIR.parent / "tg_message.txt"
    tg_file.write_text(tg_message, encoding="utf-8")
    print(f"[OK] Messaggio Telegram: {tg_message}")

    # Invia il messaggio via Telegram
    try:
        subprocess.run(
            [r"~\AppData\Local\Programs\Python\Python312\Scripts\python.exe",
             r"C:\sonno_tex\tg_IlTuoBot.py", tg_message],
            check=True,
            timeout=30
        )
        print("[OK] Messaggio Telegram inviato.")
    except Exception as e:
        print(f"[WARN] Errore nell'invio Telegram: {e}")

    print("[DONE] Elaborazione completata.")

if __name__ == "__main__":
    main()
