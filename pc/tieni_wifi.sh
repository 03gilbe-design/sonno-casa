#!/data/data/com.termux/files/usr/bin/sh
# Traffico in USCITA ogni 10 s tiene sveglia la radio. Un solo loop: pidfile.
# riaccendeva -> dopo 6 ping falliti di fila (~1') si spegne e riaccende il Wi-Fi (termux-wifi-enable), max 1 volta ogni 5'.
P=$HOME/.tieni_wifi.pid
[ -f $P ] && kill -0 $(cat $P) 2>/dev/null && exit 0
echo $$ > $P
falliti=0; ultimo=0
while true; do
  if ping -c1 -W2 192.0.2.139 >/dev/null 2>&1 || ping -c1 -W2 192.0.2.134 >/dev/null 2>&1 || ping -c1 -W2 192.0.2.3 >/dev/null 2>&1 || ping -c1 -W3 8.8.8.8 >/dev/null 2>&1; then
    falliti=0
  else
    falliti=$((falliti + 1))
    ora=$(date +%s)
    if [ $falliti -ge 6 ] && [ $((ora - ultimo)) -ge 300 ]; then
      echo "$(date '+%F %T') rete giu' da ~1': riaccendo il Wi-Fi" >> $HOME/tieni_wifi.log
      timeout 15 termux-wifi-enable false; sleep 5; timeout 15 termux-wifi-enable true
      ultimo=$ora; falliti=0
    fi
  fi
  sleep 10
done
