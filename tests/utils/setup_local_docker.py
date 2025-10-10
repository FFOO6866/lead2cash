#!/usr/bin/env python3
"""Setup local Docker infrastructure with dynamic port allocation.

This script sets up PostgreSQL, MySQL, Redis, and Ollama containers
with project-specific ports to avoid conflicts when working on multiple repos.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import requests


def run_command(cmd, check=True):
    """Run a shell command and return the output."""
    print(f"Running: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error: {result.stderr}")
        sys.exit(1)
    return result


def check_docker():
    """Check if Docker is available and running."""
    result = run_command("docker info", check=False)
    if result.returncode != 0:
        print("Error: Docker is not running or not installed.")
        print("Please start Docker Desktop or install Docker.")
        return False
    return True


def get_project_config():
    """Get project-specific configuration."""
    project_name = os.path.basename(os.getcwd())
    project_hash = abs(hash(project_name)) % 1000
    base_port = 5000 + project_hash * 10
    
    return {
        'project_name': project_name,
        'project_hash': project_hash,
        'base_port': base_port,
        'postgres_port': base_port + 0,
        'redis_port': base_port + 1,
        'ollama_port': base_port + 2,
        'mysql_port': base_port + 3,
        'mongodb_port': base_port + 4,
    }


def check_port_available(port):
    """Check if a port is available."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(('', port))
        sock.close()
        return True
    except:
        return False


def check_ports(config):
    """Check if all required ports are available."""
    conflicts = []
    ports = [
        ('PostgreSQL', config['postgres_port']),
        ('Redis', config['redis_port']),
        ('Ollama', config['ollama_port']),
        ('MySQL', config['mysql_port']),
        ('MongoDB', config['mongodb_port']),
    ]
    
    for service, port in ports:
        if not check_port_available(port):
            conflicts.append((service, port))
    
    return conflicts


def check_container_running(container_name):
    """Check if a container is already running."""
    result = run_command(
        f"docker ps --filter name={container_name} --format '{{{{.Names}}}}'",
        check=False,
    )
    return container_name in result.stdout


def wait_for_postgres(
    container_name,
    host="localhost",
    port=5432,
    user="test_user",
    password="test_password",
    database=None,
):
    """Wait for PostgreSQL to be ready."""
    print("Waiting for PostgreSQL to be ready...")
    for i in range(30):
        result = run_command(
            f"docker exec {container_name} pg_isready -h localhost -p 5432 -U {user} -d {database}",
            check=False,
        )
        if result.returncode == 0:
            print("PostgreSQL is ready!")
            return True
        time.sleep(1)
    return False


def wait_for_mysql(container_name, host="localhost", port=3306, user="root", password="test_password"):
    """Wait for MySQL to be ready."""
    print("Waiting for MySQL to be ready...")
    for i in range(30):
        result = run_command(
            f"docker exec {container_name} mysql -h localhost -u {user} -p{password} -e 'SELECT 1'",
            check=False,
        )
        if result.returncode == 0:
            print("MySQL is ready!")
            return True
        time.sleep(1)
    return False


def wait_for_redis(container_name, host="localhost", port=6379):
    """Wait for Redis to be ready."""
    print("Waiting for Redis to be ready...")
    for i in range(30):
        result = run_command(
            f"docker exec {container_name} redis-cli ping", check=False
        )
        if "PONG" in result.stdout:
            print("Redis is ready!")
            return True
        time.sleep(1)
    return False


