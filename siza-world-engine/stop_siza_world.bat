@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Falta .venv.
  pause
  exit /b 1
)
if not exist "runtime\server\conf\settings.py" (
  echo ERROR: Falta runtime.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
pushd runtime
python -m evennia stop
set RC=%ERRORLEVEL%
popd

if not "%RC%"=="0" (
  echo.
  echo No pude detener Evennia limpiamente. Revise si ya estaba apagado.
  pause
  exit /b %RC%
)

echo.
echo SIZA World Engine detenido. El estado persistente queda guardado.
pause
exit /b 0
