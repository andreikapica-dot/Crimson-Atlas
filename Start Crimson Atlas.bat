@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Crimson Atlas is not set up yet. Run "Setup Crimson Atlas.bat" once.
  pause
  exit /b 1
)
if not exist "frontend\node_modules\electron\dist\electron.exe" (
  echo Crimson Atlas desktop window is not set up yet. Run "Setup Crimson Atlas.bat" once.
  pause
  exit /b 1
)
"frontend\node_modules\electron\dist\electron.exe" "desktop\electron-main.cjs"
if errorlevel 1 pause
