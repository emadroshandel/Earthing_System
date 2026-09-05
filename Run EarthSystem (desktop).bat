@echo off
setlocal
title EarthSystem - Earthing System Design
cd /d "%~dp0"
set "LOG=%~dp0startup_log.txt"

echo ============================================================ > "%LOG%"
echo EarthSystem launcher   %DATE% %TIME%                        >> "%LOG%"
echo Folder: %~dp0                                               >> "%LOG%"
echo ============================================================ >> "%LOG%"

echo.
echo   EarthSystem - Earthing System Design
echo   Looking for Python...
echo.

set "PY="
set "PYARGS="

call :try "py" "-3"
call :try "python" ""
call :try "python3" ""
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do call :try "%%~D\python.exe" ""
for /d %%D in ("%ProgramFiles%\Python3*")                 do call :try "%%~D\python.exe" ""
for /d %%D in ("C:\Python3*")                             do call :try "%%~D\python.exe" ""
call :try "%USERPROFILE%\anaconda3\python.exe" ""
call :try "%USERPROFILE%\miniconda3\python.exe" ""
call :try "%USERPROFILE%\AppData\Local\anaconda3\python.exe" ""
call :try "C:\ProgramData\anaconda3\python.exe" ""
call :try "C:\ProgramData\miniconda3\python.exe" ""
call :try "%LOCALAPPDATA%\Continuum\anaconda3\python.exe" ""
call :try "%USERPROFILE%\Anaconda3\python.exe" ""
call :try "C:\Anaconda3\python.exe" ""
call :try "%ProgramFiles%\Anaconda3\python.exe" ""
call :try "D:\Anaconda3\python.exe" ""
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do call :try "%%~D\python.exe" ""

if not defined PY goto nopython

echo   Using: %PY% %PYARGS%
>>"%LOG%" echo   Using: %PY% %PYARGS%

"%PY%" %PYARGS% -c "import numpy" >nul 2>>"%LOG%"
if not errorlevel 1 goto haveNumpy
echo   Installing numpy (needed for the numerical solver)...
"%PY%" %PYARGS% -m pip install numpy >>"%LOG%" 2>&1
:haveNumpy
"%PY%" %PYARGS% -c "import webview" >nul 2>>"%LOG%"
if not errorlevel 1 goto haveWebview
echo.
echo   pywebview is not installed, so EarthSystem will open in your
echo   default browser instead. That works exactly the same way.
echo.
echo   For a native window, install it yourself when convenient:
echo       py -3 -m pip install pywebview
echo   (it upgrades clr_loader / pythonnet, which can affect other
echo    Python tools - a virtual environment is the safe way.)
echo.
:haveWebview

echo.
echo   Starting EarthSystem in a desktop window.
echo   Leave this window open while you use the software.
echo.
"%PY%" %PYARGS% desktop.py 2>>"%LOG%"
>>"%LOG%" echo Server exit code: %ERRORLEVEL%
echo.
echo   The server has stopped. If this was unexpected, the file
echo   startup_log.txt in this folder has the details.
echo.
pause
exit /b 0

:nopython
echo.
echo   ------------------------------------------------------------
echo   Python was not found on this computer.
echo.
echo   Install Python 3.9 or newer from
echo       https://www.python.org/downloads/
echo   and TICK "Add python.exe to PATH" during the installation.
echo.
echo   Details of what was tried are in:
echo       %LOG%
echo   ------------------------------------------------------------
echo.
echo No working Python interpreter found. >> "%LOG%"
pause
exit /b 1

:try
if defined PY goto :eof
set "CAND=%~1"
set "CARGS=%~2"
>>"%LOG%" echo --- trying: %CAND% %CARGS%
"%CAND%" %CARGS% -c "import sys; print(sys.version)" >>"%LOG%" 2>&1
if errorlevel 1 goto :eof
set "PY=%CAND%"
set "PYARGS=%CARGS%"
>>"%LOG%" echo *** SELECTED: %CAND% %CARGS%
goto :eof
