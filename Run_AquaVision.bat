@echo off
title AquaVision Production Server
color 0B
echo =======================================================
echo          AquaVision - Ultimate Enhancement Build
echo =======================================================
echo Installing/Updating Requirements...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies. Make sure Python is installed!
    pause
    exit /b %errorlevel%
)

echo.
echo =======================================================
echo Dependency check complete. Starting AquaVision Server!
echo Waitress serving active on http://127.0.0.1:5000
echo =======================================================
python app.py
if %errorlevel% neq 0 (
    echo [ERROR] Server crashed or failed to start.
    pause
)
