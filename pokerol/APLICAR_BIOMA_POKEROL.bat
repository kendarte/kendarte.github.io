@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title POKEROL - Materializar bioma

if not exist ".venv\Scripts\python.exe" goto :bad
if not exist "runtime\server\conf\settings.py" goto :bad
if not exist "overlay\world\pokemon_biome_materializer.py" goto :bad

set "BIOME_FILE=%~1"
if not defined BIOME_FILE (
  echo.
  echo Exporte el mapa desde POKEROL Map Creator como JSON.
  set /p "BIOME_FILE=Pegue la ruta completa del JSON del bioma: "
)
if not defined BIOME_FILE exit /b 1
if not exist "%BIOME_FILE%" (
  echo ERROR: No existe "%BIOME_FILE%"
  pause
  exit /b 1
)

robocopy overlay runtime /E /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 goto :fail

set "POKEROL_BIOME_FILE=%BIOME_FILE%"
pushd runtime
"..\.venv\Scripts\python.exe" -m evennia shell -c "import json,os; from world.pokemon_biome_materializer import materialize_pokemon_biome_file; print(json.dumps(materialize_pokemon_biome_file(os.environ['POKEROL_BIOME_FILE']), ensure_ascii=False, indent=2))"
set "RC=%ERRORLEVEL%"
popd
if not "%RC%"=="0" goto :fail

echo.
echo Bioma materializado. No se borro ningun Room, Exit, personaje ni prop existente.
pause
exit /b 0

:bad
echo ERROR: Este no es el workspace local correcto de POKEROL o falta ejecutar SETUP_POKEROL.bat.
pause
exit /b 1

:fail
echo ERROR: No se pudo materializar el bioma POKEROL.
pause
exit /b 1
