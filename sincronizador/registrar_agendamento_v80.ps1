param([string]$Horario='08:00', [switch]$Atualizar)
$ErrorActionPreference='Stop'
$nome='HAIZE Intelligence V80 Homologacao'
if ($Horario -notmatch '^([01]\d|2[0-3]):[0-5]\d$') { throw 'Horario invalido.' }
$existente=Get-ScheduledTask -TaskName $nome -ErrorAction SilentlyContinue
if ($existente -and -not $Atualizar) { throw 'Tarefa existente. Use -Atualizar somente se desejar substitui-la.' }
$repo=Split-Path -Parent $PSScriptRoot
$script=Join-Path $PSScriptRoot 'intelligence_agendado_v80.py'
if (-not (Test-Path -LiteralPath $script -PathType Leaf)) { throw 'Executor ausente.' }
$python=(& py -3 -c 'import sys; print(sys.executable)')
if ($LASTEXITCODE -ne 0 -or -not $python -or -not (Test-Path -LiteralPath $python -PathType Leaf)) { throw 'Python nao encontrado.' }
$cred=Join-Path $env:LOCALAPPDATA 'HaizeIntelligenceV80\neon-homologacao.dpapi'
if (-not (Test-Path -LiteralPath $cred -PathType Leaf)) { throw 'Configure a credencial primeiro.' }
$acao=New-ScheduledTaskAction -Execute $python -Argument ('-B "'+$script+'" --executar --competencia 2026-06') -WorkingDirectory $repo
$at=[DateTime]::Today.Add([TimeSpan]::ParseExact($Horario,'hh\:mm',[Globalization.CultureInfo]::InvariantCulture))
$gatilho=New-ScheduledTaskTrigger -Daily -At $at
$principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$config=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 15) -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $gatilho -Principal $principal -Settings $config -Description 'HAIZE Intelligence: homologacao local, sem envio, sem acesso a producao.' -Force:$Atualizar | Out-Null
Get-ScheduledTask -TaskName $nome | Select-Object TaskName,State
Get-ScheduledTaskInfo -TaskName $nome | Select-Object NextRunTime,LastRunTime,LastTaskResult
