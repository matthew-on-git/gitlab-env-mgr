# GitLab SSL Certificate Setup with Let's Encrypt (Internal Network)

This guide shows how to set up valid SSL certificates for internal GitLab servers using Let's Encrypt with Cloudflare DNS.

## Prerequisites

- GitLab server accessible on LAN
- Domain name pointing to internal IP (e.g., gitlab.example.com → 10.x.x.x)
- Cloudflare API token with DNS edit permissions
- Root/sudo access on GitLab server

## Step 1: Install Certbot

```bash
# For Ubuntu/Debian
sudo apt update
sudo apt install certbot python3-certbot-dns-cloudflare

# For CentOS/RHEL
sudo yum install epel-release
sudo yum install certbot python3-certbot-dns-cloudflare
```

## Step 2: Create Cloudflare Credentials

Create a Cloudflare API token:
1. Go to https://dash.cloudflare.com/profile/api-tokens
2. Create Token → Custom token
3. Permissions needed:
   - Zone:DNS:Edit
   - Zone:Zone:Read
4. Zone Resources: Include → Specific zone → your domain

Save credentials file:
```bash
sudo mkdir -p /etc/letsencrypt
sudo nano /etc/letsencrypt/cloudflare.ini
```

Content:
```ini
# Cloudflare API token
dns_cloudflare_api_token = your-api-token-here
```

Secure the file:
```bash
sudo chmod 600 /etc/letsencrypt/cloudflare.ini
```

## Step 3: Request Certificate

```bash
sudo certbot certonly \
  --dns-cloudflare \
  --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
  --dns-cloudflare-propagation-seconds 60 \
  -d gitlab.example.com \
  --agree-tos \
  --email your-email@example.com
```

## Step 4: Configure GitLab

### For Omnibus GitLab:

Edit `/etc/gitlab/gitlab.rb`:
```ruby
# URL Configuration
external_url 'https://gitlab.example.com'

# SSL Configuration
nginx['enable'] = true
nginx['redirect_http_to_https'] = true
nginx['ssl_certificate'] = "/etc/letsencrypt/live/gitlab.example.com/fullchain.pem"
nginx['ssl_certificate_key'] = "/etc/letsencrypt/live/gitlab.example.com/privkey.pem"

# Enable ACME/Let's Encrypt
letsencrypt['enable'] = false  # We're using certbot directly
```

Reconfigure GitLab:
```bash
sudo gitlab-ctl reconfigure
```

### For Docker GitLab:

Update `docker-compose.yml`:
```yaml
version: '3.8'
services:
  gitlab:
    image: gitlab/gitlab-ce:latest
    hostname: 'gitlab.example.com'
    environment:
      GITLAB_OMNIBUS_CONFIG: |
        external_url 'https://gitlab.example.com'
        nginx['enable'] = true
        nginx['redirect_http_to_https'] = true
        nginx['ssl_certificate'] = "/etc/letsencrypt/live/gitlab.example.com/fullchain.pem"
        nginx['ssl_certificate_key'] = "/etc/letsencrypt/live/gitlab.example.com/privkey.pem"
    volumes:
      - /etc/letsencrypt:/etc/letsencrypt:ro
      - gitlab-config:/etc/gitlab
      - gitlab-logs:/var/log/gitlab
      - gitlab-data:/var/opt/gitlab
    ports:
      - "443:443"
      - "80:80"
      - "22:22"
```

## Step 5: Automatic Renewal

Create renewal script:
```bash
sudo nano /etc/letsencrypt/renewal-hooks/deploy/gitlab-reload.sh
```

Content:
```bash
#!/bin/bash
# Reload GitLab after certificate renewal

# For Omnibus GitLab
if command -v gitlab-ctl &> /dev/null; then
    gitlab-ctl hup nginx
fi

# For Docker GitLab
if docker ps | grep -q gitlab; then
    docker exec gitlab gitlab-ctl hup nginx
fi
```

Make executable:
```bash
sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/gitlab-reload.sh
```

Test renewal:
```bash
sudo certbot renew --dry-run
```

## Step 6: Setup Automatic Renewal

Certbot automatically installs a systemd timer or cron job. Verify:
```bash
# Check systemd timer
sudo systemctl status certbot.timer

# Or check cron
sudo crontab -l | grep certbot
```

## Alternative: Using acme.sh (More Lightweight)

If you prefer acme.sh over certbot:

```bash
# Install acme.sh
curl https://get.acme.sh | sh -s email=your-email@example.com

# Set Cloudflare credentials
export CF_Token="your-api-token"
export CF_Account_ID="your-account-id"
export CF_Zone_ID="your-zone-id"

# Issue certificate
~/.acme.sh/acme.sh --issue --dns dns_cf -d gitlab.example.com

# Install certificate
~/.acme.sh/acme.sh --install-cert -d gitlab.example.com \
  --key-file /etc/gitlab/ssl/gitlab.example.com.key \
  --fullchain-file /etc/gitlab/ssl/gitlab.example.com.crt \
  --reloadcmd "gitlab-ctl hup nginx"
```

## Troubleshooting

### DNS Propagation Issues
- Increase propagation timeout: `--dns-cloudflare-propagation-seconds 120`
- Check DNS: `dig _acme-challenge.gitlab.example.com TXT`

### Permission Issues
- Ensure certbot can read Cloudflare credentials
- Check file ownership for certificate files

### GitLab Not Loading
- Check nginx logs: `sudo gitlab-ctl tail nginx`
- Verify certificate paths in gitlab.rb
- Test certificate: `openssl s_client -connect gitlab.example.com:443`

## Verification

After setup, verify:
```bash
# Check certificate
curl -I https://gitlab.example.com

# Check certificate details
openssl s_client -connect gitlab.example.com:443 -servername gitlab.example.com < /dev/null | openssl x509 -noout -text

# Test with your script (no more SSL errors!)
./gitlab-env-mgr.py -p "hardware-infra/imp" -o variables.json
```