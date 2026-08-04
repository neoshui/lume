@echo off
chcp 65001 >nul
cd /d "%~dp0.."

echo ===== Lume Windows Build =====

where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found!
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%CD%\scripts\build_windows.ps1" -BuildInstaller
if errorlevel 1 (
    echo [ERROR] Build failed!
    exit /b 1
)

echo Portable: %CD%\release\Lume-windows-x86_64-portable.exe
echo Installer: %CD%\release\Lume-windows-x86_64-Setup.exe
