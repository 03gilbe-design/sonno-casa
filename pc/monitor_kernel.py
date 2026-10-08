#!/usr/bin/env python3
"""Monitora il kernel Kaggle e scarica i risultati quando completato."""
import subprocess
import time
import json
import os
import sys

KERNEL_NAME = "utente/sonno-qwen-descrizione-audio-03-10"
OUTPUT_DIR = r"C:\sonno_audio"

def check_kernel_status():
    """Controlla lo stato del kernel."""
    try:
        result = subprocess.run(
            [r"~\AppData\Local\Programs\Python\Python312\Scripts\kaggle.exe",
             "kernels", "status", KERNEL_NAME],
            capture_output=True,
            text=True,
            timeout=30,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'}
        )
        return result.stdout
    except Exception as e:
        return f"Error: {e}"

def download_results():
    """Scarica i risultati del kernel."""
    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        subprocess.run(
            [r"~\AppData\Local\Programs\Python\Python312\Scripts\kaggle.exe",
             "kernels", "output", KERNEL_NAME, "-p", OUTPUT_DIR],
            check=True,
            timeout=120,
            env={**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1'}
        )
        print(f"[OK] Output scaricato in {OUTPUT_DIR}")
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False

def main():
    print(f"[*] Monitoraggio kernel: {KERNEL_NAME}")
    print("[*] Controlla ogni 4 minuti. Massimo 1 ora.")

    max_iterations = 15  # 15 * 4 = 60 minuti
    check_interval = 240  # 4 minuti

    for i in range(max_iterations):
        status = check_kernel_status()
        print(f"[{i+1}/{max_iterations}] Status: {status.strip()[:80]}")

        if "complete" in status.lower():
            print("[OK] Kernel completato!")
            if download_results():
                print("[DONE] Elaborazione completata.")
                return 0
            else:
                print("[ERROR] Errore nel download.")
                return 1

        if "error" in status.lower() or "failed" in status.lower():
            print("[ERROR] Kernel fallito!")
            print(status)
            return 1

        if i < max_iterations - 1:
            time.sleep(check_interval)

    print("[TIMEOUT] Kernel non completato entro 1 ora.")
    return 2

if __name__ == "__main__":
    sys.exit(main())
