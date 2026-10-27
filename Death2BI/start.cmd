@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed. See the error above.
  pause
  exit /b 1
)
echo The server will print its configured HTTP or HTTPS address below.
py server.py
pause
