@echo off
cd /d "%~dp0"
uv run --python 3.11 --with-requirements requirements.txt python app.py
if errorlevel 1 pause
