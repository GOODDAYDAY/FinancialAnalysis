#!/bin/bash
set -e
cd "$(dirname "$0")/.."

echo "Starting Multi-Agent Investment Research System..."
echo "Open http://localhost:8501 in your browser"
uv run streamlit run frontend/app.py --server.port=8501
