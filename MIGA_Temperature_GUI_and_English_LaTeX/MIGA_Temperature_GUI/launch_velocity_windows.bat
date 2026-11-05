@echo off
cd /d "%~dp0"
python miga_launch_gui.py
if errorlevel 1 pause
