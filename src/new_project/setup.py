"""
Setup configuration for the app template.

IMPORTANT: Update this file for your specific app!
- Change 'name' to your app name
- Update 'description' and 'author'
- Add app-specific dependencies
- Update console_scripts entry point
"""

from setuptools import setup, find_packages

# CHANGE THESE VALUES FOR YOUR APP
APP_NAME = "my-template-app"  # CHANGE THIS
APP_VERSION = "0.1.0"
APP_DESCRIPTION = "Template app for client projects"  # CHANGE THIS
APP_AUTHOR = "Your Team"  # CHANGE THIS
APP_EMAIL = "team@yourcompany.com"  # CHANGE THIS

setup(
    name=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    author=APP_AUTHOR,
    author_email=APP_EMAIL,
    packages=find_packages(),
    python_requires=">=3.9",
    
    # Core dependencies
    install_requires=[
        # Kailash SDK (installed from PyPI)
        "kailash>=0.3.0",
        
        # Web framework
        "fastapi>=0.104.0",
        "uvicorn[standard]>=0.24.0",
        
        # CLI framework
        "click>=8.1.0",
        "rich>=13.0.0",
        
        # Database
        "sqlalchemy>=2.0.0",
        "alembic>=1.12.0",
        
        # Data handling
        "pandas>=2.0.0",
        "pydantic>=2.4.0",
        
        # Utilities
        "python-dotenv>=1.0.0",
        "structlog>=23.1.0",
        
        # ADD YOUR APP-SPECIFIC DEPENDENCIES HERE
        # "requests>=2.31.0",  # For API calls
        # "redis>=5.0.0",      # For caching
        # "celery>=5.3.0",     # For background tasks
    ],
    
    # Development dependencies
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "black>=23.7.0",
            "isort>=5.12.0",
            "flake8>=6.0.0",
            "mypy>=1.5.0",
        ],
        "test": [
            "pytest>=7.4.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.1.0",
            "httpx>=0.24.0",  # For testing FastAPI
        ],
        "docs": [
            "mkdocs>=1.5.0",
            "mkdocs-material>=9.2.0",
        ],
    },
    
    # Command-line interface
    entry_points={
        "console_scripts": [
            # CHANGE 'my-app' to your app's CLI command name
            "my-app=cli.main:cli",  # CHANGE THIS
        ],
    },
    
    # Package metadata
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Framework :: FastAPI",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
    
    # Include additional files
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt", "*.yml", "*.yaml", "*.json"],
    },
    
    # Project URLs
    project_urls={
        "Documentation": f"https://github.com/yourorg/{APP_NAME}",
        "Source": f"https://github.com/yourorg/{APP_NAME}",
        "Tracker": f"https://github.com/yourorg/{APP_NAME}/issues",
    },
)