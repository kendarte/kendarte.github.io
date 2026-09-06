@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title POKEROL - Setup Windows

echo ============================================
echo POKEROL WORLD ENGINE - SETUP WINDOWS
echo ============================================
echo.

set "PYTHON_EXE="
set "PYTHON_ARGS="

python -c "import sys; raise SystemExit(0 if (3,12) <= sys.version_info[:2] <= (3,14) else 1)" >nul 2>&1
if not errorlevel 1 set "PYTHON_EXE=python"

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

if not defined PYTHON_EXE (
  echo ERROR: No encuentro Python 3.12, 3.13 o 3.14 compatible con Evennia 6.1.
  pause
  exit /b 1
)

echo [1/6] Creando entorno virtual...
if not exist ".venv\Scripts\python.exe" (
  "%PYTHON_EXE%" %PYTHON_ARGS% -m venv .venv
  if errorlevel 1 goto :fail
)
call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :fail

echo [2/6] Instalando dependencias...
python -m pip install --upgrade pip
if errorlevel 1 goto :fail
python -m pip install -r requirements.txt
if errorlevel 1 goto :fail

echo [3/6] Verificando Evennia...
python -m evennia --version
if errorlevel 1 goto :fail

echo [4/6] Creando runtime independiente...
if not exist "runtime\server\conf\settings.py" (
  python -m evennia --init runtime
  if errorlevel 1 goto :fail
)

echo [5/6] Aplicando overlay POKEROL...
robocopy overlay runtime /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :fail

echo [6/6] Preparando DB propia de POKEROL...
pushd runtime
python -m evennia migrate
if errorlevel 1 (
  popd
  goto :fail
)
popd

echo.
echo ============================================
echo SETUP POKEROL COMPLETO
echo ============================================
echo Runtime y DB son independientes de SIZA.
echo Ahora ejecute INICIAR_POKEROL.bat
pause
exit /b 0

:fail
echo.
echo ERROR: SETUP POKEROL se detuvo.
pause
exit /b 1
