#!/usr/bin/env python3
import subprocess
import sys
import os

def run_cmd(cmd: str):
    print(f"➜ Running: {cmd}")
    res = subprocess.run(cmd, shell=True)
    if res.returncode != 0:
        print(f"⚠️ Warning: Command '{cmd}' exited with code {res.returncode}")

def main():
    print("===================================================")
    print("🚀 Wisualyst Platform - Automated Deployer")
    print("===================================================")

    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("📦 1. Staging and committing changes...")
    run_cmd("git add .")
    run_cmd('git commit -m "Auto-deploy code changes"')

    print("⬆️ 2. Pushing to GitHub...")
    run_cmd("git push origin main")

    print("🖥️ 3. Deploying to EC2 via AWS API...")
    run_cmd(f"{sys.executable} scripts/deploy_ec2_aws_keys.py i-008e760e264afb4b9")

    print("\n🎉 Deployment execution finished!")

if __name__ == "__main__":
    main()
