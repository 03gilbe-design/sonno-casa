$log = "C:\sonno_audio\deploy_attesa.log"
$remoto = @'
mv ~/rec.sh.new ~/rec.sh
pkill -f 'sonno_bot/[b]ot.py'; sleep 2
cd ~/sonno_bot && nohup setsid python ~/sonno_bot/bot.py >> ~/sonno_bot/bot.log 2>&1 < /dev/null &
sleep 3; echo "bot: $(pgrep -f 'sonno_bot/[b]ot.py' | wc -l)"
bash $PREFIX/tmp/riavvia_ma.sh >/dev/null 2>&1; sleep 4
uptime -p; termux-microphone-record -i | grep -o 'isRecording[^,]*'
termux-battery-status | grep -e percentage -e plugged
echo "miniapp: $(pgrep -f '[m]iniapp.py' | wc -l)"
'@
$remoto = $remoto -replace "`r", ""
Add-Content $log "$(Get-Date -Format s) attesa avviata"
for ($i = 0; $i -lt 300; $i++) {
  $ip = (& C:\Python310\python.exe -c "import sys; sys.path.insert(0, r'C:\sonno_tex'); import a21; print(a21.ip())" 2>$null | Select-Object -Last 1)
  $o = ssh -p 8022 -o ConnectTimeout=6 -o BatchMode=yes "-o" "HostKeyAlias=[192.0.2.184]:8022" $ip "echo ok" 2>$null
  if ($o -eq "ok") {
    scp -q -P 8022 "-o" "HostKeyAlias=[192.0.2.184]:8022" C:\sonno_tex\rec_a21s_tel.sh "${ip}:rec.sh.new"
    scp -q -P 8022 "-o" "HostKeyAlias=[192.0.2.184]:8022" C:\sonno_bot\miniapp.html C:\sonno_bot\bot.py C:\sonno_bot\grafo_stati.html "${ip}:sonno_bot/"
    $r = ssh -p 8022 -o ConnectTimeout=6 -o BatchMode=yes "-o" "HostKeyAlias=[192.0.2.184]:8022" $ip $remoto 2>&1
    Add-Content $log "$(Get-Date -Format s) A21s tornato ($ip): installati rec.sh, miniapp.html, bot.py, grafo`n$($r -join "`n")"
    exit
  }
  Start-Sleep 60
}
Add-Content $log "$(Get-Date -Format s) A21s mai tornato in 5 h"
