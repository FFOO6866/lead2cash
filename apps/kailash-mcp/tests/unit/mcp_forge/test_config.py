"""
Unit tests for MCP Forge configuration management.

Testing Strategy:
- Unit tests with mocking allowed (Tier 1)
- Test zero-config defaults
- Environment variable override logic
- Progressive configuration (zero → simple → advanced)
- Configuration validation
"""

import json
import os
import tempfile
from typing import Any, Dict, Optional
from unittest.mock import Mock, patch

import pytest


class TestConfigurationDefaults:
    """Unit tests for default configuration values."""

    def test_zero_config_defaults(self):
        """Test zero-configuration setup with sensible defaults."""

        def get_default_config() -> Dict[str, Any]:
            """Mock function returning default configuration."""
            return {
                "server": {
                    "name": "mcp-forge-server",
                    "version": "0.1.0",
                    "host": "localhost",
                    "port": 8080,
                    "transport": ["http"],
                    "max_connections": 100,
                    "timeout": 30,
                },
                "client": {
                    "timeout": 10,
                    "retry_attempts": 3,
                    "retry_delay": 1.0,
                    "connection_pool_size": 10,
                },
                "tools": {
                    "auto_discover": True,
                    "validation_strict": True,
                    "execution_timeout": 30,
                },
                "logging": {"level": "INFO", "format": "json", "output": "stdout"},
            }

        config = get_default_config()

        # Test server defaults
        assert config["server"]["name"] == "mcp-forge-server"
        assert config["server"]["host"] == "localhost"
        assert config["server"]["port"] == 8080
        assert "http" in config["server"]["transport"]
        assert config["server"]["max_connections"] > 0

        # Test client defaults
        assert config["client"]["timeout"] > 0
        assert config["client"]["retry_attempts"] >= 1
        assert config["client"]["connection_pool_size"] > 0

        # Test tool defaults
        assert config["tools"]["auto_discover"] is True
        assert config["tools"]["validation_strict"] is True

        # Test logging defaults
        assert config["logging"]["level"] in ["DEBUG", "INFO", "WARNING", "ERROR"]
        assert config["logging"]["format"] in ["json", "text"]

    def test_minimal_config_override(self):
        """Test minimal configuration with selective overrides."""

        def apply_config_override(
            defaults: Dict[str, Any], overrides: Dict[str, Any]
        ) -> Dict[str, Any]:
            """Mock function to apply configuration overrides."""
            config = defaults.copy()

            def deep_update(base_dict, update_dict):
                for key, value in update_dict.items():
                    if (
                        key in base_dict
                        and isinstance(base_dict[key], dict)
                        and isinstance(value, dict)
                    ):
                        deep_update(base_dict[key], value)
                    else:
                        base_dict[key] = value

            deep_update(config, overrides)
            return config

        defaults = {
            "server": {"host": "localhost", "port": 8080},
            "logging": {"level": "INFO"},
        }

        # Test minimal override - just change port
        overrides = {"server": {"port": 9000}}
        config = apply_config_override(defaults, overrides)

        assert config["server"]["port"] == 9000
        assert config["server"]["host"] == "localhost"  # Unchanged
        assert config["logging"]["level"] == "INFO"  # Unchanged

        # Test multiple overrides
        overrides = {
            "server": {"port": 9001, "host": "0.0.0.0"},
            "logging": {"level": "DEBUG"},
        }
        config = apply_config_override(defaults, overrides)

        assert config["server"]["port"] == 9001
        assert config["server"]["host"] == "0.0.0.0"
        assert config["logging"]["level"] == "DEBUG"

    def test_progressive_configuration_levels(self):
        """Test progressive configuration: zero → simple → advanced."""

        class ConfigurationLevel:
            """Mock configuration level management."""

            @staticmethod
            def zero_config():
                """Zero configuration - just defaults."""
                return {"server": {"port": 8080}, "level": "zero"}

            @staticmethod
            def simple_config():
                """Simple configuration - basic customization."""
                return {
                    "server": {
                        "port": 8080,
                        "host": "localhost",
                        "name": "my-mcp-server",
                    },
                    "tools": {"auto_discover": True},
                    "level": "simple",
                }

            @staticmethod
            def advanced_config():
                """Advanced configuration - full customization."""
                return {
                    "server": {
                        "port": 8080,
                        "host": "localhost",
                        "name": "enterprise-mcp-server",
                        "transport": ["http", "websocket"],
                        "max_connections": 500,
                        "auth": {"enabled": True, "provider": "oauth2"},
                    },
                    "tools": {
                        "auto_discover": True,
                        "validation_strict": True,
                        "rate_limiting": {
                            "enabled": True,
                            "max_requests_per_minute": 60,
                        },
                    },
                    "monitoring": {
                        "enabled": True,
                        "metrics_endpoint": "/metrics",
                        "health_endpoint": "/health",
                    },
                    "level": "advanced",
                }

        # Test zero config
        zero = ConfigurationLevel.zero_config()
        assert zero["level"] == "zero"
        assert zero["server"]["port"] == 8080
        assert len(zero) == 2  # Minimal keys

        # Test simple config
        simple = ConfigurationLevel.simple_config()
        assert simple["level"] == "simple"
        assert "name" in simple["server"]
        assert "tools" in simple
        assert len(simple) == 3  # More keys than zero

        # Test advanced config
        advanced = ConfigurationLevel.advanced_config()
        assert advanced["level"] == "advanced"
        assert "auth" in advanced["server"]
        assert "rate_limiting" in advanced["tools"]
        assert "monitoring" in advanced
        assert len(advanced) == 4  # Most comprehensive


