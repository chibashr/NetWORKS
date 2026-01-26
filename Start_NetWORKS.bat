@echo off
setlocal enabledelayedexpansion
set NETWORKS_AUTOMATED=1

echo.
echo ==========================================
echo       Starting NetWORKS Application
echo ==========================================
echo.

:: Read version from manifest.json if Python is available
where python >nul 2>&1
if %ERRORLEVEL% equ 0 (
    if exist "venv\Scripts\python.exe" (
        for /f "tokens=*" %%a in ('venv\Scripts\python.exe -c "import json; f=open(r'.\\manifest.json'); data=json.load(f); print(data.get('version', '0.1.0')); f.close()"') do (
            set APP_VERSION=%%a
        )
    ) else (
        for /f "tokens=*" %%a in ('python -c "import json; f=open(r'.\\manifest.json'); data=json.load(f); print(data.get('version', '0.1.0')); f.close()"') do (
            set APP_VERSION=%%a
        )
    )
    echo [INFO] NetWORKS version %APP_VERSION%
) else (
    echo [INFO] NetWORKS application
)

:: Surface known dependency limitations for newer Python versions
for /f "tokens=2" %%V in ('python --version 2^>^&1') do set PYVER=%%V
for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set MAJOR=%%a
    set MINOR=%%b
)
if %MAJOR% GTR 3 goto pyver_checked
if %MAJOR% EQU 3 (
    if %MINOR% GEQ 14 (
        echo [WARNING] Python %PYVER% detected. PySide6 6.10.1 does not provide wheels for 3.14.
        echo [WARNING] Use Python 3.12 or 3.13 to install dependencies successfully.
        echo [INFO] Optional pandas/numpy are pinned to <3.13 and will be skipped on 3.13+.
    )
)
:pyver_checked

:: Check for environment variables that could block pip installation
set PIP_BLOCKED=0
if not "%PIP_NO_INDEX%"=="" (
    if "%PIP_NO_INDEX%"=="1" (
        set PIP_BLOCKED=1
        echo [ERROR] PIP_NO_INDEX is set to 1, which prevents pip from accessing PyPI.
        echo [ERROR] This will block dependency installation.
        msg * "NetWORKS Installation Error: PIP_NO_INDEX is enabled. This prevents downloading dependencies from PyPI. Please unset PIP_NO_INDEX or set it to 0, then try again."
    )
)
if not "%HTTP_PROXY%"=="" (
    echo %HTTP_PROXY% | findstr /C:"127.0.0.1:9" >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        set PIP_BLOCKED=1
        echo [ERROR] HTTP_PROXY is set to a dummy address (127.0.0.1:9), which will block pip downloads.
        echo [ERROR] This will prevent dependency installation.
        msg * "NetWORKS Installation Error: HTTP_PROXY is set to 127.0.0.1:9 (dummy address). This blocks pip from downloading dependencies. Please unset HTTP_PROXY, HTTPS_PROXY, and ALL_PROXY, then try again."
    )
)
if not "%HTTPS_PROXY%"=="" (
    echo %HTTPS_PROXY% | findstr /C:"127.0.0.1:9" >nul 2>&1
    if %ERRORLEVEL% equ 0 (
        set PIP_BLOCKED=1
        echo [ERROR] HTTPS_PROXY is set to a dummy address (127.0.0.1:9), which will block pip downloads.
        echo [ERROR] This will prevent dependency installation.
        msg * "NetWORKS Installation Error: HTTPS_PROXY is set to 127.0.0.1:9 (dummy address). This blocks pip from downloading dependencies. Please unset HTTP_PROXY, HTTPS_PROXY, and ALL_PROXY, then try again."
    )
)
if %PIP_BLOCKED% equ 1 (
    echo.
    echo [INFO] To fix this issue:
    echo   - Unset PIP_NO_INDEX: set PIP_NO_INDEX=
    echo   - Unset proxy variables: set HTTP_PROXY= ^& set HTTPS_PROXY= ^& set ALL_PROXY=
    echo   - Or restart your command prompt/terminal to clear environment variables
    echo.
    pause
    exit /b 1
)

