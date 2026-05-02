@echo off
setlocal
cd /d "%~dp0"
python "rb87_bias_coils_current_scan_ui.py"
if errorlevel 1 (
    echo.
    echo UI exited with an error.
    pause
)
