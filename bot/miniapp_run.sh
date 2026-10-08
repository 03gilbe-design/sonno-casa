#!/data/data/com.termux/files/usr/bin/bash
# Supervisore Mini App (Termux): tiene vivi server (miniapp.py) e tunnel cloudflared; scrive l'URL in miniapp_url.txt
# (miniapp.py lo legge e aggiorna il pulsante 🎧 della chat). Un'istanza sola. Partenza: boot (start.sh/boot_start.sh) o a mano.
cd "$HOME/sonno_bot" || exit 1
exec 9>"$HOME/.miniapp_run.lock"; flock -n 9 || exit 0
PORT=8765
while true; do
  pgrep -f "[p]ython .*miniapp.py" >/dev/null || (nohup setsid python "$HOME/sonno_bot/miniapp.py" >>miniapp.log 2>&1 < /dev/null 9>&- &)
  # per sempre su un URL morto -> Mini App "non va". Lo chiudo: il giro sotto ne apre uno nuovo con URL nuovo.
  tail -5 miniapp_cf.log 2>/dev/null | grep -q "Tunnel not found" && pkill -f "[c]loudflared tunnel"
  if ! pgrep -f "[c]loudflared tunnel" >/dev/null; then
    rm -f miniapp_url.txt
    : > miniapp_cf.log
    (nohup setsid cloudflared tunnel --no-autoupdate --protocol http2 --url "http://127.0.0.1:$PORT" >>miniapp_cf.log 2>&1 < /dev/null 9>&- &)
  fi
  U=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' miniapp_cf.log 2>/dev/null | tail -1)
  [ -n "$U" ] && [ "$(cat miniapp_url.txt 2>/dev/null)" != "$U" ] && echo "$U" > miniapp_url.txt
  sleep 15
done
