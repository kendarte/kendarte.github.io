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

call "%~dp0sync_siza_arena.bat"
if errorlevel 1 (
  echo ERROR: No se pudo sincronizar Siza Arena.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
pushd runtime

echo ============================================
echo SIZA WORLD ENGINE

echo Webclient: http://localhost:4001
echo Ollama:    http://127.0.0.1:11434

echo Para ver logs: evennia -l

echo ============================================
python -m evennia start
if errorlevel 1 evennia start

popd
pause
