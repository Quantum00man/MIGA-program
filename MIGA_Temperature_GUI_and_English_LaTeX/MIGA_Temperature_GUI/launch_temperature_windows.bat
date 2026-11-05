@echo off
cd /d "%~dp0"
python miga_temperature_gui.py
if errorlevel 1 pause
