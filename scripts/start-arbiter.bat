@echo off
chcp 65001 >nul
pushd "%~dp0..\services\gpu_arbiter"

echo Starting GPU Arbiter on port 8300...
python -m uv run uvicorn src.main:app --host 0.0.0.0 --port 8300 --reload

pause
