@echo off
cd /d "%~dp0"
python -m venv .venv
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto error
npm install --prefix frontend
if errorlevel 1 goto error
if not exist "frontend\node_modules\electron\dist\electron.exe" node "frontend\node_modules\electron\install.js"
if errorlevel 1 goto error
npm run build --prefix frontend
if errorlevel 1 goto error
echo.
echo Crimson Atlas is ready. Use "Start Crimson Atlas.bat".
pause
exit /b 0
:error
echo.
echo Setup failed. Check the internet connection and Python installation.
pause
exit /b 1
