@echo off
call venv\Scripts\activate.bat
echo Backend churche... http://localhost:8000/docs e giye check korun
echo Bondho korte Ctrl+C chapun
uvicorn app.main:app --reload
pause
