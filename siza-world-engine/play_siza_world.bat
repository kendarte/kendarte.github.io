@echo off
setlocal EnableExtensions
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

echo ============================================
echo SIZA WORLD ENGINE - PLAY

echo Sincronizando codigo de Siza...
robocopy overlay runtime /E /NFL /NDL /NJH /NJS /NP >nul
set RC=%ERRORLEVEL%
if %RC% GEQ 8 (
  echo ERROR: robocopy fallo con codigo %RC%.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
pushd runtime

python -m evennia start >nul 2>&1
if errorlevel 1 (
  evennia start >nul 2>&1
  if errorlevel 1 (
    popd
    echo ERROR: No se pudo iniciar Evennia.
    pause
    exit /b 1
  )
)

popd
start "" http://localhost:4001
exit /b 0
