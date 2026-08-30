@echo off
setlocal
cd /d "%~dp0"
echo.
echo Publishing portfolio...
git add -A illustration/content.json media/illustration/uploads
git diff --cached --quiet
if errorlevel 1 git commit -m "Update illustration portfolio"
git pull --rebase origin main
if errorlevel 1 goto error
git push origin main
if errorlevel 1 goto error
echo.
echo DONE - portfolio pushed to main.
pause
exit /b 0
:error
echo.
echo Publish failed. Read the Git message above.
pause
exit /b 1
