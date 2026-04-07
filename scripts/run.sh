#!/bin/bash
# ============================================================
# Multi-Agent Investment Research - Zero-dependency launcher
# Works on Linux/macOS with NOTHING installed:
#   1. Auto-installs uv if missing
#   2. uv creates Python 3.11 venv if missing
#   3. uv installs all dependencies if missing
#   4. Prompts for DeepSeek API key if .env missing
#   5. Launches Streamlit app
# ============================================================
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "============================================================"
echo " Multi-Agent Investment Research System"
echo "============================================================"
echo

# Step 1: Ensure uv is installed
if ! command -v uv >/dev/null 2>&1; then
    echo "[1/6] uv not found. Installing uv automatically..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv >/dev/null 2>&1; then
        echo "[ERROR] uv installed but not found in PATH."
        echo "Please restart your shell and run this script again."
        exit 1
    fi
    echo "     uv installed successfully."
else
    echo "[1/6] uv is already installed."
fi
echo

# Step 2: Create venv if missing
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "[2/6] Creating Python 3.11 virtual environment..."
    uv venv --python 3.11
    echo "     Virtual environment created."
else
    echo "[2/6] Virtual environment already exists."
fi
echo

# Step 3: Install dependencies
echo "[3/6] Installing/syncing dependencies (first run takes a few minutes)..."
uv pip install -r requirements.txt
echo "     Dependencies ready."
echo

# Step 4: Check / create .env
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "[4/6] .env file not found."
    echo
    echo "Please enter your DeepSeek API key (get one at https://platform.deepseek.com):"
    read -r -p "API Key: " DEEPSEEK_KEY
    if [ -z "$DEEPSEEK_KEY" ]; then
        echo "[ERROR] API key is required to run this system."
        exit 1
    fi
    cat > "$PROJECT_DIR/.env" <<EOF
# DeepSeek API Configuration
DEEPSEEK_API_KEY=$DEEPSEEK_KEY
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# LLM Settings
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=4096

# Debate Settings
DEBATE_MAX_ROUNDS=2
DEBATE_TEMPERATURE=0.7

# Agent Settings
AGENT_TIMEOUT=30
LOG_LEVEL=INFO
EOF
    echo "     .env file created."
else
    echo "[4/6] .env file found."
fi
echo

# Step 5: Start scheduler daemon
# Daemon always launches; it self-disables via config/schedule.json
# "enabled": false (or env AUTO_RUN_SCHEDULE=false as fallback).
echo "[5/6] Starting scheduler daemon in background..."
mkdir -p logs
nohup uv run --no-sync python scripts/scheduler_daemon.py > logs/scheduler-stdout.log 2>&1 &
SCHEDULER_PID=$!
echo "     Daemon started (PID $SCHEDULER_PID). Logs: logs/scheduler.log"
echo "     To disable: set \"enabled\": false in config/schedule.json"
echo
# Trap to cleanup daemon on exit
trap "echo 'Stopping scheduler daemon...'; kill $SCHEDULER_PID 2>/dev/null || true" EXIT

# Step 6: Launch Streamlit
echo "[6/6] Starting Streamlit application..."
echo
echo "============================================================"
echo " Open your browser at: http://localhost:8501"
echo " Press Ctrl+C in this terminal to stop the server."
echo "============================================================"
echo
uv run --no-sync streamlit run frontend/app.py --server.port=8501
