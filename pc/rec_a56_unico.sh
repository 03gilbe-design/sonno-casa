#!/data/data/com.termux/files/usr/bin/bash
# rec_a56_unico.sh - registrazione notturna A56: UN file unico (-l 0), da lanciare con Termux in PRIMO PIANO
# (Android silenzia il microfono se parte da background). Lo digita guardiano_dispositivi.py via adb input text.
D=$HOME/rec_a56; mkdir -p $D
termux-wake-lock
termux-microphone-record -q >/dev/null 2>&1
termux-microphone-record -f $D/notte_$(date +%Y%m%d_%H%M%S).m4a -l 0 -e aac -b 64000 -r 16000 -c 1
