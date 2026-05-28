#!/bin/bash
# ==============================================================================
# Lead to Cash Deployment Script for rr-kailash.ai
# ==============================================================================
# Usage: ./deploy.sh [command] [options]
# Commands: setup, deploy, update, rollback, status, logs, stop
# ==============================================================================

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
DEPLOY_DIR="$SCRIPT_DIR/.."
DOCKER_DIR="$DEPLOY_DIR/docker"
CONFIG_DIR="$DEPLOY_DIR/config"
SSH_DIR="$DEPLOY_DIR/ssh"

# Server Configuration
SERVER_HOST="${SERVER_HOST:-rr.kailash.ai}"
SERVER_USER="${SERVER_USER:-ubuntu}"
SERVER_KEY="${SERVER_KEY:-$PROJECT_ROOT/src/lead_to_cash/rr-kailash.pem}"
REMOTE_APP_DIR="${REMOTE_APP_DIR:-/opt/lead-to-cash}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Functions
print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "\n${BLUE}=== $1 ===${NC}\n"; }

# Validate PEM file
validate_pem() {
    if [[ ! -f "$SERVER_KEY" ]]; then
        print_error "PEM file not found at: $SERVER_KEY"
        print_info "Please ensure the PEM file exists or set SERVER_KEY environment variable"
        exit 1
    fi

    # Check permissions
    local perms=$(stat -f "%OLp" "$SERVER_KEY" 2>/dev/null || stat -c "%a" "$SERVER_KEY" 2>/dev/null)
    if [[ "$perms" != "600" && "$perms" != "400" ]]; then
        print_warn "Fixing PEM file permissions..."
        chmod 600 "$SERVER_KEY"
    fi

    print_info "PEM file validated: $SERVER_KEY"
}

# SSH command wrapper
ssh_cmd() {
    ssh -i "$SERVER_KEY" -o StrictHostKeyChecking=accept-new "${SERVER_USER}@${SERVER_HOST}" "$@"
}

# SCP command wrapper
scp_cmd() {
    scp -i "$SERVER_KEY" -o StrictHostKeyChecking=accept-new "$@"
}

# Check server connectivity
check_connection() {
    print_header "Checking Server Connection"
    validate_pem

    print_info "Testing SSH connection to ${SERVER_USER}@${SERVER_HOST}..."
    if ssh_cmd "echo 'Connection successful'" > /dev/null 2>&1; then
        print_info "SSH connection established"
        return 0
    else
        print_error "Failed to connect to server"
        return 1
    fi
}

# Setup server environment (first-time setup)
setup_server() {
    print_header "Setting Up Server Environment"
    check_connection

    print_info "Installing Docker and dependencies..."
    ssh_cmd << 'REMOTE_SCRIPT'
        set -e

        # Update system
        sudo apt-get update
        sudo apt-get upgrade -y

        # Install Docker if not present
        if ! command -v docker &> /dev/null; then
            curl -fsSL https://get.docker.com -o get-docker.sh
            sudo sh get-docker.sh
            sudo usermod -aG docker $USER
            rm get-docker.sh
        fi

        # Install Docker Compose if not present
        if ! command -v docker-compose &> /dev/null; then
            sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
            sudo chmod +x /usr/local/bin/docker-compose
        fi

        # Create application directory
        sudo mkdir -p /opt/lead-to-cash
        sudo chown -R $USER:$USER /opt/lead-to-cash

        # Configure firewall
        sudo ufw allow 22/tcp
        sudo ufw allow 80/tcp
        sudo ufw allow 443/tcp
        sudo ufw --force enable

        echo "Server setup complete"
REMOTE_SCRIPT

    print_info "Server setup completed successfully"
}

