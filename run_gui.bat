@echo off
setlocal
cd /d "%~dp0"

where py >nul 2>nul
if %ERRORLEVEL%==0 (
  py ".\src\gui_exporter.py"
  goto :done
)

where python >nul 2>nul
if %ERRORLEVEL%==0 (
  python ".\src\gui_exporter.py"
  goto :done
)

echo Python was not found.
echo Install Python 3.10 or later, then run this file again.
pause
exit /b 1

:done
