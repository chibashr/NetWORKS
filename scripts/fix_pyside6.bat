@echo off
setlocal enabledelayedexpansion

echo.
echo ==========================================
echo    PySide6 DLL Fix Script
echo ==========================================
echo.
echo This script will:
echo   1. Close any running Python processes
echo   2. Reinstall PySide6 to fix DLL issues
echo   3. Test the installation
echo.

if "%NETWORKS_AUTOMATED%"=="1" (
    echo [INFO] Automated mode detected.
) else (
    echo WARNING: This will close all Python processes.
    echo Press Ctrl+C to cancel or any key to continue...
    pause > nul
)

echo.
echo [STEP 1/3] Checking for running Python processes...
tasklist | findstr /i "python.exe" >nul 2>&1
if %ERRORLEVEL% equ 0 (
    echo [INFO] Found running Python processes. Closing them...
    taskkill /F /IM python.exe /T >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        echo [OK] Python processes closed.
        timeout /t 2 /nobreak >nul
    ) else (
        echo [WARNING] Could not close all Python processes. You may need to close them manually.
    )
) else (
    echo [OK] No Python processes running.
)

echo.
echo [STEP 2/3] Reinstalling PySide6...
cd /d "%~dp0\.."
if not exist "venv\Scripts\pip.exe" (
    echo [ERROR] Virtual environment not found. Please run repair_installation.bat first.
    if "%NETWORKS_AUTOMATED%"=="1" (
        exit /b 1
    ) else (
        pause
        exit /b 1
    )
)

echo [INFO] Uninstalling PySide6 packages...
venv\Scripts\pip.exe uninstall -y PySide6 PySide6_Essentials PySide6_Addons shiboken6 >nul 2>&1

echo [INFO] Installing PySide6...
venv\Scripts\pip.exe install --no-cache-dir "PySide6==6.10.1"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install PySide6.
    if "%NETWORKS_AUTOMATED%"=="1" (
        exit /b 1
    ) else (
        pause
        exit /b 1
    )
)

echo.
echo [STEP 3/3] Testing PySide6 installation...
venv\Scripts\python.exe -c "from PySide6.QtCore import QObject; print('[OK] PySide6.QtCore imported successfully!')" 2>&1
if %ERRORLEVEL% equ 0 (
    echo.
    echo ==========================================
    echo    PySide6 Fix Complete!
    echo ==========================================
    echo.
    echo PySide6 has been successfully reinstalled and tested.
    echo You can now run the application using Start_NetWORKS.bat
    echo.
) else (
    echo.
    echo [ERROR] PySide6 installation test failed.
    echo.
    echo This may indicate:
    echo   - Missing Visual C++ Redistributable
    echo   - System-level DLL issues
    echo   - Architecture mismatch
    echo.
    echo Please check the error message above for details.
    echo.
)

if "%NETWORKS_AUTOMATED%"=="1" (
    exit /b %ERRORLEVEL%
) else (
    pause
    exit /b %ERRORLEVEL%
)