# Deploy application
deploy() {
    print_header "Deploying Lead to Cash Application"
    check_connection

    # Check for .env file
    if [[ ! -f "$CONFIG_DIR/.env.production" ]]; then
        print_error "Production environment file not found: $CONFIG_DIR/.env.production"
        print_info "Copy .env.example to .env.production and configure it first"
        exit 1
    fi

    print_info "Creating deployment archive..."
    cd "$PROJECT_ROOT"

    # Create temporary deployment directory
    TEMP_DEPLOY=$(mktemp -d)
    trap "rm -rf $TEMP_DEPLOY" EXIT

    # Copy necessary files - maintain src structure for pyproject.toml compatibility
    mkdir -p "$TEMP_DEPLOY/src"
    cp -r src/lead_to_cash "$TEMP_DEPLOY/src/"
    cp -r sdk-users "$TEMP_DEPLOY/"
    cp pyproject.toml "$TEMP_DEPLOY/"
    cp README.md "$TEMP_DEPLOY/" 2>/dev/null || echo "README" > "$TEMP_DEPLOY/README.md"
    cp "$CONFIG_DIR/.env.production" "$TEMP_DEPLOY/.env"

    # Create archive
    ARCHIVE="$TEMP_DEPLOY/lead-to-cash-deploy.tar.gz"
    tar -czf "$ARCHIVE" -C "$TEMP_DEPLOY" src sdk-users pyproject.toml README.md .env

    print_info "Uploading to server..."
    scp_cmd "$ARCHIVE" "${SERVER_USER}@${SERVER_HOST}:/tmp/"

    print_info "Deploying on server..."
    ssh_cmd << 'REMOTE_SCRIPT'
        set -e
        cd /opt/lead-to-cash

        # Backup current deployment
        if [[ -d "current" ]]; then
            BACKUP_NAME="backup-$(date +%Y%m%d-%H%M%S)"
            mv current "$BACKUP_NAME"
            echo "Created backup: $BACKUP_NAME"
        fi

        # Extract new deployment
        mkdir -p current
        tar -xzf /tmp/lead-to-cash-deploy.tar.gz -C current
        rm /tmp/lead-to-cash-deploy.tar.gz

        # Copy production docker-compose file
        cp current/src/lead_to_cash/deployment/docker/docker-compose.yml current/docker-compose.yml

        # Move .env to root for docker-compose
        mv current/.env current/.env.prod
        ln -sf .env.prod current/.env

        # Deploy with Docker Compose from current directory
        cd current
        docker compose pull || true
        docker compose up -d --build

        # Wait for health check
        echo "Waiting for services to be healthy..."
        sleep 30

        # Check status
        docker-compose ps

        echo "Deployment complete"
REMOTE_SCRIPT

    print_info "Deployment completed successfully"
    print_info "Application available at: https://${SERVER_HOST}"
}

# Update application (hot reload)
update() {
    print_header "Updating Lead to Cash Application"
    check_connection

    print_info "Pulling latest changes and rebuilding..."
    ssh_cmd << 'REMOTE_SCRIPT'
        set -e
        cd /opt/lead-to-cash/current

        # Rebuild and restart with zero downtime
        docker compose build lead-to-cash
        docker compose up -d --no-deps lead-to-cash

        # Wait and verify
        sleep 10
        docker compose ps
REMOTE_SCRIPT

    print_info "Update completed"
}

# Rollback to previous deployment
rollback() {
    print_header "Rolling Back Deployment"
    check_connection

    ssh_cmd << 'REMOTE_SCRIPT'
        set -e
        cd /opt/lead-to-cash

        # Find latest backup
        LATEST_BACKUP=$(ls -td backup-* 2>/dev/null | head -1)

        if [[ -z "$LATEST_BACKUP" ]]; then
            echo "No backup found to rollback to"
            exit 1
        fi

        echo "Rolling back to: $LATEST_BACKUP"

        # Stop current deployment
        if [[ -d "current" ]]; then
            cd current
            docker compose down
            cd /opt/lead-to-cash
            mv current "failed-$(date +%Y%m%d-%H%M%S)"
        fi

        # Restore backup
        mv "$LATEST_BACKUP" current

        # Start restored deployment
        cd current
        docker compose up -d

        echo "Rollback complete"
REMOTE_SCRIPT

    print_info "Rollback completed"
}