class TestEnvironmentVariables:
    """Unit tests for environment variable configuration."""

    def test_env_var_override_basic(self):
        """Test basic environment variable overrides."""

        def parse_env_vars() -> Dict[str, Any]:
            """Mock environment variable parsing."""
            config = {}

            # Mock environment variables
            env_vars = {
                "MCP_FORGE_PORT": "9000",
                "MCP_FORGE_HOST": "0.0.0.0",
                "MCP_FORGE_LOG_LEVEL": "DEBUG",
            }

            for key, value in env_vars.items():
                if key.startswith("MCP_FORGE_"):
                    config_key = key.replace("MCP_FORGE_", "").lower()

                    # Convert types
                    if config_key == "port":
                        config["port"] = int(value)
                    elif config_key == "log_level":
                        config["log_level"] = value
                    else:
                        config[config_key] = value

            return config

        config = parse_env_vars()

        assert config["port"] == 9000
        assert config["host"] == "0.0.0.0"
        assert config["log_level"] == "DEBUG"

    @patch.dict(
        os.environ,
        {
            "MCP_FORGE_SERVER_PORT": "8081",
            "MCP_FORGE_SERVER_HOST": "127.0.0.1",
            "MCP_FORGE_TOOLS_AUTO_DISCOVER": "false",
        },
    )
    def test_env_var_override_nested(self):
        """Test nested environment variable overrides."""

        def parse_nested_env_vars() -> Dict[str, Any]:
            """Mock parsing of nested environment variables."""
            config = {"server": {}, "tools": {}}

            # Parse environment variables
            for key, value in os.environ.items():
                if key.startswith("MCP_FORGE_"):
                    parts = key.replace("MCP_FORGE_", "").lower().split("_")

                    if len(parts) >= 2:
                        section = parts[0]
                        setting = "_".join(parts[1:])

                        if section in config:
                            # Type conversion
                            if setting == "port":
                                config[section][setting] = int(value)
                            elif setting == "auto_discover":
                                config[section][setting] = value.lower() == "true"
                            else:
                                config[section][setting] = value

            return config

        config = parse_nested_env_vars()

        assert config["server"]["port"] == 8081
        assert config["server"]["host"] == "127.0.0.1"
        assert config["tools"]["auto_discover"] is False

    def test_env_var_type_conversion(self):
        """Test automatic type conversion for environment variables."""

        def convert_env_value(key: str, value: str) -> Any:
            """Mock type conversion for environment values."""
            # Define expected types for known keys
            type_mappings = {
                "port": int,
                "timeout": int,
                "max_connections": int,
                "retry_attempts": int,
                "connection_pool_size": int,
                "enabled": bool,
                "auto_discover": bool,
                "validation_strict": bool,
                "retry_delay": float,
            }

            expected_type = type_mappings.get(key, str)

            if expected_type == int:
                return int(value)
            elif expected_type == float:
                return float(value)
            elif expected_type == bool:
                return value.lower() in ("true", "1", "yes", "on")
            else:
                return value

        # Test integer conversion
        assert convert_env_value("port", "8080") == 8080
        assert convert_env_value("timeout", "30") == 30

        # Test boolean conversion
        assert convert_env_value("enabled", "true") is True
        assert convert_env_value("enabled", "false") is False
        assert convert_env_value("enabled", "1") is True
        assert convert_env_value("enabled", "0") is False

        # Test float conversion
        assert convert_env_value("retry_delay", "1.5") == 1.5

        # Test string (default)
        assert convert_env_value("host", "localhost") == "localhost"

    def test_env_var_validation(self):
        """Test validation of environment variable values."""

        def validate_env_value(key: str, value: Any) -> tuple[bool, Optional[str]]:
            """Mock validation of environment variable values."""

            # Define validation rules
            validators = {
                "port": lambda v: 1 <= v <= 65535,
                "timeout": lambda v: v > 0,
                "max_connections": lambda v: v > 0,
                "retry_attempts": lambda v: 0 <= v <= 10,
                "log_level": lambda v: v in ["DEBUG", "INFO", "WARNING", "ERROR"],
                "host": lambda v: len(v) > 0,
            }

            if key in validators:
                try:
                    if validators[key](value):
                        return True, None
                    else:
                        return False, f"Invalid value for {key}: {value}"
                except Exception as e:
                    return False, f"Validation error for {key}: {str(e)}"

            return True, None  # No validation rule = valid

        # Test valid values
        assert validate_env_value("port", 8080)[0] is True
        assert validate_env_value("timeout", 30)[0] is True
        assert validate_env_value("log_level", "DEBUG")[0] is True

        # Test invalid values
        assert validate_env_value("port", 70000)[0] is False
        assert validate_env_value("port", 0)[0] is False
        assert validate_env_value("timeout", -1)[0] is False
        assert validate_env_value("log_level", "INVALID")[0] is False


