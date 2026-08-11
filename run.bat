@echo off
cd /d "%~dp0"
if not exist "python\python.exe" (
    echo Missing python bundle. If you're the developer, run build.bat first.
    pause & exit /b 1
)
python\python.exe src\main.py %*
if errorlevel 1 pause