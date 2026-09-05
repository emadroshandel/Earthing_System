@echo off
setlocal
title EarthSystem - diagnostic
cd /d "%~dp0"
set "LOG=%~dp0diagnostic.txt"

echo EarthSystem diagnostic   %DATE% %TIME% > "%LOG%"
echo Folder: %~dp0 >> "%LOG%"
echo. >> "%LOG%"
echo ---- PATH ---- >> "%LOG%"
>>"%LOG%" echo %PATH%
echo. >> "%LOG%"
echo ---- where py / python / python3 ---- >> "%LOG%"
where py       >> "%LOG%" 2>&1
where python   >> "%LOG%" 2>&1
where python3  >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo ---- py -0 (installed versions) ---- >> "%LOG%"
py -0 >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo ---- version checks ---- >> "%LOG%"
py -3 -c "import sys;print('py -3 :',sys.version, sys.executable)" >> "%LOG%" 2>&1
python -c "import sys;print('python :',sys.version, sys.executable)" >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo ---- common install locations ---- >> "%LOG%"
dir /b "%LOCALAPPDATA%\Programs\Python" >> "%LOG%" 2>&1
dir /b "C:\ProgramData\anaconda3\python.exe" >> "%LOG%" 2>&1
dir /b "%USERPROFILE%\anaconda3\python.exe" >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo ---- numpy ---- >> "%LOG%"
py -3 -c "import numpy;print('numpy',numpy.__version__)" >> "%LOG%" 2>&1
python -c "import numpy;print('numpy',numpy.__version__)" >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo ---- folder contents ---- >> "%LOG%"
dir /b >> "%LOG%" 2>&1

echo.
echo   Diagnostic written to:
echo       %LOG%
echo.
type "%LOG%"
echo.
pause
