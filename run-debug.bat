@echo off

call .venv\Scripts\activate.bat
py -m pip install --require-virtualenv -r requirements.txt
py -m uvicorn webapp.main:app --reload --port 8001