# Show application status
show_status() {
    print_header "Application Status"
    check_connection

    ssh_cmd << 'REMOTE_SCRIPT'
        echo "=== Docker Containers ==="
        cd /opt/lead-to-cash/current 2>/dev/null && \
            docker compose ps || echo "No deployment found"

        echo ""
        echo "=== Health Check ==="
        curl -s http://localhost:8000/health || echo "Health check failed"

        echo ""
        echo "=== Resource Usage ==="
        docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null | head -10

        echo ""
        echo "=== Disk Usage ==="
        df -h /opt/lead-to-cash
REMOTE_SCRIPT
}

# Show application logs
show_logs() {
    print_header "Application Logs"
    check_connection

    local lines="${1:-100}"
    ssh_cmd "cd /opt/lead-to-cash/current && docker compose logs --tail=$lines -f"
}

# Stop application
stop() {
    print_header "Stopping Application"
    check_connection

    ssh_cmd << 'REMOTE_SCRIPT'
        cd /opt/lead-to-cash/current 2>/dev/null && \
            docker compose down || echo "No deployment to stop"
REMOTE_SCRIPT

    print_info "Application stopped"
}

# Start application
start() {
    print_header "Starting Application"
    check_connection

    ssh_cmd << 'REMOTE_SCRIPT'
        cd /opt/lead-to-cash/current
        docker compose up -d
        sleep 10
        docker compose ps
REMOTE_SCRIPT

    print_info "Application started"
}

# Generate secrets helper
generate_secrets() {
    print_header "Generating Secure Secrets"

    echo "Add these to your .env.production file:"
    echo ""
    echo "# Generated secrets - $(date)"
    echo "SECRET_KEY=$(openssl rand -hex 32)"
    echo "JWT_SECRET_KEY=$(openssl rand -hex 32)"
    echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)"
    echo "REDIS_PASSWORD=$(openssl rand -hex 16)"
    echo ""
    print_warn "Copy these values carefully - they cannot be recovered!"
}

# Usage help
usage() {
    cat << EOF
Lead to Cash Deployment Script for rr-kailash.ai

Usage: $0 <command> [options]

Commands:
    setup           Initial server setup (Docker, firewall, directories)
    deploy          Deploy application to server
    update          Update running application
    rollback        Rollback to previous deployment
    status          Show application status
    logs [n]        Show last n lines of logs (default: 100)
    start           Start stopped application
    stop            Stop application
    secrets         Generate secure secrets for .env file
    check           Check server connectivity

Environment Variables:
    SERVER_HOST     Server hostname (default: rr-kailash.ai)
    SERVER_USER     SSH user (default: ubuntu)
    SERVER_KEY      Path to PEM file (default: src/lead_to_cash/rr-kailash.pem)
    REMOTE_APP_DIR  Remote app directory (default: /opt/lead-to-cash)

Examples:
    $0 setup                    # First-time server setup
    $0 deploy                   # Deploy application
    $0 status                   # Check application status
    $0 logs 200                 # Show last 200 log lines
    $0 rollback                 # Rollback to previous version

EOF
}

# Main command router
case "${1:-help}" in
    setup)
        setup_server
        ;;
    deploy)
        deploy
        ;;
    update)
        update
        ;;
    rollback)
        rollback
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "${2:-100}"
        ;;
    start)
        start
        ;;
    stop)
        stop
        ;;
    secrets)
        generate_secrets
        ;;
    check)
        check_connection
        ;;
    help|--help|-h)
        usage
        ;;
    *)
        print_error "Unknown command: $1"
        usage
        exit 1
        ;;
esac
