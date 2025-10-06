# GitLab SSL Certificate Setup Script

A bash script to automatically configure SSL certificates for GitLab using Let's Encrypt with Cloudflare DNS-01 challenge.

## Overview

This script automates the process of:
- Installing certbot with Cloudflare DNS plugin
- Requesting Let's Encrypt SSL certificates
- Configuring GitLab (Omnibus or Docker) to use the certificates
- Setting up automatic certificate renewal

## Prerequisites

### System Requirements
- **Operating System**: Debian/Ubuntu or Red Hat/CentOS
- **Root Access**: Script must be run as root on the gitlab host
- **Internet Connectivity**: Required for Let's Encrypt certificate requests

### GitLab Requirements
- GitLab must be installed and running
- Domain must point to the server's IP address
- GitLab must be accessible via the domain name

### Cloudflare Requirements
- Cloudflare account with the domain
- API token with the following permissions:
  - `Zone:Read` - to read zone information
  - `DNS:Edit` - to create/delete DNS records for DNS-01 challenge

## Installation

1. **Download the script** to your GitLab server:
   ```bash
   wget https://raw.githubusercontent.com/your-repo/gitlab-env-mgr/main/scripts/setup-gitlab-ssl.sh
   chmod +x setup-gitlab-ssl.sh
   ```

2. **Create Cloudflare API Token**:
   - Log into Cloudflare dashboard
   - Go to "My Profile" → "API Tokens"
   - Click "Create Token"
   - Use "Custom token" template
   - Set permissions: `Zone:Read`, `DNS:Edit`
   - Select your domain zone
   - Create and copy the token

## Usage

### Basic Usage

```bash
sudo ./setup-gitlab-ssl.sh -d <domain> -e <email> -t <cf_token> -g <gitlab_type>
```

### Required Arguments

| Argument | Short | Description | Example |
|----------|-------|-------------|---------|
| `--domain` | `-d` | GitLab domain name | `gitlab.example.com` |
| `--email` | `-e` | Email for Let's Encrypt registration | `admin@example.com` |
| `--cf-token` | `-t` | Cloudflare API token | `your_api_token_here` |
| `--gitlab-type` | `-g` | GitLab installation type | `omnibus` or `docker` |

### Examples

**For GitLab Omnibus installation:**
```bash
sudo ./setup-gitlab-ssl.sh \
  -d gitlab.example.com \
  -e admin@example.com \
  -t your_cloudflare_api_token \
  -g omnibus
```

**For GitLab Docker installation:**
```bash
sudo ./setup-gitlab-ssl.sh \
  -d gitlab.example.com \
  -e admin@example.com \
  -t your_cloudflare_api_token \
  -g docker
```

**Show help:**
```bash
./setup-gitlab-ssl.sh --help
```

## What the Script Does

### 1. Prerequisites Check
- Verifies root access
- Detects operating system (Debian/Red Hat)
- Checks system requirements

### 2. Certbot Installation
- Installs certbot and Cloudflare DNS plugin
- Uses appropriate package manager for your OS

### 3. Cloudflare Configuration
- Creates secure credentials file at `/etc/letsencrypt/cloudflare.ini`
- Sets proper file permissions (600)

### 4. Certificate Request
- Requests Let's Encrypt certificate using DNS-01 challenge
- Uses Cloudflare API to create/delete DNS records
- Waits for DNS propagation (60 seconds)

### 5. GitLab Configuration

#### For Omnibus Installation:
- Backs up existing `/etc/gitlab/gitlab.rb`
- Adds SSL configuration to GitLab config
- Runs `gitlab-ctl reconfigure`

#### For Docker Installation:
- Creates `docker-compose.override.yml`
- Adds SSL configuration to GitLab environment
- Restarts GitLab containers

### 6. Auto-Renewal Setup
- Creates renewal hook script
- Configures automatic certificate renewal
- Tests renewal process with dry-run

### 7. Verification
- Verifies HTTPS is working
- Displays certificate information
- Shows next steps

## Configuration Details

### GitLab Omnibus Configuration
The script adds the following to `/etc/gitlab/gitlab.rb`:
```ruby
external_url 'https://your-domain.com'
nginx['enable'] = true
nginx['redirect_http_to_https'] = true
nginx['ssl_certificate'] = "/etc/letsencrypt/live/your-domain.com/fullchain.pem"
nginx['ssl_certificate_key'] = "/etc/letsencrypt/live/your-domain.com/privkey.pem"
letsencrypt['enable'] = false
```

### Docker Configuration
Creates `docker-compose.override.yml` with SSL configuration and certificate volume mounts.

## File Locations

| File | Purpose |
|------|---------|
| `/etc/letsencrypt/cloudflare.ini` | Cloudflare API credentials |
| `/etc/letsencrypt/live/domain/` | SSL certificates |
| `/etc/letsencrypt/renewal-hooks/deploy/gitlab-reload.sh` | Renewal hook script |
| `docker-compose.override.yml` | Docker SSL configuration (Docker only) |

## Troubleshooting

### Common Issues

**1. Permission Denied**
```bash
# Make sure you're running as root
sudo ./setup-gitlab-ssl.sh [arguments]
```

**2. Cloudflare API Token Issues**
- Verify token has correct permissions
- Check token is not expired
- Ensure domain is managed by Cloudflare

**3. DNS Propagation Issues**
- Wait for DNS changes to propagate
- Check DNS records manually
- Verify domain points to server IP

**4. GitLab Not Accessible**
- Check GitLab service status
- Verify firewall settings
- Check GitLab logs

### Manual Certificate Renewal
```bash
sudo certbot renew
```

### Check Certificate Status
```bash
sudo certbot certificates
```

### View GitLab Logs
```bash
# For Omnibus
sudo gitlab-ctl tail

# For Docker
docker logs gitlab
```

## Security Notes

- Cloudflare credentials are stored with restricted permissions (600)
- Script requires root access for system-level operations
- Certificates are automatically renewed before expiration
- HTTP traffic is redirected to HTTPS

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review GitLab and Let's Encrypt documentation
3. Check script logs for error messages
4. Verify all prerequisites are met

## License

This script is part of the gitlab-env-mgr project. See the main project LICENSE file for details.
