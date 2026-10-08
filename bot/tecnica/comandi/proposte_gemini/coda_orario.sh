#!/bin/bash
# Schedula ed esegue un comando o agente ad un orario prefissato (o dopo un'attesa relativa),
# con attesa opzionale del completamento di altri job in corso (es. codex, python).
# Salva l'output in un log con timestamp e mostra tempo impiegato ed esito.
#
# Sostituisce la sequenza manuale ripetuta decine di volte nel dataset:
#   now=$(date +%s); t=$(date -d "HH:MM" +%s); [ $t -gt $now ] && sleep $((t-now)); while tasklist | grep ...; do sleep 60; done; ...
#
# Uso:
#   ./coda_orario.sh +15m "python sonno.py sync"
#   ./coda_orario.sh 19:26 --attendi codex "cd /c/sonno_bot && ..."
#   ./coda_orario.sh adesso --attendi python "python /c/sonno_tex/sonno_audio.py sync"

set -e

if [ $# -lt 2 ]; then
  echo "Uso: $0 [-n] <orario|+minuti|adesso> [--attendi <processo>] [--log <file>] <comando>"
  echo "Esempi:"
  echo "  $0 05:33 \"codex exec -s workspace-write -C C:/sonno_bot '...'\""
  echo "  $0 +30m \"python sonno.py sync\""
  echo "  $0 adesso --attendi codex \"python sonno.py sync\""
  exit 1
fi

DRY_RUN=0
if [ "$1" = "-n" ]; then
  DRY_RUN=1
  shift
fi

ORARIO="$1"
shift

ATTENDI_PROC=""
CUSTOM_LOG=""

while [ $# -gt 0 ]; do
  case "$1" in
    --attendi)
      ATTENDI_PROC="$2"
      shift 2
      ;;
    --log)
      CUSTOM_LOG="$2"
      shift 2
      ;;
    *)
      break
      ;;
  esac
done

COMANDO="$*"

if [ -z "$COMANDO" ]; then
  echo "ERRORE: Nessun comando specificato da eseguire!"
  exit 1
fi

# Se il comando contiene 'codex' e non è stato esplicitato --attendi, imposta default
if [ -z "$ATTENDI_PROC" ] && echo "$COMANDO" | grep -qi "codex"; then
  ATTENDI_PROC="codex"
fi

# 1. Calcolo del ritardo (in secondi)
NOW=$(date +%s)
SECONDI=0

if [ "$ORARIO" = "adesso" ] || [ "$ORARIO" = "now" ] || [ "$ORARIO" = "0" ]; then
  SECONDI=0
elif [[ "$ORARIO" =~ ^\+([0-9]+)m$ ]]; then
  MINUTI="${BASH_REMATCH[1]}"
  SECONDI=$((MINUTI * 60))
elif [[ "$ORARIO" =~ ^\+([0-9]+)s$ ]]; then
  SECONDI="${BASH_REMATCH[1]}"
elif [[ "$ORARIO" =~ ^\+([0-9]+)h$ ]]; then
  ORE="${BASH_REMATCH[1]}"
  SECONDI=$((ORE * 3600))
else
  # Formato orario tipo HH:MM o HH:MM:SS
  TARGET=$(date -d "$ORARIO" +%s 2>/dev/null || true)
  if [ -z "$TARGET" ]; then
    echo "ERRORE: Formato orario non valido: '$ORARIO'"
    exit 2
  fi
  # Se l'orario di oggi è già passato, si intende domani
  if [ "$TARGET" -le "$NOW" ]; then
    TARGET=$(date -d "tomorrow $ORARIO" +%s 2>/dev/null)
  fi
  SECONDI=$((TARGET - NOW))
fi

ORA_TARGET=$(date -d "@$((NOW + SECONDI))" "+%Y-%m-%d %H:%M:%S" 2>/dev/null || echo "tra $SECONDI secondi")

echo "=== CODA PROGRAMMATA ==="
echo "⏰ Orario attuale: $(date '+%Y-%m-%d %H:%M:%S')"
echo "🎯 Partenza prevista: $ORA_TARGET (attesa: ${SECONDI}s / $((SECONDI / 60))m)"
[ -n "$ATTENDI_PROC" ] && echo "⏳ Attesa accodamento se attivo processo: '$ATTENDI_PROC'"
echo "💻 Comando: $COMANDO"

if [ "$DRY_RUN" -eq 1 ]; then
  echo "[DRY-RUN] Script terminato senza attendere né eseguire."
  exit 0
fi

# 2. Attesa dell'orario
if [ "$SECONDI" -gt 0 ]; then
  echo "Attesa in corso..."
  sleep "$SECONDI"
fi

# 3. Attesa che eventuali processi bloccanti finiscano
if [ -n "$ATTENDI_PROC" ]; then
  echo "Verifica disponibilità (nessun '$ATTENDI_PROC' in corso)..."
  while tasklist 2>/dev/null | grep -qi "$ATTENDI_PROC" || pgrep -f "$ATTENDI_PROC" >/dev/null 2>&1; do
    echo "   [$(date +%H:%M:%S)] Processo '$ATTENDI_PROC' ancora attivo, attendo 30s..."
    sleep 30
  done
  echo "Coda libera, procedo all'esecuzione."
fi

# 4. Preparazione cartella log
LOG_DIR="/c/sonno_bot/tasks_log"
mkdir -p "$LOG_DIR" 2>/dev/null || LOG_DIR="$(dirname "$0")/logs"
mkdir -p "$LOG_DIR" 2>/dev/null || LOG_DIR="/tmp"

if [ -n "$CUSTOM_LOG" ]; then
  LOG_FILE="$CUSTOM_LOG"
else
  TIMESTAMP=$(date +%Y%m%d_%H%M%S)
  LOG_FILE="$LOG_DIR/job_${TIMESTAMP}.log"
fi

echo "🚀 Avvio esecuzione: $(date '+%Y-%m-%d %H:%M:%S')"
echo "📝 Log salvato in: $LOG_FILE"
echo "--------------------------------------------------"

T_START=$(date +%s)
RC=0

# Esecuzione comando con log completo
eval "$COMANDO" > "$LOG_FILE" 2>&1 || RC=$?

T_END=$(date +%s)
DURATA=$((T_END - T_START))

echo "--------------------------------------------------"
if [ $RC -eq 0 ]; then
  echo "🎉 COMPLETATO CON SUCCESSO (rc=0, durata: ${DURATA}s)"
else
  echo "❌ FALLITO (rc=$RC, durata: ${DURATA}s)"
fi

echo "Estratto ultime 10 righe del log ($LOG_FILE):"
tail -n 10 "$LOG_FILE" 2>/dev/null || true

exit $RC
