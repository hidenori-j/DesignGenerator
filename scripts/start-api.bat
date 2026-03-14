@echo off
chcp 65001 >nul
cd /d "%~dp0..\apps\api"
set MOCK_API=true
echo [API] Starting API Gateway (port 4000, MOCK_API=true)...
bun run dev
