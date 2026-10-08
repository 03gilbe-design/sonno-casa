#!/usr/bin/env python3
"""Carica e esegue il kernel Qwen su Kaggle GPU."""
import json
import subprocess
import sys

# Metadata del kernel
kernel_metadata = {
    "id": "utente-utente/sonno-qwen-descrive-03-10",
    "title": "Sonno Qwen - Descrizione audio 03-10",
    "code_file": "qwen_runner.py",
    "language": "python",
    "kernel_type": "script",
    "is_private": True,
    "enable_gpu": True,
    "enable_internet": True,
    "dataset_sources": ["utente/sonno-contesto-0310", "utente/sonno-contesto-code"]
}

# Salva il metadata
with open(r"C:\sonno_tex\kernel_metadata.json", "w") as f:
    json.dump(kernel_metadata, f, indent=2)

print("Metadata kernel salvato.")
print("\nPer eseguire su Kaggle:")
print(f"1. Copia C:\\sonno_tex\\kaggle_lab\\contesto_0310\\run_kaggle.py a C:\\sonno_tex\\qwen_runner.py")
print("2. Esegui: kaggle kernels push -p C:\\sonno_tex")
print("   (richiede kernel_metadata.json e qwen_runner.py nella stessa directory)")
