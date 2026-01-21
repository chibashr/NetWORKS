@echo off
setlocal enabledelayedexpansion

echo.
echo ==========================================
echo      NetWORKS Automated Install Test
echo ==========================================
echo.

set NETWORKS_AUTOMATED=1
set QT_QPA_PLATFORM=offscreen
set TEST_VENV=.venv_test

echo [STEP 1/5] Checking Python...
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    exit /b 1
)

echo [STEP 2/5] Creating fresh virtual environment...
if exist "%TEST_VENV%" (
    rmdir /s /q "%TEST_VENV%"
)
python -m venv "%TEST_VENV%"
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Failed to create test virtual environment.
    exit /b 1
)

echo [STEP 3/5] Installing dependencies...
call "%TEST_VENV%\Scripts\activate.bat"
python -m pip install --upgrade pip >nul 2>&1
python -m pip install -r requirements.txt --no-cache-dir
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Dependency installation failed.
    call "%TEST_VENV%\Scripts\deactivate.bat"
    rmdir /s /q "%TEST_VENV%"
    exit /b 1
)

echo [STEP 4/5] Running smoke test...
python networks.py --smoke-test
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Smoke test failed.
    call "%TEST_VENV%\Scripts\deactivate.bat"
    rmdir /s /q "%TEST_VENV%"
    exit /b 1
)

echo [STEP 5/5] Cleanup...
call "%TEST_VENV%\Scripts\deactivate.bat"
rmdir /s /q "%TEST_VENV%"

echo.
echo ==========================================
echo [SUCCESS] Install + Run test completed.
echo ==========================================
echo.
exit /b 0
