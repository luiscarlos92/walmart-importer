# Installer: keep window OPEN on errors, close on success.
# This version installs pywin32 + playwright and Playwright browsers.
# Run by double-clicking installer.cmd

$ErrorActionPreference = "Stop"

function Write-Info($msg)  { Write-Host $msg -ForegroundColor Cyan }
function Write-Success($m) { Write-Host $m -ForegroundColor Green }
function Write-ErrorLine($m){ Write-Host $m -ForegroundColor Red }

try {
    Write-Info "Creating virtual environment (.venv)..."
    $python = "py"
    try { & $python -V | Out-Null } catch { $python = "python" }
    & $python -m venv .venv

    Write-Info "Activating virtual environment..."
    $venvActivate = ".\.venv\Scripts\Activate.ps1"
    . $venvActivate

    Write-Info "Upgrading pip (inside venv)..."
    python -m pip install --upgrade pip

    Write-Info "Installing required packages (pywin32)..."
    python -m pip install pywin32

    Write-Info "Installing Playwright..."
    python -m pip install playwright

    Write-Info "Installing Playwright browsers (this may take a minute)..."
    python -m playwright install

    Write-Success "Installer finished successfully."
    exit 0
}
catch {
    Write-ErrorLine "`n[ERROR] $($_.Exception.Message)"
    if ($_.InvocationInfo -and $_.InvocationInfo.PositionMessage) {
        Write-ErrorLine $_.InvocationInfo.PositionMessage
    }
    Write-Host ""
    Read-Host "Press Enter to close this window"
    exit 1
}
