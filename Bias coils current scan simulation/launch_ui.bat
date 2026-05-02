@echo off
setlocal
cd /d "%~dp0"

python "rb87_bias_coils_current_scan_ui.py"
if not errorlevel 1 goto end

echo.
echo Qt UI failed. Falling back to tkinter UI...
python "rb87_bias_coils_current_scan_ui_tk.py"

:end
if errorlevel 1 (
    echo.
    echo UI exited with an error.
    pause
)
