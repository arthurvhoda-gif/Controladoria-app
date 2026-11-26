param([switch]$Ativar)
$ErrorActionPreference='Stop'
if (-not $Ativar) { throw 'Use -Ativar apenas apos validar o ciclo sem envio.' }
$nome='HAIZE Intelligence V80 Semanal Real'
$antigo='HAIZE Intelligence V80 Homologacao'
if (Get-ScheduledTask -TaskName $nome -ErrorAction SilentlyContinue) { throw 'Tarefa real ja existe. Nao sera sobrescrita.' }
$old=Get-ScheduledTask -TaskName $antigo -ErrorAction SilentlyContinue
if (-not $old -or $old.State -eq 'Running') { throw 'Tarefa de homologacao ausente ou em execucao. Nenhuma alteracao.' }
$repo=Split-Path -Parent $PSScriptRoot
$script=Join-Path $PSScriptRoot 'intelligence_semanal_real_v80.py'
$python=(& py -3 -c 'import sys; print(sys.executable)')
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $python -PathType Leaf) -or -not (Test-Path -LiteralPath $script -PathType Leaf)) { throw 'Executor ou Python ausente.' }
$cred=Join-Path $env:LOCALAPPDATA 'HaizeIntelligenceV80\gmail-homologacao.dpapi'
if (-not (Test-Path -LiteralPath $cred -PathType Leaf)) { throw 'Credencial Gmail ausente.' }
$acao=New-ScheduledTaskAction -Execute $python -Argument ('-B "'+$script+'" --executar-semanal') -WorkingDirectory $repo
$gatilho=New-ScheduledTaskTrigger -Weekly -WeeksInterval 1 -DaysOfWeek Saturday -At ([DateTime]::Today.AddHours(7).AddMinutes(45))
$principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$config=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 15) -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$config.Enabled=$false
$oldEnabled=$old.State -ne 'Disabled'
$created=$false
try {
 Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $gatilho -Principal $principal -Settings $config -Description 'HAIZE Intelligence: parecer local semanal privado; sem banco do app.' | Out-Null
 $created=$true
 Disable-ScheduledTask -TaskName $antigo | Out-Null
 Enable-ScheduledTask -TaskName $nome | Out-Null
} catch {
 if ($created) { Disable-ScheduledTask -TaskName $nome -ErrorAction SilentlyContinue | Out-Null }
 if ($oldEnabled) { Enable-ScheduledTask -TaskName $antigo -ErrorAction SilentlyContinue | Out-Null }
 throw
}
Get-ScheduledTask -TaskName $nome,$antigo | Select-Object TaskName,State
Get-ScheduledTaskInfo -TaskName $nome | Select-Object NextRunTime,LastRunTime,LastTaskResult
