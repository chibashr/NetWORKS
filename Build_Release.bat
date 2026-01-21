@echo off
setlocal enabledelayedexpansion

echo.
echo ==========================================
echo      NetWORKS Portable EXE Builder
echo ==========================================
echo.

set NETWORKS_AUTOMATED=1
set BUILD_VENV=.venv_build
set DIST_DIR=dist

echo [STEP 1/5] Checking Python...
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    exit /b 1
)

echo [STEP 2/5] Preparing build environment...
if exist "%BUILD_VENV%" (
    rmdir /s /q "%BUILD_VENV%"
)
python -m venv "%BUILD_VENV%"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to create build virtual environment.
    exit /b 1
)

call "%BUILD_VENV%\Scripts\activate.bat"
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt --no-cache-dir
python -m pip install "pyinstaller>=6.10.0" --no-cache-dir
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to install build dependencies.
    call "%BUILD_VENV%\Scripts\deactivate.bat"
    rmdir /s /q "%BUILD_VENV%"
    exit /b 1
)

echo [STEP 3/5] Cleaning previous build output...
if exist "%DIST_DIR%" (
    rmdir /s /q "%DIST_DIR%"
)

echo [STEP 4/5] Building portable onedir executable...
pyinstaller ^
  --noconfirm ^
  --clean ^
  --onedir ^
  --name NetWORKS ^
  --noconsole ^
  --add-data "manifest.json;." ^
  --add-data "config;config" ^
  --add-data "plugins;plugins" ^
  --collect-all PySide6 ^
  --collect-all qtpy ^
  --collect-all qtawesome ^
  networks.py

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Build failed.
    call "%BUILD_VENV%\Scripts\deactivate.bat"
    rmdir /s /q "%BUILD_VENV%"
    exit /b 1
)

echo [STEP 5/5] Cleanup...
call "%BUILD_VENV%\Scripts\deactivate.bat"
rmdir /s /q "%BUILD_VENV%"

echo.
echo ==========================================
echo [SUCCESS] Build complete.
echo Output: %CD%\%DIST_DIR%\NetWORKS\
echo ==========================================
echo.
exit /b 0