def wait_for_ollama(base_url="http://localhost:11435"):
    """Wait for Ollama to be ready."""
    print("Waiting for Ollama to be ready...")
    for i in range(30):
        try:
            response = requests.get(f"{base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                print("Ollama is ready!")
                return True
        except:
            pass
        time.sleep(1)
    return False


def setup_postgres(config):
    """Setup PostgreSQL container for testing."""
    container_name = f"{config['project_name']}_test_postgres"
    database_name = f"{config['project_name']}_test"
    
    if check_container_running(container_name):
        print(f"PostgreSQL container {container_name} already running.")
        return True

    print(f"Starting PostgreSQL container on port {config['postgres_port']}...")
    run_command(
        f"docker run -d "
        f"--name {container_name} "
        f"-e POSTGRES_DB={database_name} "
        f"-e POSTGRES_USER=test_user "
        f"-e POSTGRES_PASSWORD=test_password "
        f'-e POSTGRES_INITDB_ARGS="-c shared_buffers=256MB -c max_connections=200" '
        f"-p {config['postgres_port']}:5432 "
        f"--health-cmd 'pg_isready -U test_user -d {database_name}' "
        f"--health-interval 10s "
        f"--health-timeout 5s "
        f"--health-retries 5 "
        f"--network {config['project_name']}_test_network "
        f"postgres:15"
    )

    if not wait_for_postgres(container_name, database=database_name):
        print("Failed to start PostgreSQL")
        return False

    # Create test database and schema
    print("Setting up test database...")
    run_command(
        f"docker exec {container_name} psql -U test_user -d {database_name} -c "
        f"'CREATE SCHEMA IF NOT EXISTS public;'"
    )

    return True


def setup_mysql(config):
    """Setup MySQL container for testing."""
    container_name = f"{config['project_name']}_test_mysql"
    database_name = f"{config['project_name']}_test"
    
    if check_container_running(container_name):
        print(f"MySQL container {container_name} already running.")
        return True

    print(f"Starting MySQL container on port {config['mysql_port']}...")
    run_command(
        f"docker run -d "
        f"--name {container_name} "
        f"-e MYSQL_ROOT_PASSWORD=test_password "
        f"-e MYSQL_DATABASE={database_name} "
        f"-e MYSQL_USER={config['project_name']}_test "
        f"-e MYSQL_PASSWORD=test_password "
        f"-p {config['mysql_port']}:3306 "
        f"--network {config['project_name']}_test_network "
        f"mysql:8.0"
    )

    if not wait_for_mysql(container_name):
        print("Failed to start MySQL")
        return False

    return True


def setup_redis(config):
    """Setup Redis container for testing."""
    container_name = f"{config['project_name']}_test_redis"
    
    if check_container_running(container_name):
        print(f"Redis container {container_name} already running.")
        return True

    print(f"Starting Redis container on port {config['redis_port']}...")
    run_command(
        f"docker run -d "
        f"--name {container_name} "
        f"-p {config['redis_port']}:6379 "
        f"--health-cmd 'redis-cli ping' "
        f"--health-interval 10s "
        f"--health-timeout 5s "
        f"--health-retries 5 "
        f"--network {config['project_name']}_test_network "
        f"redis:7-alpine "
        f"redis-server "
        f"--maxmemory 1gb "
        f"--maxmemory-policy allkeys-lru "
        f'--save "" '
        f"--appendonly no"
    )

    if not wait_for_redis(container_name):
        print("Failed to start Redis")
        return False

    return True


def setup_ollama(config):
    """Setup Ollama container for testing."""
    container_name = f"{config['project_name']}_test_ollama"
    
    if check_container_running(container_name):
        print(f"Ollama container {container_name} already running.")
        return True

    print(f"Starting Ollama container on port {config['ollama_port']}...")
    run_command(
        f"docker run -d "
        f"--name {container_name} "
        f"-p {config['ollama_port']}:11434 "
        f"-v {config['project_name']}_ollama_models:/root/.ollama "
        f"--network {config['project_name']}_test_network "
        f"ollama/ollama:latest"
    )

    if not wait_for_ollama(f"http://localhost:{config['ollama_port']}"):
        print("Failed to start Ollama")
        return False

    # Pull a small model for testing
    print("Pulling test model (this may take a few minutes)...")
    try:
        response = requests.post(
            f"http://localhost:{config['ollama_port']}/api/pull",
            json={"name": "llama3.2:1b"},  # Small 1B parameter model
            timeout=300,
        )
        if response.status_code == 200:
            print("Test model pulled successfully!")
        else:
            print(f"Warning: Failed to pull model: {response.text}")
    except Exception as e:
        print(f"Warning: Failed to pull model: {e}")

    return True


def generate_test_data_with_ollama(config):
    """Generate test data using Ollama."""
    print("\nGenerating test data with Ollama...")
    ollama_url = f"http://localhost:{config['ollama_port']}"

    try:
        # Generate test API responses
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": "llama3.2:1b",
                "prompt": "Generate a JSON response for a user API with fields: id, name, email, role. Make it realistic.",
                "stream": False,
            },
            timeout=30,
        )

        if response.status_code == 200:
            generated = response.json()
            print(f"Generated API response: {generated.get('response', '')[:200]}...")

        # Generate test SQL data
        response = requests.post(
            f"{ollama_url}/api/generate",
            json={
                "model": "llama3.2:1b",
                "prompt": "Generate SQL INSERT statements for a users table with columns: id, name, email, created_at. Create 5 realistic users.",
                "stream": False,
            },
            timeout=30,
        )

        if response.status_code == 200:
            generated = response.json()
            print(f"Generated SQL data: {generated.get('response', '')[:200]}...")

    except Exception as e:
        print(f"Warning: Failed to generate test data: {e}")


