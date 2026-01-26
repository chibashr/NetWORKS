@echo off
setlocal enabledelayedexpansion
set NETWORKS_AUTOMATED=1

:: Change to script directory to ensure we're in the right location
cd /d "%~dp0" 2>nul
if errorlevel 1 (
    echo [WARNING] Could not change to script directory. Continuing from current directory...
)

echo.
echo ==========================================
echo       Starting NetWORKS Application
echo ==========================================
echo.

:: Check if Python is installed first
where python >nul 2>&1
if errorlevel 1 (
    echo.
    echo ==========================================
    echo      Python Not Found
    echo ==========================================
    echo.
    echo [ERROR] Python is not installed or not in PATH.
    echo [ERROR] Please install Python 3.8 or later from https://www.python.org/downloads/
    echo.
    echo [INFO] Make sure to check "Add Python to PATH" during installation.
    echo.
    echo ==========================================
    echo.
    echo This window will remain open so you can read this message.
    echo.
    echo Press any key to close this window...
    pause
    exit /b 1
)

:: Read version from manifest.json if Python is available
set APP_VERSION=
set VERSION_SCRIPT=import json^; f=open(r'manifest.json'^)^; data=json.load(f^)^; print(data.get('version', '0.1.0'^)^)^; f.close(^)
if exist "venv\Scripts\python.exe" (
    for /f "tokens=*" %%a in ('venv\Scripts\python.exe -c "%VERSION_SCRIPT%" 2^>nul') do (
        set "APP_VERSION=%%a"
    )
) else (
    for /f "tokens=*" %%a in ('python -c "%VERSION_SCRIPT%" 2^>nul') do (
        set "APP_VERSION=%%a"
    )
)
if not "%APP_VERSION%"=="" (
    echo [INFO] NetWORKS version %APP_VERSION%
) else (
    echo [INFO] NetWORKS application
)

:: Surface known dependency limitations for newer Python versions
:pyver_checked

:: Check for environment variables that could block pip installation
:: Automatically unset problematic proxy variables for this session (NetWORKS does not use HTTP proxy)
set PIP_BLOCKED=0
set PROXY_FIXED=0

if "%PIP_NO_INDEX%"=="1" (
    set PIP_BLOCKED=1
    echo [ERROR] PIP_NO_INDEX is set to 1. This prevents pip from accessing PyPI.
    echo [ERROR] This will block dependency installation.
)

if not "%HTTP_PROXY%"=="" (
    echo %HTTP_PROXY% | findstr /C:"127.0.0.1:9" >nul 2>&1
    if not errorlevel 1 (
        echo [INFO] HTTP_PROXY is set to a dummy address. Unsetting for this session...
        echo [INFO] NetWORKS will not use HTTP proxy.
        set HTTP_PROXY=
        set PROXY_FIXED=1
    )
)

if not "%HTTPS_PROXY%"=="" (
    echo %HTTPS_PROXY% | findstr /C:"127.0.0.1:9" >nul 2>&1
    if not errorlevel 1 (
        echo [INFO] HTTPS_PROXY is set to a dummy address. Unsetting for this session...
        echo [INFO] NetWORKS will not use HTTP proxy.
        set HTTPS_PROXY=
        set PROXY_FIXED=1
    )
)

if not "%ALL_PROXY%"=="" (
    echo %ALL_PROXY% | findstr /C:"127.0.0.1:9" >nul 2>&1
    if not errorlevel 1 (
        echo [INFO] ALL_PROXY is set to a dummy address. Unsetting for this session...
        set ALL_PROXY=
        set PROXY_FIXED=1
    )
)

if %PROXY_FIXED% equ 1 (
    echo [INFO] Proxy variables have been unset for this session.
    echo.
)

