@echo off
setlocal
title LocalWhisper Uninstaller

rem --- Self-elevate to Administrator ---
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo Stopping LocalWhisper ...
schtasks /Delete /TN "LocalWhisper" /F >nul 2>&1
taskkill /IM LocalWhisper.exe /F >nul 2>&1

set "DEST=%ProgramFiles%\LocalWhisper"
echo Removing "%DEST%" ...
if exist "%DEST%" rmdir /s /q "%DEST%"

echo.
echo LocalWhisper has been uninstalled.
echo (Your log file at %%LOCALAPPDATA%%\LocalWhisper was left in place.)
echo.
pause
