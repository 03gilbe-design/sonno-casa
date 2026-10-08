#!/data/data/com.termux/files/usr/bin/sh
# Requires python, coreutils, procps, cronie and Termux:Boot.
timeout 8 termux-wake-lock
{ crontab -l 2>/dev/null | grep -v '# sonno-rec-watch';
  echo '* * * * * python "$HOME/rec_guard.py" --watch >> "$HOME/rec_watch.log" 2>&1 # sonno-rec-watch';
} | crontab -
pgrep -x crond >/dev/null || crond
python "$HOME/rec_guard.py" --watch
pgrep -f '^sh .*/tieni_wifi.sh$' >/dev/null || nohup setsid sh "$HOME/tieni_wifi.sh" >/dev/null 2>&1 < /dev/null &
