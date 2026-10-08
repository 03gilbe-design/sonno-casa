#!/data/data/com.termux/files/usr/bin/sh
# Watchdog A56: mantiene controllo remoto e automazione sonno senza intervento manuale.
LOG="$HOME/a56_watchdog.log"
echo $$ > "$HOME/.a56_watchdog.pid"

while true; do
    # Raccolta indipendente dai tempi degli altri controlli, una volta al minuto.
    if ! pgrep -f '^python .*/segnale_uso[.]py --loop' >/dev/null 2>&1; then
        nohup python "$HOME/segnale_uso.py" --loop >>"$LOG" 2>&1 </dev/null &
    fi
    if ! pgrep -x sshd >/dev/null 2>&1; then
        sshd >>"$LOG" 2>&1
        echo "$(date '+%F %T') sshd riavviato" >>"$LOG"
    fi

    if ! pgrep -f '^python .*/sonno_webhook[.]py' >/dev/null 2>&1; then
        nohup python "$HOME/sonno_webhook.py" >>"$HOME/sonno_webhook.log" 2>&1 </dev/null &
        echo "$(date '+%F %T') webhook riavviato" >>"$LOG"
    fi

    "$HOME/sonno_app.sh"

    H=$(date +%H)
    if { [ "$H" -ge 22 ] || [ "$H" -lt 6 ]; } && ! pgrep -f 'sensori_minuti[.]py' >/dev/null 2>&1; then
        nohup python "$HOME/sensori_minuti.py" >>"$HOME/sensori_notte.log" 2>&1 </dev/null &
        echo "$(date '+%F %T') sensori notte avviati" >>"$LOG"
    fi
    # di giorno). <=20% e non in carica -> risparmio energetico di Android + sensori fermi (10 Hz consumano).
    # settings da Termux richiede WRITE_SECURE_SETTINGS (dato dal PC via adb, aggiorna_a56). ponytail: soglia 20%
    B=$(termux-battery-status 2>/dev/null | tr -d ' ",')
    P=$(echo "$B" | grep '^percentage:' | cut -d: -f2)
    if [ -n "$P" ] && [ "$P" -le 20 ] && echo "$B" | grep -q '^plugged:UNPLUGGED'; then
        if [ "$(settings get global low_power 2>/dev/null)" != "1" ]; then
            settings put global low_power 1 >>"$LOG" 2>&1
            echo "$(date '+%F %T') batteria $P%: risparmio energetico acceso" >>"$LOG"
        fi
        pkill -f 'sensori_minuti[.]py' && echo "$(date '+%F %T') batteria $P%: sensori fermati" >>"$LOG"
    fi
    sleep 60
done
