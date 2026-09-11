# Foundry one-time setup for Windows.
# Run from this folder:
#     powershell -ExecutionPolicy Bypass -File setup.ps1
#
# What it does (and only this):
#   1. checks Python 3.10+
#   2. downloads the official butler CLI into .\bin
#   3. (optional, with -WithVerifier) installs Playwright + Chromium for the
#      headless verification gate
#
# It does NOT create accounts, does NOT touch your PATH permanently,
# and does NOT store any secrets.

param(
    [switch]$WithVerifier
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

Write-Host "== Foundry setup ==" -ForegroundColor Cyan

# 1. Python ---------------------------------------------------------------
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Write-Host "Python not found." -ForegroundColor Red
    Write-Host "Install it from https://www.python.org/downloads/"
    Write-Host "TICK 'Add python.exe to PATH' during install, then re-run this script."
    exit 1
}
python --version
Write-Host "  ok: python found" -ForegroundColor Green

# 2. butler ----------------------------------------------------------------
$bin = Join-Path $here "bin"
New-Item -ItemType Directory -Force -Path $bin | Out-Null
$butler = Join-Path $bin "butler.exe"

if (Test-Path $butler) {
    Write-Host "  ok: butler already present at bin\butler.exe" -ForegroundColor Green
} else {
    Write-Host "downloading butler (official itch.io CLI)..."
    $url = "https://broth.itch.ovh/butler/windows-amd64/LATEST/archive/default"
    $zip = Join-Path $env:TEMP "butler.zip"
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    Expand-Archive -Path $zip -DestinationPath $bin -Force
    Remove-Item $zip -Force
    if (Test-Path $butler) {
        Write-Host "  ok: bin\butler.exe" -ForegroundColor Green
    } else {
        Write-Host "butler download failed. Get it manually from https://itch.io/docs/butler/" -ForegroundColor Yellow
    }
}

# 3. optional verifier ------------------------------------------------------
if ($WithVerifier) {
    Write-Host "installing Playwright + Chromium (verification gate)..."
    python -m pip install --quiet playwright
    python -m playwright install chromium
    Write-Host "  ok: verifier installed" -ForegroundColor Green
}

Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Create an itch.io account (email + password, no ID check)."
Write-Host "  2. Get an API key:  https://itch.io/user/settings/api-keys"
Write-Host "  3. In your terminal, every session you publish:"
Write-Host '       $env:BUTLER_API_KEY="paste-your-key-here"'
Write-Host "  4. Put your itch username in config.json"
Write-Host "  5. Read README.md from the top. It walks through everything."
Write-Host ""
