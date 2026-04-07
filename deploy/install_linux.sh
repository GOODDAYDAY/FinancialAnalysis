#!/bin/bash
# ============================================================
# Linux server installation script (tested on Ubuntu/Debian)
# Run on a fresh Singapore Linux server.
#
# Usage:
#   bash deploy/install_linux.sh
#
# This will:
#   1. Install system prerequisites (curl, git, build essentials)
#   2. Install uv (Python package manager)
#   3. Create venv and install all dependencies
#   4. Set up systemd service for the Streamlit app
#   5. Set up systemd timer for scheduled email task
#   6. Configure firewall (if ufw present)
# ============================================================
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

echo "============================================================"
echo " Installing AI Investment Research on Linux"
echo " Project: $PROJECT_DIR"
echo "============================================================"

# ---- 1. System prerequisites ----
echo
echo "[1/6] Installing system prerequisites..."
if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq curl git build-essential
elif command -v yum >/dev/null 2>&1; then
    sudo yum install -y -q curl git gcc
fi

# ---- 2. Install uv ----
if ! command -v uv >/dev/null 2>&1; then
    echo
    echo "[2/6] Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
    if ! grep -q '\.local/bin' ~/.bashrc; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
    fi
else
    echo
    echo "[2/6] uv already installed."
fi

# ---- 3. Create venv and install deps ----
echo
echo "[3/6] Creating venv and installing dependencies..."
if [ ! -d "$PROJECT_DIR/.venv" ]; then
    uv venv --python 3.11
fi
uv pip install -r requirements.txt

# ---- 4. Check .env ----
echo
echo "[4/6] Checking .env file..."
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo "WARNING: .env not found. Copying from .env.example..."
    cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
    echo "IMPORTANT: Edit $PROJECT_DIR/.env with your real DeepSeek and QQ Mail credentials before starting the service!"
fi

# ---- 5. Install systemd units ----
echo
echo "[5/6] Installing systemd units..."

CURRENT_USER=$(whoami)

# Web app service
sudo tee /etc/systemd/system/ai-investment-web.service > /dev/null <<EOF
[Unit]
Description=AI Investment Research Streamlit Web App
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$HOME/.local/bin/uv run streamlit run frontend/app.py --server.port=8501 --server.address=0.0.0.0 --server.headless=true
Restart=on-failure
RestartSec=10
StandardOutput=append:$PROJECT_DIR/logs/web.log
StandardError=append:$PROJECT_DIR/logs/web.log

[Install]
WantedBy=multi-user.target
EOF

# Scheduled task service (oneshot)
sudo tee /etc/systemd/system/ai-investment-scheduled.service > /dev/null <<EOF
[Unit]
Description=AI Investment Research Scheduled Stock Analysis
After=network.target

[Service]
Type=oneshot
User=$CURRENT_USER
WorkingDirectory=$PROJECT_DIR
EnvironmentFile=$PROJECT_DIR/.env
ExecStart=$HOME/.local/bin/uv run python scripts/scheduled_analysis.py
StandardOutput=append:$PROJECT_DIR/logs/scheduled.log
StandardError=append:$PROJECT_DIR/logs/scheduled.log
EOF

# Timer for the scheduled service
sudo tee /etc/systemd/system/ai-investment-scheduled.timer > /dev/null <<EOF
[Unit]
Description=Run AI Investment Research analysis daily after market close
Requires=ai-investment-scheduled.service

[Timer]
# Singapore time = UTC+8. A-share market closes at 15:00 SGT.
# Run at 17:30 SGT = 09:30 UTC
OnCalendar=Mon..Fri 09:30:00 UTC
Persistent=true

[Install]
WantedBy=timers.target
EOF

mkdir -p "$PROJECT_DIR/logs"

sudo systemctl daemon-reload
sudo systemctl enable ai-investment-web.service
sudo systemctl enable ai-investment-scheduled.timer

# ---- 6. Firewall ----
echo
echo "[6/6] Configuring firewall..."
if command -v ufw >/dev/null 2>&1; then
    sudo ufw allow 8501/tcp || true
    echo "ufw rule added for port 8501"
fi

echo
echo "============================================================"
echo " Installation complete!"
echo "============================================================"
echo
echo "Next steps:"
echo "  1. Edit .env with real credentials:"
echo "       nano $PROJECT_DIR/.env"
echo
echo "  2. Start the web app:"
echo "       sudo systemctl start ai-investment-web"
echo "       sudo systemctl status ai-investment-web"
echo
echo "  3. Start the scheduled timer:"
echo "       sudo systemctl start ai-investment-scheduled.timer"
echo "       sudo systemctl list-timers | grep ai-investment"
echo
echo "  4. Test the scheduled task immediately:"
echo "       sudo systemctl start ai-investment-scheduled.service"
echo "       tail -f logs/scheduled.log"
echo
echo "  5. View logs:"
echo "       tail -f $PROJECT_DIR/logs/web.log"
echo "       tail -f $PROJECT_DIR/logs/scheduled.log"
echo "       sudo journalctl -u ai-investment-web -f"
echo
echo "Access the web app at http://YOUR_SERVER_IP:8501"
