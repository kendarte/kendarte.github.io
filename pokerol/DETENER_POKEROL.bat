@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Falta .venv.
  pause
  exit /b 1
)
if not exist "runtime\server\conf\settings.py" (
  echo ERROR: Falta runtime.
  pause
  exit /b 1
)
pushd runtime
"..\.venv\Scripts\python.exe" -m evennia stop
set "RC=%ERRORLEVEL%"
popd
exit /b %RC%
