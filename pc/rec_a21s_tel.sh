# Copia di ~/rec.sh dell'A21s (quello che gira davvero; rec.sh qui accanto e' un'altra versione mai usata).
# Deploy: scp -P 8022 rec_a21s_tel.sh <a21s>:rec.sh
# Gira in Termux sull'A21s. Registra blocchi da 30' SOLO quando il telefono e' in carica, e dopo ogni blocco lo
# analizza sul telefono (sonno_tel.py) a priorita' minima.
# Tutto in ~/rec (home di Termux): visibile anche quando il loop e' lanciato da run-as (che NON vede /sdcard).
# Termux:API ha lo stesso utente di Termux, quindi puo' scrivere qui.
export SONNO_DIR=$HOME/rec PYTHONWARNINGS=ignore
D=$SONNO_DIR
mkdir -p "$D"
termux-wake-lock
while true; do
  # bot @IlTuoBot sempre vivo (e il bot tiene vivo questo loop)
  pgrep -f "sonno_bot/bot.py" >/dev/null || (cd ~/sonno_bot && nohup setsid python ~/sonno_bot/bot.py >> ~/sonno_bot/bot.log 2>&1 < /dev/null &)
  # protezione batteria all'85% non si sa come Samsung riporta "plugged")
  b=$(termux-battery-status)
  pct=$(echo "$b" | grep -o '"percentage": [0-9]*' | grep -o '[0-9]*$')
  # niente piu' soglia del 20%; sotto il 30% si saltano le analisi pesanti (sotto) per far durare la batteria.
  if true; then
    termux-microphone-record -q >/dev/null 2>&1
    # (-91 dB). Prova di 3 s prima di ogni blocco: se e' silenzio, Termux in primo piano (permesso "sopra altre app"
    # dato via adb) e si riprova; se resta muto lo si scrive in ~/rec/MUTO (lo legge il guardiano).
    for prova in 1 2; do
      t=$PREFIX/tmp/prova_mic.m4a; rm -f $t
      termux-microphone-record -e aac -b 64 -r 16000 -c 1 -l 3 -f $t >/dev/null; sleep 5
      db=$(ffmpeg -hide_banner -nostats -i $t -af volumedetect -f null - 2>&1 | grep -o 'mean_volume: -[0-9.]*' | grep -o '[0-9.]*$')
      [ -n "$db" ] && [ "${db%.*}" -lt 85 ] && { rm -f "$D/MUTO"; break; }
      echo "$(date '+%F %T') mic muto (${db:-?} dB): apro Termux" >> "$D/MUTO"
      am start -n com.termux/.app.TermuxActivity >/dev/null 2>&1; sleep 4
    done
    termux-microphone-record -e aac -b 64 -r 16000 -c 1 -l 1800 -f "$D/$(date +%Y%m%d_%H%M%S).m4a" >/dev/null
    sleep 1802
  else
    sleep 120
  fi
  # un solo lavoro pesante alla volta (CODEX_PIPELINE): lucchetto occupato = si salta, i blocchi restano per il giro dopo
  [ "${pct:-100}" -lt 30 ] && { echo "$(date '+%F %T') analisi saltata: batteria ${pct}%" >> ~/analizza.log; continue; }
  (flock -n 9 || { echo "$(date '+%F %T') analisi saltata: lucchetto occupato"; exit 0; }
   nice -n 19 python ~/sonno_tel.py analizza; nice -n 19 python ~/conferma.py) 9>~/.analisi.lock >> ~/analizza.log 2>&1 &
done
