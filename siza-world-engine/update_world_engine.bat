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
echo 3. Reiniciando Evennia completamente...
python -m evennia stop >nul 2>&1

timeout /t 2 /nobreak >nul

python -m evennia start
if errorlevel 1 (
  evennia start
  if errorlevel 1 (
    popd
    goto :fail
  )
)

popd

echo.
echo ============================================
echo UPDATE COMPLETO - SERVIDOR REINICIADO
echo ============================================
echo.
echo El mundo y la base de datos NO se borraron.
echo Vuelva a conectar al webclient si se desconecto.
echo.
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
