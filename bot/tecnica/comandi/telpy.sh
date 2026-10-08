#!/bin/bash
# Esegue sul telefono il python letto da stdin, dentro ~/sonno_bot, con sys.path HOME/sonno_bot e senza rumore
# di Warning/findfont. Uso:
#   ./telpy.sh <<'EOF'
#   import bot; print(bot.leggi_csv("notti.csv")[-1])
#   EOF
# (TEL=ip per l'altro telefono)  Il codice viaggia in base64: nessun problema di virgolette.
B=$(base64 -w0)
"$(dirname "$0")/tel.sh" "cd ~/sonno_bot && echo $B | base64 -d | PYTHONPATH=\$HOME/sonno_bot:\$HOME python -W ignore - 2>&1 | grep -v -i -E 'warn|findfont'"
