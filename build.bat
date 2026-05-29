@echo off
:: ============================================================
:: build.bat — builds PhoenixCheckoutTool exe, installer, and zips
::
:: Requires:
::   pip install pyinstaller
::   Inno Setup 6  (https://jrsoftware.org/isinfo.php)
:: ============================================================

:: ── APP SETTINGS ─────────────────────────────────────────────
set APP_NAME=PhoenixCheckoutTool
set APP_MAIN=checkout_tool_gui.py
set APP_ICON=PTT_Normal_green.ico
:: ─────────────────────────────────────────────────────────────

:: Python 3.12 soft-warn (FROZEN_BUILD_BASELINE / ADR-014)
for /f "tokens=2" %%P in ('python --version 2^>^&1') do set PYTHON_VERSION=%%P
echo Detected Python: %PYTHON_VERSION%
echo %PYTHON_VERSION% | findstr /b "3.12." >nul
if errorlevel 1 (
    echo WARNING: Canonical frozen-build venv is Python 3.12 per ADR-014 / FROZEN_BUILD_BASELINE.
    echo          Current interpreter is %PYTHON_VERSION%. Build will proceed but the
    echo          S1-safe bootloader profile is only verified on 3.12.
)

:: Phase 3B retrofit preflight: verify the phoenix-commons submodule is
:: initialised (ADR-015 — submodule + editable install is the official
:: transport). A fresh clone needs `git submodule update --init --recursive`
:: before `pip install -r requirements.txt` can resolve the `-e ./commons` line.
if not exist "commons\src\phoenix_commons\__init__.py" (
    echo.
    echo ERROR: phoenix-commons submodule missing. Run:
    echo        git submodule update --init --recursive
    echo        pip install -r requirements.txt
    exit /b 1
)
python -c "import phoenix_commons" >nul 2>&1
if errorlevel 1 (
    echo ERROR: phoenix_commons not importable. Re-install:
    echo        pip install -e .\commons
    exit /b 1
)

:: Read version from version.py
for /f "tokens=3 delims= " %%v in ('findstr "__version__" version.py') do set VERSION=%%~v

:: Step 0: full cleanup (FROZEN_BUILD_BASELINE)
if exist dist  rmdir /s /q dist
if exist build rmdir /s /q build

echo ============================================================
echo  Building %APP_NAME% v%VERSION%
echo ============================================================
echo.

:: ── Step 1: PyInstaller ──────────────────────────────────────
echo [1/3] Running PyInstaller...
pyinstaller ^
    --onedir ^
    --windowed ^
    --noconfirm ^
    --noupx ^
    --icon=%APP_ICON% ^
    --name=%APP_NAME% ^
    --add-data="%APP_ICON%;." ^
    --add-data="green.png;." ^
    --add-data="checkout_template.xlsx;." ^
    --add-data="template_gex.xlsx;." ^
    --add-data="template_mav.xlsx;." ^
    --add-data="template_cscp_fh.xlsx;." ^
    --add-data="template_pbc_room.xlsx;." ^
    --collect-all=phoenix_commons ^
    --exclude-module=tkinter ^
    --exclude-module=_tkinter ^
    --exclude-module=tcl ^
    --exclude-module=tk ^
    --exclude-module=lib2to3 ^
    --exclude-module=idlelib ^
    --exclude-module=turtle ^
    --exclude-module=turtledemo ^
    %APP_MAIN%

if errorlevel 1 (
    echo.
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)
echo [1/3] PyInstaller complete.
echo.

:: ── Step 2: Inno Setup installer ─────────────────────────────
echo [2/3] Building installer with Inno Setup...

set ISCC=""
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set ISCC="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe"       set ISCC="C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" set ISCC="%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"

if %ISCC%=="" (
    echo.
    echo WARNING: Inno Setup 6 not found. Skipping installer creation.
    echo          Download from: https://jrsoftware.org/isinfo.php
    echo          Then re-run build.bat.
    echo.
    goto :zips
)

%ISCC% /DMyAppVersion=%VERSION% installer.iss
if errorlevel 1 (
    echo.
    echo ERROR: Inno Setup build failed.
    pause
    exit /b 1
)
echo [2/3] Installer created: dist\%APP_NAME%Setup.exe
echo.

:: ── Step 3: Create zips ──────────────────────────────────────
:zips
echo [3/3] Creating zip archives...

:: Zip 1 - exe only for auto-updater
powershell -Command "Compress-Archive -Path 'dist\%APP_NAME%\%APP_NAME%.exe' -DestinationPath 'dist\%APP_NAME%.zip' -Force"
echo   Created: dist\%APP_NAME%.zip  (auto-updater)

:: Zip 2 - full folder for manual fresh installs
powershell -Command "Compress-Archive -Path 'dist\%APP_NAME%' -DestinationPath 'dist\%APP_NAME%_FullInstall.zip' -Force"
echo   Created: dist\%APP_NAME%_FullInstall.zip  (manual install)

echo.
echo ============================================================
echo  Build complete — v%VERSION%
echo ============================================================
echo.
echo  dist\%APP_NAME%\%APP_NAME%.exe        ^<-- test this first
echo  dist\%APP_NAME%Setup.exe              ^<-- installer
echo  dist\%APP_NAME%.zip                   ^<-- auto-updater zip
echo  dist\%APP_NAME%_FullInstall.zip       ^<-- manual install zip
echo.
echo  Upload to GitHub Release:
echo    - %APP_NAME%.zip             (required for auto-updater)
echo    - %APP_NAME%Setup.exe        (recommended for new users)
echo.
pause
