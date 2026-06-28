@echo off
chcp 65001 >nul
title Amazon Ads Optimization Agent

echo ============================================
echo   Amazon Ads Optimization Agent
echo ============================================
echo.

REM Check Python
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Please install Python first.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Install dependencies if not installed
echo Checking dependencies...
python -c "import flask" 2>nul
if %errorlevel% neq 0 (
    echo Installing dependencies...
    pip install flask waitress python-dotenv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

REM Check .env file
if not exist ".env" (
    echo [WARNING] .env file not found. Copying from .env.example...
    copy .env.example .env >nul
    echo [WARNING] Please edit .env and add your API keys before using.
    echo.
)

echo.
echo Starting server...
echo Open your browser: http://localhost:5000
echo Press Ctrl+C to stop.
echo.

cd /d "%~dp0"
python app.py

pause
