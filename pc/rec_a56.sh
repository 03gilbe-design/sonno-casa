#!/data/data/com.termux/files/usr/bin/bash
# piano (Android silenzia il microfono se parte da background). Blocchi 30' in ~/rec_a56. Stop: touch ~/rec_a56/STOP
D=$HOME/rec_a56; mkdir -p $D; rm -f $D/STOP
termux-wake-lock
while [ ! -f $D/STOP ]; do
  f=$D/$(date +%Y%m%d_%H%M%S).m4a
  termux-microphone-record -q >/dev/null 2>&1
  termux-microphone-record -f $f -l 1800 -e aac -b 64000 -r 16000 -c 1 >/dev/null
  find $D -name '*.m4a' -mtime +3 -delete
  sleep 1802
done
termux-microphone-record -q; termux-wake-unlock; echo "rec_a56 fermato"
