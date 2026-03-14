@echo off
chcp 65001 >nul
pushd "%~dp0..\services\generation"

echo Starting Generation Service on port 8100...
python -m uv run uvicorn src.main:app --host 0.0.0.0 --port 8100 --reload

pause
