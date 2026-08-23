@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo SIZA WORLD ENGINE - SETUP WINDOWS
echo ============================================
echo.

set "PYTHON_EXE="
set "PYTHON_ARGS="

echo [1/7] Buscando Python compatible con Evennia 6.1 ^(3.12, 3.13 o 3.14^)...

rem 1) python en PATH. En esta maquina esto detecta Python 3.14.x.
python -c "import sys; raise SystemExit(0 if (3,12) <= sys.version_info[:2] <= (3,14) else 1)" >nul 2>&1
if not errorlevel 1 set "PYTHON_EXE=python"

rem 2) Python Launcher, si existe y tiene alguna version compatible registrada.
if not defined PYTHON_EXE (
  py -3.14 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,14) else 1)" >nul 2>&1
  if not errorlevel 1 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3.14"
  )
)
if not defined PYTHON_EXE (
  py -3.13 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,13) else 1)" >nul 2>&1
  if not errorlevel 1 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3.13"
  )
)
if not defined PYTHON_EXE (
  py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 1)" >nul 2>&1
  if not errorlevel 1 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3.12"
  )
)

rem 3) Alias alternativos en PATH.
if not defined PYTHON_EXE (
  python3.14 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,14) else 1)" >nul 2>&1
  if not errorlevel 1 set "PYTHON_EXE=python3.14"
)
if not defined PYTHON_EXE (
  python3.13 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,13) else 1)" >nul 2>&1
  if not errorlevel 1 set "PYTHON_EXE=python3.13"
)
if not defined PYTHON_EXE (
  python3.12 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 1)" >nul 2>&1
  if not errorlevel 1 set "PYTHON_EXE=python3.12"
)

if not defined PYTHON_EXE (
  echo.
  echo ERROR: No encuentro una version de Python compatible con Evennia 6.1.
  echo Evennia 6.1 soporta Python 3.12, 3.13 y 3.14.
  echo.
  echo Ejecute y copie el resultado:
  echo   python --version
  echo   where python
  echo.
  pause
  exit /b 1
)

echo Python detectado:
"%PYTHON_EXE%" %PYTHON_ARGS% --version
if errorlevel 1 goto :fail

echo.
echo [2/7] Creando entorno virtual...
if not exist ".venv\Scripts\python.exe" (
  "%PYTHON_EXE%" %PYTHON_ARGS% -m venv .venv
  if errorlevel 1 goto :fail
) else (
  echo .venv ya existe; se reutiliza.
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :fail

echo Python del entorno virtual:
python --version
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
  echo ERROR: Evennia no responde dentro del entorno virtual.
  goto :fail
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
