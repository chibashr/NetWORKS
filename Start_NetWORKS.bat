@echo off
setlocal enabledelayedexpansion
Fix these command managset NETWORKS_AUTOMATED=1

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
venv\Scripts\python.exe scripts\check_core_deps.py PySide6 qtpy qtawesome yaml jsonschema markdown loguru chardet >nul 2>&1
if errorlevel 1 goto missing_deps
goto deps_done

:missing_deps
echo [WARNING] Some required dependencies are missing. Attempting targeted installation...

echo [INFO] Installing dependencies from requirements.txt...
venv\Scripts\pip.exe install -r requirements.txt --no-cache-dir

echo [INFO] Attempting optional pandas install (non-blocking)...
venv\Scripts\pip.exe install "pandas>=2.3.3,<3.0" --only-binary=:all: --no-cache-dir >nul 2>&1
if errorlevel 1 goto pandas_missing
echo [INFO] Optional dependency pandas installed.
goto pandas_done
:pandas_missing
echo [WARNING] Optional dependency pandas could not be installed. Some features may be unavailable.
:pandas_done

:: Check again if all dependencies are now available
venv\Scripts\python.exe scripts\check_core_deps.py PySide6 qtpy qtawesome yaml jsonschema markdown loguru chardet >nul 2>&1
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
        echo [ERROR] Application crashed with error code %APP_EXIT_CODE%. See logs for details.
        
        echo [INFO] Checking if this is a dependency issue...
        venv\Scripts\python.exe -c "import sys; print('This is a test to see if Python is working properly.')" >nul 2>&1
        
        if %ERRORLEVEL% neq 0 (
            echo [WARNING] Python environment may be corrupt. Attempting repair...
            if exist "repair_installation.bat" (
                call venv\Scripts\deactivate.bat
                call repair_installation.bat
                echo [INFO] Please try running the application again after repair.
            )
        ) else (
            echo [INFO] Python environment seems functional. This may be an application issue.
            echo [INFO] Please check the logs in the 'logs' directory for more information.
        )
        
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