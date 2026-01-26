@echo off
setlocal enabledelayedexpansion

echo.
echo ==========================================
echo       NetWORKS Setup Assistant
echo ==========================================
echo.

:: Change to parent directory (root of NetWORKS)
cd /d "%~dp0\.."

:: Check if Python is installed
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.8 or later from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

:: Check Python version
for /f "tokens=2" %%V in ('python --version 2^>^&1') do set PYVER=%%V
echo [INFO] Detected Python version: %PYVER%
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set MAJOR=%%a
    set MINOR=%%b
)

if %MAJOR% LSS 3 (
    echo [ERROR] Python 3.8 or later is required.
    echo Current version: %PYVER%
    echo.
    pause
    exit /b 1
)

if %MAJOR% EQU 3 (
    if %MINOR% LSS 8 (
        echo [ERROR] Python 3.8 or later is required.
        echo Current version: %PYVER%
        echo.
        pause
        exit /b 1
    )
)

:: Check if venv exists
if not exist "venv" (
    echo [INFO] Creating virtual environment...
    python -m venv venv
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [SUCCESS] Virtual environment created.
) else (
    echo [INFO] Virtual environment already exists.
)

:: Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

:: Install dependencies
echo [INFO] Installing dependencies...
python -m pip install --upgrade pip
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Failed to upgrade pip, continuing anyway...
)

echo [INFO] Installing required packages...
pip install -r requirements.txt --no-cache-dir
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install requirements.
    pause
    exit /b 1
)

echo.
echo ==========================================
echo [SUCCESS] NetWORKS setup complete!
echo.
echo To run NetWORKS:
echo   1. Activate the virtual environment: venv\Scripts\activate
echo   2. Run the application: python networks.py
echo ==========================================
echo.

pause
