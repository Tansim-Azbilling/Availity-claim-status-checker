# Build Availity Automation with PyInstaller using the project .venv.
# Outputs:
#   dist/Availity Automation.exe
#   dist/Availity Automation_onedir/Availity Automation.exe
# Uses azbilling-new-logo.png for the Windows .exe icon and bundled GUI branding.

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$LogoPng = Join-Path $Root "azbilling-new-logo.png"
$LogoIco = Join-Path $Root "azbilling-new-logo.ico"

if (-not (Test-Path $Python)) {
    Write-Error "Missing .venv. Create it and install dependencies first:`n  python -m venv .venv`n  .\.venv\Scripts\pip install -r requirements.txt pyinstaller"
}

if (-not (Test-Path $LogoPng)) {
    Write-Error "Missing app logo: $LogoPng"
}

Set-Location $Root

Write-Host "Preparing app icon from azbilling-new-logo.png..."
& $Python (Join-Path $Root "build_icon.py") $LogoPng $LogoIco
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Building onefile..."
& $Python -m PyInstaller --noconfirm --clean Availity_Automation_onefile.spec
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Building onedir..."
& $Python -m PyInstaller --noconfirm --clean Availity_Automation_onedir.spec
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Done."
Write-Host "  logo:    azbilling-new-logo.png (GUI + source)"
Write-Host "  icon:    azbilling-new-logo.ico (Windows .exe)"
Write-Host "  onefile: dist\Availity Automation.exe"
Write-Host "  onedir:  dist\Availity Automation_onedir\Availity Automation.exe"
