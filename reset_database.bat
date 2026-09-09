@echo off
echo ===================================================
echo Resetting and Reseeding Supply Chain Database
echo ===================================================
cd /d "%~dp0"
python database/seeds/seed_db.py
echo ===================================================
echo Database reset complete!
echo ===================================================
pause
