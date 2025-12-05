@echo off
REM PyPottery Suite Launcher - Windows
REM This script launches the PyPottery Suite GUI

setlocal enabledelayedexpansion

echo.
echo ========================================
echo   PyPottery Suite Launcher
echo ========================================
echo.

REM Get script directory
set "SCRIPT_DIR=%~dp0"

REM Check for Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python not found in PATH
    echo Please install Python 3.9+ from https://python.org
    pause
    exit /b 1
)

REM Run the install script (it will handle dependencies and launch)
cd /d "%SCRIPT_DIR%"
python install.py %*

if %ERRORLEVEL% neq 0 (
    echo.
    echo [ERROR] Failed to launch PyPottery Suite
    pause
    exit /b 1
)

exit /b 0
