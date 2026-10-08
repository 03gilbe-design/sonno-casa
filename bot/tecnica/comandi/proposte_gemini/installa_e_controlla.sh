#!/bin/bash
# Esegue il ciclo completo di rilascio del bot:
# 1. Controllo sintassi locale (sintassi.sh)
# 2. Test del bot su PC (prova_bot.py, a meno di --rapido)
# 3. Installazione sul telefono A21s (sonno.py installa)
# 4. Verifica processo bot attivo sul telefono via tel.sh (pgrep bot.py)
# 5. Smoke test sul telefono via telpy.sh (import bot; bot.stato())
# 6. Lettura e segnalazione di errori.log e bot.log remoti
#
# Risolve il limite di prova_bot_tel.sh (che si fermava a "installa" senza verificare il telefono).
# Sostituisce la sequenza ripetuta oltre 110 volte nel dataset.
#
# Uso:
#   ./installa_e_controlla.sh             -> ciclo completo: sintassi + prova + installa + verifica tel
#   ./installa_e_controlla.sh --rapido    -> salta prova_bot.py locale, fa sintassi + installa + verifica tel
#   ./installa_e_controlla.sh --solo-tel  -> salta l'installazione, controlla solo processo e log sul telefono
#
# Riusa: sintassi.sh, tel.sh, telpy.sh

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SINTASSI_SH="$DIR/../sintassi.sh"
TEL_SH="$DIR/../tel.sh"
TELPY_SH="$DIR/../telpy.sh"

MODO="completo"
[ "$1" = "--rapido" ] && MODO="rapido"
[ "$1" = "--solo-tel" ] && MODO="solo-tel"

echo "=== CICLO DEPLOY & VERIFICA BOT ==="

if [ "$MODO" != "solo-tel" ]; then
  # 1. Controllo sintassi
  echo "1/5. Controllo sintassi..."
  if [ -x "$SINTASSI_SH" ]; then
    "$SINTASSI_SH" /c/sonno_bot/bot.py /c/sonno_tex/sonno_tel.py || {
      echo "❌ ERRORE SINTASSI: Deploy abortito!"
      exit 1
    }
  else
    python -m py_compile /c/sonno_bot/bot.py || { echo "❌ ERRORE SINTASSI!"; exit 1; }
  fi

  # 2. Test PC facoltativo
  if [ "$MODO" = "completo" ]; then
    echo "2/5. Prova locale bot.py su PC..."
    (cd /c/sonno_bot && PYTHONIOENCODING=utf-8 timeout 120 python -W ignore prova_bot.py 2>&1 | tail -4) || {
      echo "❌ PROVA LOCALE FALLITA: Deploy abortito!"
      exit 1
    }
  else
    echo "2/5. Prova locale saltata (--rapido)"
  fi

  # 3. Deploy sul telefono
  echo "3/5. Installazione sul telefono A21s (sonno.py installa)..."
  (cd /c/sonno_bot && timeout 180 python sonno.py installa 2>&1 | tail -4) || {
    echo "❌ INSTALLAZIONE FALLITA!"
    exit 1
  }

  echo "Attesa stabilizzazione processo (3s)..."
  sleep 3
else
  echo "Modalità --solo-tel: verifica stato remoto senza reinstallare"
fi

# 4. Verifica processo sul telefono
echo "4/5. Controllo processo bot.py sul telefono..."
if [ ! -x "$TEL_SH" ]; then
  echo "⚠️  $TEL_SH non trovato: impossibile verificare il telefono"
  exit 1
fi

PROC_INFO=$("$TEL_SH" "pgrep -fa '^python .*bot[.]py' | grep -v pgrep" 2>&1 || true)
PROC_COUNT=$(echo "$PROC_INFO" | grep -v "^$" | wc -l)

if [ "$PROC_COUNT" -eq 0 ]; then
  echo "❌ ATTENZIONE CRITICA: Il bot NON è in esecuzione sul telefono!"
elif [ "$PROC_COUNT" -gt 1 ]; then
  echo "⚠️  ATTENZIONE: Trovati $PROC_COUNT processi bot in esecuzione contemporaneamente!"
  echo "$PROC_INFO"
else
  echo "✅ Processo attivo: $PROC_INFO"
fi

# 5. Smoke test sul telefono
echo "5/5. Smoke test e lettura log remoti..."
if [ -x "$TELPY_SH" ]; then
  echo "   Test import e stato():"
  "$TELPY_SH" <<'EOF' || echo "   ⚠️ Smoke test fallito!"
import bot
s = bot.stato()
print("   -> Stato bot:", s[0] if isinstance(s, (list, tuple)) else s)
EOF
fi

# Controllo errori.log e bot.log
echo ""
echo "--- ULTIMI ERRORI SUL TELEFONO (~/sonno_bot/errori.log) ---"
ERRORI=$("$TEL_SH" "tail -n 8 ~/sonno_bot/errori.log 2>/dev/null" 2>&1 || echo "Nessun file errori.log")
if [ -n "$ERRORI" ] && [ "$ERRORI" != "Nessun file errori.log" ]; then
  echo "$ERRORI"
  if echo "$ERRORI" | grep -i -E "traceback|error|exception" >/dev/null; then
    echo "⚠️  ATTENZIONE: Trovati errori recenti in errori.log!"
  else
    echo "   (Nessun errore critico recente)"
  fi
else
  echo "   (Vuoto o non presente: ottimo)"
fi

echo ""
echo "--- ULTIME RIGHE LOG BOT (~/sonno_bot/bot.log) ---"
"$TEL_SH" "tail -n 5 ~/sonno_bot/bot.log 2>/dev/null" 2>&1 || true

echo ""
if [ "$PROC_COUNT" -eq 1 ]; then
  echo "🎉 ESITO: DEPLOY COMPLETATO, BOT ATTIVO E VERIFICATO"
else
  echo "⚠️  ESITO: DEPLOY EFFETTUATO MA STATO PROCESSO ANOMALO (vedi sopra)"
  exit 2
fi
