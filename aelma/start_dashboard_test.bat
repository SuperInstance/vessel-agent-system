@echo off
REM AELMA Dashboard Test Startup Script
REM This script starts all necessary services for dashboard testing

echo ============================================
echo AELMA Dashboard Test Environment
echo ============================================
echo.

echo [1/3] Starting Test TwinCore Server...
start /B python test_twin_server.py
timeout /t 2 /nobreak >nul
echo     - TwinCore test server running on ws://localhost:8090
echo.

echo [2/3] Starting Viewer Server...
cd viewer
start /B python serve.py --port 8080
timeout /t 2 /nobreak >nul
echo     - Viewer server running on http://localhost:8080
echo.

echo [3/3] Opening Dashboard...
start http://localhost:8080/dashboard.html
timeout /t 1 /nobreak >nul
echo     - Dashboard opened in browser
echo.

echo ============================================
echo Dashboard Test Environment Ready!
echo ============================================
echo.
echo Services running:
echo   - Test TwinCore: ws://localhost:8090
echo   - Viewer:        http://localhost:8080/dashboard.html
echo.
echo Press Ctrl+C to stop all services
echo.

REM Keep script running
wait
