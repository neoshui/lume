# Lume Launcher - Windows build
# Right-click -> "Run with PowerShell"

param(
    [switch]$BuildInstaller
)

$ErrorActionPreference = "Stop"
$PROJ = Split-Path -Parent $PSScriptRoot
Set-Location $PROJ

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Python not found!" -ForegroundColor Red
    exit 1
}

Write-Host "Installing pinned build dependencies..." -ForegroundColor Green
& python -m pip install --disable-pip-version-check --quiet `
    "PySide6==6.11.1" "PyInstaller==6.21.0" "pypinyin==0.55.0" "Pillow>=10"
if ($LASTEXITCODE -ne 0) { exit 1 }

& python scripts\validate_version.py
if ($LASTEXITCODE -ne 0) { exit 1 }

& python scripts\create_windows_icon.py
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "Building Lume..." -ForegroundColor Green
& python -m PyInstaller --clean Lume.spec
if ($LASTEXITCODE -ne 0 -or -not (Test-Path dist\Lume.exe)) {
    Write-Host "[ERROR] PyInstaller failed!" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Path release -Force | Out-Null
Copy-Item dist\Lume.exe release\Lume-windows-x86_64-portable.exe -Force

if ($BuildInstaller) {
    if (-not (Get-Command iscc -ErrorAction SilentlyContinue)) {
        $iscc = Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"
    } else {
        $iscc = (Get-Command iscc).Source
    }
    if (-not (Test-Path $iscc)) {
        Write-Host "[ERROR] Inno Setup ISCC.exe not found!" -ForegroundColor Red
        exit 1
    }
    $version = (& python scripts\validate_version.py).Trim()
    & $iscc "/DMyAppVersion=$version" installer\Lume.iss
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path release\Lume-windows-x86_64-Setup.exe)) {
        Write-Host "[ERROR] Inno Setup failed!" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Portable: $(Join-Path $PROJ 'release\Lume-windows-x86_64-portable.exe')" -ForegroundColor Yellow
if ($BuildInstaller) {
    Write-Host "Installer: $(Join-Path $PROJ 'release\Lume-windows-x86_64-Setup.exe')" -ForegroundColor Yellow
}
