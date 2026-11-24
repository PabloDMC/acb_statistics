<#
Actualización automática: descarga lo nuevo, reconstruye la base y la publica en Hugging Face.

  Ejecutar a mano:          .\scripts\scheduled_update.ps1
  Programarla (una vez):    .\scripts\scheduled_update.ps1 -Register
  Quitar la programación:   Unregister-ScheduledTask -TaskName "ACB Statistics update" -Confirm:$false

Se programa a diario a las 05:30 y, si el PC estaba apagado a esa hora, se lanza en cuanto se
encienda (StartWhenAvailable). Si no hay partidos nuevos, publish_db.py no sube nada.
El registro de cada ejecución queda en logs\update_AAAAMMDD_HHMM.log.
#>
param([switch]$Register, [string]$At = "05:30")

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"

if ($Register) {
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -WorkingDirectory $Root
    $trigger = New-ScheduledTaskTrigger -Daily -At $At
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Hours 3)
    Register-ScheduledTask -TaskName "ACB Statistics update" -Action $action -Trigger $trigger `
        -Settings $settings -Description "Ingesta ACB + dbt + publicar en Hugging Face" -Force | Out-Null
    Write-Host "Tarea 'ACB Statistics update' programada a diario a las $At."
    exit 0
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root "logs") | Out-Null
$Log = Join-Path $Root ("logs\update_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmm"))
Set-Location $Root
$env:PYTHONIOENCODING = "utf-8"

& $Python scripts\update_data.py *>&1 | Tee-Object -FilePath $Log
if ($LASTEXITCODE -ne 0) { Write-Host "update_data falló; no se publica."; exit 1 }

& $Python scripts\publish_db.py *>&1 | Tee-Object -FilePath $Log -Append
exit $LASTEXITCODE
