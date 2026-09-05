@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "NO_PAUSE=0"
if /I "%~1"=="/nopause" set "NO_PAUSE=1"
set "SIZA_DARKHAVEN_MAP=%CD%\map-creator\presets\darkhaven-academy.siza-map.json"
set "SIZA_WEBCLIENT_URL=http://127.0.0.1:4001/webclient/?siza_build=20260905-stable-room-actions&force=9"

echo ========================================
echo SIZA WORLD ENGINE - UPDATE

echo 1. Git pull

git pull
if errorlevel 1 goto :fail

if not exist ".venv\Scripts\python.exe" (
  echo ERROR: Falta .venv. Ejecute setup_windows.bat primero.
  goto :fail
)
if not exist "runtime\server\conf\settings.py" (
  echo ERROR: Falta runtime. Ejecute setup_windows.bat primero.
  goto :fail
)
if not exist "%SIZA_DARKHAVEN_MAP%" (
  echo ERROR: Falta preset profundo de Darkhaven:
  echo %SIZA_DARKHAVEN_MAP%
  goto :fail
)

echo.
echo 2. Aplicando overlay...
robocopy overlay runtime /E /NFL /NDL /NJH /NJS /NP >nul
set RC=%ERRORLEVEL%
if %RC% GEQ 8 (
  echo ERROR: robocopy fallo con codigo %RC%.
  goto :fail
)

echo.
echo 2b. Sincronizando Siza Arena local para el webclient...
if not exist "..\siza-mobile-test\index.html" (
  echo ERROR: Falta ..\siza-mobile-test\index.html
  goto :fail
)
if not exist "..\siza-core\cards.js" (
  echo ERROR: Falta ..\siza-core\cards.js
  goto :fail
)

robocopy "..\siza-mobile-test" "runtime\web\static\webclient\tcg\siza-mobile-test" /E /NFL /NDL /NJH /NJS /NP >nul
set RC=%ERRORLEVEL%
if %RC% GEQ 8 (
  echo ERROR: fallo al sincronizar siza-mobile-test con codigo %RC%.
  goto :fail
)

robocopy "..\siza-core" "runtime\web\static\webclient\tcg\siza-core" /E /NFL /NDL /NJH /NJS /NP >nul
set RC=%ERRORLEVEL%
if %RC% GEQ 8 (
  echo ERROR: fallo al sincronizar siza-core con codigo %RC%.
  goto :fail
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 goto :fail

pushd runtime

echo.
echo 3. Reiniciando Evennia completamente...
python -m evennia stop >nul 2>&1

timeout /t 2 /nobreak >nul

python -m evennia start
if errorlevel 1 (
  evennia start
  if errorlevel 1 (
    popd
    goto :fail
  )
)

echo.
echo 4. Instalando/actualizando Academia Darkhaven Zona 7...
python -m evennia shell -c "from world.darkhaven_academy_seed import install; r=install(); print('DARKHAVEN_ACADEMY=', r); assert r.get('status') == 'INSTALLED', r"
if errorlevel 1 (
  popd
  goto :fail
)

echo.
echo 4a. Aplicando reglas de progresion del tutorial Darkhaven...
python -m evennia shell -c "from world.darkhaven_tutorial_patch import apply; r=apply(); print('DARKHAVEN_TUTORIAL_PATCH=', r); assert r.get('status') == 'PATCHED', r"
if errorlevel 1 (
  popd
  goto :fail
)

echo.
echo 4b. Activando autonomia controlada de Darkhaven...
python -m evennia shell -c "from world.darkhaven_autonomy_patch import apply; r=apply(); print('DARKHAVEN_AUTONOMY_PATCH=', r); assert r.get('status') == 'PATCHED', r"
if errorlevel 1 (
  popd
  goto :fail
)

echo.
echo 4c. Aplicando contenido profundo del Map Creator a Darkhaven...
python -m evennia shell -c "import os; from world.editor_content_importer import apply_map_file, apply_scene_entities_file; p=os.environ.get('SIZA_DARKHAVEN_MAP'); m=apply_map_file(p); s=apply_scene_entities_file(p); print('DARKHAVEN_EDITOR_CONTENT=', {'map_updated': m.get('updated_count'), 'map_missing': m.get('missing_count'), 'scene_created': s.get('created_count'), 'scene_updated': s.get('updated_count'), 'scene_conflicts': s.get('conflicts_count'), 'scene_invalid': s.get('invalid_count')})"
if errorlevel 1 (
  popd
  goto :fail
)

echo.
echo 4d. Conservando contenido Faro Ahogado VS01...
python -m evennia shell -c "from world.faro_ahogado_vs01_seed import install; r=install(); print('FARO_AHOGADO_VS01=', r); assert r.get('status') == 'INSTALLED', r"
if errorlevel 1 (
  popd
  goto :fail
)

echo.
echo 4e. Garantizando World Tick Siza unico...
python -m evennia shell -c "from typeclasses.world_tick import ensure_world_tick; r=ensure_world_tick(); print('WORLD_TICK_BOOTSTRAP=', r); assert r.get('duplicate_count') == 0, r"
if errorlevel 1 (
  popd
  goto :fail
)

popd

echo.
echo ========================================
echo UPDATE COMPLETO - SERVIDOR REINICIADO
echo ========================================
echo.
echo El mundo y la base de datos NO se borraron.
echo Academia Darkhaven Zona 7 fue instalada/actualizada de forma idempotente.
echo Tutorial Darkhaven fue endurecido para evitar rutas duplicadas o beats adelantados.
echo Autonomia controlada de Darkhaven fue activada para el grupo seguro de prueba.
echo Contenido profundo del Map Creator fue aplicado a Darkhaven.
echo World Tick Siza fue garantizado como script unico.
echo Faro Ahogado permanece instalado como contenido disponible, pero ya no es el arranque local por defecto.
echo Siza Arena fue sincronizado al webclient local.
echo Abriendo webclient actualizado...
start "" "%SIZA_WEBCLIENT_URL%"
echo.
if "%NO_PAUSE%"=="0" pause
exit /b 0

:fail
echo.
echo ========================================
echo UPDATE DETENIDO POR ERROR

echo Copie la salida desde la primera linea de ERROR.
echo ========================================
if "%NO_PAUSE%"=="0" pause
exit /b 1