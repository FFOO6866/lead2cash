"""Docker infrastructure configuration with dynamic port allocation.

This module provides configuration for test infrastructure services.
Ports are dynamically allocated based on project name to prevent conflicts.
"""

import os
from pathlib import Path


def load_port_config():
    """Load port configuration from .docker-ports.lock file if it exists."""
    lock_file = Path("tests/.docker-ports.lock")
    config = {}
    
    if lock_file.exists():
        with open(lock_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    config[key] = value
    
    # Calculate defaults if lock file doesn't exist
    if not config:
        project_name = os.path.basename(os.getcwd())
        project_hash = abs(hash(project_name)) % 1000
        base_port = 5000 + project_hash * 10
        
        config = {
            "PROJECT_NAME": project_name,
            "BASE_PORT": str(base_port),
            "POSTGRES_PORT": str(base_port + 0),
            "REDIS_PORT": str(base_port + 1),
            "OLLAMA_PORT": str(base_port + 2),
            "MYSQL_PORT": str(base_port + 3),
            "MONGODB_PORT": str(base_port + 4),
        }
    
    return config


# Load port configuration
PORT_CONFIG = load_port_config()
PROJECT_NAME = PORT_CONFIG.get("PROJECT_NAME", os.path.basename(os.getcwd()))

# PostgreSQL configuration
DATABASE_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", PORT_CONFIG.get("POSTGRES_PORT", "5432"))),
    "database": os.getenv("DB_NAME", f"{PROJECT_NAME}_test"),
    "user": os.getenv("DB_USER", "test_user"),
    "password": os.getenv("DB_PASSWORD", "test_password"),
}

# Redis configuration
REDIS_CONFIG = {
    "host": os.getenv("REDIS_HOST", "localhost"),
    "port": int(os.getenv("REDIS_PORT", PORT_CONFIG.get("REDIS_PORT", "6379"))),
}

# Ollama configuration
OLLAMA_CONFIG = {
    "host": os.getenv("OLLAMA_HOST", "localhost"),
    "port": int(os.getenv("OLLAMA_PORT", PORT_CONFIG.get("OLLAMA_PORT", "11434"))),
    "base_url": os.getenv("OLLAMA_BASE_URL", f"http://localhost:{PORT_CONFIG.get('OLLAMA_PORT', '11434')}"),
    "model": os.getenv("OLLAMA_MODEL", "llama3.2:1b"),
}

# MySQL configuration
MYSQL_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", PORT_CONFIG.get("MYSQL_PORT", "3306"))),
    "database": os.getenv("MYSQL_DATABASE", f"{PROJECT_NAME}_test"),
    "user": os.getenv("MYSQL_USER", f"{PROJECT_NAME}_test"),
    "password": os.getenv("MYSQL_PASSWORD", "test_password"),
}

# MongoDB configuration
MONGODB_CONFIG = {
    "host": os.getenv("MONGO_HOST", "localhost"),
    "port": int(os.getenv("MONGO_PORT", PORT_CONFIG.get("MONGODB_PORT", "27017"))),
    "username": os.getenv("MONGO_USER", PROJECT_NAME),
    "password": os.getenv("MONGO_PASSWORD", f"{PROJECT_NAME}123"),
}

# Optional services (not in base Docker setup)
KAFKA_CONFIG = {
    "bootstrap_servers": os.getenv("KAFKA_SERVERS", "localhost:9092"),
}

OAUTH2_CONFIG = {
    "host": os.getenv("OAUTH2_HOST", "http://localhost:8080"),
}

QDRANT_CONFIG = {
    "host": os.getenv("QDRANT_HOST", "localhost"),
    "port": int(os.getenv("QDRANT_PORT", "6333")),
}

# Vector database configuration (uses PostgreSQL with pgvector)
VECTOR_DB_CONFIG = {
    "connection_string": None,  # Will be set to PostgreSQL connection string
    "embedding_dimension": 384,  # For all-MiniLM-L6-v2
}


# Connection string helpers
def get_postgres_connection_string(database=None):
    """Get PostgreSQL connection string."""
    db = database or DATABASE_CONFIG["database"]
    return (
        f"postgresql://{DATABASE_CONFIG['user']}:{DATABASE_CONFIG['password']}"
        f"@{DATABASE_CONFIG['host']}:{DATABASE_CONFIG['port']}/{db}"
    )


def get_redis_url():
    """Get Redis URL."""
    return f"redis://{REDIS_CONFIG['host']}:{REDIS_CONFIG['port']}"


def get_mysql_connection_string(database=None):
    """Get MySQL connection string."""
    db = database or MYSQL_CONFIG["database"]
    return (
        f"mysql://{MYSQL_CONFIG['user']}:{MYSQL_CONFIG['password']}"
        f"@{MYSQL_CONFIG['host']}:{MYSQL_CONFIG['port']}/{db}"
    )


def get_mongodb_connection_string(database=None):
    """Get MongoDB connection string."""
    db = database or PROJECT_NAME
    return (
        f"mongodb://{MONGODB_CONFIG['username']}:{MONGODB_CONFIG['password']}"
        f"@{MONGODB_CONFIG['host']}:{MONGODB_CONFIG['port']}/{db}"
    )


# Update vector DB config with PostgreSQL connection
VECTOR_DB_CONFIG["connection_string"] = get_postgres_connection_string()


# Test data
TEST_USERS = [
    {"id": 1, "name": "User 1", "email": "user1@test.com", "active": True},
    {"id": 2, "name": "User 2", "email": "user2@test.com", "active": True},
    {"id": 3, "name": "User 3", "email": "user3@test.com", "active": False},
]

TEST_EMBEDDINGS = [
    {
        "id": 1,
        "content": "Kailash SDK is a powerful workflow automation tool",
        "metadata": {"category": "documentation"},
    },
    {
        "id": 2,
        "content": "PostgreSQL with pgvector enables similarity search",
        "metadata": {"category": "database"},
    },
    {
        "id": 3,
        "content": "Async operations improve performance significantly",
        "metadata": {"category": "performance"},
    },
]


async def ensure_docker_services():
    """Ensure Docker services are available."""
    import asyncio
    
    try:
        # Check PostgreSQL
        import asyncpg
        
        conn = await asyncpg.connect(get_postgres_connection_string())
        await conn.close()
        
        # Check Redis
        import redis
        
        r = redis.Redis(**REDIS_CONFIG)
        r.ping()
        
        # Check MySQL (optional)
        try:
            import pymysql
            
            conn = pymysql.connect(
                host=MYSQL_CONFIG["host"],
                port=MYSQL_CONFIG["port"],
                user=MYSQL_CONFIG["user"],
                password=MYSQL_CONFIG["password"],
                database=MYSQL_CONFIG["database"],
            )
            conn.close()
        except:
            pass  # MySQL is optional
        
        # Check Ollama
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{OLLAMA_CONFIG['base_url']}/api/tags",
                timeout=5.0,
            )
            if response.status_code != 200:
                return False
        
        return True
    except Exception as e:
        print(f"Docker services check failed: {e}")
        return False


# Legacy compatibility - map old config names
TEST_DB_CONFIG = {
    "postgresql": DATABASE_CONFIG,
    "connection_string": get_postgres_connection_string(),
}

# Container names based on project
CONTAINER_NAMES = {
    "postgres": f"{PROJECT_NAME}_test_postgres",
    "redis": f"{PROJECT_NAME}_test_redis",
    "ollama": f"{PROJECT_NAME}_test_ollama",
    "mysql": f"{PROJECT_NAME}_test_mysql",
    "mongodb": f"{PROJECT_NAME}_test_mongodb",
}