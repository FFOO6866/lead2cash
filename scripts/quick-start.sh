#!/bin/bash
# Quick Start Script for Kailash Project Template
# Usage: ./quick-start.sh

set -e

echo "=========================================="
echo "Kailash Project Template - Quick Start"
echo "=========================================="
echo ""

# Check for GH_TOKEN
if [ -z "$GH_TOKEN" ]; then
    echo "Error: GH_TOKEN environment variable not set"
    echo "Please set your GitHub Personal Access Token:"
    echo "  export GH_TOKEN=your_token_here"
    echo ""
    echo "Token must have these scopes:"
    echo "  - repo (Full control of private repositories)"
    echo "  - read:org (Read org and team membership)"
    echo "  - project (Full control of projects)"
    exit 1
fi

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found"
    echo "Please install Python 3.8 or higher"
    exit 1
fi

# Install dependencies
echo "Installing Python dependencies..."
pip install -q -r scripts/requirements.txt
echo "✓ Dependencies installed"
echo ""

# Get project details
echo "Let's create your new Kailash project!"
echo ""

read -p "GitHub Organization: " ORG
read -p "Repository Name: " REPO
read -p "Project Name: " PROJECT_NAME
read -p "Project Description: " PROJECT_DESC

echo ""
echo "Configuration:"
echo "  Organization: $ORG"
echo "  Repository: $REPO"
echo "  Project: $PROJECT_NAME"
echo ""
read -p "Create project? (y/n): " CONFIRM

if [ "$CONFIRM" != "y" ]; then
    echo "Cancelled"
    exit 0
fi

echo ""
echo "Creating project..."
python3 scripts/create-kailash-project.py \
    --org "$ORG" \
    --repo "$REPO" \
    --name "$PROJECT_NAME" \
    --description "$PROJECT_DESC"

echo ""
echo "✓ Project created successfully!"
echo ""
echo "Next steps:"
echo "  1. Visit your project board"
echo "  2. Review and customize Story 0"
echo "  3. Update .github/project-template-config.yaml"
echo "  4. Create feature stories using the template"
echo "  5. Begin Story 0 validation sprint"
echo ""
