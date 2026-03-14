@echo off
chcp 65001 >nul
cd /d "%~dp0..\services\ingest"
echo [Ingest] Starting Ingest Service (port 8200)...
echo Requires: Qdrant (6333), Redis (6379)
python -m uv run uvicorn src.main:app --host 0.0.0.0 --port 8200 --reload
