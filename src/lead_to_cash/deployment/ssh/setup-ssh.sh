#!/bin/bash
# ==============================================================================
# SSH Setup Script for Lead to Cash Deployment
# Sets up SSH keys and configuration for connecting to rr-kailash.ai
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
PEM_SOURCE="$PROJECT_ROOT/src/lead_to_cash/rr-kailash.pem"
SSH_DIR="$HOME/.ssh"
PEM_DEST="$SSH_DIR/rr-kailash.pem"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

echo "=============================================="
echo "SSH Setup for Lead to Cash (rr-kailash.ai)"
echo "=============================================="
echo ""

# Check if source PEM exists
if [[ ! -f "$PEM_SOURCE" ]]; then
    print_error "PEM file not found at: $PEM_SOURCE"
    print_info "Please ensure the rr-kailash.pem file is in the project directory"
    exit 1
fi

# Create .ssh directory if it doesn't exist
if [[ ! -d "$SSH_DIR" ]]; then
    print_info "Creating SSH directory..."
    mkdir -p "$SSH_DIR"
    chmod 700 "$SSH_DIR"
fi

# Copy PEM file
if [[ -f "$PEM_DEST" ]]; then
    print_warn "PEM file already exists at $PEM_DEST"
    read -p "Overwrite? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Skipping PEM file copy"
    else
        cp "$PEM_SOURCE" "$PEM_DEST"
        print_info "PEM file copied to $PEM_DEST"
    fi
else
    cp "$PEM_SOURCE" "$PEM_DEST"
    print_info "PEM file copied to $PEM_DEST"
fi

# Set correct permissions
chmod 600 "$PEM_DEST"
print_info "PEM file permissions set to 600"

# Backup existing SSH config
SSH_CONFIG="$SSH_DIR/config"
if [[ -f "$SSH_CONFIG" ]]; then
    if grep -q "Host rr-kailash" "$SSH_CONFIG"; then
        print_warn "SSH config for rr-kailash already exists"
        print_info "To update, manually edit $SSH_CONFIG"
    else
        # Append new config
        echo "" >> "$SSH_CONFIG"
        cat "$SCRIPT_DIR/config" >> "$SSH_CONFIG"
        print_info "SSH config appended to $SSH_CONFIG"
    fi
else
    # Create new config
    cp "$SCRIPT_DIR/config" "$SSH_CONFIG"
    chmod 600 "$SSH_CONFIG"
    print_info "SSH config created at $SSH_CONFIG"
fi

echo ""
echo "=============================================="
echo "Setup Complete!"
echo "=============================================="
echo ""
print_info "You can now connect with: ssh rr-kailash"
echo ""
print_info "Quick commands:"
echo "  ssh rr-kailash                    # Connect to server"
echo "  ssh rr-kailash 'docker ps'        # Run command remotely"
echo "  scp file.txt rr-kailash:/tmp/     # Copy file to server"
echo ""

# Test connection
read -p "Test SSH connection now? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Testing connection..."
    if ssh -o ConnectTimeout=10 rr-kailash "echo 'Connection successful!'" 2>/dev/null; then
        print_info "SSH connection test passed!"
    else
        print_warn "Connection test failed. The server may not be accessible yet."
        print_info "Verify the server is running and the domain resolves correctly."
    fi
fi
