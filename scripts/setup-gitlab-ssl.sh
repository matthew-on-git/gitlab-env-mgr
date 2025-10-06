#!/bin/bash

# GitLab SSL Certificate Setup Script
# Uses Let's Encrypt with Cloudflare DNS-01 challenge

set -euo pipefail

# Default values
DOMAIN=""
EMAIL=""
CF_TOKEN=""
GITLAB_TYPE=""

# Usage function
usage() {
    cat << EOF
Usage: $0 -d DOMAIN -e EMAIL -t CF_TOKEN -g GITLAB_TYPE [OPTIONS]

REQUIRED ARGUMENTS:
    -d, --domain DOMAIN        GitLab domain name (e.g., gitlab.example.com)
    -e, --email EMAIL          Email address for Let's Encrypt registration
    -t, --cf-token TOKEN       Cloudflare API token for DNS-01 challenge
    -g, --gitlab-type TYPE     GitLab installation type (omnibus or docker)

OPTIONS:
    -h, --help                 Show this help message and exit

EXAMPLES:
    # For GitLab Omnibus installation
    $0 -d gitlab.example.com -e admin@example.com -t your_cf_token -g omnibus

    # For GitLab Docker installation
    $0 -d gitlab.example.com -e admin@example.com -t your_cf_token -g docker

ENVIRONMENT VARIABLES:
    This script requires the following to be set or provided as arguments:
    - DOMAIN: Your GitLab domain name
    - EMAIL: Email for Let's Encrypt certificate registration
    - CF_TOKEN: Cloudflare API token with Zone:Read and DNS:Edit permissions
    - GITLAB_TYPE: Either 'omnibus' or 'docker'

PREREQUISITES:
    - Must be run as root
    - GitLab must be installed and running
    - Domain must point to this server's IP address
    - Cloudflare API token with appropriate permissions

EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -d|--domain)
                DOMAIN="$2"
                shift 2
                ;;
            -e|--email)
                EMAIL="$2"
                shift 2
                ;;
            -t|--cf-token)
                CF_TOKEN="$2"
                shift 2
                ;;
            -g|--gitlab-type)
                GITLAB_TYPE="$2"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done

    # Validate required arguments
    if [[ -z "$DOMAIN" ]]; then
        echo "Error: Domain is required"
        usage
        exit 1
    fi

    if [[ -z "$EMAIL" ]]; then
        echo "Error: Email is required"
        usage
        exit 1
    fi

    if [[ -z "$CF_TOKEN" ]]; then
        echo "Error: Cloudflare token is required"
        usage
        exit 1
    fi

    if [[ -z "$GITLAB_TYPE" ]]; then
        echo "Error: GitLab type is required"
        usage
        exit 1
    fi

    # Validate GitLab type
    if [[ "$GITLAB_TYPE" != "omnibus" && "$GITLAB_TYPE" != "docker" ]]; then
        echo "Error: GitLab type must be either 'omnibus' or 'docker'"
        usage
        exit 1
    fi
}

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

# Check prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check if running as root
    if [[ $EUID -ne 0 ]]; then
        error "This script must be run as root"
    fi
    
    # Detect OS
    if [[ -f /etc/debian_version ]]; then
        OS="debian"
    elif [[ -f /etc/redhat-release ]]; then
        OS="redhat"
    else
        error "Unsupported operating system"
    fi
    
    log "Prerequisites check passed"
}

# Install certbot
install_certbot() {
    log "Installing certbot and Cloudflare plugin..."
    
    if [[ "$OS" == "debian" ]]; then
        apt-get update
        apt-get install -y certbot python3-certbot-dns-cloudflare
    elif [[ "$OS" == "redhat" ]]; then
        yum install -y epel-release
        yum install -y certbot python3-certbot-dns-cloudflare
    fi
    
    log "Certbot installed successfully"
}

# Setup Cloudflare credentials
setup_cloudflare() {
    log "Setting up Cloudflare credentials..."
    
    mkdir -p /etc/letsencrypt
    
    cat > /etc/letsencrypt/cloudflare.ini << EOF
# Cloudflare API token
dns_cloudflare_api_token = ${CF_TOKEN}
EOF
    
    chmod 600 /etc/letsencrypt/cloudflare.ini
    
    log "Cloudflare credentials configured"
}

# Request certificate
request_certificate() {
    log "Requesting Let's Encrypt certificate for $DOMAIN..."
    
    certbot certonly \
        --non-interactive \
        --agree-tos \
        --email "$EMAIL" \
        --dns-cloudflare \
        --dns-cloudflare-credentials /etc/letsencrypt/cloudflare.ini \
        --dns-cloudflare-propagation-seconds 60 \
        -d "$DOMAIN"
    
    if [[ $? -eq 0 ]]; then
        log "Certificate obtained successfully!"
    else
        error "Failed to obtain certificate"
    fi
}

