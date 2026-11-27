@echo off
cd /d "%~dp0"
python -m co_xam
if errorlevel 1 pause
