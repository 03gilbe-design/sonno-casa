#!/data/data/com.termux/files/usr/bin/sh
h=$(date +%H)
[ "$h" -ge 21 ] || [ "$h" -lt 13 ] || exit 0
flag=$HOME/.sonno_app_$(date -d '-14 hours' +%Y%m%d)   # una "notte" = dalle 14 del giorno prima
[ -f "$flag" ] && exit 0
termux-battery-status | grep -q '"plugged": "UNPLUGGED"' && exit 0
am broadcast -p com.urbandroid.sleep -a com.urbandroid.sleep.alarmclock.START_SLEEP_TRACK >/dev/null 2>&1 || exit 0
touch "$flag"
sleep 20  # mentre registra, Sleep as Android tiene una notifica (serve "accesso notifiche" a Termux:API)
if timeout 15 termux-notification-list 2>/dev/null | grep -q com.urbandroid.sleep; then esito="registra OK"
else esito="NON verificato (notifica non vista)"; fi
echo "$(date '+%F %T') avviato, $esito" >> "$HOME/sonno_app.log"
