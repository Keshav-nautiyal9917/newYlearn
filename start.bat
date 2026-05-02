@echo off
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   YLearn — YouTube Learning Assistant    ║
echo  ╚══════════════════════════════════════════╝
echo.

REM Check for .env file
if not exist "backend\.env" (
  echo  [!] No .env file found. Copying from .env.example...
  copy "backend\.env.example" "backend\.env"
  echo  [!] Please edit backend\.env and add your GEMINI_API_KEY
  echo      Get a free key at: https://aistudio.google.com/app/apikey
  echo.
  pause
  notepad "backend\.env"
)

echo  [+] Installing Python dependencies...
cd backend
pip install -r requirements.txt

echo.
echo  [+] Starting YLearn server at http://localhost:8000
echo      Press Ctrl+C to stop.
echo.
python main.py
