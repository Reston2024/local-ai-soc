@echo off
rem start.cmd — wrapper for start.ps1 (requires PowerShell 7 / pwsh)
where pwsh.exe >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: PowerShell 7 ^(pwsh^) not found.
    echo Install it with:  winget install Microsoft.PowerShell
    echo Then re-run: scripts\start.cmd
    exit /b 1
)
pwsh -NoLogo -File "%~dp0start.ps1" %*
