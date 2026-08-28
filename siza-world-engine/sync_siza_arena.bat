@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "..\siza-mobile-test\index.html" (
  echo ERROR: Falta ..\siza-mobile-test\index.html
  exit /b 1
)
if not exist "..\siza-core\cards.js" (
  echo ERROR: Falta ..\siza-core\cards.js
  exit /b 1
)
if not exist "runtime\web\static\webclient" (
  echo ERROR: Falta runtime\web\static\webclient. Ejecute setup_windows.bat primero.
  exit /b 1
)

echo Sincronizando Siza Arena canonico...
robocopy "..\siza-mobile-test" "runtime\web\static\webclient\tcg\siza-mobile-test" /MIR /NFL /NDL /NJH /NJS /NP >nul
set RC=%ERRORLEVEL%
if %RC% GEQ 8 (
  echo ERROR: fallo al sincronizar siza-mobile-test con codigo %RC%.
  exit /b 1
)

robocopy "..\siza-core" "runtime\web\static\webclient\tcg\siza-core" /MIR /NFL /NDL /NJH /NJS /NP >nul
set RC=%ERRORLEVEL%
if %RC% GEQ 8 (
  echo ERROR: fallo al sincronizar siza-core con codigo %RC%.
  exit /b 1
)

echo Siza Arena sincronizado desde las fuentes canonicas.
exit /b 0
