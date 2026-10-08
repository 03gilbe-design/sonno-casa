# Ogni 10' (attivita' SonnoBancoProva): PC fermo da >= 10' -> avvia banco_prova.py (priorita' bassa, 1 soggetto);
# PC usato -> chiude il banco (il .wav a meta' resta .part e si riscarica la volta dopo: meglio che rubargli il PC).
Add-Type @'
using System; using System.Runtime.InteropServices;
public static class Fermo {
  [StructLayout(LayoutKind.Sequential)] struct LII { public uint cbSize; public uint dwTime; }
  [DllImport("user32.dll")] static extern bool GetLastInputInfo(ref LII p);
  public static double Minuti() { var l = new LII(); l.cbSize = (uint)Marshal.SizeOf(l); GetLastInputInfo(ref l);
    return ((uint)Environment.TickCount - l.dwTime) / 60000.0; }
}
'@
$log = 'C:\sonno_tex\banco\banco_se_fermo.log'
$gira = Get-CimInstance Win32_Process -Filter "name='python.exe'" | Where-Object { $_.CommandLine -match 'banco_prova\.py' }
$fermo = [Fermo]::Minuti()
if ($fermo -lt 10 -and $gira) {
    $gira | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
    Add-Content $log "$(Get-Date -Format s) PC usato: banco chiuso"
} elseif ($fermo -ge 10 -and -not $gira) {
    $p = Start-Process python -ArgumentList 'C:\sonno_tex\banco_prova.py 1' -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput 'C:\sonno_tex\banco\ultimo.log' -RedirectStandardError 'C:\sonno_tex\banco\errori.log'
    $p.PriorityClass = 'Idle'
    Add-Content $log "$(Get-Date -Format s) PC fermo da $([int]$fermo)': banco avviato (pid $($p.Id))"
}
