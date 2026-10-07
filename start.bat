@echo off
cd /d "%~dp0"
if not exist character mkdir character
if not exist character\avatar.png copy /y assets\cat.png character\avatar.png >nul
where py >nul 2>&1
if errorlevel 1 (
  echo Python is not installed. Install it from python.org and enable Add Python to PATH.
  pause
  exit /b 1
)
py -m pip install --user -r requirements.txt
if errorlevel 1 (
  echo The required packages could not be installed.
  pause
  exit /b 1
)
start "" pyw app.py
echo Running. Find the blue water-drop icon next to the Windows clock.
pause
