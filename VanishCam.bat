@echo off
rem Dubbelklik om VanishCam te starten met virtuele camera voor Teams.
cd /d "%~dp0"
uv run vanishcam.py --virtual %*
if errorlevel 1 pause
