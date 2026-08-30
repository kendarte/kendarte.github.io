@echo off
setlocal
set "REPO=%USERPROFILE%\Desktop\kendarte.github.io"

where git >nul 2>&1
if errorlevel 1 (
  echo Git is not available in PATH.
  pause
  exit /b 1
)

if not exist "%REPO%\.git" (
  echo Cloning portfolio to %REPO% ...
  git clone https://github.com/kendarte/kendarte.github.io.git "%REPO%"
  if errorlevel 1 (
    echo Clone failed.
    pause
    exit /b 1
  )
) else (
  echo Updating local portfolio...
  cd /d "%REPO%"
  git pull --ff-only origin main
)

cd /d "%REPO%"

where py >nul 2>&1
if not errorlevel 1 (
  py -3 "%REPO%\portfolio_editor\server.py"
  exit /b %errorlevel%
)

where python >nul 2>&1
if not errorlevel 1 (
  python "%REPO%\portfolio_editor\server.py"
  exit /b %errorlevel%
)

echo Python was not found.
pause
exit /b 1
