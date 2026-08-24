@echo off
setlocal EnableExtensions
cd /d "%~dp0"

call "%~dp0update_world_engine.bat" /nopause
if errorlevel 1 goto :fail

echo.
echo ============================================
echo SIZA QA READY
echo ============================================
echo.
echo Se abrira el webclient.
echo Dentro del MUD ejecute solo:
echo.
echo     siza-qa-latest

echo.
start "" "http://localhost:4001/webclient/"
exit /b 0

:fail
echo.
echo ============================================
echo QA NO INICIADO: UPDATE FALLO
echo ============================================
pause
exit /b 1
