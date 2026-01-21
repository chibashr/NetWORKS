@echo off
setlocal enabledelayedexpansion

echo.
echo ==========================================
echo      NetWORKS Repair Installation
echo ==========================================
echo.
echo This script will repair your NetWORKS installation by:
echo  - Checking Python installation
echo  - Validating/recreating the virtual environment
echo  - Reinstalling all dependencies
echo  - Verifying the installation
echo.
if "%NETWORKS_AUTOMATED%"=="1" (
    echo [INFO] Automated mode detected. Continuing without prompt...
) else (
    echo Press Ctrl+C to cancel or any key to continue...
    pause > nul
)

:: Check if Python is installed
echo.
echo [STEP 1/4] Checking Python installation...
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.8 or later from https://www.python.org/downloads/
    echo.
    if "%NETWORKS_AUTOMATED%"=="1" (
        echo [INFO] Automated mode: skipping pause.
    ) else (
        pause
    )
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
    if "%NETWORKS_AUTOMATED%"=="1" (
        echo [INFO] Automated mode: skipping pause.
    ) else (
        pause
    )
    exit /b 1
)

if %MAJOR% EQU 3 (
    if %MINOR% LSS 8 (
        echo [ERROR] Python 3.8 or later is required.
        echo Current version: %PYVER%
        echo.
        if "%NETWORKS_AUTOMATED%"=="1" (
            echo [INFO] Automated mode: skipping pause.
        ) else (
            pause
        )
        exit /b 1
    )
)

:: Check for requirements.txt
echo.
echo [STEP 2/4] Checking installation files...
if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found in the current directory.
    echo Please run this script from the root directory of NetWORKS.
    echo.
    if "%NETWORKS_AUTOMATED%"=="1" (
        echo [INFO] Automated mode: skipping pause.
    ) else (
        pause
    )
    exit /b 1
)

:: Check and recreate virtual environment
echo.
echo [STEP 3/4] Checking virtual environment...

if exist "venv" (
    echo [INFO] Existing virtual environment found.
    
    :: Test if the virtual environment is functional
    echo [INFO] Testing virtual environment...
    call venv\Scripts\activate.bat 2>nul
    if %ERRORLEVEL% neq 0 (
        echo [WARNING] Virtual environment appears to be corrupt.
        echo [INFO] Removing existing virtual environment...
        rmdir /s /q "venv"
        echo [INFO] Creating new virtual environment...
        python -m venv venv
        if !ERRORLEVEL! neq 0 (
            echo [ERROR] Failed to create virtual environment.
            if "%NETWORKS_AUTOMATED%"=="1" (
                echo [INFO] Automated mode: skipping pause.
            ) else (
                pause
            )
            exit /b 1
        )
    ) else (
        call venv\Scripts\deactivate.bat
        echo [INFO] Virtual environment is functional.
        
        :: Ask if user wants to recreate it anyway
        if "%NETWORKS_AUTOMATED%"=="1" (
            set RECREATE=n
            echo [INFO] Automated mode: skipping venv recreation prompt.
        ) else (
            set /p RECREATE="Do you want to recreate the virtual environment anyway? (y/n): "
        )
        if /i "!RECREATE!"=="y" (
            echo [INFO] Removing existing virtual environment...
            call venv\Scripts\deactivate.bat 2>nul
            rmdir /s /q "venv"
            echo [INFO] Creating new virtual environment...
            python -m venv venv
            if !ERRORLEVEL! neq 0 (
                echo [ERROR] Failed to create virtual environment.
                if "%NETWORKS_AUTOMATED%"=="1" (
                    echo [INFO] Automated mode: skipping pause.
                ) else (
                    pause
                )
                exit /b 1
            )
        )
    )
) else (
    echo [INFO] No virtual environment found. Creating new one...
    python -m venv venv
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        if "%NETWORKS_AUTOMATED%"=="1" (
            echo [INFO] Automated mode: skipping pause.
        ) else (
            pause
        )
        exit /b 1
    )
)

