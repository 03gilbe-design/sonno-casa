# silenzio.ps1        -> spegne le attivita' che possono partire da sole (registrazione, sync, sessioni Claude)
#                        e chiude una registrazione del PC in corso (il microfono puo' servire all'esame)
# silenzio.ps1 -Fine  -> le riaccende
param([switch]$Fine)
$T = 'SonnoRegistraPC', 'SonnoAudioSync', 'ClaudeResumeSonno', 'ClaudeResumeSchemiBD', 'SonnoBancoProva'
$log = 'C:\sonno_audio\silenzio.log'
if ($Fine) {
    foreach ($t in $T) { Enable-ScheduledTask -TaskName $t | Out-Null }
    Add-Content $log "$(Get-Date -Format s) fine silenzio: riaccese $($T -join ', ')"
    return
}
foreach ($t in $T) { Disable-ScheduledTask -TaskName $t | Out-Null }
Get-ChildItem C:\sonno_audio\tre_dispositivi\*\pc_stato.json -ErrorAction SilentlyContinue | ForEach-Object {
    $s = Get-Content $_.FullName -Raw | ConvertFrom-Json
    if (-not $s.terminata -and (Get-Process -Id $s.pid -ErrorAction SilentlyContinue)) {
        taskkill /PID $s.pid /T /F | Out-Null  # anche ffmpeg figlio
        Add-Content $log "$(Get-Date -Format s) chiusa registrazione PC pid $($s.pid)"
    }
}
Get-CimInstance Win32_Process -Filter "name='python.exe' or name='ffmpeg.exe'" |
    Where-Object { $_.CommandLine -match 'banco_prova\.py|dshow' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Add-Content $log "$(Get-Date -Format s) chiuso $($_.Name) $($_.ProcessId)" }
Add-Content $log "$(Get-Date -Format s) inizio silenzio: spente $($T -join ', ')"

