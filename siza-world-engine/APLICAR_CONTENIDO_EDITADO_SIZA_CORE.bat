@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "SIZA_PYTHON=%CD%\.venv\Scripts\python.exe"
set "SIZA_RUNTIME=%CD%\runtime"

if not exist "%SIZA_PYTHON%" goto :bad_workspace
if not exist "%SIZA_RUNTIME%\server\conf\settings.py" goto :bad_workspace
if not exist "%CD%\overlay\world\editor_content_importer.py" goto :bad_workspace

robocopy overlay runtime /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
  echo ERROR: No se pudo sincronizar el importador de contenido.
  goto :end_error
)

pushd "%SIZA_RUNTIME%"
"%SIZA_PYTHON%" -m evennia shell -c "import json, os; from world.editor_content_importer import preview_files; print(json.dumps(preview_files(os.environ.get('SIZA_MAP_FILE') or None, os.environ.get('SIZA_NPC_FILE') or None), ensure_ascii=False, indent=2))"
if errorlevel 1 (
  popd
  echo ERROR: La vista previa no pudo leer los archivos.
  goto :end_error
)
popd

echo.
set "SIZA_CONFIRM="
set /p "SIZA_CONFIRM=Escriba APLICAR para actualizar solo contenido existente: "
if /I not "%SIZA_CONFIRM%"=="APLICAR" (
  echo Operacion cancelada. No se modifico el mundo.
  goto :end_ok
)

pushd "%SIZA_RUNTIME%"
"%SIZA_PYTHON%" -m evennia shell -c "import json, os; from world.editor_content_importer import apply_files; print(json.dumps(apply_files(os.environ.get('SIZA_MAP_FILE') or None, os.environ.get('SIZA_NPC_FILE') or None), ensure_ascii=False, indent=2))"
set "SIZA_RC=!ERRORLEVEL!"
popd
if not "!SIZA_RC!"=="0" (
  echo ERROR: La aplicacion de contenido fallo.
  goto :end_error
)

echo.
echo CONTENIDO APLICADO.
echo Se actualizaron solo objetos ya existentes por room_id y npc_id.
echo Personajes, salidas, ubicaciones, inventarios y progreso quedan intactos.
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
