#!/data/data/com.termux/files/usr/bin/bash
# (120 s se incerto/in transizione, 600 s se certo e stabile da >= 20'); qui si dorme quel tempo (limiti 60-900 s).
# NON scrive stato_storia.csv: lo scarto audio resta spento (vedi ~/SCARTO_ATTIVO in sonno_tel.py).
export PYTHONWARNINGS=ignore
cd "$HOME"
while true; do
  timeout 90 python "$HOME/stato.py" >/dev/null 2>>"$HOME/stato_loop.err"
  N=$(python -c "import json;n=json.load(open('stato.json')).get('intervallo_s',120);print(max(60,min(900,int(n))))" 2>/dev/null || echo 120)
  sleep "${N:-120}"
done
