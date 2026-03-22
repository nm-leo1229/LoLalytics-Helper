@echo off
cd /d "%~dp0"
if exist "data\" (
    echo data 폴더 삭제 중...
    rmdir /s /q "data"
)
mkdir "data" 2>nul
call python C:\Users\user\Documents\LoLalytics-Helper\LoLalytics-Helper\scraper.py
