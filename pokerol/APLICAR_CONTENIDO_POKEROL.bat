@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "POKEROL_PYTHON=%CD%\.venv\Scripts\python.exe"
set "POKEROL_RUNTIME=%CD%\runtime"

if not exist "%POKEROL_PYTHON%" goto :bad
if not exist "%POKEROL_RUNTIME%\server\conf\settings.py" goto :bad
if not exist "%CD%\overlay\world\editor_content_importer.py" goto :bad
if not exist "%CD%\overlay\world\pokemon_content_importer.py" goto :bad

robocopy overlay runtime /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :fail

pushd "%POKEROL_RUNTIME%"
"%POKEROL_PYTHON%" -m evennia shell -c "import json,os; from world.editor_content_importer import preview_files; from world.pokemon_content_importer import preview_pokemon_file; m=os.environ.get('POKEROL_MAP_FILE') or None; n=os.environ.get('POKEROL_NPC_FILE') or None; p=os.environ.get('POKEROL_POKEMON_FILE') or None; r={}; r.update(preview_files(m,n)) if (m or n) else None; r.update({'pokemon':preview_pokemon_file(p)}) if p else None; (_ for _ in ()).throw(ValueError('Seleccione al menos un archivo de contenido.')) if not r else None; print(json.dumps(r, ensure_ascii=False, indent=2))"
if errorlevel 1 (
  popd
  goto :fail
)
popd

echo.
echo Archivos opcionales por variables de entorno:
echo   POKEROL_MAP_FILE
echo   POKEROL_NPC_FILE
echo   POKEROL_POKEMON_FILE
set "CONFIRM="
set /p "CONFIRM=Escriba APLICAR para actualizar contenido POKEROL: "
if /I not "%CONFIRM%"=="APLICAR" exit /b 0

pushd "%POKEROL_RUNTIME%"
"%POKEROL_PYTHON%" -m evennia shell -c "import json,os; from world.editor_content_importer import apply_files; from world.pokemon_content_importer import apply_pokemon_file; m=os.environ.get('POKEROL_MAP_FILE') or None; n=os.environ.get('POKEROL_NPC_FILE') or None; p=os.environ.get('POKEROL_POKEMON_FILE') or None; r={}; r.update(apply_files(m,n)) if (m or n) else None; r.update({'pokemon':apply_pokemon_file(p)}) if p else None; (_ for _ in ()).throw(ValueError('Seleccione al menos un archivo de contenido.')) if not r else None; print(json.dumps(r, ensure_ascii=False, indent=2))"
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
