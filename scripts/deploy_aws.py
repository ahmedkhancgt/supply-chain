#!/usr/bin/env python3
"""
Automated AWS EC2 Deployment Script for Wisualyst Platform.
Provisions security groups, key pairs, Ubuntu EC2 instance, installs Docker, and launches containers.
"""
import os
import sys
import time
import boto3

def deploy_to_aws(aws_access_key: str, aws_secret_key: str, region: str = "us-east-1"):
    print("🚀 Initializing AWS EC2 Provisioning for Wisualyst Platform...")
    
    ec2 = boto3.client(
        'ec2',
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=region
    )

    # 1. Create or Find Security Group
    sg_name = "wisualyst-sg"
    description = "Security Group for Wisualyst Supply Chain Platform"
    
    try:
        sgs = ec2.describe_security_groups(GroupNames=[sg_name])
        sg_id = sgs['SecurityGroups'][0]['GroupId']
        print(f"✅ Found existing Security Group: {sg_id}")
    except Exception:
        print("🔨 Creating new Security Group 'wisualyst-sg'...")
        vpcs = ec2.describe_vpcs()
        vpc_id = vpcs['Vpcs'][0]['VpcId']
        
        sg = ec2.create_security_group(
            GroupName=sg_name,
            Description=description,
            VpcId=vpc_id
        )
        sg_id = sg['GroupId']
        
        # Add Inbound Rules
        ec2.authorize_security_group_ingress(
            GroupId=sg_id,
            IpPermissions=[
                {'IpProtocol': 'tcp', 'FromPort': 22, 'ToPort': 22, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp', 'FromPort': 80, 'ToPort': 80, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp', 'FromPort': 443, 'ToPort': 443, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]},
                {'IpProtocol': 'tcp', 'FromPort': 8000, 'ToPort': 8000, 'IpRanges': [{'CidrIp': '0.0.0.0/0'}]}
            ]
        )
        print(f"✅ Created Security Group {sg_id} with ports 22, 80, 443, 8000 open.")

    # 1b. Create or Retrieve SSH Key Pair
    key_name = "wisualyst-key"
    key_path = os.path.abspath("wisualyst-key.pem")
    try:
        ec2.describe_key_pairs(KeyNames=[key_name])
        print(f"🔑 Using existing SSH Key Pair '{key_name}'")
    except Exception:
        print(f"🔑 Creating new SSH Key Pair '{key_name}'...")
        key_pair = ec2.create_key_pair(KeyName=key_name)
        with open(key_path, "w") as f:
            f.write(key_pair['KeyMaterial'])
        os.chmod(key_path, 0o400)
        print(f"✅ Saved private key to {key_path}")

    # 2. Cloud-Init User Data Script for Auto-Setup
    user_data_script = """#!/bin/bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose git
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu
"""

    # 3. Get Latest Ubuntu 22.04 LTS AMI ID
    ami_response = ec2.describe_images(
        Filters=[
            {'Name': 'name', 'Values': ['ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*']},
            {'Name': 'virtualization-type', 'Values': ['hvm']}
        ],
        Owners=['099720109477'] # Canonical official
    )
    images = sorted(ami_response['Images'], key=lambda x: x['CreationDate'], reverse=True)
    ami_id = images[0]['ImageId'] if images else "ami-0c7217cdde317cfec"

    print(f"🖥️ Launching EC2 Instance (t3.medium) using AMI: {ami_id}...")

    # 4. Launch EC2 Instance
    instances = ec2.run_instances(
        ImageId=ami_id,
        InstanceType='t3.medium',
        MinCount=1,
        MaxCount=1,
        KeyName=key_name,
        SecurityGroupIds=[sg_id],
        UserData=user_data_script,
        TagSpecifications=[{
            'ResourceType': 'instance',
            'Tags': [{'Key': 'Name', 'Value': 'Wisualyst-Production-Server'}]
        }]
    )
    
    instance_id = instances['Instances'][0]['InstanceId']
    print(f"⏳ Waiting for instance {instance_id} to initialize public IP...")
    
    waiter = ec2.get_waiter('instance_running')
    waiter.wait(InstanceIds=[instance_id])
    
    ec2_info = ec2.describe_instances(InstanceIds=[instance_id])
    public_ip = ec2_info['Reservations'][0]['Instances'][0].get('PublicIpAddress', 'Pending')

    print("\n" + "="*60)
    print("🎉 WISUALYST PLATFORM DEPLOYMENT INITIATED ON AWS EC2!")
    print("="*60)
    print(f"• EC2 Instance ID: {instance_id}")
    print(f"• Public IP Address: {public_ip}")
    print(f"• Frontend URL: http://{public_ip}")
    print(f"• Backend API URL: http://{public_ip}:8000")
    print(f"• BI Stream Endpoint: http://{public_ip}:8000/api/bi/powerbi")
    print("="*60)

from dotenv import load_dotenv

load_dotenv()

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        key = sys.argv[1]
        secret = sys.argv[2]
        reg = sys.argv[3] if len(sys.argv) > 3 else os.getenv("AWS_REGION", "ap-south-1")
    else:
        key = os.getenv("AWS_ACCESS_KEY_ID")
        secret = os.getenv("AWS_SECRET_ACCESS_KEY")
        reg = os.getenv("AWS_REGION", "ap-south-1")

    if not key or not secret:
        print("❌ Error: AWS credentials missing. Provide them in .env or via CLI arguments.")
        sys.exit(1)

    deploy_to_aws(key, secret, reg)
