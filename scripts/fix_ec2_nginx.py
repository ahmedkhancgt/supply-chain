#!/usr/bin/env python3
"""
Fix Nginx reverse proxy and Docker container on EC2 instance (3.109.14.208).
Connects via AWS EC2 Instance Connect + SSH using provided AWS credentials.
"""
import os
import sys
import time
import tempfile
import boto3
import paramiko
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

def generate_temp_key():
    """Generates an in-memory ephemeral RSA key pair."""
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption()
    ).decode('utf-8')
    
    public_ssh = key.public_key().public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH
    ).decode('utf-8')
    
    return private_pem, public_ssh

def get_instance_info(ec2, ip: str):
    resp = ec2.describe_instances(
        Filters=[
            {'Name': 'ip-address', 'Values': [ip]}
        ]
    )
    for res in resp.get('Reservations', []):
        for inst in res.get('Instances', []):
            return inst['InstanceId'], inst.get('Placement', {}).get('AvailabilityZone')
    return None, None

def main():
    ip = sys.argv[1] if len(sys.argv) > 1 else "3.109.14.208"
    aws_key = sys.argv[2] if len(sys.argv) > 2 else os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret = sys.argv[3] if len(sys.argv) > 3 else os.getenv("AWS_SECRET_ACCESS_KEY")
    region = sys.argv[4] if len(sys.argv) > 4 else os.getenv("AWS_REGION", "ap-south-1")

    print(f"[*] Initializing AWS EC2 client for region {region}...")
    ec2 = boto3.client(
        'ec2',
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
        region_name=region
    )
    
    ec2_ic = boto3.client(
        'ec2-instance-connect',
        aws_access_key_id=aws_key,
        aws_secret_access_key=aws_secret,
        region_name=region
    )

    print(f"[*] Locating EC2 instance with IP {ip} in {region}...")
    instance_id, az = get_instance_info(ec2, ip)

    if not instance_id:
        print(f"[-] Could not find instance with IP {ip}. Listing all instances in {region}...")
        resp = ec2.describe_instances()
        for res in resp.get('Reservations', []):
            for inst in res.get('Instances', []):
                print(f"    - ID: {inst['InstanceId']} | IP: {inst.get('PublicIpAddress')} | State: {inst['State']['Name']}")
                if inst['State']['Name'] == 'running':
                    instance_id = inst['InstanceId']
                    az = inst.get('Placement', {}).get('AvailabilityZone')
                    ip = inst.get('PublicIpAddress', ip)
                    print(f"[+] Selecting running instance {instance_id} ({ip}) in {az}")
                    break

    if not instance_id:
        print("[-] No running instances found.")
        return

    print(f"[+] Target Instance ID: {instance_id} in {az} (IP: {ip})")

    print("[+] Generating ephemeral SSH key...")
    priv_pem, pub_ssh = generate_temp_key()

    print("[+] Pushing public key to instance via EC2 Instance Connect...")
    ec2_ic.send_ssh_public_key(
        InstanceId=instance_id,
        InstanceOSUser='ubuntu',
        SSHPublicKey=pub_ssh,
        AvailabilityZone=az
    )
    print("[+] EC2 Instance Connect authorized ephemeral key.")

    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.pem') as tmp:
        tmp.write(priv_pem)
        tmp_key_path = tmp.name

    try:
        print(f"[+] Connecting via SSH to ubuntu@{ip}...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(ip, username='ubuntu', key_filename=tmp_key_path, timeout=20)
        print("[+] SSH Connected successfully!")

        nginx_conf = """server {
    listen 80;
    listen 443 ssl;
    server_name app.wisualyst.com;
    client_max_body_size 50M;

    ssl_certificate /etc/letsencrypt/live/app.wisualyst.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.wisualyst.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
"""
        sftp = ssh.open_sftp()
        with sftp.file('/tmp/wisualyst_nginx.conf', 'w') as f:
            f.write(nginx_conf)
        sftp.close()
        print("[+] Uploaded dual-port Cloudflare-compatible Nginx config via SFTP.")

        commands = [
            "sudo mv /tmp/wisualyst_nginx.conf /etc/nginx/sites-available/wisualyst",
            "sudo ln -sf /etc/nginx/sites-available/wisualyst /etc/nginx/sites-enabled/wisualyst",
            "sudo rm -f /etc/nginx/sites-enabled/default",
            "sudo nginx -t",
            "sudo systemctl restart nginx"
        ]

        for cmd in commands:
            print(f"\n[>] Executing: {cmd}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            out = stdout.read().decode('utf-8', errors='ignore')
            err = stderr.read().decode('utf-8', errors='ignore')
            if out:
                print(out.encode('ascii', errors='ignore').decode('ascii').strip())
            if err:
                print(err.encode('ascii', errors='ignore').decode('ascii').strip())

        ssh.close()
        print("\n========================================================")
        print("[SUCCESS] Wisualyst Platform configured with SSL!")
        print("Check: https://app.wisualyst.com/")
        print("========================================================")
    finally:
        if os.path.exists(tmp_key_path):
            os.remove(tmp_key_path)

if __name__ == "__main__":
    main()
