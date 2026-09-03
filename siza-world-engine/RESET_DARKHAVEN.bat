@echo off
setlocal EnableExtensions
cd /d "%~dp0"

echo ============================================
echo SIZA - RESET DARKHAVEN TUTORIAL

echo 1. Actualizando World Engine y contenido...
call "%~dp0update_world_engine.bat" /nopause
if errorlevel 1 goto :fail

if not exist ".venv\Scripts\python.exe" goto :fail

pushd runtime

echo.
echo 2. Reseteando personaje y tutorial Darkhaven...
"..\.venv\Scripts\python.exe" -m evennia shell -c "from world.darkhaven_reset import reset; r=reset(); print('DARKHAVEN_RESET=', r); assert r.get('status') == 'RESET', r"
if errorlevel 1 (
  popd
  goto :fail
)
popd

echo.
echo ============================================
echo DARKHAVEN LISTO

echo Nereida comienza en Puerta de Darkhaven.
echo Campana activa: CAMPAIGN-DARKHAVEN-TUTORIAL-V01
echo Cierre y vuelva a abrir el webclient si estaba conectado.
echo ============================================
pause
exit /b 0

:fail
echo.
echo ============================================
echo RESET DARKHAVEN DETENIDO POR ERROR

echo Copie la salida desde la primera linea de ERROR.
echo ============================================
pause
exit /b 1