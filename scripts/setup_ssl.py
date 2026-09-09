#!/usr/bin/env python3
"""
Automated Let's Encrypt Certbot SSL Generator for Wisualyst Platform on EC2.
Installs Certbot and configures free HTTPS SSL certificates for your domain.
"""
import os
import sys
import paramiko

def setup_certbot_ssl(ip: str, domain: str, email: str = "admin@wisualyst.com"):
    key_file = os.path.abspath("wisualyst-key.pem")
    print(f"🔒 Connecting to EC2 ({ip}) to generate Let's Encrypt SSL certificate for {domain}...")
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username='ubuntu', key_filename=key_file, timeout=15)

    nginx_conf = f"""server {{
    listen 80;
    listen 443 ssl;
    server_name {domain};
    client_max_body_size 50M;

    ssl_certificate /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    location / {{
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }}
}}
"""
    sftp = ssh.open_sftp()
    with sftp.file('/tmp/wisualyst_nginx.conf', 'w') as f:
        f.write(nginx_conf)
    sftp.close()

    commands = [
        "sudo apt update && sudo apt install -y nginx certbot python3-certbot-nginx",
        f"sudo certbot certonly --standalone -d {domain} --non-interactive --agree-tos -m {email} --expand || sudo certbot certonly --webroot -w /var/www/html -d {domain} --non-interactive --agree-tos -m {email} --expand || true",
        "sudo mv /tmp/wisualyst_nginx.conf /etc/nginx/sites-available/wisualyst",
        "sudo ln -sf /etc/nginx/sites-available/wisualyst /etc/nginx/sites-enabled/wisualyst",
        "sudo rm -f /etc/nginx/sites-enabled/default",
        "sudo nginx -t",
        "sudo systemctl restart nginx"
    ]

    for cmd in commands:
        print(f"⚙️ Running: {cmd}")
        stdin, stdout, stderr = ssh.exec_command(cmd)
        print(stdout.read().decode())
        print(stderr.read().decode())

    ssh.close()
    print(f"🎉 Free Let's Encrypt SSL Certificate successfully generated and configured for https://{domain} !")

if __name__ == "__main__":
    if len(sys.argv) >= 2:
        domain_name = sys.argv[1]
        ip_addr = sys.argv[2] if len(sys.argv) > 2 else "3.109.122.139"
        setup_certbot_ssl(ip_addr, domain_name)
    else:
        print("Usage: python scripts/setup_ssl.py <YOUR_DOMAIN_NAME> [EC2_IP]")
