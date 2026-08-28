@echo off
echo ================================================
echo   GrowthPro Backend Setup
echo ================================================
echo.

where python >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Python paoa jayni. Age python.org theke Python install korun,
    echo install korar somoy "Add Python to PATH" tick korte bhulben na.
    pause
    exit /b 1
)

echo [1/5] Virtual environment banano hocche...
python -m venv venv

echo [2/5] Virtual environment activate kora hocche...
call venv\Scripts\activate.bat

echo [3/5] Packages install kora hocche (kichu minute lagte pare)...
pip install -r requirements.txt

echo [4/5] .env file banano hocche...
if not exist .env (
    copy .env.example .env
    echo .env file toiri hoyeche - EKHON eta text editor diye khule
    echo SECRET_KEY ebong TOKEN_ENCRYPTION_KEY bosate hobe.
) else (
    echo .env already ache, skip kora hocche.
)

echo [5/5] TOKEN_ENCRYPTION_KEY generate kora hocche - eta copy kore .env-e bosan:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

echo.
echo ================================================
echo   Setup shesh! Ekhon ja korte hobe:
echo   1. Upore je key ta dekhalo, seta .env file-e
echo      TOKEN_ENCRYPTION_KEY= er por paste korun
echo   2. SECRET_KEY= er por je kono lomba random text din
echo   3. Docker Desktop chalu koren, tarpor ei command chalan:
echo      docker compose up -d db redis
echo   4. Tarpor RUN_BACKEND.bat file-e double click korun
echo ================================================
pause
