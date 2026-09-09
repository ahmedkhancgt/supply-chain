@echo off
echo ===================================================
echo 🚀 Wisualyst Platform - 1-Click EC2 Deployer
echo ===================================================
cd /d "%~dp0"

echo 📦 1. Staging and committing all code changes...
git add .
git commit -m "Automated update and EC2 deployment"

echo ⬆️ 2. Pushing code to GitHub...
git push origin main

echo 🖥️ 3. Deploying updated code to AWS EC2 Instance...
python scripts/deploy_ec2_aws_keys.py i-008e760e264afb4b9

echo ===================================================
echo 🎉 Deployment Finished!
echo ===================================================
pause
