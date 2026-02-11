@echo off
setlocal

echo ===================================================
echo   SAP Tax Code Exempt Updater  v2.0
echo ===================================================
echo.

:: ---------------------------------------------------
::  Check Python is available
:: ---------------------------------------------------
where py >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python launcher ^(py^) not found on PATH.
    echo         Please install Python 3.x from https://www.python.org/
    pause
    exit /b 1
)

:: ---------------------------------------------------
::  Install / upgrade dependencies (quiet mode)
:: ---------------------------------------------------
echo [1/2] Checking dependencies ...
pip install --quiet --upgrade requests keyring
if %ERRORLEVEL% neq 0 (
    echo [WARN] pip install had issues -- continuing anyway.
)
echo       Done.
echo.

:: ---------------------------------------------------
::  Run the main script
:: ---------------------------------------------------
echo [2/2] Starting update script ...
echo.
py "%~dp00._PYTHON_SCRIPTS\Run_Tax_Code_Exempt.PY"
set SCRIPT_EXIT=%ERRORLEVEL%

echo.
if %SCRIPT_EXIT% equ 0 (
    echo [FINISHED] Script completed successfully.
) else (
    echo [FINISHED] Script exited with code %SCRIPT_EXIT%.
)

echo.
pause
endlocal
exit /b %SCRIPT_EXIT%
