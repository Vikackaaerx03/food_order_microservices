@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0run-local.ps1" start
if errorlevel 1 (echo Project could not be started.& pause & exit /b 1)
start "" "http://127.0.0.1:8080"
