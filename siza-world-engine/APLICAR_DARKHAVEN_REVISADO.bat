@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "SIZA_MAP_FILE=%CD%\map-creator\presets\darkhaven-academy.siza-map.json"
set "SIZA_NPC_FILE=%CD%\npc-creator\presets\darkhaven-academy.siza-npcs.json"

if not exist "%SIZA_MAP_FILE%" (
  echo ERROR: Falta el preset de mapa Darkhaven.
  pause
  exit /b 1
)
if not exist "%SIZA_NPC_FILE%" (
  echo ERROR: Falta el preset de NPCs Darkhaven.
  pause
  exit /b 1
)

call "%~dp0APLICAR_CONTENIDO_EDITADO_SIZA_CORE.bat"
exit /b %ERRORLEVEL%
