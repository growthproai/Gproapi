#!/usr/bin/env bash
set -e
echo "================================================"
echo "  GrowthPro Backend Setup"
echo "================================================"
echo ""

if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python paoa jayni. Age python.org theke Python 3.12+ install korun."
    read -p "Enter chapun bondho korte..."
    exit 1
fi

echo "[1/5] Virtual environment banano hocche..."
python3 -m venv venv

echo "[2/5] Virtual environment activate kora hocche..."
source venv/bin/activate

echo "[3/5] Packages install kora hocche (kichu minute lagte pare)..."
pip install -r requirements.txt

echo "[4/5] .env file banano hocche..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo ".env file toiri hoyeche - EKHON eta text editor diye khule"
    echo "SECRET_KEY ebong TOKEN_ENCRYPTION_KEY bosate hobe."
else
    echo ".env already ache, skip kora hocche."
fi

echo "[5/5] TOKEN_ENCRYPTION_KEY generate kora hocche - eta copy kore .env-e bosan:"
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

echo ""
echo "================================================"
echo "  Setup shesh! Ekhon ja korte hobe:"
echo "  1. Upore je key ta dekhalo, seta .env file-e"
echo "     TOKEN_ENCRYPTION_KEY= er por paste korun"
echo "  2. SECRET_KEY= er por je kono lomba random text din"
echo "  3. Docker Desktop chalu koren, tarpor ei command chalan:"
echo "     docker compose up -d db redis"
echo "  4. Tarpor: bash RUN_BACKEND.sh"
echo "================================================"
read -p "Enter chapun bondho korte..."
