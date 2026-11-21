@echo off
rem Tailor launcher for Windows. Double click this file.
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Get it from https://www.python.org/downloads/
  echo Tick "Add Python to PATH" when you install it, then run this file again.
  pause
  exit /b 1
)
if not exist ".venv" (
  echo First run: setting things up. This takes a minute...
  python -m venv .venv
)
call ".venv\Scripts\activate.bat"
python -m pip install --quiet --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo Could not install what Tailor needs. Check your internet and try again.
  pause
  exit /b 1
)
python app.py
pause
