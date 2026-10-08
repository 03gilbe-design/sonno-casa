#!/data/data/com.termux/files/usr/bin/bash
# Traffico ogni 60 s = la scheda wifi resta sveglia e ssh/adb rispondono.
while true; do ping -c1 -W2 192.0.2.3 >/dev/null 2>&1; sleep 60; done
