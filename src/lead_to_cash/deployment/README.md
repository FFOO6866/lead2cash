# Lead to Cash Deployment Guide

Production deployment documentation for **rr-kailash.ai**.

## Table of Contents

- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Directory Structure](#directory-structure)
- [SSH Setup](#ssh-setup)
- [Environment Configuration](#environment-configuration)
- [Deployment Commands](#deployment-commands)
- [Docker Configuration](#docker-configuration)
- [Monitoring and Health Checks](#monitoring-and-health-checks)
- [Troubleshooting](#troubleshooting)
- [Security Best Practices](#security-best-practices)

---

## Quick Start

```bash
# 1. Setup SSH access
./deployment/ssh/setup-ssh.sh

# 2. Generate secrets
./deployment/scripts/deploy.sh secrets

# 3. Configure environment
cp deployment/config/.env.example deployment/config/.env.production
# Edit .env.production with generated secrets

# 4. Initial server setup (first time only)
./deployment/scripts/deploy.sh setup

# 5. Deploy application
./deployment/scripts/deploy.sh deploy
```

---

## Prerequisites

### Local Machine
- Bash shell
- SSH client
- Docker (for local testing)
- `openssl` (for secret generation)

### Server (rr-kailash.ai)
- Ubuntu 22.04 LTS (or compatible)
- Minimum 4GB RAM, 2 vCPU
- Docker and Docker Compose (installed by setup script)
- Ports 22, 80, 443 accessible

### Files Required
- `rr-kailash.pem` - SSH private key (already in project)
- `.env.production` - Production environment variables (you create)

---

## Directory Structure

```
src/lead_to_cash/deployment/
├── docker/
│   ├── Dockerfile              # Multi-stage production Docker image
│   └── docker-compose.yml      # Production compose configuration
├── config/
│   ├── .env.example            # Environment template
│   └── init-scripts/           # Database initialization
│       └── 01-create-extensions.sql
├── scripts/
│   └── deploy.sh               # Main deployment script
├── ssh/
│   ├── config                  # SSH client configuration
│   └── setup-ssh.sh            # SSH setup helper
└── README.md                   # This file
```

---

## SSH Setup

### Automatic Setup (Recommended)

```bash
# Run the setup script
./deployment/ssh/setup-ssh.sh
```

This will:
1. Copy PEM file to `~/.ssh/rr-kailash.pem`
2. Set correct permissions (600)
3. Add SSH host configuration

### Manual Setup

```bash
# Copy PEM file
cp src/lead_to_cash/rr-kailash.pem ~/.ssh/rr-kailash.pem
chmod 600 ~/.ssh/rr-kailash.pem

# Add to SSH config (~/.ssh/config)
Host rr-kailash
    HostName rr-kailash.ai
    User ubuntu
    IdentityFile ~/.ssh/rr-kailash.pem
    IdentitiesOnly yes
```

### Test Connection

```bash
ssh rr-kailash
# or
ssh -i ~/.ssh/rr-kailash.pem ubuntu@rr-kailash.ai
```

---

## Environment Configuration

### Generate Secrets

```bash
# Generate all required secrets
./deployment/scripts/deploy.sh secrets
```

Output example:
```
SECRET_KEY=a1b2c3d4e5f6...
JWT_SECRET_KEY=f6e5d4c3b2a1...
POSTGRES_PASSWORD=abc123def456...
REDIS_PASSWORD=xyz789uvw012...
```

### Create Production Environment File

```bash
cp deployment/config/.env.example deployment/config/.env.production
```

Edit `.env.production` and replace placeholder values:

| Variable | Description | How to Generate |
|----------|-------------|-----------------|
| `SECRET_KEY` | Application secret | `openssl rand -hex 32` |
| `JWT_SECRET_KEY` | JWT signing key | `openssl rand -hex 32` |
| `POSTGRES_PASSWORD` | Database password | `openssl rand -hex 16` |
| `REDIS_PASSWORD` | Cache password | `openssl rand -hex 16` |
| `ACME_EMAIL` | SSL cert email | Your admin email |
| `TRAEFIK_BASIC_AUTH` | Dashboard auth | `htpasswd -nb admin pass` |

### Security Checklist

- [ ] All secrets generated with `openssl rand`
- [ ] `.env.production` is NOT in git (check `.gitignore`)
- [ ] File permissions: `chmod 600 .env.production`
- [ ] CORS_ORIGINS restricted to production domains
- [ ] DEBUG=false for production

---

## Deployment Commands

### Full Command Reference

```bash
./deployment/scripts/deploy.sh <command>

Commands:
    setup       # Initial server setup (Docker, firewall)
    deploy      # Full deployment to server
    update      # Quick update (rebuild app container)
    rollback    # Rollback to previous deployment
    status      # Show application status
    logs [n]    # Show logs (default: 100 lines)
    start       # Start stopped application
    stop        # Stop application
    secrets     # Generate secure secrets
    check       # Test SSH connection
```

### Deployment Workflow

#### First-Time Deployment

```bash
# 1. Setup server infrastructure
./deployment/scripts/deploy.sh setup

# 2. Deploy application
./deployment/scripts/deploy.sh deploy

# 3. Verify deployment
./deployment/scripts/deploy.sh status
```

#### Regular Updates

```bash
# Quick update (hot reload)
./deployment/scripts/deploy.sh update

# or Full redeploy
./deployment/scripts/deploy.sh deploy
```

#### Emergency Rollback

```bash
# Rollback to previous version
./deployment/scripts/deploy.sh rollback

# Check logs for issues
./deployment/scripts/deploy.sh logs 500
```

---

## Docker Configuration

### Services

| Service | Image | Port | Description |
|---------|-------|------|-------------|
| lead-to-cash | Custom | 8000 | Main application |
| postgres | pgvector/pgvector:pg15 | 5432 | Database with vector support |
| redis | redis:7-alpine | 6379 | Cache and session storage |
| traefik | traefik:v3.0 | 80, 443 | Reverse proxy with SSL |

### Resource Limits

| Service | CPU Limit | Memory Limit |
|---------|-----------|--------------|
| lead-to-cash | 2.0 cores | 4GB |
| postgres | 2.0 cores | 4GB |
| redis | 1.0 cores | 2GB |

### Volumes

| Volume | Purpose |
|--------|---------|
| `postgres_data` | Database persistence |
| `redis_data` | Cache persistence |
| `app_logs` | Application logs |
| `traefik_letsencrypt` | SSL certificates |

---

## Monitoring and Health Checks

### Health Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /health` | Liveness probe |
| `GET /` | Basic status |
| `GET /workflows` | Available workflows |

### Check Application Health

```bash
# Via deployment script
./deployment/scripts/deploy.sh status

# Direct curl (from server)
curl https://rr-kailash.ai/health
```

### View Logs

```bash
# Last 100 lines
./deployment/scripts/deploy.sh logs

# Last 500 lines, follow
./deployment/scripts/deploy.sh logs 500

# Directly on server
ssh rr-kailash 'cd /opt/lead-to-cash/current/lead_to_cash/deployment/docker && docker-compose logs -f'
```

### Docker Health Checks

```yaml
# Built into docker-compose.yml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

---

## Troubleshooting

### SSH Connection Issues

```bash
# Verbose connection test
ssh -v -i ~/.ssh/rr-kailash.pem ubuntu@rr-kailash.ai

# Check PEM permissions
ls -la ~/.ssh/rr-kailash.pem
# Should be: -rw-------

# Fix permissions
chmod 600 ~/.ssh/rr-kailash.pem
```

### Container Not Starting

```bash
# Check container status
./deployment/scripts/deploy.sh status

# View startup logs
./deployment/scripts/deploy.sh logs 500

# SSH to server and check manually
ssh rr-kailash
cd /opt/lead-to-cash/current/lead_to_cash/deployment/docker
docker-compose ps
docker-compose logs lead-to-cash
```

### Database Connection Failed

```bash
# Check PostgreSQL container
ssh rr-kailash 'docker exec lead-to-cash-postgres pg_isready'

# View PostgreSQL logs
ssh rr-kailash 'docker logs lead-to-cash-postgres'

# Connect to database
ssh rr-kailash 'docker exec -it lead-to-cash-postgres psql -U lead_to_cash_user -d lead_to_cash_db'
```

### SSL Certificate Issues

```bash
# Check Traefik logs
ssh rr-kailash 'docker logs lead-to-cash-traefik'

# Verify certificate
curl -vI https://rr-kailash.ai

# Force certificate renewal
ssh rr-kailash 'docker exec lead-to-cash-traefik rm /letsencrypt/acme.json'
# Then restart Traefik
```

### Out of Memory

```bash
# Check resource usage
ssh rr-kailash 'docker stats --no-stream'

# Check system memory
ssh rr-kailash 'free -h'

# Restart containers
./deployment/scripts/deploy.sh stop
./deployment/scripts/deploy.sh start
```

---

## Security Best Practices

### Credential Management

1. **Never commit secrets to git**
   ```bash
   # Ensure .gitignore includes:
   .env
   .env.*
   *.pem
   ```

2. **Generate strong secrets**
   ```bash
   # Use openssl for all secrets
   openssl rand -hex 32  # For keys
   openssl rand -hex 16  # For passwords
   ```

3. **Rotate secrets regularly**
   - Database passwords: Quarterly
   - JWT secrets: Monthly in high-security environments
   - API keys: When team members change

### Network Security

1. **Firewall (UFW)**
   ```bash
   # Allow only necessary ports
   sudo ufw allow 22/tcp
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

2. **SSL/TLS**
   - TLS 1.3 enforced via Traefik
   - Automatic certificate renewal via Let's Encrypt

3. **CORS**
   - Restrict to production domains only
   - Never use `*` in production

### Container Security

1. **Non-root user**
   - Application runs as `appuser`, not root

2. **Read-only mounts where possible**
   - Config files mounted as read-only

3. **Resource limits**
   - CPU and memory limits prevent resource exhaustion

### Backup Strategy

```bash
# Database backup (run on server)
docker exec lead-to-cash-postgres pg_dump -U lead_to_cash_user lead_to_cash_db > backup.sql

# Automated backup recommendation:
# - Daily database backups
# - Weekly full system snapshots
# - Store backups in separate AWS S3 bucket
```

---

## AWS Integration Notes

Based on `docs/AWS_Setup_Requirements.md`:

| Requirement | Status | Notes |
|-------------|--------|-------|
| Region | ap-southeast-1 | Configurable per client |
| TLS Version | TLS 1.3 | Via Traefik |
| Authentication | OAuth 2.0 | Nexus built-in |
| Secrets Management | AWS Secrets Manager | For production credentials |

### DNS Configuration

Point these records to your server IP:
```
rr-kailash.ai.    A     <server-ip>
www.rr-kailash.ai. CNAME rr-kailash.ai.
```

---

## Support

For deployment issues:
1. Check this README troubleshooting section
2. Review logs: `./deployment/scripts/deploy.sh logs 500`
3. Check server status: `./deployment/scripts/deploy.sh status`

For application issues:
1. Review gateway.py for endpoint configuration
2. Check manifest.yaml for capability settings
3. Review AWS_Setup_Requirements.md for client requirements
