@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "POKEROL_PYTHON=%CD%\.venv\Scripts\python.exe"
set "POKEROL_RUNTIME=%CD%\runtime"

if not exist "%POKEROL_PYTHON%" goto :bad
if not exist "%POKEROL_RUNTIME%\server\conf\settings.py" goto :bad
if not exist "%CD%\overlay\world\editor_content_importer.py" goto :bad

robocopy overlay runtime /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :fail

pushd "%POKEROL_RUNTIME%"
"%POKEROL_PYTHON%" -m evennia shell -c "import json,os; from world.editor_content_importer import preview_files; print(json.dumps(preview_files(os.environ.get('POKEROL_MAP_FILE') or None, os.environ.get('POKEROL_NPC_FILE') or None), ensure_ascii=False, indent=2))"
if errorlevel 1 (
  popd
  goto :fail
)
popd

echo.
set "CONFIRM="
set /p "CONFIRM=Escriba APLICAR para actualizar contenido existente: "
if /I not "%CONFIRM%"=="APLICAR" exit /b 0

pushd "%POKEROL_RUNTIME%"
"%POKEROL_PYTHON%" -m evennia shell -c "import json,os; from world.editor_content_importer import apply_files; print(json.dumps(apply_files(os.environ.get('POKEROL_MAP_FILE') or None, os.environ.get('POKEROL_NPC_FILE') or None), ensure_ascii=False, indent=2))"
set "RC=!ERRORLEVEL!"
popd
exit /b !RC!

:bad
echo ERROR: Este no es el workspace local correcto de POKEROL.
pause
exit /b 1

:fail
echo ERROR: No se pudo aplicar contenido POKEROL.
pause
exit /b 1