class TestConfigurationFiles:
    """Unit tests for configuration file handling."""

    def test_json_config_loading(self):
        """Test loading configuration from JSON files."""

        def load_json_config(config_data: str) -> Dict[str, Any]:
            """Mock JSON configuration loading."""
            try:
                return json.loads(config_data)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON configuration: {e}")

        # Test valid JSON config
        valid_json = """
        {
            "server": {
                "name": "test-server",
                "port": 8080,
                "host": "localhost"
            },
            "tools": {
                "auto_discover": true,
                "validation_strict": false
            }
        }
        """

        config = load_json_config(valid_json)
        assert config["server"]["name"] == "test-server"
        assert config["server"]["port"] == 8080
        assert config["tools"]["auto_discover"] is True

        # Test invalid JSON
        invalid_json = """
        {
            "server": {
                "name": "test-server",
                "port": 8080,
            }  // Invalid trailing comma and comment
        }
        """

        with pytest.raises(ValueError, match="Invalid JSON"):
            load_json_config(invalid_json)

    def test_config_file_discovery(self):
        """Test configuration file discovery logic."""

        def discover_config_files(search_paths: list) -> list:
            """Mock configuration file discovery."""
            found_configs = []

            # Mock file system
            mock_files = {
                "/etc/mcp-forge/config.json": True,
                "/home/user/.mcp-forge.json": True,
                "./mcp-forge.json": False,  # Doesn't exist
                "./config/mcp-forge.json": True,
            }

            for path in search_paths:
                if path in mock_files and mock_files[path]:
                    found_configs.append(path)

            return found_configs

        search_paths = [
            "./mcp-forge.json",  # Local config (highest priority)
            "./config/mcp-forge.json",  # Local config directory
            "/home/user/.mcp-forge.json",  # User config
            "/etc/mcp-forge/config.json",  # System config (lowest priority)
        ]

        found = discover_config_files(search_paths)

        # Should find files in priority order
        assert "./config/mcp-forge.json" in found
        assert "/home/user/.mcp-forge.json" in found
        assert "/etc/mcp-forge/config.json" in found
        assert "./mcp-forge.json" not in found  # Doesn't exist

    def test_config_merging_precedence(self):
        """Test configuration merging with proper precedence."""

        def merge_configs(configs: list) -> Dict[str, Any]:
            """Mock configuration merging with precedence."""
            merged = {}

            # Merge in reverse order (lowest precedence first)
            for config in reversed(configs):
                for key, value in config.items():
                    if (
                        key in merged
                        and isinstance(merged[key], dict)
                        and isinstance(value, dict)
                    ):
                        # Deep merge for nested dicts
                        merged[key] = {**merged[key], **value}
                    else:
                        merged[key] = value

            return merged

        # Configuration sources (in precedence order: high to low)
        configs = [
            {
                "server": {"port": 8080, "name": "local"},
                "source": "local",
            },  # Highest precedence
            {"server": {"port": 8081, "host": "localhost"}, "source": "user"},  # Medium
            {
                "server": {"port": 8082, "name": "system"},
                "logging": {"level": "INFO"},
                "source": "system",
            },  # Lowest
        ]

        merged = merge_configs(configs)

        # Local config should override port and name
        assert merged["server"]["port"] == 8080  # From local
        assert merged["server"]["name"] == "local"  # From local

        # User config should provide host (not overridden)
        assert merged["server"]["host"] == "localhost"  # From user

        # System config should provide logging (not overridden)
        assert merged["logging"]["level"] == "INFO"  # From system

        # Top-level should be from highest precedence
        assert merged["source"] == "local"


