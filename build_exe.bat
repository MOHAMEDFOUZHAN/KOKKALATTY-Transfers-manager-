@echo off
echo ========================================================
echo   KOKKALATTY Transfers - Build Standalone Executable
echo ========================================================
echo.
echo Compiling application with PyInstaller...
pyinstaller --noconfirm --clean KOKKALATTY_TRANSFERS.spec
echo.
if exist "dist\KOKKALATTY_Transfers.exe" (
    echo ========================================================
    echo   SUCCESS: Executable created at:
    echo   dist\KOKKALATTY_Transfers.exe
    echo ========================================================
) else (
    echo [ERROR] Build failed! Check the log above for details.
)
pause
