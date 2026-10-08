param([datetime]$Fine = (Get-Date).Date.AddHours(16))
$ErrorActionPreference = 'Stop'
$mutex = New-Object System.Threading.Mutex($false, 'Global\SonnoTreDispositiviPC')
try { $owned = $mutex.WaitOne(0, $false) } catch [System.Threading.AbandonedMutexException] { $owned = $true }
if (-not $owned) { $mutex.Dispose(); exit 0 }
$encoder = $null
try {
    if ($Fine -le (Get-Date)) { $Fine = (Get-Date).Date.AddDays(1).AddHours(16) }
    (Get-Process -Id $PID).PriorityClass = 'Idle'
    $mic = "Microphone Array (Tecnologia Intel$([char]0x00AE) Smart Sound per microfoni digitali)"
    $outDir = "C:\sonno_audio\tre_dispositivi\$($Fine.ToString('yyyyMMdd'))"
    New-Item -Path $outDir -ItemType Directory -Force | Out-Null
    $statusPath = Join-Path $outDir 'pc_stato.json'
    $logPath = Join-Path $outDir 'pc_ffmpeg.log'
    $gapPath = Join-Path $outDir 'buchi.csv'
    $gap = $null
    $cause = ''
    if (Test-Path -LiteralPath $statusPath) {
        try {
            $old = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
            if (-not $old.terminata) {
                $gap = if ($old.gap_start) { [datetime]$old.gap_start } elseif ($old.audio_at) { [datetime]$old.audio_at } else { Get-Date }
                $cause = if ($old.gap_cause) { $old.gap_cause } else { 'processo PC interrotto' }
            }
        } catch { $gap = Get-Date; $cause = 'stato PC non leggibile' }
    }
    $state = @{
        pid = $PID; parent_start = (Get-Process -Id $PID).StartTime.ToString('o')
        iniziata = (Get-Date).ToString('o'); fine_prevista = $Fine.ToString('o')
        microfono = $mic; cartella = $outDir
        gap_start = $(if ($gap) { $gap.ToString("o") } else { $null }); gap_cause = $cause
    }
    function Save-State {
        $state.heartbeat = (Get-Date).ToString('o')
        $state | ConvertTo-Json | Set-Content -LiteralPath "$statusPath.tmp" -Encoding UTF8
        Move-Item -LiteralPath "$statusPath.tmp" -Destination $statusPath -Force
    }
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class SonnoPower {
    [DllImport("kernel32.dll")]
    public static extern uint SetThreadExecutionState(uint flags);
}
"@
    $continuous = [uint32]2147483648
    [SonnoPower]::SetThreadExecutionState([uint32]($continuous -bor 1)) | Out-Null
    Save-State
    while ((Get-Date) -lt $Fine) {
        try {
            $seconds = [Math]::Max(1, [int]($Fine - (Get-Date)).TotalSeconds)
            $pattern = Join-Path $outDir 'pc_%Y%m%d_%H%M%S.flac'
            $arguments = "-hide_banner -loglevel warning -f dshow -audio_buffer_size 100 -i `"audio=$mic`" -t $seconds -ac 1 -ar 16000 -c:a flac -f segment -segment_time 1800 -reset_timestamps 1 -strftime 1 `"$pattern`""
            $encoder = Start-Process ffmpeg -WindowStyle Hidden -ArgumentList $arguments -RedirectStandardError $logPath -PassThru
            $state.ffmpeg_pid = $encoder.Id
            $state.ffmpeg_start = $encoder.StartTime.ToString('o')
            $lastGrowth = Get-Date
            $signature = ''
            Save-State
            while (-not $encoder.HasExited -and (Get-Date) -lt $Fine) {
                Start-Sleep -Seconds 10
                $audio = Get-ChildItem -LiteralPath $outDir -Filter 'pc_*.flac' -File |
                    Sort-Object LastWriteTime | Select-Object -Last 1
                if ($audio -and $audio.Length -gt 0 -and $audio.LastWriteTime -ge $encoder.StartTime) {
                    $next = "$($audio.Name):$($audio.Length)"
                    if ($next -ne $signature) {
                        $signature = $next
                        $lastGrowth = Get-Date
                        if ($gap) {
                            [pscustomobject]@{inizio=$gap.ToString('s');fine=$lastGrowth.ToString('s');causa=$cause} |
                                Export-Csv -LiteralPath $gapPath -NoTypeInformation -Append -Encoding UTF8
                            $gap = $null
                            $state.Remove('gap_start'); $state.Remove('gap_cause')
                        }
                    }
                }
                $state.audio_at = $lastGrowth.ToString('o')
                Save-State
                if (((Get-Date) - $lastGrowth).TotalSeconds -ge 40) { throw 'file non cresce' }
                $encoder.Refresh()
            }
            if ((Get-Date) -ge $Fine) { $encoder.WaitForExit(5000) | Out-Null }
            if ((Get-Date) -lt $Fine) { throw "ffmpeg terminato ($($encoder.ExitCode))" }
        } catch {
            if (-not $gap) { $gap = $lastGrowth; if (-not $gap) { $gap = Get-Date }; $cause = $_.Exception.Message }
            $state.gap_start = $gap.ToString('o'); $state.gap_cause = $cause
            Add-Content -LiteralPath $logPath -Value "$(Get-Date -Format s) recupero: $cause"
        } finally {
            if ($encoder -and -not $encoder.HasExited) { $encoder.Kill(); $encoder.WaitForExit(5000) | Out-Null }
            $encoder = $null
            $state.ffmpeg_pid = $null
            if (-not $gap) { $state.Remove('gap_start'); $state.Remove('gap_cause') }
            Save-State
        }
        if ((Get-Date) -lt $Fine) { Start-Sleep -Seconds 10 }
    }
} finally {
    if ($encoder -and -not $encoder.HasExited) { $encoder.Kill() }
    if ('SonnoPower' -as [type]) { [SonnoPower]::SetThreadExecutionState([uint32]2147483648) | Out-Null }
    try { if ($state) { $state.terminata = (Get-Date).ToString('o'); Save-State } }
    finally { $mutex.ReleaseMutex(); $mutex.Dispose() }
}
