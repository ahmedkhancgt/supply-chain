@echo off
echo ===================================================
echo Starting Supply Chain Control Tower Frontend UI
echo ===================================================
cd /d "%~dp0frontend"
if not exist node_modules (
    echo Installing Frontend Dependencies...
    npm install
)
npm run dev
pause
