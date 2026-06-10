@echo off
setlocal

cd /d "%~dp0"

set "APP_FILE=app.py"
set "BASE_PORT=8501"
set "PORT="
set "PYTHON_EXE="
set "DRY_RUN="

if /i "%~1"=="--dry-run" (
    set "DRY_RUN=1"
)

if exist "%~dp0.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
)

if not defined PYTHON_EXE (
    if exist "D:\ANACONDA\python.exe" (
        set "PYTHON_EXE=D:\ANACONDA\python.exe"
    )
)

if not defined PYTHON_EXE (
    for /f "delims=" %%I in ('where python.exe 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%I"
    )
)

if not defined PYTHON_EXE (
    echo [ERROR] Python was not found.
    echo Install Python or Anaconda, then run this file again.
    pause
    exit /b 1
)

if not exist "%APP_FILE%" (
    echo [ERROR] %APP_FILE% was not found in:
    echo %CD%
    pause
    exit /b 1
)

"%PYTHON_EXE%" -c "import streamlit" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Streamlit is not installed in this Python environment:
    echo %PYTHON_EXE%
    echo.
    echo Run this command first:
    echo "%PYTHON_EXE%" -m pip install streamlit
    pause
    exit /b 1
)

echo Python:
echo %PYTHON_EXE%
echo.

if not defined PORT (
    set "PORT=%BASE_PORT%"
)

:find_free_port
netstat -ano | findstr /R /C:":%PORT% .*LISTENING" >nul
if not errorlevel 1 (
    set /a PORT+=1
    goto find_free_port
)

echo Starting ChatGPT LaTeX Cleaner...
echo Local URL: http://localhost:%PORT%
echo Close this window to stop the app.
echo.

if defined DRY_RUN (
    echo Dry run OK. No server was started.
    exit /b 0
)

start "" /min powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Sleep -Seconds 3; Start-Process 'http://localhost:%PORT%'"
"%PYTHON_EXE%" -m streamlit run "%APP_FILE%" --server.port %PORT% --server.headless true

echo.
echo The app has stopped.
pause
