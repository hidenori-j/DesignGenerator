@echo off
chcp 65001 >nul
set ROOT=%~dp0..
echo Starting DesignGenerator (API + Web)...
start "DesignGenerator API" cmd /k "cd /d %ROOT%\apps\api && set MOCK_API=true && bun run dev"
timeout /t 2 /nobreak >nul
start "DesignGenerator Web" cmd /k "cd /d %ROOT%\apps\web && bun run dev"
echo.
echo API: http://localhost:4000
echo Web: http://localhost:3000
echo Close the two windows to stop.
