#!/data/data/com.termux/files/usr/bin/bash
export SONNO_DIR="$HOME/rec" PYTHONWARNINGS=ignore
timeout 8 termux-wake-lock
exec python "$HOME/rec_guard.py" --loop
