@echo off
setlocal
title TGF3162 Controller
pushd "%~dp0"
if errorlevel 1 exit /b 1

if defined TGF_PYTHON goto custom_python
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 (
    py -3 launcher.py %*
    goto finished
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>nul
if not errorlevel 1 (
    python launcher.py %*
    goto finished
)
echo Python 3.10 or newer was not found.
echo Install Python, then run this launcher again:
echo   winget install --id Python.Python.3.12 -e
echo Or download Python from https://www.python.org/downloads/windows/
echo Enable "Add python.exe to PATH" during installation.
set "TGF_EXIT=1"
goto cleanup

:custom_python
"%TGF_PYTHON%" launcher.py %*

:finished
set "TGF_EXIT=%errorlevel%"
:cleanup
popd
if not "%TGF_EXIT%"=="0" (
    echo.
    echo Startup failed. Read the message above for the next step.
    if not defined TGF_NO_PAUSE pause
)
exit /b %TGF_EXIT%
