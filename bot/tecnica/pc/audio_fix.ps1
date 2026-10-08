# Ripara l'audio del Lenovo 82HS (Realtek ALC257 su Intel Smart Sound): eseguito come amministratore.
# Reversibile: punto di ripristino + il driver generico di Windows resta sempre disponibile.
$log = "$env:TEMPudio_fix.log"
Start-Transcript -Path $log -Force | Out-Null
"== 1. punto di ripristino"
try { Enable-ComputerRestore -Drive "C:\" -ErrorAction Stop; Checkpoint-Computer -Description "Prima driver audio Realtek (Claude)" -RestorePointType MODIFY_SETTINGS -ErrorAction Stop; "ok" } catch { "non creato: $($_.Exception.Message)" }
"== 2. riavvio Intel Smart Sound OED (errore 43)"
$oed = Get-PnpDevice -PresentOnly | Where-Object { $_.FriendlyName -match 'OED' }
if ($oed) { pnputil /restart-device "$($oed.InstanceId)"; Start-Sleep 5; "OED stato: " + (Get-PnpDevice -InstanceId $oed.InstanceId).Status }
"== 3. driver Realtek (gia' nel PC) sulla scheda audio"
pnputil /add-driver C:\Windows\INF\oem121.inf /install
Start-Sleep 8
"== 4. risultato"
Get-PnpDevice -PresentOnly | Where-Object { $_.Class -in 'MEDIA','AudioEndpoint' -or $_.FriendlyName -match 'Smart Sound' } | Format-Table Status, Class, FriendlyName -AutoSize | Out-String
Stop-Transcript | Out-Null
