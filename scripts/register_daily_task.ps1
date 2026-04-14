param(
    [string]$TaskName = "DailyNewsAutoPublish",
    [string]$Time = "07:00",
    [string]$Branch = "April26",
    [switch]$Unattended,
    [string]$Password
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$publishScript = Join-Path $PSScriptRoot "daily_publish.ps1"
$userName = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

$actionArgs = '-NoProfile -ExecutionPolicy Bypass -File "' + $publishScript + '" -Branch "' + $Branch + '"'
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $actionArgs
$trigger = New-ScheduledTaskTrigger -Daily -At $Time
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -WakeToRun `
    -MultipleInstances IgnoreNew `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 15) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 12)

if ($Unattended -and -not $Password) {
    throw "Unattended mode requires -Password so Windows can store the account credential for the task."
}

if ($Password) {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -User $userName `
        -Password $Password `
        -Description "Generate daily news and push results to GitHub at 07:00" `
        -Force | Out-Null

    Write-Host "Scheduled task '$TaskName' created for $Time with password-backed unattended mode."
    exit 0
}

$principal = New-ScheduledTaskPrincipal -UserId $userName -LogonType Interactive -RunLevel Limited
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "Generate daily news and push results to GitHub at 07:00" `
    -Force | Out-Null

Write-Host "Scheduled task '$TaskName' created for $Time in logged-in mode."
Write-Host "To switch to unattended mode, rerun this script with -Unattended -Password <your Windows password>."
