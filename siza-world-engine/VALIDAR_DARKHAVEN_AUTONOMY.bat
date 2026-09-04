@echo off
setlocal
call ".venv\Scripts\activate.bat"
if errorlevel 1 exit /b 1
pushd runtime
python -m evennia shell -c "from world.darkhaven_autonomy_validator import validate; r=validate(); print('DARKHAVEN_AUTONOMY=', r); assert r.get('status') == 'VALID', r"
set RC=%ERRORLEVEL%
popd
exit /b %RC%
