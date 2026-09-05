@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "SIZA_MAP_FILE=%CD%\map-creator\presets\darkhaven-academy.siza-map.json"
set "SIZA_PYTHON=%CD%\.venv\Scripts\python.exe"
set "SIZA_RUNTIME=%CD%\runtime"

if not exist "%SIZA_MAP_FILE%" (
  echo ERROR: Falta el preset de mapa Darkhaven.
  goto :end_error
)
if not exist "%SIZA_PYTHON%" goto :bad_workspace
if not exist "%SIZA_RUNTIME%\server\conf\settings.py" goto :bad_workspace
if not exist "%CD%\overlay\world\editor_content_importer.py" goto :bad_workspace

robocopy overlay runtime /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
  echo ERROR: No se pudo sincronizar el materializador de escena.
  goto :end_error
)

pushd "%SIZA_RUNTIME%"
"%SIZA_PYTHON%" -m evennia shell -c "import json, os; from world.editor_content_importer import preview_scene_entities_file; print(json.dumps(preview_scene_entities_file(os.environ.get('SIZA_MAP_FILE')), ensure_ascii=False, indent=2))"
if errorlevel 1 (
  popd
  echo ERROR: La vista previa de utileria no pudo leerse.
  goto :end_error
)
popd

echo.
set "SIZA_CONFIRM="
set /p "SIZA_CONFIRM=Escriba ESCENA para crear o actualizar solo utileria estatica del mapa: "
if /I not "%SIZA_CONFIRM%"=="ESCENA" (
  echo Operacion cancelada. No se modifico el mundo.
  goto :end_ok
)

pushd "%SIZA_RUNTIME%"
"%SIZA_PYTHON%" -m evennia shell -c "import json, os; from world.editor_content_importer import apply_scene_entities_file; print(json.dumps(apply_scene_entities_file(os.environ.get('SIZA_MAP_FILE')), ensure_ascii=False, indent=2))"
set "SIZA_RC=!ERRORLEVEL!"
popd
if not "!SIZA_RC!"=="0" (
  echo ERROR: La materializacion de escena fallo.
  goto :end_error
)

echo.
echo ESCENA MATERIALIZADA.
echo Solo se crearon o actualizaron props estaticos con object_id estable.
echo Personajes, salidas, inventarios, ubicaciones de jugador y progreso quedan intactos.
goto :end_ok

:bad_workspace
echo ERROR: Este no es el workspace local correcto de SIZA.
goto :end_error

:end_ok
echo.
pause
exit /b 0

:end_error
echo.
pause
exit /b 1
