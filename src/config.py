"""
Application configuration - loads settings from environment variables.

Coach Simple explains:
    "This is like the control panel for the whole system. It reads your
    secret API keys from the .env file (so they never get shared publicly)
    and sets up all the settings the system needs to run."

Usage:
    from src.config import settings
    print(settings.anthropic_api_key)
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings

# Load .env file from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- API Keys ---
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key for Claude",
    )

    # --- Model Settings ---
    default_model: str = Field(
        default="claude-sonnet-4-5-20250929",
        description="Default Claude model for most agent tasks",
    )
    expensive_model: str = Field(
        default="claude-opus-4-5-20250929",
        description="Powerful model for complex reasoning tasks",
    )

    # --- Application Settings ---
    log_level: str = Field(default="INFO")
    debug: bool = Field(default=False)

    # --- Paths ---
    project_root: Path = Field(default=PROJECT_ROOT)
    data_dir: Path = Field(default=PROJECT_ROOT / "src" / "data")
    output_dir: Path = Field(default=PROJECT_ROOT / "output")
    fixtures_dir: Path = Field(default=PROJECT_ROOT / "tests" / "fixtures")

    model_config = {
        "env_prefix": "",
        "case_sensitive": False,
        "env_file": ".env",
        "extra": "ignore",
    }


# Singleton settings instance
settings = Settings()
