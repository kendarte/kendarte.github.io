@echo off
setlocal
cd /d "%~dp0"
echo.
echo Publishing architectural visualization portfolio...
git add -A architectural-visualization/portfolio.json architectural-visualization/media/uploads architectural-visualization/index.html
git diff --cached --quiet
if errorlevel 1 git commit -m "Update architectural visualization portfolio"
git pull --rebase origin main
if errorlevel 1 goto error
git push origin main
if errorlevel 1 goto error
echo.
echo DONE - archviz portfolio pushed to main.
pause
exit /b 0
:error
echo.
echo Publish failed. Read the Git message above.
pause
exit /b 1
