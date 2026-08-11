@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

REM ---- Pinned to the last 3.11 with an embeddable build ----
set "PYVER=3.11.9"
set "PYDIR=python"
set "EMBED=python-%PYVER%-embed-amd64.zip"
set "PYURL=https://www.python.org/ftp/python/%PYVER%/%EMBED%"
set "PIPURL=https://bootstrap.pypa.io/get-pip.py"

echo ============================================
echo  Building portable Python bundle (%PYVER%)
echo ============================================

if exist "%PYDIR%\python.exe" (
    set /p REBUILD="[build] %PYDIR%\ exists. Delete and rebuild? [y/N] "
    if /i "!REBUILD!"=="y" ( rmdir /s /q "%PYDIR%" ) else ( goto :deps )
)

echo [build] Downloading embeddable Python...
curl -L -o "%EMBED%" "%PYURL%" || goto :error

echo [build] Extracting...
mkdir "%PYDIR%" 2>nul
tar -xf "%EMBED%" -C "%PYDIR%" || goto :error
del "%EMBED%"

echo [build] Writing ._pth (enables site-packages + pip)...
powershell -NoProfile -Command "Set-Content -Path '%PYDIR%\python311._pth' -Value @('python311.zip','.','Lib\site-packages','import site') -Encoding ASCII" || goto :error

echo [build] Bootstrapping pip...
curl -L -o get-pip.py "%PIPURL%" || goto :error
"%PYDIR%\python.exe" get-pip.py --no-warn-script-location || goto :error
del get-pip.py

:deps
echo [build] Installing dependencies...
"%PYDIR%\python.exe" -m pip install --upgrade pip --no-warn-script-location || goto :error
"%PYDIR%\python.exe" -m pip install -r requirements.txt --no-warn-script-location || goto :error

echo [build] Trimming caches...
for /d /r "%PYDIR%" %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
"%PYDIR%\python.exe" -m pip cache purge 2>nul

echo.
echo [build] Done. Zip the whole project folder to distribute.
goto :end

:error
echo.
echo [build] ERROR (exit %errorlevel%). See messages above.
pause & exit /b 1

:end
pause