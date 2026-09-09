@echo off
echo ===================================================
echo Launching Supply Chain AI System (Backend + Frontend)
echo ===================================================
cd /d "%~dp0"

echo 1. Reseeding Database...
python database/seeds/seed_db.py

echo 2. Launching Backend in new window...
start "Supply Chain AI Backend (Port 8000)" cmd /k "run_backend.bat"

echo 3. Launching Frontend in new window...
start "Supply Chain Control Tower Frontend (Port 3000)" cmd /k "run_frontend.bat"

echo ===================================================
echo Both Backend and Frontend launched!
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:3000
echo ===================================================
pause
