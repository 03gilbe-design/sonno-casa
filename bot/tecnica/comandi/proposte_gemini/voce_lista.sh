#!/bin/bash
# Aggiunge una voce (o segna completata) in C:\sonno_bot\LISTA.md e crea il commit Git.
#
# Sostituisce la sequenza ripetuta oltre 130 volte nel dataset:
#   python heredoc per leggere LISTA.md, r.replace(...), open("w").write(...) && bash commit.sh "lista: ..."
#
# Uso:
#   ./voce_lista.sh "descrizione nuova idea"               -> aggiunge sotto ## URGENTE e committa
#   ./voce_lista.sh "descrizione" "Grafica"               -> aggiunge in fondo alla sezione "## Grafica / concept"
#   ./voce_lista.sh --fatto "testo da cercare"            -> trasforma "- [ ] ...testo..." in "- [x] DD/MM ...testo..." e committa
#   ./voce_lista.sh --corso "testo da cercare"            -> trasforma in "- [~] DD/MM ...testo..." (in corso) e committa
#   ./voce_lista.sh -n "descrizione"                      -> solo anteprima (dry-run), non modifica né committa
#
# Riusa: commit.sh (nella cartella superiore) per eseguire il commit con Co-Authored-By

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LISTA_PATH="/c/sonno_bot/LISTA.md"
[ -f "$LISTA_PATH" ] || LISTA_PATH="$DIR/../../LISTA.md"
COMMIT_SH="$DIR/../commit.sh"

if [ $# -eq 0 ]; then
  echo "Uso: $0 <descrizione> [sezione]"
  echo "     $0 --fatto <testo-voce>"
  echo "     $0 --corso <testo-voce>"
  echo "     $0 -n <descrizione> [sezione] (dry-run)"
  exit 1
fi

DRY_RUN=0
MODO="aggiungi"

if [ "$1" = "-n" ]; then
  DRY_RUN=1
  shift
fi

if [ "$1" = "--fatto" ] || [ "$1" = "-x" ]; then
  MODO="fatto"
  shift
  TESTO="$*"
elif [ "$1" = "--corso" ] || [ "$1" = "-~" ]; then
  MODO="corso"
  shift
  TESTO="$*"
else
  TESTO="$1"
  SEZIONE="${2:-URGENTE}"
fi

export MODO TESTO SEZIONE DRY_RUN LISTA_PATH
export PYTHONIOENCODING=utf-8

MSG=$(MSYS_NO_PATHCONV=1 python - <<'EOF'
import os, sys, re
from datetime import datetime

modo = os.environ.get("MODO", "aggiungi")
testo = os.environ.get("TESTO", "").strip()
sezione_target = os.environ.get("SEZIONE", "URGENTE").strip().lower()
dry_run = os.environ.get("DRY_RUN", "0") == "1"
p = os.environ.get("LISTA_PATH", "LISTA.md")

if not os.path.exists(p):
    print(f"ERRORE: File {p} non trovato!", file=sys.stderr)
    sys.exit(1)

content = open(p, "r", encoding="utf-8").read()
today = datetime.now().strftime("%d/%m")

if modo in ("fatto", "corso"):
    simbolo = "x" if modo == "fatto" else "~"
    pattern = re.compile(r"^(\s*-\s*\[)[ ~xX](\]\s*.*" + re.escape(testo) + r".*)$", re.MULTILINE)
    match = pattern.search(content)
    if not match:
        # Ricerca parziale flessibile per parole chiave
        words = [re.escape(w) for w in testo.split() if len(w) > 3]
        if words:
            flex_pattern = re.compile(r"^(\s*-\s*\[)[ ~xX](\]\s*.*" + ".*".join(words) + r".*)$", re.MULTILINE)
            match = flex_pattern.search(content)

    if not match:
        print(f"ERRORE: Nessuna voce trovata corrispondente a: '{testo}'", file=sys.stderr)
        sys.exit(2)

    vecchia_riga = match.group(0)
    # Se non c'è già una data dopo la spunta, aggiungila
    resto = match.group(2)
    if not re.search(r"\]\s*\d{2}/\d{2}", resto):
        resto = re.sub(r"\]\s*", f"] {today} ", resto, count=1)

    nuova_riga = f"{match.group(1)}{simbolo}{resto}"

    if dry_run:
        print(f"[DRY-RUN] Modificherei:\n- VECCHIA: {vecchia_riga}\n+ NUOVA:   {nuova_riga}")
        sys.exit(0)

    content = content[:match.start()] + nuova_riga + content[match.end():]
    open(p, "w", encoding="utf-8").write(content)
    print(f"lista: [{simbolo}] {testo[:60]}")

else:
    # Aggiungi nuova voce sotto la sezione corretta
    # Cerca intestazione sezione tipo "## URGENTE" o "## Grafica / concept"
    lines = content.splitlines(keepends=True)
    idx_target = -1
    for i, line in enumerate(lines):
        if line.startswith("## ") and sezione_target in line.lower():
            idx_target = i
            break

    if idx_target == -1:
        # Sezione non trovata: ripiega su URGENTE o prima sezione ##
        for i, line in enumerate(lines):
            if line.startswith("## "):
                idx_target = i
                break

    if idx_target == -1:
        insert_idx = len(lines)
    else:
        # Trova la fine della sezione (prima della prossima sezione ## o fine file)
        insert_idx = len(lines)
        for i in range(idx_target + 1, len(lines)):
            if lines[i].startswith("## "):
                # Inserisci prima della riga vuota che precede la nuova sezione
                insert_idx = i - 1 if (i > 0 and lines[i-1].strip() == "") else i
                break

    riga_nuova = f"- [ ] {today} {testo}\n"

    if dry_run:
        sezione_nome = lines[idx_target].strip() if idx_target != -1 else "Fine file"
        print(f"[DRY-RUN] Inserirei in '{sezione_nome}':\n+ {riga_nuova.strip()}")
        sys.exit(0)

    lines.insert(insert_idx, riga_nuova)
    open(p, "w", encoding="utf-8").writelines(lines)
    print(f"lista: + {testo[:60]}")
EOF
)

if [ "$DRY_RUN" -eq 1 ]; then
  exit 0
fi

echo "LISTA.md aggiornato: $MSG"
if [ -x "$COMMIT_SH" ]; then
  "$COMMIT_SH" "$MSG"
else
  cd /c/sonno_bot && git add LISTA.md && git commit -m "$MSG"
fi
