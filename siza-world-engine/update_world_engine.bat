@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo SIZA WORLD ENGINE - UPDATE

echo 1. Git pull

git pull
if errorlevel 1 goto :fail

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Falta .venv. Ejecute setup_windows.bat primero.
  goto :fail
)
if not exist "runtime\server\conf\settings.py" (
  echo ERROR: Falta runtime. Ejecute setup_windows.bat primero.
  goto :fail
)

echo.
echo 2. Aplicando overlay...
robocopy overlay runtime /E /NFL /NDL /NJH /NJS /NP >nul
set RC=%ERRORLEVEL%
if %RC% GEQ 8 (
  echo ERROR: robocopy fallo con codigo %RC%.
  goto :fail
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :fail

pushd runtime

echo.
echo 3. Recargando Evennia...
python -m evennia reload
if errorlevel 1 (
  echo Reload no disponible; intentando start...
  python -m evennia start
  if errorlevel 1 (
    popd
    goto :fail
  )
)

popd

echo.
echo ============================================
echo UPDATE COMPLETO

echo Pruebe en el juego:
echo   voy hacia la plaza

echo Si Ollama falla, ahora vera el error real.
echo ============================================
pause
exit /b 0

:fail
echo.
echo ============================================
echo UPDATE DETENIDO POR ERROR

echo Copie la salida desde la primera linea de ERROR.
echo ============================================
pause
exit /b 1
