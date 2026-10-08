#!/bin/bash
# Controllo sintassi python (ast) + caratteri di controllo sporchi (controlla_file.py). Uso:
#   sintassi.sh                     -> bot.py e sonno_tel.py
#   sintassi.sh file1.py file2.py
F=("$@"); [ $# -eq 0 ] && F=(/c/sonno_bot/bot.py /c/sonno_tex/sonno_tel.py)
PYTHONIOENCODING=utf-8 python -c "
import ast,sys
for p in sys.argv[1:]:
    try: ast.parse(open(p,encoding='utf-8').read()); print('sintassi ok', p)
    except SyntaxError as e: print('ERRORE', p, e); sys.exit(1)" "${F[@]}" && python "$(dirname "$0")/../controlla_file.py" "${F[@]}"
