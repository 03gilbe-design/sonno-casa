#!/bin/bash
# Commit di tutto in C:\sonno_bot e C:\sonno_tex (add -A) con la riga Co-Authored-By. Uso:
#   commit.sh "messaggio"      |   commit.sh -n   (solo cosa cambierebbe, non committa)
# Il modello nella riga si cambia con MODELLO="Claude Opus 5.5".
M=${MODELLO:-Claude Opus 5.5}
for d in /c/sonno_bot /c/sonno_tex; do
  cd "$d" || continue; [ -d .git ] || git init -q -b main
  if [ "$1" = "-n" ]; then echo "$d: $(git status -s | wc -l) file cambiati"; continue; fi
  git add -A 2>/dev/null
  git -c core.autocrlf=true commit -q -m "$1

Co-Authored-By: $M <email@example.com>" 2>/dev/null
  echo "$d :: $(git log --oneline | head -1)"
done
