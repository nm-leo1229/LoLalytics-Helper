@echo off
cd /d "%~dp0" || exit /b 1
if exist "data\*_*.json" del /q "data\*_*.json"
python "%~dp0scraper.py"
