#!/usr/bin/env python3
import os
import sys
import boto3
import paramiko
from dotenv import load_dotenv

load_dotenv()

aws_key = os.getenv("AWS_ACCESS_KEY_ID")
aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")
aws_region = os.getenv("AWS_REGION", "ap-south-1")
instance_id = "i-008e760e264afb4b9"

ec2 = boto3.client('ec2', aws_access_key_id=aws_key, aws_secret_access_key=aws_secret, region_name=aws_region)
eic = boto3.client('ec2-instance-connect', aws_access_key_id=aws_key, aws_secret_access_key=aws_secret, region_name=aws_region)

desc = ec2.describe_instances(InstanceIds=[instance_id])
inst = desc['Reservations'][0]['Instances'][0]
public_ip = inst.get('PublicIpAddress')
az = inst['Placement']['AvailabilityZone']

key = paramiko.RSAKey.generate(2048)
key_str = f"ssh-rsa {key.get_base64()}"

eic.send_ssh_public_key(InstanceId=instance_id, InstanceOSUser='ubuntu', SSHPublicKey=key_str, AvailabilityZone=az)

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(public_ip, username='ubuntu', pkey=key, timeout=15)

print("=== DOCKER CONTAINERS STATUS ===")
stdin, stdout, stderr = ssh.exec_command("cd /home/ubuntu/app && sudo docker-compose ps")
print(stdout.read().decode())

print("=== DOCKER CONTAINER LOGS ===")
stdin, stdout, stderr = ssh.exec_command("cd /home/ubuntu/app && sudo docker-compose logs --tail=40")
print(stdout.read().decode())
print(stderr.read().decode())

print("=== HOST NGINX CONFIG ===")
stdin, stdout, stderr = ssh.exec_command("cat /etc/nginx/sites-enabled/* || cat /etc/nginx/conf.d/*")
print(stdout.read().decode())

print("=== HOST NGINX ERROR LOG ===")
stdin, stdout, stderr = ssh.exec_command("sudo tail -n 30 /var/log/nginx/error.log")
print(stdout.read().decode())

ssh.close()
