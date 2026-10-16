@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 "%~dp0scripts\installer.py" launch --agent-args gui
  exit /b %ERRORLEVEL%
)
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  python "%~dp0scripts\installer.py" launch --agent-args gui
  exit /b %ERRORLEVEL%
)
echo Python 3.11+ is required.
pause
exit /b 2
