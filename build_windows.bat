@echo off
setlocal
cd /d "%~dp0"
echo ========================================
echo  VYZN Windows executable builder
echo ========================================
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher 'py' was not found. Install Python 3.11+ from python.org first.
  pause
  exit /b 1
)
if not exist .venv\Scripts\python.exe (
  py -3 -m venv .venv
  if errorlevel 1 goto :error
)
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
if errorlevel 1 goto :error
python -m pip install -r requirements.txt
if errorlevel 1 goto :error
python -m PyInstaller --noconfirm --clean --windowed --onedir --name VYZN --icon "assets\icons\VYZN.ico" --add-data "assets\icons\VYZN.ico;assets\icons" --collect-all qtawesome --collect-all PySide6 --paths src src\vyzn\main.py
if errorlevel 1 goto :error
if exist dist\VYZN\data rmdir /s /q dist\VYZN\data
if exist dist\VYZN_SHARE.zip del /q dist\VYZN_SHARE.zip
powershell -NoProfile -ExecutionPolicy Bypass -Command "Compress-Archive -Path 'dist\VYZN\*' -DestinationPath 'dist\VYZN_SHARE.zip' -Force"
if errorlevel 1 goto :error
echo.
echo BUILD COMPLETE!
echo App folder: %CD%\dist\VYZN
echo Shareable ZIP: %CD%\dist\VYZN_SHARE.zip
echo Share the ZIP with your friends. They extract it and double-click VYZN.exe.
echo Each Windows user gets a separate database under %%APPDATA%%\VYZN.
pause
exit /b 0
:error
echo.
echo BUILD FAILED. Read the error above, then try again.
pause
exit /b 1