if %PIP_BLOCKED% equ 1 (
    echo.
    echo ==========================================
    echo      Environment Variable Issue
    echo ==========================================
    echo.
    echo [ERROR] PIP_NO_INDEX is set to 1, which prevents pip from accessing PyPI.
    echo.
    echo [INFO] To permanently fix this issue:
    echo   1. Open System Properties ^> Environment Variables
    echo   2. Find PIP_NO_INDEX in User or System variables
    echo   3. Either delete it or set its value to 0
    echo   4. Restart your computer
    echo.
    echo [INFO] Or unset it for this session by running:
    echo   set PIP_NO_INDEX=
    echo.
    echo [INFO] Then try running Start_NetWORKS.bat again.
    echo.
    echo ==========================================
    echo.
    msg * "NetWORKS Error: PIP_NO_INDEX is set to 1, which blocks dependency installation. Please unset this variable and try again."
    echo.
    echo IMPORTANT: You must fix PIP_NO_INDEX before NetWORKS can run.
    echo.
    echo Press any key to close this window...
    pause
    exit /b 1
)

:: Check if repair_installation.bat exists
if not exist "scripts\repair_installation.bat" (
    echo [WARNING] Repair script not found. Some automatic repairs will not be available.
)

:: Check if virtual environment exists
if not exist "venv" (
    echo [INFO] Virtual environment not found. Running setup first...
    
    if exist "scripts\repair_installation.bat" (
        echo [INFO] Using repair installation script for setup...
        call scripts\repair_installation.bat
    ) else if exist "scripts\setup.bat" (
        call scripts\setup.bat
    ) else (
        echo.
        echo ==========================================
        echo      Scripts Not Found
        echo ==========================================
        echo.
        echo [ERROR] Neither repair_installation.bat nor setup.bat found in scripts folder.
        echo [ERROR] Please ensure the scripts are in the scripts directory.
        echo.
        echo ==========================================
        echo Press any key to close...
        pause
        exit /b 1
    )
    
    if errorlevel 1 (
        echo.
        echo ==========================================
        echo      Setup Failed
        echo ==========================================
        echo.
        echo [ERROR] Setup failed. Please check the error messages above.
        echo [ERROR] You can try running scripts\setup.bat or scripts\repair_installation.bat manually.
        echo.
        echo ==========================================
        echo.
        echo Press any key to close...
        pause
        exit /b 1
    )
) else (
    echo [INFO] Using existing virtual environment.
    
    :: Quick validation of virtual environment
    if exist "venv\Scripts\activate.bat" (
        :: Do nothing, environment looks valid
        echo [INFO] Virtual environment structure looks valid.
    ) else (
        echo [WARNING] Virtual environment may be corrupt.
        if exist "scripts\repair_installation.bat" (
            echo [INFO] Running repair installation script...
            call scripts\repair_installation.bat
            if errorlevel 1 (
                echo.
                echo ==========================================
                echo      Repair Failed
                echo ==========================================
                echo.
                echo [ERROR] Repair failed. Please try running scripts\repair_installation.bat manually.
                echo.
                echo ==========================================
                echo Press any key to close...
                pause
                exit /b 1
            )
        ) else (
            echo [WARNING] Cannot automatically repair. Virtual environment may need to be rebuilt.
            echo [INFO] Attempting to continue anyway...
        )
    )
)

:: Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat
    if errorlevel 1 (
        echo [ERROR] Failed to activate virtual environment.
        echo [INFO] This may indicate a corrupt environment. Attempting repair...
        
        if exist "scripts\repair_installation.bat" (
            call scripts\repair_installation.bat
            if %ERRORLEVEL% equ 0 (
                echo [INFO] Repair successful. Retrying activation...
                call venv\Scripts\activate.bat
                if errorlevel 1 (
                    echo.
                    echo ==========================================
                    echo      Activation Failed
                    echo ==========================================
                    echo.
                    echo [ERROR] Still unable to activate environment after repair.
                    echo.
                    echo ==========================================
                    echo Press any key to close...
                    pause
                    exit /b 1
                )
            ) else (
                echo.
                echo ==========================================
                echo      Repair Failed
                echo ==========================================
                echo.
                echo [ERROR] Repair failed. Please try running scripts\repair_installation.bat manually.
                echo.
                echo ==========================================
                echo Press any key to close...
                pause
                exit /b 1
            )
        ) else (
            echo.
            echo ==========================================
            echo      Cannot Repair
            echo ==========================================
            echo.
            echo [ERROR] Cannot automatically repair. Please reinstall the application.
            echo.
            echo ==========================================
            echo Press any key to close...
            pause
            exit /b 1
        )
    )

