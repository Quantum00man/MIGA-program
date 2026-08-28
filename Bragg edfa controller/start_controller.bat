@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Please run: python -m venv .venv ^&^& .venv\Scripts\python -m pip install -r requirements.txt
  pause
  exit /b 1
)
start "CEFA EDFA Controller" ".venv\Scripts\pythonw.exe" "edfa_controller.py"
