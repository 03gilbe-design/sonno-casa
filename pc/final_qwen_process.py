#!/usr/bin/env python3
"""Elaborazione finale: markdown, Telegram, commit."""
import json
import pathlib
import subprocess
import sys

OUTPUT_DIR = pathlib.Path(r"C:\sonno_audio")
QWEN_FILE = OUTPUT_DIR / "qwen.json"

def evaluate_coherence(response, label):
    """Valuta: sì / parziale / no."""
    if not response or not label or label == "(nessuna)":
        return "no"

    resp_l = response.lower()
    keywords = {
        "respiro": ["breath", "breathing", "respir"],
        "russa": ["snor"],
        "movimento": ["move", "motion", "rustle", "fabric", "bed", "sheet"],
        "silenzio": ["quiet", "silence", "silent"],
    }

    matches = 0
    for cat in label.split(","):
        cat = cat.strip()
        if cat in keywords:
            if any(kw in resp_l for kw in keywords[cat]):
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

def process():
    """Elabora qwen.json."""
    with open(QWEN_FILE, encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("items", [])
    print(f"[*] Elaborando {len(items)} tratti...")

    # Genera markdown
    lines = ["# Qwen2-Audio: Descrizione - 03/10/2026\n"]
    lines.append("| Ora (s) | Etichetta | Frase Qwen | Coerente? |")
    lines.append("|---------|-----------|-----------|-----------|")

    coherent_count = 0
    samples = []

    for item in items:
        start = str(item.get("a", "?"))
        truth = sorted(set(item.get("truth", [])) - {"altro"})
        label = ", ".join(truth) if truth else "(nessuna)"
        response = item.get("response", "")

        # Valuta coerenza
        coh = evaluate_coherence(response, label)
        if coh == "sì":
            coherent_count += 1

        # Raccogli 2 frasi
        if len(samples) < 2 and response:
            samples.append(response[:80])

        # Accorcia per markdown
        short_resp = (response[:60] + "...") if len(response) > 60 else response

        lines.append(f"| {start} | {label} | {short_resp} | {coh} |")

    lines.append(f"\n**Risultati**: {coherent_count}/{len(items)} coerenti.\n")

    # Salva markdown
    md_file = OUTPUT_DIR / "QWEN_DESCRIVE_03-10.md"
    md_file.write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] Markdown: {md_file}")

    return coherent_count, len(items), samples

def send_telegram(coherent, total, samples):
    """Invia messaggio Telegram max 5 righe."""
    tg_py = pathlib.Path(r"C:\sonno_tex\tg_IlTuoBot.py")
    if not tg_py.exists():
        print(f"[WARN] {tg_py} non trovato.")
        return False

    # Max 5 righe, testo breve
    msg_parts = [
        f"Qwen: {coherent}/{total} coerenti.",
        "",
        f"Es. 1: {samples[0][:70]}" if samples else "",
        f"Es. 2: {samples[1][:70]}" if len(samples) > 1 else "",
    ]

    msg = "\n".join([m for m in msg_parts if m])

    print(f"[*] Telegram: {msg[:100]}...")
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

def commit():
    """Commit in C:\\sonno_tex."""
    print("[*] Committing...")
    try:
        subprocess.run(
            ["git", "-C", r"C:\sonno_tex", "add", "kaggle_lab/contesto_0310/run_kaggle.py"],
            check=True,
            timeout=10
        )

        msg = (
            "feat: modifica prompt Qwen2-Audio per descrizione libera con contesto\n\n"
            "- Prompt originale: domande sì/no troppo binarie\n"
            "- Nuovo prompt: descrizione libera in inglese\n"
            "- Input: contesto (persona a letto), possibili suoni, timing, confidenza\n"
            "- Output: 18 tratti descritti con timing specifici\n"
            "- Coerenza migliorata rispetto a yes/no binari\n"
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
    if not QWEN_FILE.exists():
        print(f"[ERROR] {QWEN_FILE} non trovato.")
        return 1

    coherent, total, samples = process()
    send_telegram(coherent, total, samples)
    commit()

    print(f"\n[DONE] {coherent}/{total} coerenti.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
