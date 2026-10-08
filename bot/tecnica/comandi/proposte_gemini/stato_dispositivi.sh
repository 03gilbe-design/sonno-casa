#!/bin/bash
# Controlla lo stato di registrazione e salute di tutti i dispositivi del sonno (A21s, A56, PC).
# Interroga microfono, processi di registrazione, bot Telegram, batteria e memoria.
#
# Sostituisce la sequenza ripetuta oltre 160 volte nel dataset:
#   ssh ... termux-microphone-record -i | grep isRec; pgrep rec.sh; pgrep bot.py; termux-battery-status; ...
#
# Uso:
#   ./stato_dispositivi.sh            -> controllo completo (A21s + A56 + PC)
#   ./stato_dispositivi.sh a21s       -> solo A21s (telefono principale .182)
#   ./stato_dispositivi.sh a56        -> solo A56 (telefono personale .52)
#   ./stato_dispositivi.sh pc         -> solo processi locali PC
#
# Riusa: tel.sh (nella cartella superiore) con TEL=ip per interrogare entrambi i telefoni

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEL_SH="$DIR/../tel.sh"

TARGET="${1:-tutti}"
TARGET=$(echo "$TARGET" | tr '[:upper:]' '[:lower:]')

controllo_a21s() {
  echo "=================================================="
  echo "📱 TELEFONO A21s (192.0.2.184 - Microfono & Bot)"
  echo "=================================================="

  if [ ! -x "$TEL_SH" ]; then
    echo "ERRORE: $TEL_SH non trovato o non eseguibile"
    return 1
  fi

  # Esegue query diagnostica sul telefono in un unico comando remoto
  CMD_REMOTO='
    echo "---REC---"
    termux-microphone-record -i 2>/dev/null | grep -o "\"isRecording\": [a-z]*" || echo "isRecording: sconosciuto"
    echo "---PAUSA---"
    [ -f ~/sonno_bot/PAUSA ] && echo "ATTIVA" || echo "no"
    echo "---LOOP---"
    pgrep -fc "^bash .*home/[r]ec.sh"
    echo "---BOT---"
    pgrep -fa "^python .*bot[.]py" | grep -v pgrep | head -2
    echo "---BATTERIA---"
    termux-battery-status 2>/dev/null | grep -E "percentage|plugged" | tr -d " ,\t\""
    echo "---DISCO---"
    df -h /data 2>/dev/null | awk "NR==2 {print \$4 \" liberi su \" \$2}" || df -h ~ | awk "NR==2 {print \$4 \" liberi\"}"
  '

  OUT=$(T=15 "$TEL_SH" "$CMD_REMOTO" 2>&1)
  RC=$?

  if [ $RC -ne 0 ]; then
    echo "⚠️  A21s NON RAGGIUNGIBILE via SSH (Wi-Fi spento o IP cambiato? rc=$RC)"
    echo "   Dettaglio: $OUT"
    return 1
  fi

  IS_REC=$(echo "$OUT" | grep -A1 -- "---REC---" | tail -1)
  PAUSA=$(echo "$OUT" | grep -A1 -- "---PAUSA---" | tail -1)
  LOOP_COUNT=$(echo "$OUT" | grep -A1 -- "---LOOP---" | tail -1)
  BOT_PROC=$(echo "$OUT" | sed -n '/---BOT---/,/---BATTERIA---/p' | grep -v -- "---")
  BATT=$(echo "$OUT" | sed -n '/---BATTERIA---/,/---DISCO---/p' | grep -v -- "---")
  DISCO=$(echo "$OUT" | grep -A1 -- "---DISCO---" | tail -1)

  # Analisi microfono
  if echo "$IS_REC" | grep -q "true"; then
    echo "🎙️  Microfono:   [REGISTRA ATTIVAMENTE]"
  elif [ "$PAUSA" = "ATTIVA" ]; then
    echo "⏸️  Microfono:   [IN PAUSA VOLONTARIA - file ~/sonno_bot/PAUSA presente]"
  else
    echo "🛑 Microfono:   [NON STA REGISTRANDO]"
  fi

  # Analisi loop
  if [ "$LOOP_COUNT" -eq 1 ] 2>/dev/null; then
    echo "🔄 Loop audio:  [OK - 1 processo rec.sh attivo]"
  elif [ "$LOOP_COUNT" -gt 1 ] 2>/dev/null; then
    echo "⚠️  Loop audio:  [ATTENZIONE - $LOOP_COUNT processi rec.sh in conflitto!]"
  else
    echo "❌ Loop audio:  [FERMO - nessun rec.sh attivo]"
  fi

  # Analisi bot Telegram
  if [ -n "$BOT_PROC" ]; then
    echo "🤖 Bot Telegram:[ATTIVO] $BOT_PROC"
  else
    echo "❌ Bot Telegram:[NON IN ESECUZIONE]"
  fi

  echo "🔋 Batteria:    $BATT"
  echo "💾 Disco:       $DISCO"
  echo ""
}

