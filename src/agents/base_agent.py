"""
Base Agent - the parent class that all agents inherit from.

Coach Simple explains:
    "Think of this like a job description template. Every worker on the
    construction site (Parser, Calculator, Mapper, etc.) has the same basic
    rules: they get a clipboard (state), do their job, log what they did,
    and pass the clipboard to the next worker. This base class defines
    those common rules."

All agents in src/agents/ must inherit from BaseAgent and implement execute().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from src.utils.logger import get_logger


class BaseAgent(ABC):
    """Base class for all agents in the Metraj system.

    Every agent:
    1. Has a name and description
    2. Receives a ProjectState dict
    3. Does its work (execute method)
    4. Returns the updated ProjectState dict
    5. Logs its actions
    """

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.logger = get_logger(f"agent.{name}")

    @abstractmethod
    async def execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's task and return updated state.

        Args:
            state: The current ProjectState as a dictionary.

        Returns:
            The updated ProjectState dictionary with this agent's results added.
        """

    def log(self, message: str) -> None:
        """Log a message with the agent's name prefix."""
        self.logger.info(f"[{self.name}] {message}")

    def log_error(self, message: str) -> None:
        """Log an error with the agent's name prefix."""
        self.logger.error(f"[{self.name}] {message}")

    def log_warning(self, message: str) -> None:
        """Log a warning with the agent's name prefix."""
        self.logger.warning(f"[{self.name}] {message}")

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}')>"
