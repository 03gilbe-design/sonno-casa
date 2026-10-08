#!/bin/bash
# Legge l'output di un task in background (id = nome del file .output). Uso:
#   task.sh bo4cphtou [righe]     (ultime 40 di default)   |   task.sh   -> elenca i task piu' recenti
D=$(ls -dt ~/AppData/Local/Temp/claude/C--Users-utente-utente/*/tasks | head -1)
[ -z "$1" ] && { ls -t "$D" | head -10; exit; }
tail -n "${2:-40}" "$D/$1.output"
