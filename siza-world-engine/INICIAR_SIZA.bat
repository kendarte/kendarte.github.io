@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

title SIZA - Arranque completo

set "SIZA_PYTHON=%CD%\.venv\Scripts\python.exe"
set "SIZA_RUNTIME=%CD%\runtime"
set "SIZA_WEBCLIENT=http://127.0.0.1:4001/webclient/?siza_build=20260905-room-authoring"
set "SIZA_OLLAMA_MODEL=qwen3:8b"
set "SIZA_OLLAMA_ENDPOINT=http://127.0.0.1:11434/api/chat"
set "SIZA_STATUS_FILE=%TEMP%\siza_evennia_status_%RANDOM%_%RANDOM%.txt"

echo ============================================
echo SIZA - ARRANQUE COMPLETO
echo ============================================
echo.

if not exist "%SIZA_PYTHON%" (
  echo ERROR: Falta .venv. Ejecute setup_windows.bat primero.
  goto :fail
)

if not exist "%SIZA_RUNTIME%\server\conf\settings.py" (
  echo ERROR: Falta runtime. Ejecute setup_windows.bat primero.
  goto :fail
)

echo [1/4] Sincronizando el World Engine...
robocopy overlay runtime /E /NFL /NDL /NJH /NJS /NP >nul
set "SIZA_RC=!ERRORLEVEL!"
if !SIZA_RC! GEQ 8 (
  echo ERROR: robocopy fallo con codigo !SIZA_RC!.
  goto :fail
)

echo [2/4] Comprobando el DM local...
call :ollama_ready
if not errorlevel 1 goto :ollama_running

where ollama >nul 2>&1
if errorlevel 1 (
  echo AVISO: Ollama no esta activo y Windows no encuentra ollama.exe.
  echo El mundo abrira, pero las acciones que necesitan el DM local fallaran.
  goto :start_evennia
)

echo Iniciando Ollama...
start "SIZA Ollama" /min ollama serve
set /a SIZA_TRIES=0

:wait_ollama
call :ollama_ready
if not errorlevel 1 goto :ollama_running
set /a SIZA_TRIES+=1
if !SIZA_TRIES! GEQ 20 (
  echo AVISO: Ollama no respondio despues de 20 segundos.
  echo El mundo abrira, pero las acciones que necesitan el DM local fallaran.
  goto :start_evennia
)
timeout /t 1 /nobreak >nul
goto :wait_ollama

:ollama_running
echo Ollama esta activo.
where ollama >nul 2>&1
if errorlevel 1 goto :start_evennia
ollama show "%SIZA_OLLAMA_MODEL%" >nul 2>&1
if errorlevel 1 (
  echo AVISO: Ollama esta activo, pero falta el modelo %SIZA_OLLAMA_MODEL%.
  echo Instale el modelo una sola vez con: ollama pull %SIZA_OLLAMA_MODEL%
)

:start_evennia
echo [3/4] Comprobando Portal y Server...
pushd "%SIZA_RUNTIME%"
call :evennia_ready
if not errorlevel 1 (
  echo Reiniciando Evennia para aplicar la version sincronizada...
  "%SIZA_PYTHON%" -m evennia stop >nul 2>&1
  timeout /t 2 /nobreak >nul
)

echo Iniciando Evennia...
"%SIZA_PYTHON%" -m evennia start
if errorlevel 1 (
  echo ERROR: Evennia no pudo iniciar.
  popd
  goto :fail
)

set /a SIZA_TRIES=0

:wait_evennia
call :evennia_ready
if not errorlevel 1 goto :wait_webclient
set /a SIZA_TRIES+=1
if !SIZA_TRIES! GEQ 60 (
  echo ERROR: Portal y Server no quedaron activos despues de 60 segundos.
  if exist "%SIZA_STATUS_FILE%" type "%SIZA_STATUS_FILE%"
  popd
  goto :fail
)
timeout /t 1 /nobreak >nul
goto :wait_evennia

:wait_webclient
echo [4/4] Esperando el webclient...
set /a SIZA_TRIES=0

:wait_web
call :webclient_ready
if not errorlevel 1 goto :ready
set /a SIZA_TRIES+=1
if !SIZA_TRIES! GEQ 20 (
  echo ERROR: Evennia esta activo, pero el puerto web 4001 no respondio en 20 segundos.
  if exist "%SIZA_STATUS_FILE%" type "%SIZA_STATUS_FILE%"
  popd
  goto :fail
)
timeout /t 1 /nobreak >nul
goto :wait_web

:ready
popd
if exist "%SIZA_STATUS_FILE%" del /q "%SIZA_STATUS_FILE%" >nul 2>&1
echo.
echo SIZA esta listo. Abriendo el MUD...
start "" "%SIZA_WEBCLIENT%"
exit /b 0

:ollama_ready
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {}; exit 1" >nul 2>&1
exit /b %ERRORLEVEL%

:evennia_ready
"%SIZA_PYTHON%" -m evennia status > "%SIZA_STATUS_FILE%" 2>&1
findstr /C:"Portal: RUNNING" "%SIZA_STATUS_FILE%" >nul 2>&1
if errorlevel 1 exit /b 1
findstr /C:"Server: RUNNING" "%SIZA_STATUS_FILE%" >nul 2>&1
if errorlevel 1 exit /b 1
exit /b 0

:webclient_ready
powershell -NoProfile -ExecutionPolicy Bypass -Command "$client = New-Object System.Net.Sockets.TcpClient; try { $task = $client.ConnectAsync('127.0.0.1', 4001); if ($task.Wait(2000) -and $client.Connected) { exit 0 }; exit 1 } catch { exit 1 } finally { $client.Dispose() }" >nul 2>&1
exit /b %ERRORLEVEL%

:fail
if exist "%SIZA_STATUS_FILE%" del /q "%SIZA_STATUS_FILE%" >nul 2>&1
echo.
echo SIZA NO SE INICIO. La ventana queda abierta para mostrar el error.
pause
exit /b 1