# Configure GitLab Omnibus
configure_gitlab_omnibus() {
    log "Configuring GitLab Omnibus..."
    
    # Backup current configuration
    cp /etc/gitlab/gitlab.rb /etc/gitlab/gitlab.rb.backup.$(date +%Y%m%d%H%M%S)
    
    # Update GitLab configuration
    cat >> /etc/gitlab/gitlab.rb << EOF

# SSL Configuration added by setup-gitlab-ssl.sh
external_url 'https://${DOMAIN}'
nginx['enable'] = true
nginx['redirect_http_to_https'] = true
nginx['ssl_certificate'] = "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
nginx['ssl_certificate_key'] = "/etc/letsencrypt/live/${DOMAIN}/privkey.pem"
letsencrypt['enable'] = false
EOF
    
    log "Reconfiguring GitLab..."
    gitlab-ctl reconfigure
    
    log "GitLab Omnibus configured successfully"
}

# Configure GitLab Docker
configure_gitlab_docker() {
    log "Configuring GitLab Docker..."
    
    # Create docker-compose override
    cat > docker-compose.override.yml << EOF
version: '3.8'
services:
  gitlab:
    environment:
      GITLAB_OMNIBUS_CONFIG: |
        external_url 'https://${DOMAIN}'
        nginx['enable'] = true
        nginx['redirect_http_to_https'] = true
        nginx['ssl_certificate'] = "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"
        nginx['ssl_certificate_key'] = "/etc/letsencrypt/live/${DOMAIN}/privkey.pem"
    volumes:
      - /etc/letsencrypt:/etc/letsencrypt:ro
EOF
    
    log "Restarting GitLab Docker..."
    docker-compose down
    docker-compose up -d
    
    log "GitLab Docker configured successfully"
}

# Setup auto-renewal
setup_renewal() {
    log "Setting up automatic renewal..."
    
    # Create renewal hook script
    mkdir -p /etc/letsencrypt/renewal-hooks/deploy
    
    cat > /etc/letsencrypt/renewal-hooks/deploy/gitlab-reload.sh << 'EOF'
#!/bin/bash
# Reload GitLab after certificate renewal

if command -v gitlab-ctl &> /dev/null; then
    echo "Reloading GitLab Omnibus nginx..."
    gitlab-ctl hup nginx
elif docker ps | grep -q gitlab; then
    echo "Reloading GitLab Docker nginx..."
    docker exec gitlab gitlab-ctl hup nginx
fi
EOF
    
    chmod +x /etc/letsencrypt/renewal-hooks/deploy/gitlab-reload.sh
    
    # Test renewal
    log "Testing certificate renewal..."
    certbot renew --dry-run
    
    if [[ $? -eq 0 ]]; then
        log "Auto-renewal configured successfully"
    else
        warn "Auto-renewal test failed. Please check configuration."
    fi
}

# Verify certificate
verify_certificate() {
    log "Verifying certificate installation..."
    
    # Wait for GitLab to be ready
    sleep 10
    
    # Check HTTPS
    if curl -ksI "https://${DOMAIN}" | grep -q "200 OK\|302 Found"; then
        log "HTTPS is working!"
    else
        warn "HTTPS check failed. GitLab might still be starting up."
    fi
    
    # Show certificate info
    log "Certificate details:"
    openssl s_client -connect "${DOMAIN}:443" -servername "${DOMAIN}" < /dev/null 2>/dev/null | \
        openssl x509 -noout -subject -issuer -dates
}

# Main execution
main() {
    # Parse command line arguments
    parse_args "$@"
    
    cat << EOF
====================================
GitLab SSL Certificate Setup Script
====================================
Domain: $DOMAIN
Email: $EMAIL
GitLab Type: $GITLAB_TYPE
====================================

This script will:
1. Install certbot with Cloudflare plugin
2. Request a Let's Encrypt certificate
3. Configure GitLab to use the certificate
4. Setup automatic renewal

EOF

    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 0
    fi
    
    check_prerequisites
    install_certbot
    setup_cloudflare
    request_certificate
    
    if [[ "$GITLAB_TYPE" == "omnibus" ]]; then
        configure_gitlab_omnibus
    elif [[ "$GITLAB_TYPE" == "docker" ]]; then
        configure_gitlab_docker
    else
        error "Unknown GitLab type: $GITLAB_TYPE"
    fi
    
    setup_renewal
    verify_certificate
    
    cat << EOF

${GREEN}✅ SSL Certificate Setup Complete!${NC}

Your GitLab instance is now accessible at:
https://${DOMAIN}

Certificate will auto-renew before expiration.

To manually renew:
sudo certbot renew

To check certificate status:
sudo certbot certificates

${YELLOW}Note: DNS must point to this server's IP for the certificate to work externally.${NC}

EOF
}

# Run main function
main "$@"