:: Check if repair_installation.bat exists
if not exist "repair_installation.bat" (
    echo [WARNING] Repair script not found. Some automatic repairs will not be available.
)

:: Check if virtual environment exists
if not exist "venv" (
    echo [INFO] Virtual environment not found. Running setup first...
    
    if exist "repair_installation.bat" (
        echo [INFO] Using repair installation script for setup...
        call repair_installation.bat
    ) else (
        call setup.bat
    )
    
    if %ERRORLEVEL% neq 0 (
        echo [ERROR] Setup failed. Please run setup.bat manually.
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
        if exist "repair_installation.bat" (
            echo [INFO] Running repair installation script...
            call repair_installation.bat
            if %ERRORLEVEL% neq 0 (
                echo [ERROR] Repair failed. Please try running repair_installation.bat manually.
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
    
    if exist "repair_installation.bat" (
        call repair_installation.bat
        if %ERRORLEVEL% equ 0 (
            echo [INFO] Repair successful. Retrying activation...
            call venv\Scripts\activate.bat
            if %ERRORLEVEL% neq 0 (
                echo [ERROR] Still unable to activate environment after repair.
                pause
                exit /b 1
            )
        ) else (
            echo [ERROR] Repair failed. Please try running repair_installation.bat manually.
            pause
            exit /b 1
        )
    ) else (
        echo [ERROR] Cannot automatically repair. Please reinstall the application.
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
if exist "repair_installation.bat" (
    echo [INFO] Running full repair...
    call venv\Scripts\deactivate.bat
    call repair_installation.bat
    call venv\Scripts\activate.bat
) else (
    echo [ERROR] Cannot automatically repair. Please reinstall the application.
    pause
    exit /b 1
)

:deps_done

echo [INFO] Starting NetWORKS...
venv\Scripts\python.exe networks.py
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
            
            if exist "repair_installation.bat" (
                call venv\Scripts\deactivate.bat
                call repair_installation.bat
                if %ERRORLEVEL% equ 0 (
                    echo [INFO] Repair successful. Reactivating environment and restarting application...
                    call venv\Scripts\activate.bat
                    venv\Scripts\python.exe networks.py
                    set APP_EXIT_CODE=%ERRORLEVEL%
                    
                    if %APP_EXIT_CODE% neq 0 (
                        echo [ERROR] Application still fails after repair.
                        echo [INFO] Please check the logs in the 'logs' directory for more information.
                        pause
                        exit /b %APP_EXIT_CODE%
                    )
                ) else (
                    echo [ERROR] Repair failed. Please try running repair_installation.bat manually.
                    pause
                    exit /b 1
                )
            ) else (
                echo [ERROR] Cannot automatically repair. Please check the logs for details.
                pause
                exit /b %APP_EXIT_CODE%
            )
        )
    ) else (
        echo [ERROR] Application crashed with error code %APP_EXIT_CODE%.
        echo.
        echo ==========================================
        echo      Application Error Detected
        echo ==========================================
        echo.
        echo The application exited with error code %APP_EXIT_CODE%.
        echo.
        echo If a crash dialog appeared, it contains the detailed error information.
        echo Otherwise, please check the logs directory for error details.
        echo.
        
        :: Show error message box
        msg * "NetWORKS Error: Application crashed with exit code %APP_EXIT_CODE%. Check the console output and logs directory for details."
        
        echo [INFO] Checking if this is a dependency issue...
        venv\Scripts\python.exe -c "import sys; print('This is a test to see if Python is working properly.')" >nul 2>&1
        
        if %ERRORLEVEL% neq 0 (
            echo [WARNING] Python environment may be corrupt. Attempting repair...
            if exist "repair_installation.bat" (
                call venv\Scripts\deactivate.bat
                call repair_installation.bat
                if %ERRORLEVEL% equ 0 (
                    echo [INFO] Repair completed. Please try running the application again.
                ) else (
                    echo [ERROR] Repair failed. Please check the error messages above.
                )
            )
        ) else (
            echo [INFO] Python environment seems functional. This may be an application issue.
            echo [INFO] Please check the logs in the 'logs' directory for more information.
        )
        
        echo.
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