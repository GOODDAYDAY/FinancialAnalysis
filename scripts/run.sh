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
    echo "[1/5] uv not found. Installing uv automatically..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    if ! command -v uv >/dev/null 2>&1; then
        echo "[ERROR] uv installed but not found in PATH."
        echo "Please restart your shell and run this script again."
        exit 1
    fi
    echo "     uv installed successfully."
else
    echo "[1/5] uv is already installed."
fi
echo

# Step 2: Create venv if missing
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    echo "[2/5] Creating Python 3.11 virtual environment..."
    uv venv --python 3.11
    echo "     Virtual environment created."
else
    echo "[2/5] Virtual environment already exists."
fi
echo

# Step 3: Install dependencies
echo "[3/5] Checking dependencies..."
if ! uv pip install -r requirements.txt --quiet 2>/dev/null; then
    echo "     Installing dependencies (this may take a few minutes)..."
    uv pip install -r requirements.txt
fi
echo "     Dependencies ready."
echo

# Step 4: Check / create .env
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "[4/5] .env file not found."
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
    echo "[4/5] .env file found."
fi
echo

# Step 5: Launch Streamlit
echo "[5/5] Starting Streamlit application..."
echo
echo "============================================================"
echo " Open your browser at: http://localhost:8501"
echo " Press Ctrl+C in this terminal to stop the server."
echo "============================================================"
echo
uv run streamlit run frontend/app.py --server.port=8501
