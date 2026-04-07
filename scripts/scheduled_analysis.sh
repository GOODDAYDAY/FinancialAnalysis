#!/bin/bash
# ============================================================
# Scheduled stock analysis with email notification
# For Linux/macOS cron
#
# Example crontab entry (daily at 17:30):
#   30 17 * * 1-5 /path/to/scripts/scheduled_analysis.sh
# ============================================================
set -e

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

mkdir -p logs
LOG_FILE="logs/scheduled_$(date +%Y-%m-%d).log"

echo "[$(date)] Starting scheduled stock analysis" >> "$LOG_FILE"
uv run python scripts/scheduled_analysis.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?
echo "[$(date)] Scheduled analysis finished with exit code $EXIT_CODE" >> "$LOG_FILE"

exit $EXIT_CODE
