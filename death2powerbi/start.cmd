@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed. See the error above.
  pause
  exit /b 1
)
echo Open http://127.0.0.1:8765 in your browser.
py server.py
pause