:: Quick validation of critical dependencies
echo [INFO] Validating core dependencies...
venv\Scripts\python.exe scripts\check_core_deps.py PySide6 qtawesome yaml markdown loguru chardet >nul 2>&1
if errorlevel 1 goto missing_deps
goto deps_done

:missing_deps
echo [WARNING] Some required dependencies are missing. Attempting targeted installation...

echo [INFO] Installing dependencies from requirements.txt...
venv\Scripts\pip.exe install -r requirements.txt --no-cache-dir >pip_install.log 2>&1
set PIP_EXIT=%ERRORLEVEL%
findstr /C:"ProxyError" /C:"Cannot connect to proxy" /C:"No matching distribution found" pip_install.log >nul 2>&1
if %ERRORLEVEL% equ 0 (
    if %PIP_EXIT% neq 0 (
        echo [ERROR] Pip installation failed due to proxy or network issues.
        type pip_install.log
        msg * "NetWORKS Installation Error: Failed to install dependencies. This may be due to proxy settings (HTTP_PROXY/HTTPS_PROXY) or PIP_NO_INDEX being enabled. Check your environment variables and network settings."
        del pip_install.log >nul 2>&1
        echo.
        echo ==========================================
        echo.
        echo Press any key to close...
        pause
        exit /b 1
    )
)
del pip_install.log >nul 2>&1
if %PIP_EXIT% neq 0 (
    echo [WARNING] Some dependencies may have failed to install. Check the output above for details.
)

echo [INFO] Attempting optional pandas install (non-blocking)...
venv\Scripts\pip.exe install "pandas>=2.3.3,<3.0" --only-binary=:all: --no-cache-dir >nul 2>&1
if errorlevel 1 goto pandas_missing
echo [INFO] Optional dependency pandas installed.
goto pandas_done
:pandas_missing
echo [WARNING] Optional dependency pandas could not be installed. Some features may be unavailable.
:pandas_done

:: Check again if all dependencies are now available
venv\Scripts\python.exe scripts\check_core_deps.py PySide6 qtawesome yaml markdown loguru chardet >nul 2>&1
if errorlevel 1 goto deps_failed
echo [INFO] Dependencies installed successfully.
goto deps_done

:deps_failed
echo [ERROR] Critical dependencies still missing after installation attempts.
if exist "scripts\repair_installation.bat" (
    echo [INFO] Running full repair...
    call venv\Scripts\deactivate.bat
    call scripts\repair_installation.bat
    call venv\Scripts\activate.bat
) else (
    echo.
    echo ==========================================
    echo      Cannot Repair
    echo ==========================================
    echo.
    echo [ERROR] Cannot automatically repair. Please reinstall the application.
    echo.
    echo ==========================================
    echo.
    echo IMPORTANT: You must fix these environment variables before NetWORKS can run.
    echo.
    echo Press any key to close this window...
    pause
    exit /b 1
)

:deps_done

echo [INFO] Starting NetWORKS...
echo.

:: Run the application and capture any immediate errors
venv\Scripts\python.exe networks.py 2>&1
set APP_EXIT_CODE=%ERRORLEVEL%

