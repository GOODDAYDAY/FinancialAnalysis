@echo off
REM Run the Streamlit app locally on Windows

cd /d "%~dp0\.."

REM Load .env if exists
if exist .env (
    for /f "tokens=*" %%a in ('type .env ^| findstr /v "^#"') do set %%a
)

echo Starting Multi-Agent Investment Research System...
echo Open http://localhost:8501 in your browser
streamlit run frontend/app.py --server.port=8501
