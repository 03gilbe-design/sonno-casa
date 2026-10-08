#!/data/data/com.termux/files/usr/bin/bash
# accelerometro 10 Hz = movimenti e respiro; luce + prossimita' 1 Hz = coperto/scoperto (sotto il cuscino).
# Si ferma da solo dopo 10 ore. Dati in ~/notte_sensori/<data>_*.json (NON in storage condiviso).
D=$HOME/notte_sensori; mkdir -p $D; T=$(date +%Y%m%d_%H%M)
termux-wake-lock
python $HOME/sensori_minuti.py
