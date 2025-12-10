"""Configuration loader for AI Executive Assistant scripts.

This module provides configuration management for the genericized scripts,
loading settings from config.yaml and providing path resolution utilities.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class Config:
    """Configuration manager for AI Executive Assistant."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration.

        Args:
            config_path: Path to config.yaml. If None, looks in current directory
                        and parent directories.
        """
        if config_path is None:
            config_path = self._find_config()

        if not config_path or not os.path.exists(config_path):
            raise FileNotFoundError(
                "config.yaml not found. Please create one based on config.example.yaml"
            )

        with open(config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f) or {}

    def _find_config(self) -> Optional[str]:
        """Find config.yaml in current or parent directories."""
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            config_file = parent / "config.yaml"
            if config_file.exists():
                return str(config_file)
        return None

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key.

        Supports dot notation for nested keys, e.g., 'paths.vault_root'
        """
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default

    @property
    def vault_path(self) -> str:
        """Get vault root path."""
        path = self.get('paths.vault_root')
        if not path:
            raise ValueError("paths.vault_root not configured")
        return os.path.expanduser(path)

    @property
    def meetings_folder(self) -> str:
        """Get meetings folder path (relative to vault root)."""
        return self.get('paths.meetings_folder', 'Meetings')

    @property
    def people_folder(self) -> str:
        """Get people folder path (relative to vault root)."""
        return self.get('paths.people_folder', 'People')

    @property
    def reference_file(self) -> str:
        """Get reference file path (relative to vault root)."""
        return self.get('paths.reference_file', 'Templates/Tag Reference.md')

    @property
    def log_file(self) -> Optional[str]:
        """Get log file path (relative to vault root). Returns None if not configured."""
        return self.get('paths.log_file')

    @property
    def ai_provider(self) -> str:
        """Get AI provider name."""
        return self.get('ai.provider', 'vertex')

    @property
    def ai_model(self) -> str:
        """Get AI model name."""
        return self.get('ai.model', 'gemini-2.5-pro')

    @property
    def embedding_provider(self) -> str:
        """Get embedding provider name."""
        return self.get('ai.embedding_provider', self.ai_provider)

    @property
    def embedding_model(self) -> Optional[str]:
        """Get embedding model name."""
        return self.get('ai.embedding_model')

    def get_full_path(self, relative_path: str) -> str:
        """Convert vault-relative path to absolute path."""
        return os.path.join(self.vault_path, relative_path)


# Global config instance
_config: Optional[Config] = None


def get_config(config_path: Optional[str] = None) -> Config:
    """Get or create global config instance.

    Args:
        config_path: Path to config.yaml. Only used on first call.

    Returns:
        Config instance
    """
    global _config
    if _config is None:
        _config = Config(config_path)
    return _config


def reset_config():
    """Reset global config instance. Mainly for testing."""
    global _config
    _config = None