def setup_environment_variables(config):
    """Setup environment variables for testing."""
    env_vars = {
        "PROJECT_NAME": config['project_name'],
        "PROJECT_HASH": str(config['project_hash']),
        "BASE_PORT": str(config['base_port']),
        "DB_HOST": "localhost",
        "DB_PORT": str(config['postgres_port']),
        "DB_NAME": f"{config['project_name']}_test",
        "DB_USER": "test_user",
        "DB_PASSWORD": "test_password",
        "REDIS_HOST": "localhost",
        "REDIS_PORT": str(config['redis_port']),
        "OLLAMA_HOST": "localhost",
        "OLLAMA_PORT": str(config['ollama_port']),
        "OLLAMA_BASE_URL": f"http://localhost:{config['ollama_port']}",
        "MYSQL_HOST": "localhost",
        "MYSQL_PORT": str(config['mysql_port']),
        "MYSQL_DATABASE": f"{config['project_name']}_test",
        "MYSQL_USER": f"{config['project_name']}_test",
        "MYSQL_PASSWORD": "test_password",
        "POSTGRES_TEST_URL": f"postgresql://test_user:test_password@localhost:{config['postgres_port']}/{config['project_name']}_test",
        "MYSQL_TEST_URL": f"mysql://{config['project_name']}_test:test_password@localhost:{config['mysql_port']}/{config['project_name']}_test",
        "REDIS_TEST_URL": f"redis://localhost:{config['redis_port']}",
        "OLLAMA_TEST_URL": f"http://localhost:{config['ollama_port']}",
        "TEST_DOCKER_AVAILABLE": "true",
    }

    print("\nEnvironment variables for testing:")
    for key, value in env_vars.items():
        print(f"export {key}={value}")
        os.environ[key] = value

    # Write to .env.test file
    env_file = Path(".env.test")
    with open(env_file, "w") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")
    print(f"\nEnvironment variables written to {env_file}")


def create_network(config):
    """Create Docker network for the project."""
    network_name = f"{config['project_name']}_test_network"
    result = run_command(f"docker network ls --filter name={network_name} --format '{{{{.Name}}}}'", check=False)
    if network_name not in result.stdout:
        print(f"Creating Docker network: {network_name}")
        run_command(f"docker network create {network_name}")
    return True