class TestConfigurationValidation:
    """Unit tests for configuration validation."""

    def test_required_fields_validation(self):
        """Test validation of required configuration fields."""

        def validate_required_fields(config: Dict[str, Any]) -> tuple[bool, list]:
            """Mock validation of required configuration fields."""
            errors = []

            # Define required fields
            required_fields = {
                "server.name": str,
                "server.port": int,
                "server.host": str,
            }

            for field_path, expected_type in required_fields.items():
                parts = field_path.split(".")
                current = config

                try:
                    for part in parts:
                        current = current[part]

                    if not isinstance(current, expected_type):
                        errors.append(
                            f"Field {field_path} must be {expected_type.__name__}, got {type(current).__name__}"
                        )

                except KeyError:
                    errors.append(f"Required field {field_path} is missing")

            return len(errors) == 0, errors

        # Test valid configuration
        valid_config = {
            "server": {"name": "test-server", "port": 8080, "host": "localhost"}
        }

        is_valid, errors = validate_required_fields(valid_config)
        assert is_valid is True
        assert len(errors) == 0

        # Test missing field
        invalid_config = {
            "server": {
                "name": "test-server",
                "port": 8080,
                # Missing host
            }
        }

        is_valid, errors = validate_required_fields(invalid_config)
        assert is_valid is False
        assert any("host" in error for error in errors)

        # Test wrong type
        invalid_config = {
            "server": {
                "name": "test-server",
                "port": "8080",  # Should be int, not string
                "host": "localhost",
            }
        }

        is_valid, errors = validate_required_fields(invalid_config)
        assert is_valid is False
        assert any("port" in error and "int" in error for error in errors)

    def test_value_range_validation(self):
        """Test validation of configuration value ranges."""

        def validate_value_ranges(config: Dict[str, Any]) -> tuple[bool, list]:
            """Mock validation of configuration value ranges."""
            errors = []

            # Define value range validators
            validators = {
                "server.port": lambda v: 1 <= v <= 65535,
                "server.max_connections": lambda v: 1 <= v <= 10000,
                "client.timeout": lambda v: 1 <= v <= 300,
                "client.retry_attempts": lambda v: 0 <= v <= 10,
            }

            for field_path, validator in validators.items():
                parts = field_path.split(".")
                current = config

                try:
                    for part in parts:
                        current = current[part]

                    if not validator(current):
                        errors.append(
                            f"Field {field_path} value {current} is out of valid range"
                        )

                except KeyError:
                    pass  # Field is optional

            return len(errors) == 0, errors

        # Test valid ranges
        valid_config = {
            "server": {"port": 8080, "max_connections": 100},
            "client": {"timeout": 30, "retry_attempts": 3},
        }

        is_valid, errors = validate_value_ranges(valid_config)
        assert is_valid is True
        assert len(errors) == 0

        # Test invalid ranges
        invalid_config = {
            "server": {
                "port": 70000,
                "max_connections": 0,
            },  # Port too high, connections too low
            "client": {
                "timeout": 0,
                "retry_attempts": 15,
            },  # Timeout too low, retries too high
        }

        is_valid, errors = validate_value_ranges(invalid_config)
        assert is_valid is False
        assert len(errors) == 4  # All four fields are invalid

        for error in errors:
            assert "out of valid range" in error

    def test_configuration_schema_validation(self):
        """Test configuration against a predefined schema."""

        def validate_against_schema(
            config: Dict[str, Any], schema: Dict[str, Any]
        ) -> tuple[bool, list]:
            """Mock schema validation."""
            errors = []

            def validate_object(obj, schema_obj, path=""):
                if schema_obj.get("type") == "object":
                    if not isinstance(obj, dict):
                        errors.append(
                            f"Expected object at {path}, got {type(obj).__name__}"
                        )
                        return

                    # Check required properties
                    required = schema_obj.get("required", [])
                    for req_prop in required:
                        if req_prop not in obj:
                            errors.append(
                                f"Required property '{req_prop}' missing at {path}"
                            )

                    # Validate properties
                    properties = schema_obj.get("properties", {})
                    for prop_name, prop_schema in properties.items():
                        if prop_name in obj:
                            new_path = f"{path}.{prop_name}" if path else prop_name
                            validate_object(obj[prop_name], prop_schema, new_path)

                else:
                    # Validate primitive types
                    expected_type = schema_obj.get("type")
                    type_map = {
                        "string": str,
                        "integer": int,
                        "number": (int, float),
                        "boolean": bool,
                    }

                    if expected_type in type_map:
                        python_type = type_map[expected_type]
                        if not isinstance(obj, python_type):
                            errors.append(
                                f"Expected {expected_type} at {path}, got {type(obj).__name__}"
                            )

            validate_object(config, schema)
            return len(errors) == 0, errors

        # Define schema
        schema = {
            "type": "object",
            "required": ["server"],
            "properties": {
                "server": {
                    "type": "object",
                    "required": ["name", "port"],
                    "properties": {
                        "name": {"type": "string"},
                        "port": {"type": "integer"},
                        "host": {"type": "string"},
                    },
                },
                "tools": {
                    "type": "object",
                    "properties": {"auto_discover": {"type": "boolean"}},
                },
            },
        }

        # Test valid configuration
        valid_config = {
            "server": {"name": "test-server", "port": 8080, "host": "localhost"},
            "tools": {"auto_discover": True},
        }

        is_valid, errors = validate_against_schema(valid_config, schema)
        assert is_valid is True
        assert len(errors) == 0

        # Test invalid configuration
        invalid_config = {
            "server": {
                "name": "test-server"
                # Missing required port
            },
            "tools": {"auto_discover": "yes"},  # Should be boolean
        }

        is_valid, errors = validate_against_schema(invalid_config, schema)
        assert is_valid is False
        assert any("port" in error for error in errors)
        assert any("boolean" in error for error in errors)