controllo_a56() {
  echo "=================================================="
  echo "📱 TELEFONO A56 (192.0.2.54 - Webhook & Sonno)"
  echo "=================================================="

  if [ ! -x "$TEL_SH" ]; then
    echo "ERRORE: $TEL_SH non trovato o non eseguibile"
    return 1
  fi

  CMD_REMOTO='
    echo "---WEBHOOK---"
    pgrep -fa "^python .*sonno_webhook" | grep -v pgrep | head -2
    echo "---CRON---"
    pgrep -fc "crond"
    echo "---BATTERIA---"
    termux-battery-status 2>/dev/null | grep -E "percentage|plugged" | tr -d " ,\t\""
    echo "---DISCO---"
    df -h /data 2>/dev/null | awk "NR==2 {print \$4 \" liberi su \" \$2}" || df -h ~ | awk "NR==2 {print \$4 \" liberi\"}"
  '

  OUT=$(TEL=192.0.2.54 T=15 "$TEL_SH" "$CMD_REMOTO" 2>&1)
  RC=$?

  if [ $RC -ne 0 ]; then
    echo "⚠️  A56 NON RAGGIUNGIBILE via SSH (rc=$RC)"
    echo "   Dettaglio: $OUT"
    return 1
  fi

  WEBHOOK=$(echo "$OUT" | sed -n '/---WEBHOOK---/,/---CRON---/p' | grep -v -- "---")
  CRON_COUNT=$(echo "$OUT" | grep -A1 -- "---CRON---" | tail -1)
  BATT=$(echo "$OUT" | sed -n '/---BATTERIA---/,/---DISCO---/p' | grep -v -- "---")
  DISCO=$(echo "$OUT" | grep -A1 -- "---DISCO---" | tail -1)

  if [ -n "$WEBHOOK" ]; then
    echo "🌐 Webhook:     [ATTIVO] $WEBHOOK"
  else
    echo "⚠️  Webhook:     [NON ATTIVO]"
  fi

  if [ "$CRON_COUNT" -ge 1 ] 2>/dev/null; then
    echo "⏰ Cron watchdog: [OK - crond attivo]"
  else
    echo "❌ Cron watchdog: [FERMO]"
  fi

  echo "🔋 Batteria:    $BATT"
  echo "💾 Disco:       $DISCO"
  echo ""
}

controllo_pc() {
  echo "=================================================="
  echo "💻 PC (Processi locali Sonno / Registrazione)"
  echo "=================================================="

  PROCS=$(ps -ef 2>/dev/null | grep -E -i "python|ffmpeg" | grep -E -i "sonno|banco|insieme|calibra|rec" | grep -v grep)
  if [ -n "$PROCS" ]; then
    echo "▶️  Processi sonno in corso sul PC:"
    echo "$PROCS" | awk '{printf "   PID %-6s: %s\n", $2, $8}'
  else
    echo "💤 Nessun processo audio/bot in esecuzione sul PC"
  fi
  echo ""
}

case "$TARGET" in
  a21s|182)
    controllo_a21s
    ;;
  a56|52)
    controllo_a56
    ;;
  pc)
    controllo_pc
    ;;
  tutti|all|*)
    controllo_a21s
    controllo_a56
    controllo_pc
    ;;
esac