def create_port_lock_file(config):
    """Create or update the port lock file."""
    lock_file = Path("tests/.docker-ports.lock")
    
    content = f"""# Docker Port Allocation Lock File
# This file locks in the specific ports for this project's test infrastructure
# Generated by: python tests/utils/setup_local_docker.py
# Generated at: {time.strftime('%Y-%m-%d %H:%M:%S')}

PROJECT_NAME={config['project_name']}
PROJECT_HASH={config['project_hash']}
BASE_PORT={config['base_port']}

# Service Port Allocations
POSTGRES_PORT={config['postgres_port']}
REDIS_PORT={config['redis_port']}
OLLAMA_PORT={config['ollama_port']}
MYSQL_PORT={config['mysql_port']}
MONGODB_PORT={config['mongodb_port']}

# Docker Network
NETWORK_NAME={config['project_name']}_test_network

# Container Names
POSTGRES_CONTAINER={config['project_name']}_test_postgres
REDIS_CONTAINER={config['project_name']}_test_redis
OLLAMA_CONTAINER={config['project_name']}_test_ollama
MYSQL_CONTAINER={config['project_name']}_test_mysql
MONGODB_CONTAINER={config['project_name']}_test_mongodb

# Volume Names
POSTGRES_VOLUME={config['project_name']}_postgres_data
REDIS_VOLUME={config['project_name']}_redis_data
OLLAMA_VOLUME={config['project_name']}_ollama_models
MYSQL_VOLUME={config['project_name']}_mysql_data
MONGODB_VOLUME={config['project_name']}_mongodb_data

# ⚠️  DO NOT EDIT THIS FILE MANUALLY
# To change ports, use: python tests/utils/setup_local_docker.py --custom-base-port <PORT>
"""
    
    with open(lock_file, "w") as f:
        f.write(content)
    print(f"\nPort configuration locked in {lock_file}")


def main():
    """Main setup function."""
    parser = argparse.ArgumentParser(description="Setup Docker test infrastructure")
    parser.add_argument('--check-ports', action='store_true', help='Check port availability')
    parser.add_argument('--custom-base-port', type=int, help='Use custom base port')
    parser.add_argument('--cleanup', action='store_true', help='Clean up containers')
    args = parser.parse_args()
    
    # Get project configuration
    config = get_project_config()
    if args.custom_base_port:
        config['base_port'] = args.custom_base_port
        # Recalculate all ports
        config['postgres_port'] = config['base_port'] + 0
        config['redis_port'] = config['base_port'] + 1
        config['ollama_port'] = config['base_port'] + 2
        config['mysql_port'] = config['base_port'] + 3
        config['mongodb_port'] = config['base_port'] + 4
    
    print(f"=== Test Infrastructure Setup for {config['project_name']} ===")
    print(f"Base port: {config['base_port']} (range: {config['base_port']}-{config['base_port']+9})")
    
    if args.check_ports:
        conflicts = check_ports(config)
        if conflicts:
            print("\n⚠️  Port conflicts detected:")
            for service, port in conflicts:
                print(f"  - {service}: port {port} is already in use")
            print("\nSuggested alternatives:")
            print(f"  1. Stop conflicting containers")
            print(f"  2. Use --custom-base-port flag (e.g., --custom-base-port 7000)")
            return 1
        else:
            print("\n✅ All ports are available!")
            return 0
    
    if args.cleanup:
        print("\nCleaning up containers...")
        containers = [
            f"{config['project_name']}_test_postgres",
            f"{config['project_name']}_test_mysql",
            f"{config['project_name']}_test_redis",
            f"{config['project_name']}_test_ollama",
        ]
        for container in containers:
            run_command(f"docker stop {container}", check=False)
            run_command(f"docker rm {container}", check=False)
        print("Cleanup complete!")
        return 0

    if not check_docker():
        return 1

    # Create network
    create_network(config)

    # Setup all containers
    services = [
        ("PostgreSQL", setup_postgres),
        ("MySQL", setup_mysql),
        ("Redis", setup_redis),
        ("Ollama", setup_ollama),
    ]

    for service_name, setup_func in services:
        print(f"\n--- Setting up {service_name} ---")
        if not setup_func(config):
            print(f"Failed to setup {service_name}")
            return 1

    # Generate test data
    generate_test_data_with_ollama(config)

    # Setup environment variables
    setup_environment_variables(config)

    print("\n=== Setup Complete! ===")
    print("\nYou can now run all tests:")
    print("  source tests/.env.test")
    print("  pytest tests/unit/ -v")
    print("\nTo stop all test containers:")
    print(f"  python tests/utils/setup_local_docker.py --cleanup")
    
    # Create port lock file
    create_port_lock_file(config)
    
    # Register ports globally
    port_registry = Path.home() / ".docker_port_registry"
    with open(port_registry, "a") as f:
        f.write(f"{config['project_name']}: {config['base_port']}-{config['base_port']+9}\n")
    print(f"\nPorts registered in {port_registry}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
