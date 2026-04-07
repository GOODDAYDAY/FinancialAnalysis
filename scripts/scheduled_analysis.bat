@echo off
REM ============================================================
REM Scheduled stock analysis with email notification
REM Designed for Windows Task Scheduler
REM ============================================================

cd /d "%~dp0\.."

REM Ensure logs directory exists
if not exist logs mkdir logs

REM Run analysis with timestamped log
set LOG_FILE=logs\scheduled_%date:~0,4%-%date:~5,2%-%date:~8,2%.log

echo [%date% %time%] Starting scheduled stock analysis >> "%LOG_FILE%"
uv run python scripts\scheduled_analysis.py >> "%LOG_FILE%" 2>&1
echo [%date% %time%] Scheduled analysis finished with exit code %ERRORLEVEL% >> "%LOG_FILE%"

exit /b %ERRORLEVEL%
