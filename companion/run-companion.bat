@echo off
REM One-click launcher for the Comp Forge Party Companion.
REM 1) Close any running companion window first (so it can rebuild).
REM 2) Double-click this file.
REM 3) Click "Yes" on the Windows admin prompt.
REM It rebuilds the latest code, then runs it as Administrator with --debug.
cd /d "%~dp0"
echo Building companion (first build is slow, later ones are quick)...
dotnet build -c Release -v quiet --nologo
if errorlevel 1 (
  echo.
  echo Build failed. If it says the exe is "locked" / "used by another process",
  echo close the other companion window and run this again.
  pause
  exit /b 1
)
echo Launching as Administrator...
powershell -NoProfile -Command "Start-Process -FilePath '%~dp0bin\Release\net8.0\compforge-companion.exe' -ArgumentList '--debug' -Verb RunAs"
