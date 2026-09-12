@echo off
title DroneMap 3D Web Studio Launcher (SIH26158)
echo ========================================================
echo   DroneMap 3D Photogrammetry Studio - SIH26158 (NTRO)
echo ========================================================
echo.
echo [*] Checking local environment and dependencies...
python -m uv --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Warning: uv not found in PATH, falling back to python.
)

echo [*] Starting DroneMap API Server on port 8000...
start /b python -m uv run dronemap serve --port 8000 > server_output.log 2>&1

echo [*] Waiting for server to initialize...
timeout /t 3 /nobreak >nul

echo [*] Opening Web Studio in default browser...
start http://127.0.0.1:8000

echo.
echo ========================================================
echo   DroneMap Web Studio is ACTIVE!
echo   URL: http://127.0.0.1:8000
echo   To stop the server, close this window.
echo ========================================================
echo.
pause
