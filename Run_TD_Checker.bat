
@echo off
REM Double-click to run the TD Checker (requires Python + pip)
python -m pip install -r requirements.txt
python -m streamlit run app.py
pause
