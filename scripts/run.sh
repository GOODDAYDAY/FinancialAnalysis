#!/bin/bash
# Run the Streamlit app locally
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

# Load .env if exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

echo "Starting Multi-Agent Investment Research System..."
echo "Open http://localhost:8501 in your browser"
streamlit run frontend/app.py --server.port=8501
