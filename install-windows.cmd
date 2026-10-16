@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  py -3 "%~dp0scripts\installer_gui.py"
  exit /b %ERRORLEVEL%
)
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  python "%~dp0scripts\installer_gui.py"
  exit /b %ERRORLEVEL%
)
echo Python 3.11 or newer with Tkinter is required.
echo Install Python from its official publisher and rerun this launcher.
pause
exit /b 2
