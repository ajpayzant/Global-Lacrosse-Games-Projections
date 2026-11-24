@echo off
cd /d "%~dp0"
python -m streamlit run app\glg_app.py --server.port 8690
