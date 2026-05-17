@echo off
"C:\Program Files\7-Zip\7z.exe" a ..\hp-database.7z . -xr!.git -xr!.venv -xr!.claude -xr!__pycache__
