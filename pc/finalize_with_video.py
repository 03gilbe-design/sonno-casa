#!/usr/bin/env python3
"""Finalizza con video e commit una volta che i dati di Qwen sono disponibili."""
import json
import pathlib
import subprocess
import sys

OUTPUT_DIR = pathlib.Path(r"C:\sonno_audio")
KERNEL_OUTPUT = OUTPUT_DIR / "sonno-qwen-descrizione-audio-03-10"

def check_qwen_json():
    """Controlla se qwen.json è disponibile."""
    qwen_file = KERNEL_OUTPUT / "qwen.json"
    return qwen_file.exists(), qwen_file

def generate_markdown(qwen_file):
    """Genera il markdown dai risultati di Qwen."""
    with open(qwen_file, encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
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

        coh = evaluate_coherence(response, label)
        if coh == "sì":
            coherent += 1

        if len(samples) < 2 and response:
            samples.append(response[:85])

        short = (response[:65] + "...") if len(response) > 65 else response
        lines.append(f"| {start} | {label} | {short} | {coh} |")

    lines.append(f"\n**Risultati**: {coherent}/{len(items)} coerenti.\n")

    md_file = OUTPUT_DIR / "QWEN_DESCRIVE_03-10.md"
    md_file.write_text("\n".join(lines), encoding="utf-8")

    return md_file, coherent, len(items), samples

def evaluate_coherence(response, label):
    if not response or not label or label == "(nessuna)":
        return "no"

    resp_l = response.lower()
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

def send_telegram(coherent, total, samples):
    """Invia messaggio Telegram."""
    tg_py = pathlib.Path(r"C:\sonno_tex\tg_IlTuoBot.py")
    if not tg_py.exists():
        print(f"[WARN] {tg_py} non trovato.")
        return False

    msg_lines = [
        f"Qwen: {coherent}/{total} coerenti.",
        samples[0][:70] if samples else "",
        samples[1][:70] if len(samples) > 1 else ""
    ]
    msg = "\n".join([m for m in msg_lines if m])[:200]  # Max 200 caratteri

    print(f"[*] Inviando Telegram: {msg[:80]}")
    try:
        subprocess.run(
            [r"~\AppData\Local\Programs\Python\Python312\Scripts\python.exe",
             str(tg_py), msg],
            check=True,
            timeout=30
        )
        print("[OK] Telegram inviato.")
        return True
    except Exception as e:
        print(f"[WARN] Errore Telegram: {e}")
        return False

def commit_changes(coherent, total):
    """Fa il commit in C:\\sonno_tex."""
    print("[*] Facendo il commit...")
    try:
        subprocess.run(
            ["git", "-C", r"C:\sonno_tex", "add", "kaggle_lab/contesto_0310/run_kaggle.py"],
            check=True,
            timeout=10
        )

        msg = (
            "feat: modifica prompt Qwen2-Audio per descrizione libera con contesto\n\n"
            "- Prompt originale: domande sì/no troppo binarie\n"
            "- Nuovo prompt: descrizione libera in inglese con contesto\n"
            "- Input: possibili suoni, timing, confidenza\n"
            "- Output: 18 tratti descritti con Qwen2-Audio-7B-Instruct\n"
            f"- Coerenza valutata: {coherent}/{total} coerenti\n"
            "\n"
            "Co-Authored-By: Claude Opus 5.5 <email@example.com>"
        )

        subprocess.run(
            ["git", "-C", r"C:\sonno_tex", "commit", "-m", msg],
            check=True,
            timeout=10
        )
        print("[OK] Commit effettuato.")
        return True
    except Exception as e:
        print(f"[WARN] Errore commit: {e}")
        return False

def main():
    exists, qwen_file = check_qwen_json()
    if not exists:
        print(f"[ERROR] {qwen_file} non trovato.")
        return 1

    print(f"[*] Processando {qwen_file}")
    md_file, coherent, total, samples = generate_markdown(qwen_file)
    print(f"[OK] Markdown: {md_file}")
    print(f"[*] {coherent}/{total} coerenti")

    send_telegram(coherent, total, samples)
    commit_changes(coherent, total)

    print("[DONE]")
    return 0

if __name__ == "__main__":
    sys.exit(main())
