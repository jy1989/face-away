@echo off
setlocal
cd /d "%~dp0"
if not exist "models\face_detection_yunet_2023mar.onnx" (
  echo Models missing. Run setup.bat first.
  pause
  exit /b 1
)
if not exist "models\face_recognition_sface_2021dec.onnx" (
  echo Models missing. Run setup.bat first.
  pause
  exit /b 1
)
echo Building FaceAway-v0.3.exe (Windows, single file, no console)...
uv run --python 3.11 --with-requirements requirements.txt --with "pyinstaller>=6.10,<7" python -m PyInstaller ^
  --noconfirm --clean --onefile --windowed ^
  --name "FaceAway-v0.3" ^
  --add-data "models;models" ^
  --exclude-module "tkinter" ^
  app.py
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)
echo.
echo Finished: "%~dp0dist\FaceAway-v0.3.exe"
echo You can double-click the EXE. No Python / BAT / console required.
pause
