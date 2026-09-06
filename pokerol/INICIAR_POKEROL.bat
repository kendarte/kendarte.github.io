@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title POKEROL - Arranque completo

set "POKEROL_PYTHON=%CD%\.venv\Scripts\python.exe"
set "POKEROL_RUNTIME=%CD%\runtime"
set "POKEROL_REPO=%CD%\.."
set "POKEROL_WEBCLIENT=http://127.0.0.1:4001/webclient/?pokerol_build=20260906-event-editor2"
set "POKEROL_OLLAMA_MODEL=qwen3:8b"
set "POKEROL_OLLAMA_URL=http://127.0.0.1:11434/api/chat"
set "POKEROL_OLLAMA_NUM_CTX=8192"

rem Compatibilidad temporal con servicios heredados que aun usan el namespace tecnico SIZA.
set "SIZA_OLLAMA_MODEL=%POKEROL_OLLAMA_MODEL%"
set "SIZA_OLLAMA_URL=%POKEROL_OLLAMA_URL%"
set "SIZA_OLLAMA_NUM_CTX=%POKEROL_OLLAMA_NUM_CTX%"

if not exist "%POKEROL_PYTHON%" (
  echo ERROR: Falta .venv. Ejecute SETUP_POKEROL.bat primero.
  goto :fail
)
if not exist "%POKEROL_RUNTIME%\server\conf\settings.py" (
  echo ERROR: Falta runtime. Ejecute SETUP_POKEROL.bat primero.
  goto :fail
)
if not exist "%POKEROL_REPO%\.git" (
  echo ERROR: POKEROL no esta dentro del repositorio local esperado.
  goto :fail
)
where git >nul 2>&1
if errorlevel 1 (
  echo ERROR: Git no esta disponible en PATH.
  goto :fail
)

echo [1/5] Actualizando archivos de POKEROL desde main...
git -C "%POKEROL_REPO%" fetch origin main
if errorlevel 1 (
  echo ERROR: No se pudo consultar origin/main.
  goto :fail
)
git -C "%POKEROL_REPO%" merge --ff-only origin/main
if errorlevel 1 (
  echo ERROR: El workspace local no puede actualizarse por fast-forward.
  echo Revise cambios locales o commits sin integrar antes de continuar.
  goto :fail
)

echo [2/5] Sincronizando POKEROL Engine al runtime...
robocopy overlay runtime /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
  echo ERROR: Fallo la sincronizacion overlay ^> runtime.
  goto :fail
)

echo [3/5] Comprobando DM local...
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2; if($r.StatusCode -eq 200){exit 0}} catch{}; exit 1" >nul 2>&1
if errorlevel 1 (
  where ollama >nul 2>&1
  if not errorlevel 1 (
    start "POKEROL Ollama" /min ollama serve
    timeout /t 2 /nobreak >nul
  )
)

echo [4/5] Reiniciando Evennia con el overlay actualizado...
pushd "%POKEROL_RUNTIME%"
"%POKEROL_PYTHON%" -m evennia status > "%TEMP%\pokerol_status.txt" 2>&1
findstr /C:"Portal: RUNNING" "%TEMP%\pokerol_status.txt" >nul 2>&1
if not errorlevel 1 (
  "%POKEROL_PYTHON%" -m evennia stop >nul 2>&1
  timeout /t 2 /nobreak >nul
)
"%POKEROL_PYTHON%" -m evennia start
if errorlevel 1 (
  popd
  goto :fail
)

echo [5/5] Esperando webclient...
set /a TRIES=0
:waitweb
powershell -NoProfile -ExecutionPolicy Bypass -Command "$c=New-Object Net.Sockets.TcpClient; try{$t=$c.ConnectAsync('127.0.0.1',4001); if($t.Wait(2000)-and$c.Connected){exit 0}; exit 1}catch{exit 1}finally{$c.Dispose()}" >nul 2>&1
if not errorlevel 1 goto :ready
set /a TRIES+=1
if !TRIES! GEQ 30 (
  popd
  goto :fail
)
timeout /t 1 /nobreak >nul
goto :waitweb

:ready
popd
del "%TEMP%\pokerol_status.txt" >nul 2>&1
echo.
echo POKEROL actualizado y listo. Abriendo webclient...
start "" "%POKEROL_WEBCLIENT%"
exit /b 0

:fail
echo.
echo POKEROL NO SE INICIO. La ventana queda abierta para mostrar el error.
pause
exit /b 1
