@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo SIZA WORLD ENGINE - SETUP WINDOWS
echo ============================================
echo.

echo [1/7] Verificando Python 3.12...
py -3.12 --version
if errorlevel 1 (
  echo ERROR: No encuentro Python 3.12 mediante el launcher py.
  echo Pruebe: py -0p
  pause
  exit /b 1
)

echo.
echo [2/7] Creando entorno virtual...
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 goto :fail
) else (
  echo .venv ya existe; se reutiliza.
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :fail

echo.
echo [3/7] Instalando Evennia...
python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo.
echo [4/7] Verificando Evennia...
python -m evennia --version
if errorlevel 1 (
  echo El wrapper de Windows puede necesitar inicializarse una vez.
  python -m evennia
)

echo.
echo [5/7] Creando game dir runtime...
if not exist "runtime\server\conf\settings.py" (
  python -m evennia --init runtime
  if errorlevel 1 (
    echo Fallo python -m evennia --init runtime; intentando comando evennia...
    evennia --init runtime
    if errorlevel 1 goto :fail
  )
) else (
  echo runtime ya existe; no se regenera.
)

echo.
echo [6/7] Aplicando overlay de Siza...
robocopy overlay runtime /E /NFL /NDL /NJH /NJS /NP >nul
set RC=%ERRORLEVEL%
if %RC% GEQ 8 (
  echo ERROR: robocopy fallo con codigo %RC%.
  goto :fail
)

echo.
echo [7/7] Preparando base de datos...
pushd runtime
python -m evennia migrate
if errorlevel 1 (
  evennia migrate
  if errorlevel 1 (
    popd
    goto :fail
  )
)
popd

echo.
echo ============================================
echo SETUP COMPLETO
echo ============================================
echo.
echo Ahora ejecute:
echo   start_world_engine.bat
echo.
echo Cuando el servidor este arriba abra:
echo   http://localhost:4001
echo.
echo Como superusuario ejecute dentro del juego:
echo   batchcode kalnaj_pilot
echo.
pause
exit /b 0

:fail
echo.
echo ============================================
echo SETUP DETENIDO POR ERROR
echo ============================================
echo Copie desde la primera linea de ERROR y pasemela.
pause
exit /b 1
