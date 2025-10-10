#!/usr/bin/env python3
"""
Validation script to check if required services are running.
Uses dynamic container names based on project.
"""

import os
import subprocess
import sys
from pathlib import Path


def get_project_name():
    """Get project name from current directory or lock file."""
    lock_file = Path("tests/.docker-ports.lock")
    if lock_file.exists():
        with open(lock_file, "r") as f:
            for line in f:
                if line.startswith("PROJECT_NAME="):
                    return line.split("=", 1)[1].strip()
    return os.path.basename(os.getcwd())


def check_container(container_name):
    """Check if a Docker container is running."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            check=True
        )
        return container_name in result.stdout
    except:
        return False


def main():
    """Check all required services."""
    project_name = get_project_name()
    
    services = {
        "PostgreSQL": f"{project_name}_test_postgres",
        "Redis": f"{project_name}_test_redis",
        "Ollama": f"{project_name}_test_ollama",
        "MySQL": f"{project_name}_test_mysql",
    }
    
    all_good = True
    for service, container in services.items():
        if check_container(container):
            print(f"✓ {service} is running ({container})")
        else:
            print(f"✗ {service} is NOT running (expected: {container})")
            all_good = False
    
    return 0 if all_good else 1


if __name__ == "__main__":
    sys.exit(main())