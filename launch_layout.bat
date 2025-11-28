@echo off
REM Launch PyPotteryLayout in a new window

echo ========================================
echo Starting PyPotteryLayout...
echo ========================================

REM Change to the script directory
cd /d "%~dp0PyPotteryLayout"

REM Use the conda environment Python explicitly
set PYTHON_EXE=C:\Users\larth\anaconda3\envs\pypottery\python.exe

REM Set flag to prevent auto-opening browser (PyPotteryLayout checks this)
set PYPOTTERY_LAUNCHED_FROM_WRAPPER=1

REM Check if Python exists
if not exist "%PYTHON_EXE%" (
    echo ERROR: Python not found at %PYTHON_EXE%
    echo Please update the path in launch_layout.bat
    pause
    exit /b 1
)

echo Using Python: %PYTHON_EXE%
echo Current directory: %CD%
echo Environment: PYPOTTERY_LAUNCHED_FROM_WRAPPER=1
echo.
echo Starting Flask app...
echo.

REM Run the app
"%PYTHON_EXE%" app.py

REM If we get here, the app has stopped
echo.
echo App stopped. Press any key to close this window...
pause
