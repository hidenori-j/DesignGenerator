@echo off
chcp 65001 >nul

REM Resolve absolute path to project root
pushd "%~dp0.."
set ROOT=%CD%
popd

echo ============================================
echo  DesignGenerator - Full Stack Launch
echo ============================================
echo.

REM --- 1. Docker ---
where docker >nul 2>nul
if errorlevel 1 (
    echo [1/7] Docker not found - using MOCK mode.
    set MOCK_API=true
    goto skip_docker
)
echo [1/7] Starting Docker infrastructure...
docker compose -f %ROOT%\infra\docker-compose.yml up -d
timeout /t 3 /nobreak >nul
:skip_docker

REM --- 2. Ingest ---
if defined MOCK_API (
    echo [2/7] Skipping Ingest (mock mode^).
    goto skip_ingest
)
echo [2/7] Starting Ingest Service (port 8200^)...
start "Ingest" cmd /c "cd /d %ROOT%\services\ingest & python -m uv run uvicorn src.main:app --host 0.0.0.0 --port 8200 --reload"
timeout /t 5 /nobreak >nul
:skip_ingest

REM --- 3. Generation ---
if defined MOCK_API (
    echo [3/7] Skipping Generation (mock mode^).
    goto skip_generation
)
echo [3/7] Starting Generation Service (port 8100^)...
start "Generation" cmd /c "cd /d %ROOT%\services\generation & python -m uv run uvicorn src.main:app --host 0.0.0.0 --port 8100 --reload"
timeout /t 3 /nobreak >nul
:skip_generation

REM --- 4. GPU Arbiter ---
if defined MOCK_API (
    echo [4/7] Skipping GPU Arbiter (mock mode^).
    goto skip_arbiter
)
echo [4/7] Starting GPU Arbiter (port 8300^)...
start "GPU-Arbiter" cmd /c "cd /d %ROOT%\services\gpu_arbiter & python -m uv run uvicorn src.main:app --host 0.0.0.0 --port 8300 --reload"
timeout /t 3 /nobreak >nul
:skip_arbiter

REM --- 5. Agent ---
if defined MOCK_API (
    echo [5/7] Skipping Agent (mock mode^).
    goto skip_agent
)
echo [5/7] Starting Agent Service (port 8000^)...
start "Agent" cmd /c "cd /d %ROOT%\services\agent & python -m uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 3 /nobreak >nul
:skip_agent

REM --- 6. Collector ---
if defined MOCK_API (
    echo [6/7] Skipping Collector (mock mode^).
    goto skip_collector
)
echo [6/7] Starting Collector Service (port 8400^)...
start "Collector" cmd /c "cd /d %ROOT%\services\collector & python -m uv run uvicorn src.main:app --host 0.0.0.0 --port 8400 --reload"
timeout /t 3 /nobreak >nul
:skip_collector

REM --- 7. API + Web ---
echo [7/7] Starting API Gateway (4000^) + Web (3000^)...
if defined MOCK_API (
    start "API" cmd /c "cd /d %ROOT%\apps\api & set MOCK_API=true & bun run dev"
) else (
    start "API" cmd /c "cd /d %ROOT%\apps\api & bun run dev"
)
timeout /t 2 /nobreak >nul
start "Web" cmd /c "cd /d %ROOT%\apps\web & bun run dev"

echo.
echo ============================================
echo  All services started!
echo ============================================
if defined MOCK_API (
    echo  Mode: MOCK
) else (
    echo  Mode: FULL
    echo  Ingest:     http://localhost:8200
    echo  Generation: http://localhost:8100
    echo  GPU Arbiter:http://localhost:8300
    echo  Agent:      http://localhost:8000
    echo  Collector:  http://localhost:8400
)
echo  API:        http://localhost:4000
echo  Web:        http://localhost:3000
echo.
echo  Opening browser...
echo  Close the windows to stop.
echo ============================================

REM Wait for Next.js to be ready, then open browser
timeout /t 5 /nobreak >nul
start "" http://localhost:3000

pause
