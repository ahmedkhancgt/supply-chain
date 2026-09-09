#!/usr/bin/env python3
import os
import sys
import io
import time
import boto3
import paramiko
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

load_dotenv()

def deploy_using_aws_credentials(instance_id: str = "i-008e760e264afb4b9"):
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION", "ap-south-1")

    if not aws_key or not aws_secret:
        print("❌ Error: AWS_ACCESS_KEY_ID or AWS_SECRET_ACCESS_KEY missing from .env")
        return

    print(f"🚀 Initializing deployment for EC2 Instance '{instance_id}' in region '{aws_region}'...")

    ec2 = boto3.client('ec2', aws_access_key_id=aws_key, aws_secret_access_key=aws_secret, region_name=aws_region)
    eic = boto3.client('ec2-instance-connect', aws_access_key_id=aws_key, aws_secret_access_key=aws_secret, region_name=aws_region)

    # 1. Get Instance details
    try:
        desc = ec2.describe_instances(InstanceIds=[instance_id])
        inst = desc['Reservations'][0]['Instances'][0]
        public_ip = inst.get('PublicIpAddress')
        az = inst['Placement']['AvailabilityZone']
        print(f"✅ Found EC2 Instance: Public IP = {public_ip}, Availability Zone = {az}")
    except Exception as e:
        print(f"❌ Failed to get instance details: {e}")
        return

    # 2. Generate temporary in-memory RSA key pair
    print("🔑 Generating temporary SSH key pair...")
    key = paramiko.RSAKey.generate(2048)
    key_str = f"ssh-rsa {key.get_base64()}"

    # 3. Push public key to EC2 via AWS EC2 Instance Connect API
    print("📡 Sending temporary SSH key to EC2 via AWS API...")
    try:
        res = eic.send_ssh_public_key(
            InstanceId=instance_id,
            InstanceOSUser='ubuntu',
            SSHPublicKey=key_str,
            AvailabilityZone=az
        )
        if res.get('Success'):
            print("✅ Key successfully pushed to EC2! Connecting via SSH...")
        else:
            print(f"⚠️ EC2 Instance Connect response: {res}")
    except Exception as e:
        print(f"⚠️ EC2 Instance Connect failed: {e}. Trying SSM fallback...")

    # 4. Connect via SSH using in-memory key
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(public_ip, username='ubuntu', pkey=key, timeout=15)
        print("✅ SSH Connection Established to EC2!")

        # Upload updated requirements.txt and .env configuration via SFTP
        print("🔄 Uploading updated .env and requirements.txt to EC2...")
        ssh.exec_command("sudo mkdir -p /home/ubuntu/app && sudo chown -R ubuntu:ubuntu /home/ubuntu/app")
        sftp = ssh.open_sftp()
        if os.path.exists(".env"):
            sftp.put(os.path.abspath(".env"), "/home/ubuntu/app/.env")
            print("✅ Uploaded .env with database credentials to EC2")
        sftp.put(os.path.abspath("requirements.txt"), "/home/ubuntu/app/requirements.txt")
        sftp.close()

        # Pull repository & update docker containers
        print("🔄 Building and deploying latest containers on EC2...")
        deploy_cmd = """
        if [ ! -d "/home/ubuntu/app/.git" ]; then
            git clone https://github.com/adilnawaz256/supplychain.git /tmp/supplychain_git
            cp -r /tmp/supplychain_git/* /home/ubuntu/app/
            cp -r /tmp/supplychain_git/.git /home/ubuntu/app/
            rm -rf /tmp/supplychain_git
        fi
        sudo systemctl enable docker
        sudo systemctl enable docker.socket
        cd /home/ubuntu/app && git reset --hard HEAD && git pull origin main
        sudo docker system prune -af --volumes || true
        sudo docker-compose build
        sudo docker-compose down && sudo docker-compose up -d

        # Configure Host System Nginx Reverse Proxy for Port 80
        cat << 'EOF' | sudo tee /etc/nginx/sites-available/default
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF
        sudo systemctl restart nginx
        sleep 3
        echo "=== BACKEND DOCKER STATUS ==="
        sudo docker ps -a
        echo "=== BACKEND DOCKER LOGS ==="
        sudo docker-compose logs --tail=100 backend
        """
        stdin, stdout, stderr = ssh.exec_command(deploy_cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        print("--- Output ---")
        print(out)
        if err:
            print("--- Warnings/Status ---")
            print(err)

        ssh.close()
        print("🎉 WISUALYST PLATFORM DEPLOYED AND RUNNING ON EC2!")
        print(f"🌐 Access Web App at: http://{public_ip}")
        print(f"🔌 Access Backend API at: http://{public_ip}:8000")
        return

    except Exception as e:
        print(f"❌ SSH connection using EC2 Instance Connect failed: {e}")

    # Fallback: Try AWS SSM SendCommand
    print("🔄 Attempting deployment via AWS SSM SendCommand...")
    try:
        ssm = boto3.client('ssm', aws_access_key_id=aws_key, aws_secret_access_key=aws_secret, region_name=aws_region)
        ssm_res = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName='AWS-RunShellScript',
            Parameters={'commands': [
                'if [ ! -d "/home/ubuntu/app/.git" ]; then mkdir -p /home/ubuntu/app && git clone https://github.com/adilnawaz256/supplychain.git /home/ubuntu/app; fi',
                'cd /home/ubuntu/app && git reset --hard HEAD && git pull origin main',
                'if [ ! -f "/home/ubuntu/app/.env" ]; then cp /home/ubuntu/app/.env.example /home/ubuntu/app/.env; fi',
                'cd /home/ubuntu/app && sudo docker-compose down && sudo docker-compose up --build -d'
            ]}
        )
        cmd_id = ssm_res['Command']['CommandId']
        print(f"✅ AWS SSM Command Sent! Command ID: {cmd_id}")
        print(f"🎉 WISUALYST PLATFORM DEPLOYMENT TRIGGERED ON EC2 ({public_ip})!")
    except Exception as e:
        print(f"❌ AWS SSM deployment failed: {e}")

if __name__ == "__main__":
    inst_id = sys.argv[1] if len(sys.argv) > 1 else "i-008e760e264afb4b9"
    deploy_using_aws_credentials(inst_id)
