@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo SIZA WORLD ENGINE - SETUP WINDOWS
echo ============================================
echo.

set "PYTHON_EXE="
set "PYTHON_ARGS="

echo [1/7] Buscando Python 3.12...

rem 1) Python Launcher
py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 1)" >nul 2>&1
if not errorlevel 1 (
  set "PYTHON_EXE=py"
  set "PYTHON_ARGS=-3.12"
)

rem 2) python en PATH
if not defined PYTHON_EXE (
  python -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 1)" >nul 2>&1
  if not errorlevel 1 set "PYTHON_EXE=python"
)

rem 3) python3.12 en PATH
if not defined PYTHON_EXE (
  python3.12 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3,12) else 1)" >nul 2>&1
  if not errorlevel 1 set "PYTHON_EXE=python3.12"
)

rem 4) Rutas comunes del instalador oficial de Python
if not defined PYTHON_EXE if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
  set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
)
if not defined PYTHON_EXE if exist "%ProgramFiles%\Python312\python.exe" (
  set "PYTHON_EXE=%ProgramFiles%\Python312\python.exe"
)
if not defined PYTHON_EXE if defined ProgramFiles^(x86^) if exist "%ProgramFiles(x86)%\Python312\python.exe" (
  set "PYTHON_EXE=%ProgramFiles(x86)%\Python312\python.exe"
)

if not defined PYTHON_EXE (
  echo.
  echo ERROR: Python 3.12 puede estar instalado, pero Windows no lo expone por una ruta que este instalador pueda detectar.
  echo.
  echo Ejecute estos tres comandos y copie el resultado:
  echo   python --version
  echo   where python
  echo   py -0p
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
