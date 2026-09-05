@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "SIZA_MAP_FILE="
set "SIZA_NPC_FILE="

for /f "usebackq delims=" %%F in (`powershell -NoProfile -STA -Command "Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.OpenFileDialog; $d.Title='Seleccione el JSON exportado por SIZA Map Creator (Cancelar para omitir)'; $d.Filter='JSON de SIZA (*.json)|*.json|Todos los archivos (*.*)|*.*'; if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){[Console]::WriteLine($d.FileName)}"`) do set "SIZA_MAP_FILE=%%F"
for /f "usebackq delims=" %%F in (`powershell -NoProfile -STA -Command "Add-Type -AssemblyName System.Windows.Forms; $d=New-Object System.Windows.Forms.OpenFileDialog; $d.Title='Seleccione el JSON exportado por SIZA NPC Creator (Cancelar para omitir)'; $d.Filter='JSON de SIZA (*.json)|*.json|Todos los archivos (*.*)|*.*'; if($d.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){[Console]::WriteLine($d.FileName)}"`) do set "SIZA_NPC_FILE=%%F"

if "%SIZA_MAP_FILE%"=="" if "%SIZA_NPC_FILE%"=="" (
  echo No se selecciono contenido.
  pause
  exit /b 1
)

call "%~dp0APLICAR_CONTENIDO_EDITADO_SIZA_CORE.bat"
exit /b %ERRORLEVEL%
