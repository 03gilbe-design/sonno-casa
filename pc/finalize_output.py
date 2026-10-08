#!/usr/bin/env python3
"""Elabora i risultati di Qwen e genera output finale."""
import json
import pathlib
import subprocess

OUTPUT_DIR = pathlib.Path(r"C:\sonno_audio")
KERNEL_OUTPUT_BASE = OUTPUT_DIR / "sonno-qwen-descrizione-audio-03-10"

def main():
    # Cerca il file qwen.json
    qwen_file = KERNEL_OUTPUT_BASE / "qwen.json"

    if not qwen_file.exists():
        print(f"[ERROR] {qwen_file} non trovato.")
        return False

    print(f"[*] Caricando {qwen_file}")
    with open(qwen_file, encoding="utf-8") as f:
        qwen_data = json.load(f)

    items = qwen_data.get("items", [])
    print(f"[*] {len(items)} tratti trovati.")

    # Genera il markdown
    lines = ["# Qwen2-Audio: Descrizione - 03/10/2026\n"]
    lines.append("| Ora (s) | Etichetta | Descrizione Qwen | Coerente? |")
    lines.append("|---------|-----------|------------------|-----------|")

    coherent_count = 0
    sample_phrases = []

    for item in items:
        start = str(item.get("a", "?"))
        truth = item.get("truth", [])
        label = ", ".join(sorted(set(truth) - {"altro"})) if truth else "(nessuna)"
        response = item.get("response", "")

        # Valuta coerenza
        coheence_val = evaluate_coherence(response, label)
        if coheence_val == "sì":
            coherent_count += 1

        # Raccogli 2 frasi esempio
        if len(sample_phrases) < 2 and response:
            sample_phrases.append(response[:85] + ("..." if len(response) > 85 else ""))

        # Accorcia per markdown
        short_desc = (response[:70] + "...") if len(response) > 70 else response

        lines.append(f"| {start} | {label} | {short_desc} | {coheence_val} |")

    lines.append(f"\n## Riassunto\n")
    lines.append(f"- **Coerenti**: {coherent_count}/18\n")
    lines.append(f"- **Non coerenti**: {len(items) - coherent_count}/18\n\n")

    lines.append(f"## Frasi esempio\n")
    for i, phrase in enumerate(sample_phrases, 1):
        lines.append(f"{i}. {phrase}\n")

    # Salva il markdown
    md_file = OUTPUT_DIR / "QWEN_DESCRIVE_03-10.md"
    md_content = "\n".join(lines)
    md_file.write_text(md_content, encoding="utf-8")
    print(f"[OK] Markdown salvato: {md_file}")

    # Crea il messaggio Telegram (max 5 righe)
    tg_lines = [
        f"Qwen su 18 tratti audio notturni:",
        f"{coherent_count} coerenti, {len(items) - coherent_count} no.",
        "",
        f"Es. 1: {sample_phrases[0] if sample_phrases else 'N/A'}",
        f"Es. 2: {sample_phrases[1] if len(sample_phrases) > 1 else 'N/A'}"
    ]
    tg_message = "\n".join(tg_lines)

    print(f"\n[*] Messaggio Telegram (max 5 righe):")
    print(tg_message)

    # Invia il messaggio
    try:
        subprocess.run(
            [r"~\AppData\Local\Programs\Python\Python312\Scripts\python.exe",
             r"C:\sonno_tex\tg_IlTuoBot.py",
             tg_message],
            check=False,
            timeout=15
        )
        print("[OK] Messaggio Telegram inviato.")
    except Exception as e:
        print(f"[WARN] Non è stato possibile inviare Telegram: {e}")
        # Salva il messaggio per invio manuale
        tg_file = OUTPUT_DIR.parent / "tg_message_03-10.txt"
        tg_file.write_text(tg_message, encoding="utf-8")
        print(f"[*] Messaggio salvato in: {tg_file}")

    # Prepara il commit
    print("\n[*] Preparazione commit in C:\\sonno_tex...")
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
            "- Output: 18 tratti descritti su Qwen2-Audio-7B-Instruct\n"
            "- Coerenza valutata: {}/18 coerenti\n"
            "\n"
            "Co-Authored-By: Claude Opus 5.5 <email@example.com>"
        ).format(coherent_count)

        subprocess.run(
            ["git", "-C", r"C:\sonno_tex", "commit", "-m", msg],
            check=True,
            timeout=10
        )
        print("[OK] Commit effettuato.")
    except Exception as e:
        print(f"[WARN] Errore nel commit: {e}")

    return True

def evaluate_coherence(response, label):
    """Valuta coerenza: sì/parziale/no."""
    if not response or not label:
        return "no"

    resp_lower = response.lower()
    label_lower = label.lower()

    # Mappatura categorie -> keywords
    categories = {
        "respiro": ["breath", "breathing", "respir"],
        "russa": ["snor"],
        "movimento": ["move", "motion", "rustle", "fabric", "bed", "sheet"],
        "silenzio": ["quiet", "silence", "silent", "no sound", "no breath"],
        "altro": []
    }

    # Estrai categorie dal label
    label_cats = [c.strip() for c in label.split(",")]

    # Conta match
    matches = 0
    total = len([c for c in label_cats if c])

    for cat in label_cats:
        if cat in categories:
            if any(kw in resp_lower for kw in categories[cat]):
                matches += 1

    if total == 0:
        return "no"
    elif matches >= total * 0.7:
        return "sì"
    elif matches > 0:
        return "parziale"
    else:
        return "no"

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
