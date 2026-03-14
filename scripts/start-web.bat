@echo off
chcp 65001 >nul
cd /d "%~dp0..\apps\web"
echo [Web] Starting Next.js (port 3000)...
bun run dev
