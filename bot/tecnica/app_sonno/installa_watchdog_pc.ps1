# Run during deployment, after reviewing the recording changes. Does not start recording now.
$ErrorActionPreference = 'Stop'
$task = Get-ScheduledTask -TaskName 'SonnoRegistraPC'
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File "C:\sonno_bot\tecnica\app_sonno\registra_se_dormi.ps1"'
$settings = $task.Settings
$settings.MultipleInstances = 'IgnoreNew'
Set-ScheduledTask -TaskName $task.TaskName -TaskPath $task.TaskPath -Trigger $trigger -Action $action -Settings $settings | Out-Null
