@echo off
chcp 65001 >nul
pushd "%~dp0..\services\collector"

echo ============================================
echo  Design Collector CLI
echo ============================================
echo.
echo Usage:
echo   python -m src.cli scrape dribbble -q "web design"
echo   python -m src.cli scrape-all -q "UI design" --ingest
echo   python -m src.cli hf-download user/dataset --max 100
echo   python -m src.cli hf-defaults --ingest
echo.
echo Starting interactive shell...
echo.

cmd /k "echo Ready. Type: python -m src.cli --help"
