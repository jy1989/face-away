@echo off
cd /d "%~dp0"
echo Installing Python packages and downloading verified ONNX models...
uv run --python 3.11 --with-requirements requirements.txt python models.py
if errorlevel 1 pause
