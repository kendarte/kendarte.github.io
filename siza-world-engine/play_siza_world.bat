@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Falta .venv. Ejecute setup_windows.bat primero.
  pause
  exit /b 1
)
if not exist "runtime\server\conf\settings.py" (
  echo ERROR: Falta runtime. Ejecute setup_windows.bat primero.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
pushd runtime
python -m evennia start >nul 2>&1
popd

start "" http://localhost:4001
exit /b 0
