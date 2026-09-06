@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title POKEROL - Prueba SOLO

if not exist "INICIAR_POKEROL.bat" (
  echo ERROR: Este no es el workspace local correcto de POKEROL.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Falta .venv. Ejecute SETUP_POKEROL.bat primero.
  pause
  exit /b 1
)
if not exist "runtime\server\conf\settings.py" (
  echo ERROR: Falta runtime. Ejecute SETUP_POKEROL.bat primero.
  pause
  exit /b 1
)

set "POKEROL_SOLO_TEST_MODE=1"
call INICIAR_POKEROL.bat
if errorlevel 1 (
  echo.
  echo ERROR: POKEROL no pudo iniciar en modo SOLO.
  pause
  exit /b 1
)

echo.
echo ============================================
echo POKEROL - MODO PRUEBA SOLO ACTIVO
echo ============================================
echo.
echo 1. Entre con una cuenta/personaje normal de Evennia.
echo 2. En el juego escriba: solo-prueba
echo 3. Debe abrirse el Battle Stage con Party y Bag preparados.
echo.
echo Comandos utiles durante la prueba:
echo   equipo
 echo   bolsa
 echo   batalla
 echo   movimiento THUNDER-SHOCK
 echo   capturar
 echo   huir
 echo.
echo Esta ventana puede quedarse abierta durante la prueba.
pause
exit /b 0
