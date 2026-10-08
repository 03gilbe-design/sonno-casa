#!/data/data/com.termux/files/usr/bin/sh
# Termux:Boot: servizi e watchdog del sonno.
export HOME=/data/data/com.termux/files/home
export PREFIX=/data/data/com.termux/files/usr
export PATH="$PREFIX/bin:$PATH"
. "$PREFIX/etc/profile.d/start-services.sh"
sv up sshd 2>/dev/null
sv up crond 2>/dev/null

pidfile="$HOME/.a56_watchdog.pid"
if [ -f "$pidfile" ] && kill -0 "$(cat "$pidfile")" 2>/dev/null; then
    exit 0
fi
nohup sh "$HOME/a56_watchdog.sh" >>"$HOME/a56_watchdog.log" 2>&1 </dev/null &
