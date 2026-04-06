@echo off
REM Run the Streamlit app using uv
cd /d "%~dp0\.."

echo Starting Multi-Agent Investment Research System...
echo Open http://localhost:8501 in your browser
uv run streamlit run frontend/app.py --server.port=8501
