# GitHub Actions Workflow Strategy - Template Sync System

## Overview

This repository provides a **template synchronization system** for distributing Kailash SDK updates, documentation, and development patterns to client projects. The workflows focus purely on template management and synchronization.

## Template Sync Workflows

### 1. `sync-to-downstream.yml` - Template Distribution
- **Purpose**: Syncs template updates to all downstream repositories
- **Triggers**: 
  - Push to `main` branch
  - Manual dispatch with optional target repo
- **Functions**:
  - Distributes SDK documentation updates
  - Syncs development patterns and guidelines
  - Updates shared components and tools
- **Target**: All repositories with `kailash-template` topic

### 2. `push-template-updates.yml` - Automated Sync Trigger  
- **Purpose**: Automatically triggers sync workflows in downstream repos
- **Triggers**: Push to `main` branch
- **Functions**:
  - Notifies downstream repositories of updates
  - Triggers template sync workflows
  - Handles rate limiting and error recovery

### 3. `notify-downstream-repos.yml` - Update Notifications
- **Purpose**: Creates notification issues in downstream repositories
- **Triggers**: Push to `main` branch  
- **Functions**:
  - Creates GitHub issues alerting teams to template updates
  - Provides summary of changes
  - Links to template sync PRs

## Client Repository Workflows

### 4. `sync-from-template.yml` - Client-Side Sync
- **Purpose**: Receives and applies template updates in client repositories
- **Triggers**: 
  - Workflow dispatch from template repository
  - Manual dispatch for ad-hoc syncs
- **Functions**:
  - Creates template sync PRs
  - Preserves client-specific code and configurations
  - Merges template updates safely

### 5. `template-sync-check.yml` - Lightweight Validation
- **Purpose**: Validates template sync PRs without full CI overhead
- **Triggers**: Template sync PRs only
- **Functions**:
  - Basic syntax validation
  - Template structure verification
  - Prevents GitHub Actions credit consumption
- **Duration**: 30-60 seconds

### 6. `template-init.yml` - New Repository Setup
- **Purpose**: Automatically configures repositories created from template
- **Triggers**: Repository creation from template
- **Functions**:
  - Adds `kailash-template` topic for discovery
  - Sets up initial project structure
  - Configures template sync system

## File Sync Strategy

### Always Synced (Replace Mode)
- `sdk-users/` - SDK documentation and guides
- `CLAUDE.md` - Development patterns and workflows  
- Template workflows - Essential sync functionality
- `apps/` - Example applications
- `src/new_project/` - Template project structure

### Sync If Missing (Preserve Mode)
- Root files: `README.md`, `pyproject.toml`, `.gitignore`
- `solutions/`, `deployment/`, `data/` directories

### Never Synced (Client-Owned)
- Client applications and custom code
- Project-specific configurations
- Custom workflows (outside of template sync)

## Repository Discovery

The template system uses **topic-based discovery**:
- **Search**: `org:Integrum-Global+topic:kailash-template`
- **Automatic**: Repositories created from template get the topic automatically
- **Manual**: Use `scripts/link-existing-repo.sh` to add existing repos

## Key Principles

1. **Client Code Protection**: Template sync never overwrites client applications or custom code
2. **Selective Sync**: Only template-related files are synchronized
3. **Conflict Prevention**: Client code is isolated from template updates
4. **Automatic Cleanup**: Obsolete template files are automatically removed
5. **Credit Conservation**: Template sync uses lightweight validation to minimize GitHub Actions usage

## For Client Projects

Client projects receive template updates but maintain full control over:
- Their application code
- Custom CI/CD workflows  
- Project-specific configurations
- Development processes

The template system provides:
- Latest SDK documentation
- Proven development patterns
- Shared tooling and utilities
- Example applications for reference

## Documentation

- **Template Sync Guide**: `scripts/TEMPLATE_SYNC_GUIDE.md`
- **PR Management**: `scripts/PR_AND_TOPIC_SYNC_SUMMARY.md`
- **CLAUDE.md**: Development patterns and SDK best practices