:: Check if the application exited with an error code
if %APP_EXIT_CODE% neq 0 (
    if %APP_EXIT_CODE% equ 1 (
        echo [INFO] Application exited with code 1. Dependencies may have been installed.
        echo [INFO] Restarting application...
        venv\Scripts\python.exe networks.py
        set APP_EXIT_CODE=%ERRORLEVEL%
        
        if %APP_EXIT_CODE% neq 0 (
            echo [ERROR] Application failed to start after dependency installation.
            echo [INFO] Attempting repair...
            
            if exist "scripts\repair_installation.bat" (
                call venv\Scripts\deactivate.bat
                call scripts\repair_installation.bat
                if %ERRORLEVEL% equ 0 (
                    echo [INFO] Repair successful. Reactivating environment and restarting application...
                    call venv\Scripts\activate.bat
                    venv\Scripts\python.exe networks.py
                    set APP_EXIT_CODE=%ERRORLEVEL%
                    
                    if %APP_EXIT_CODE% neq 0 (
                        echo [ERROR] Application still fails after repair.
                        echo [INFO] Please check the logs in the 'logs' directory for more information.
                        echo.
                        echo ==========================================
                        echo Press any key to close...
                        pause
                        exit /b %APP_EXIT_CODE%
                    )
                ) else (
                    echo.
                    echo ==========================================
                    echo      Repair Failed
                    echo ==========================================
                    echo.
                    echo [ERROR] Repair failed. Please try running scripts\repair_installation.bat manually.
                    echo.
                    echo ==========================================
                    echo Press any key to close...
                    pause
                    exit /b 1
                )
            ) else (
                echo.
                echo ==========================================
                echo      Cannot Repair
                echo ==========================================
                echo.
                echo [ERROR] Cannot automatically repair. Please check the logs for details.
                echo.
                echo ==========================================
                echo Press any key to close...
                pause
                exit /b %APP_EXIT_CODE%
            )
        )
    ) else (
        echo.
        echo ==========================================
        echo      Application Error Detected
        echo ==========================================
        echo.
        echo [ERROR] Application crashed with error code %APP_EXIT_CODE%.
        echo.
        echo If a crash dialog appeared, it contains the detailed error information.
        echo Otherwise, please check the logs directory for error details.
        echo.
        
        :: Show error message box
        msg * "NetWORKS Error: Application crashed with exit code %APP_EXIT_CODE%. Check the console output and logs directory for details."
        
        echo [INFO] Checking if this is a dependency issue...
        if exist "venv\Scripts\python.exe" (
            venv\Scripts\python.exe -c "import sys; print('This is a test to see if Python is working properly.')" >nul 2>&1
            
            if %ERRORLEVEL% neq 0 (
                echo [WARNING] Python environment may be corrupt. Attempting repair...
                if exist "scripts\repair_installation.bat" (
                    call venv\Scripts\deactivate.bat 2>nul
                    call scripts\repair_installation.bat
                    if %ERRORLEVEL% equ 0 (
                        echo [INFO] Repair completed. Please try running the application again.
                    ) else (
                        echo [ERROR] Repair failed. Please check the error messages above.
                    )
                ) else (
                    echo [ERROR] Repair script not found. Cannot automatically repair.
                )
            ) else (
                echo [INFO] Python environment seems functional. This may be an application issue.
                echo [INFO] Please check the logs in the 'logs' directory for more information.
            )
        ) else (
            echo [ERROR] Virtual environment Python executable not found.
            echo [INFO] Attempting to run repair script...
            if exist "scripts\repair_installation.bat" (
                call scripts\repair_installation.bat
            )
        )
        
        echo.
        echo ==========================================
        echo      Error Information Displayed
        echo ==========================================
        echo.
        echo ==========================================
        echo.
        echo This window will remain open so you can read the error information.
        echo.
        echo Press any key to close...
        pause
        exit /b %APP_EXIT_CODE%
    )
)

:: Deactivate virtual environment before exiting
call venv\Scripts\deactivate.bat

echo.
echo ==========================================
echo      NetWORKS Application Closed
echo ==========================================
echo.
echo Application exited normally.
echo This window will close in 3 seconds...
timeout /t 3 >nul
