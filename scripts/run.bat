@echo off
chcp 65001 >nul
REM ============================================================
REM Multi-Agent Investment Research - Zero-dependency launcher
REM Works on Windows with NOTHING installed:
REM   1. Auto-installs uv (via PowerShell) if missing
REM   2. uv creates Python 3.11 venv if missing
REM   3. uv installs all dependencies if missing
REM   4. Prompts for DeepSeek API key if .env missing
REM   5. Launches Streamlit app
REM ============================================================
setlocal enabledelayedexpansion

cd /d "%~dp0\.."
set PROJECT_DIR=%CD%

echo ============================================================
echo  Multi-Agent Investment Research System
echo ============================================================
echo.

REM -------- Step 1: Ensure uv is installed --------
where uv >nul 2>nul
if errorlevel 1 (
    echo [1/5] uv not found. Installing uv automatically...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    if errorlevel 1 (
        echo [ERROR] Failed to install uv automatically.
        echo Please install manually from: https://docs.astral.sh/uv/getting-started/installation/
        pause
        exit /b 1
    )
    REM Add uv to PATH for current session
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
    where uv >nul 2>nul
    if errorlevel 1 (
        echo [ERROR] uv installed but not found in PATH.
        echo Please restart your terminal and run this script again.
        pause
        exit /b 1
    )
    echo      uv installed successfully.
) else (
    echo [1/5] uv is already installed.
)
echo.

REM -------- Step 2: Create venv if missing --------
if not exist "%PROJECT_DIR%\.venv" (
    echo [2/5] Creating Python 3.11 virtual environment...
    uv venv --python 3.11
    if errorlevel 1 (
        echo [ERROR] Failed to create venv.
        pause
        exit /b 1
    )
    echo      Virtual environment created.
) else (
    echo [2/5] Virtual environment already exists.
)
echo.

REM -------- Step 3: Install dependencies --------
echo [3/5] Installing/syncing dependencies (first run takes a few minutes)...
uv pip install -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo      Dependencies ready.
echo.

REM -------- Step 4: Check / create .env --------
if not exist "%PROJECT_DIR%\.env" (
    echo [4/5] .env file not found.
    echo.
    echo Please enter your DeepSeek API key (get one at https://platform.deepseek.com):
    set /p DEEPSEEK_KEY="API Key: "
    if "!DEEPSEEK_KEY!"=="" (
        echo [ERROR] API key is required to run this system.
        pause
        exit /b 1
    )
    (
        echo # DeepSeek API Configuration
        echo DEEPSEEK_API_KEY=!DEEPSEEK_KEY!
        echo DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
        echo DEEPSEEK_MODEL=deepseek-chat
        echo.
        echo # LLM Settings
        echo LLM_TEMPERATURE=0.3
        echo LLM_MAX_TOKENS=4096
        echo.
        echo # Debate Settings
        echo DEBATE_MAX_ROUNDS=2
        echo DEBATE_TEMPERATURE=0.7
        echo.
        echo # Agent Settings
        echo AGENT_TIMEOUT=30
        echo LOG_LEVEL=INFO
    ) > "%PROJECT_DIR%\.env"
    echo      .env file created.
) else (
    echo [4/5] .env file found.
)
echo.

REM -------- Step 5: Launch Streamlit --------
echo [5/5] Starting Streamlit application...
echo.
echo ============================================================
echo  Open your browser at: http://localhost:8501
echo  Press Ctrl+C in this window to stop the server.
echo ============================================================
echo.
uv run --no-sync streamlit run frontend/app.py --server.port=8501 --server.headless=true

endlocal
