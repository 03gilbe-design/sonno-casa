# sveglio o no"; dorme a orari diversi ogni giorno, un orario fisso non va). Lanciato ogni minuto dall'attivita' pianificata
# SonnoRegistraPC. Dopo 5 minuti senza input parte una sessione di 6 ore, che continua anche usando il PC.
$ErrorActionPreference = 'Stop'
Add-Type @'
using System; using System.Runtime.InteropServices;
public static class Inattivo {
  [StructLayout(LayoutKind.Sequential)] struct LII { public uint cbSize; public uint dwTime; }
  [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LII p);
  public static double Minuti() { var l = new LII(); l.cbSize = (uint)Marshal.SizeOf(l); GetLastInputInfo(ref l);
    return ((uint)Environment.TickCount - l.dwTime) / 60000.0; }
}
'@
$fermo = [Inattivo]::Minuti()
$stato = Get-ChildItem C:\sonno_audio\tre_dispositivi\*\pc_stato.json -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTime | Select-Object -Last 1
$attiva = $null
$recupero = $false
function Processo-Verificato($idRegistrato, $avvioRegistrato, $nome) {
    if (-not $idRegistrato -or -not $avvioRegistrato) { return $null }
    $p = Get-Process -Id $idRegistrato -ErrorAction SilentlyContinue
    if ($p -and $p.ProcessName -like $nome -and
        [Math]::Abs(($p.StartTime - [datetime]$avvioRegistrato).TotalSeconds) -lt 1) { return $p }
    return $null
}
if ($stato) {
    try { $s = Get-Content -LiteralPath $stato.FullName -Raw | ConvertFrom-Json } catch { $s = $null }
    if ($s -and -not $s.terminata) {
        $parent = Processo-Verificato $s.pid $s.parent_start 'powershell*'
        $child = Processo-Verificato $s.ffmpeg_pid $s.ffmpeg_start 'ffmpeg'
        $fresh = $s.heartbeat -and ((Get-Date) - [datetime]$s.heartbeat).TotalSeconds -lt 40
        if ($parent -and $fresh) { $attiva = $s }
        elseif ($s.parent_start) {
            if ($parent) { Stop-Process -Id $parent.Id -Force; $parent.WaitForExit(5000) | Out-Null }
            # Parent may die between Start-Process and persisting ffmpeg_pid.
            # Bound the fallback by parent PID, start time AND exact output pattern.
            if (-not $child -and $s.cartella) {
                $pattern = Join-Path $s.cartella 'pc_%Y%m%d_%H%M%S.flac'
                $candidates = Get-CimInstance Win32_Process -Filter "Name = 'ffmpeg.exe' AND ParentProcessId = $([int]$s.pid)" -OperationTimeoutSec 5 -ErrorAction SilentlyContinue
                foreach ($candidate in $candidates) {
                    if ($candidate.CommandLine -and $candidate.CommandLine.IndexOf($pattern, [StringComparison]::OrdinalIgnoreCase) -ge 0 -and
                        $candidate.CreationDate -ge [datetime]$s.parent_start) {
                        $orphan = Processo-Verificato $candidate.ProcessId $candidate.CreationDate 'ffmpeg'
                        if ($orphan) { Stop-Process -Id $orphan.Id -Force; $orphan.WaitForExit(5000) | Out-Null }
                    }
                }
            }
            # PID plus creation time: never stop an unrelated process after PID reuse.
            if ($child) { Stop-Process -Id $child.Id -Force; $child.WaitForExit(5000) | Out-Null }
            $recupero = [datetime]$s.fine_prevista -gt (Get-Date)
        } else {
            # Legacy state lacks process identity. Do not kill or supersede it blindly.
            if (Get-Process -Id $s.pid -ErrorAction SilentlyContinue) { $attiva = $s }
        }
    }
}
$log = "C:\sonno_audio\registra_se_dormi.log"
# Rete di sicurezza: se un ffmpeg sta gia' registrando dal microfono, non se ne avvia un altro.
$giaMic = Get-CimInstance Win32_Process -Filter "Name = 'ffmpeg.exe'" -OperationTimeoutSec 5 -ErrorAction SilentlyContinue |
          Where-Object { $_.CommandLine -like '*-f dshow*' }
if ($giaMic) { $attiva = $true }
# col PC al 100% la query WMI (timeout 5 s) e il battito (40 s) sbagliano. Il disco non sbaglia: un FLAC scritto
# negli ultimi 2' = si sta gia' registrando.
$scritto = Get-ChildItem C:\sonno_audio\tre_dispositivi\*\pc_*.flac -ErrorAction SilentlyContinue |
           Where-Object { $_.LastWriteTime -gt (Get-Date).AddMinutes(-2) } | Select-Object -First 1
if ($scritto) { $attiva = $true }
if (($fermo -ge 5 -or $recupero) -and -not $attiva) {
    $fine = (Get-Date).AddHours(6)
    Add-Content $log "$(Get-Date -Format s) PC fermo da $([int]$fermo)': avvio registrazione fino $($fine.ToString('HH:mm'))"
    # processo separato: questo controllo deve tornare subito (ogni minuto deve poter vedere se il PC e' di nuovo usato)
    Start-Process powershell.exe -WindowStyle Hidden -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"C:\sonno_bot\tecnica\app_sonno\registra_pc_notte.ps1`" -Fine `"$($fine.ToString('s'))`""
}
