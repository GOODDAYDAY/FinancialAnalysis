@echo off
REM ============================================================
REM Register scheduled_analysis.bat with Windows Task Scheduler
REM
REM Default schedule: Daily at 17:30 (after A-share market close)
REM Customize by editing /SC and /ST below
REM
REM Run as Administrator the first time
REM ============================================================
setlocal

cd /d "%~dp0\.."
set PROJECT_DIR=%CD%
set SCRIPT_PATH=%PROJECT_DIR%\scripts\scheduled_analysis.bat
set TASK_NAME=AIInvestmentResearch_DailyAnalysis

echo Registering Windows scheduled task...
echo   Task Name: %TASK_NAME%
echo   Script:    %SCRIPT_PATH%
echo   Schedule:  Daily at 17:30
echo.

schtasks /Create ^
    /TN "%TASK_NAME%" ^
    /TR "\"%SCRIPT_PATH%\"" ^
    /SC DAILY ^
    /ST 17:30 ^
    /RL LIMITED ^
    /F

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to register task. Try running as Administrator.
    pause
    exit /b 1
)

echo.
echo Task registered successfully.
echo.
echo To verify:
echo   schtasks /Query /TN "%TASK_NAME%"
echo.
echo To run immediately for testing:
echo   schtasks /Run /TN "%TASK_NAME%"
echo.
echo To unregister:
echo   schtasks /Delete /TN "%TASK_NAME%" /F
echo.
pause
endlocal
