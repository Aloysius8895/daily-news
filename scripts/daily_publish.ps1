param(
    [string]$Date,
    [string]$Branch,
    [switch]$SkipPull,
    [switch]$SkipPush,
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $repoRoot "data\logs"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null
$logFile = Join-Path $logDir ("publish_{0}.log" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
Set-Location -LiteralPath $repoRoot

function Write-Log {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message,
        [ValidateSet("INFO", "WARN", "ERROR")]
        [string]$Level = "INFO"
    )

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[{0}] [{1}] {2}" -f $timestamp, $Level, $Message
    Write-Host $line
    Add-Content -LiteralPath $logFile -Value $line
}

function Write-CommandOutput {
    param(
        [object[]]$Output
    )

    foreach ($entry in $Output) {
        $line = [string]$entry
        if ($line.Length -eq 0) {
            continue
        }
        Write-Host $line
        Add-Content -LiteralPath $logFile -Value $line
    }
}

function Invoke-WithRetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action,
        [int]$MaxAttempts = 3,
        [int]$DelaySeconds = 20
    )

    for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {
        try {
            Write-Log "$Label (attempt $attempt/$MaxAttempts)"
            & $Action
            return
        } catch {
            if ($attempt -ge $MaxAttempts) {
                throw
            }

            Write-Log "$Label failed: $($_.Exception.Message). Retrying in $DelaySeconds seconds." "WARN"
            Start-Sleep -Seconds $DelaySeconds
        }
    }
}

$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python virtual environment not found at $pythonPath"
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    $output = & git @Args 2>&1
    Write-CommandOutput -Output $output
    if ($LASTEXITCODE -ne 0) {
        throw "git command failed: git $($Args -join ' ')"
    }
}

function Get-GitOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    $output = & git @Args 2>&1
    Write-CommandOutput -Output $output
    if ($LASTEXITCODE -ne 0) {
        throw "git command failed: git $($Args -join ' ')"
    }
    return ($output | Out-String).Trim()
}

Write-Log "Starting daily publish job in $repoRoot"

if (-not $Branch) {
    $Branch = Get-GitOutput -Args @("branch", "--show-current")
}

$statusOutput = Get-GitOutput -Args @("status", "--porcelain")
if ($statusOutput) {
    Write-Log "Aborting because the working tree is dirty." "ERROR"
    throw "Working tree is not clean. Commit or stash existing changes before running automation."
}

if (-not $SkipPull) {
    Invoke-WithRetry -Label "git pull --rebase origin $Branch" -Action {
        Invoke-Git -Args @("pull", "--rebase", "origin", $Branch)
    }
}

$mainArgs = @("-m", "app.main")
if ($Date) {
    $mainArgs += @("--date", $Date)
}
if ($DryRun) {
    $mainArgs += "--dry-run"
}

Invoke-WithRetry -Label "Daily news pipeline" -Action {
    $output = & $pythonPath @mainArgs 2>&1
    Write-CommandOutput -Output $output
    if ($LASTEXITCODE -ne 0) {
        throw "Daily news pipeline failed."
    }
} -MaxAttempts 2 -DelaySeconds 30

$targetDate = if ($Date) {
    $Date
} else {
    $computedDate = & $pythonPath -c "from app.config import load_settings; from app.utils import get_target_date; print(get_target_date(None, load_settings().target_timezone).isoformat())" 2>&1
    Write-CommandOutput -Output $computedDate
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to compute target date."
    }
    $computedDate
}
$targetDate = ($targetDate | Out-String).Trim()
$archiveMonth = $targetDate.Substring(0, 7)
Write-Log "Preparing generated files for $targetDate"

$pathsToStage = @(
    "data/raw/news_raw_$targetDate.json",
    "data/cleaned/news_final_$targetDate.json",
    "data/cleaned/news_final_$targetDate.md",
    "data/cleaned/news_final_$targetDate.csv",
    "data/archive/$archiveMonth/$targetDate.md"
)

$gptFiles = Get-ChildItem -Path (Join-Path $repoRoot "data\gpt_raw") -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "*$targetDate*" } |
    ForEach-Object { $_.FullName.Substring($repoRoot.Length + 1).Replace('\', '/') }

$pathsToStage += $gptFiles

$existingPaths = $pathsToStage | Where-Object {
    Test-Path -LiteralPath (Join-Path $repoRoot $_)
} | Select-Object -Unique

if (-not $existingPaths) {
    Write-Log "No generated output files found for $targetDate" "ERROR"
    throw "No generated output files found for $targetDate"
}

Invoke-Git -Args (@("add", "--") + $existingPaths)

& git diff --cached --quiet -- @existingPaths
if ($LASTEXITCODE -eq 0) {
    Write-Host "No changes to commit for $targetDate"
    exit 0
}
if ($LASTEXITCODE -ne 1) {
    throw "git diff --cached failed."
}

$commitMessage = "Daily news $targetDate"
Invoke-Git -Args @("commit", "-m", $commitMessage)

if (-not $SkipPush) {
    Invoke-WithRetry -Label "git push origin $Branch" -Action {
        Invoke-Git -Args @("push", "origin", $Branch)
    }
}

Write-Log "Daily news pipeline completed and published for $targetDate on branch $Branch"
Write-Host "Daily news pipeline completed and published for $targetDate on branch $Branch"