:: Activate virtual environment and reinstall dependencies
echo.
echo [STEP 4/4] Reinstalling dependencies...
call venv\Scripts\activate.bat
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    if "%NETWORKS_AUTOMATED%"=="1" (
        echo [INFO] Automated mode: skipping pause.
    ) else (
        pause
    )
    exit /b 1
)

:: Update pip first
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Failed to upgrade pip. Continuing anyway...
)

:: Install dependencies
echo [INFO] Installing all dependencies from requirements.txt...
pip install -r requirements.txt --no-cache-dir
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Failed to install some dependencies from requirements.txt. Will try individual installations...
)

:: Try to install critical packages directly to be sure
echo [INFO] Ensuring critical packages are installed...
echo [INFO] Installing core dependencies...
pip install PySide6>=6.9.0 --force-reinstall --no-cache-dir
pip install loguru==0.7.3 --force-reinstall --no-cache-dir
pip install chardet==5.2.0 --force-reinstall --no-cache-dir

echo [INFO] Attempting optional pandas install (non-blocking)...
pip install "pandas>=2.3.3,<3.0" --only-binary=:all: --no-cache-dir
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Optional pandas install failed. Some file import features may be unavailable.
) else (
    echo [INFO] Optional pandas installed successfully.
)

echo [INFO] Installing plugin dependencies...
pip install paramiko==3.5.1 --no-cache-dir
pip install python-nmap==0.7.1 --no-cache-dir
pip install netifaces==0.11.0 --only-binary=:all: --no-cache-dir
if %ERRORLEVEL% neq 0 (
    echo [WARNING] Optional plugin dependency netifaces failed to install.
)
pip install scapy==2.6.1 --no-cache-dir
pip install bcrypt==4.3.0 --no-cache-dir
pip install pycryptodome==3.22.0 --no-cache-dir
echo [INFO] Plugin dependencies installation completed.

:: Verify installation
echo.
echo [INFO] Verifying installation...
python -c "import importlib.util; packages=['PySide6', 'qtpy', 'qtawesome', 'yaml', 'jsonschema', 'loguru', 'six', 'chardet']; missing = [p for p in packages if importlib.util.find_spec(p) is None]; print('All required dependencies are installed!' if not missing else 'Missing: ' + ', '.join(missing))"

echo.
echo [INFO] Checking optional dependencies...
python -c "import importlib.util; packages=['pandas', 'openpyxl', 'docx', 'xlrd']; missing = [p for p in packages if importlib.util.find_spec(p) is None]; print('All optional dependencies are installed!' if not missing else 'Some optional dependencies are missing: ' + ', '.join(missing))"

echo.
echo [INFO] Checking plugin dependencies...
python -c "import importlib.util; packages=['paramiko', 'nmap', 'netifaces', 'scapy', 'bcrypt', 'Crypto']; missing = [p for p in packages if importlib.util.find_spec(p) is None]; print('All plugin dependencies are installed!' if not missing else 'Some plugin dependencies are missing: ' + ', '.join(missing))"

:: Try direct imports for most problematic packages
echo.
echo [INFO] Testing critical imports directly...
python -c "import importlib.util; mod='PySide6'; print('PySide6 imported successfully' if importlib.util.find_spec(mod) else f'Failed to import {mod}')"
python -c "import importlib.util; mod='pandas'; print('pandas imported successfully' if importlib.util.find_spec(mod) else f'Failed to import {mod}')"

:: Deactivate virtual environment
call venv\Scripts\deactivate.bat

echo.
echo ==========================================
echo      NetWORKS Repair Complete!
echo ==========================================
echo.
echo Your NetWORKS installation has been repaired.
echo.
echo To run NetWORKS:
echo   1. Use the Start_NetWORKS.bat script
echo   or
echo   2. Activate the virtual environment: venv\Scripts\activate
echo      and run: python networks.py
echo.
echo ==========================================
echo.

if "%NETWORKS_AUTOMATED%"=="1" (
    echo [INFO] Automated mode: skipping pause.
) else (
    pause
)