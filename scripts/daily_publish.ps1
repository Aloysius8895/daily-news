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
Set-Location -LiteralPath $repoRoot

$pythonPath = Join-Path $repoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python virtual environment not found at $pythonPath"
}

function Invoke-Git {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    & git @Args
    if ($LASTEXITCODE -ne 0) {
        throw "git command failed: git $($Args -join ' ')"
    }
}

function Get-GitOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    $output = & git @Args
    if ($LASTEXITCODE -ne 0) {
        throw "git command failed: git $($Args -join ' ')"
    }
    return ($output | Out-String).Trim()
}

if (-not $Branch) {
    $Branch = Get-GitOutput -Args @("branch", "--show-current")
}

$statusOutput = Get-GitOutput -Args @("status", "--porcelain")
if ($statusOutput) {
    throw "Working tree is not clean. Commit or stash existing changes before running automation."
}

if (-not $SkipPull) {
    Invoke-Git -Args @("pull", "--rebase", "origin", $Branch)
}

$mainArgs = @("-m", "app.main")
if ($Date) {
    $mainArgs += @("--date", $Date)
}
if ($DryRun) {
    $mainArgs += "--dry-run"
}

& $pythonPath @mainArgs
if ($LASTEXITCODE -ne 0) {
    throw "Daily news pipeline failed."
}

$targetDate = if ($Date) {
    $Date
} else {
    & $pythonPath -c "from app.config import load_settings; from app.utils import get_target_date; print(get_target_date(None, load_settings().target_timezone).isoformat())"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to compute target date."
    }
}
$targetDate = ($targetDate | Out-String).Trim()
$archiveMonth = $targetDate.Substring(0, 7)

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
    Invoke-Git -Args @("push", "origin", $Branch)
}

Write-Host "Daily news pipeline completed and published for $targetDate on branch $Branch"
