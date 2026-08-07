@echo off
echo Installing PyInstaller and dependencies...
pip install pyinstaller waitress pywebview fpdf
echo.
echo Building Standalone Executable...
pyinstaller --noconfirm --clean KOKKALATTY_TRANSFERS.spec
echo.
echo Done! Your executable is in the 'dist' folder.
pause
