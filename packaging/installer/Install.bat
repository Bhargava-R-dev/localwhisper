@echo off
setlocal
title LocalWhisper Installer

rem --- Self-elevate to Administrator (needed for global hotkeys + login task) ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "SRC=%~dp0LocalWhisper"
set "DEST=%ProgramFiles%\LocalWhisper"
set "EXE=%DEST%\LocalWhisper.exe"

if not exist "%SRC%\LocalWhisper.exe" (
    echo ERROR: Could not find "%SRC%\LocalWhisper.exe".
    echo Make sure you extracted the whole ZIP and kept the folder structure.
    pause
    exit /b 1
)

echo Stopping any running LocalWhisper (upgrading an existing install) ...
taskkill /IM LocalWhisper.exe /F >nul 2>&1
timeout /t 1 /nobreak >nul

echo Installing LocalWhisper to "%DEST%" ...
if exist "%DEST%" rmdir /s /q "%DEST%"
mkdir "%DEST%"
robocopy "%SRC%" "%DEST%" /e /nfl /ndl /njh /njs /nc /ns >nul

echo Registering auto-start at login (runs elevated so hotkeys work) ...
schtasks /Create /TN "LocalWhisper" /TR "\"%EXE%\"" /SC ONLOGON /RL HIGHEST /F >nul

echo Starting LocalWhisper ...
start "" "%EXE%"

echo.
echo ============================================================
echo  LocalWhisper installed successfully.
echo  It will start automatically every time you log in.
echo.
echo  How to use (put your cursor anywhere you can type):
echo    - Hold  Ctrl+B  and speak, release to insert
echo    - Tap   Alt+N   to start, tap again to stop
echo    - Say   "Hey Jarvis"  then speak (hands-free)
echo.
echo  A grey/green/amber icon appears in the system tray.
echo  Right-click it to Quit.
echo ============================================================
echo.
pause
