"""
LLM Service - wrapper around the Claude API for all AI interactions.

Coach Simple explains:
    "This is the translator between our system and Claude's brain.
    When an agent needs to ask Claude a question (like 'what materials
    does this wall need?'), it uses this service. The service handles
    all the technical details of talking to the API."

Usage:
    from src.services.llm_service import LLMService
    llm = LLMService()
    answer = await llm.ask("You are an expert.", "What materials does a wall need?")
"""

from __future__ import annotations

import json
from typing import Any, Optional

from anthropic import AsyncAnthropic

from src.config import settings
from src.utils.logger import get_logger

logger = get_logger("llm_service")


class LLMService:
    """Wrapper around the Anthropic Claude API.

    Provides simple methods for all AI interactions in the system.
    All agents use this service instead of calling the API directly.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.anthropic_api_key
        if not self.api_key:
            logger.warning("No ANTHROPIC_API_KEY set. LLM calls will fail.")
        self.client = AsyncAnthropic(api_key=self.api_key) if self.api_key else None
        self.default_model = settings.default_model
        self.expensive_model = settings.expensive_model

    async def ask(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        """Send a message to Claude and get a text response.

        Args:
            system_prompt: The system instructions (who Claude should be).
            user_message: The actual question or task.
            model: Model ID override. Defaults to settings.default_model.
            temperature: 0.0 = deterministic, 1.0 = creative.
            max_tokens: Maximum response length.

        Returns:
            Claude's text response.
        """
        if not self.client:
            raise RuntimeError(
                "LLM Service not initialized. Set ANTHROPIC_API_KEY in .env"
            )

        logger.debug(f"Sending request to {model or self.default_model}")

        response = await self.client.messages.create(
            model=model or self.default_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        text = response.content[0].text
        logger.debug(
            f"Response received: {response.usage.input_tokens} in, "
            f"{response.usage.output_tokens} out"
        )
        return text

    async def ask_json(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> dict[str, Any]:
        """Send a message to Claude and parse the response as JSON.

        The prompt is enhanced to request JSON output. Claude's response
        is parsed and returned as a Python dictionary.

        Args:
            system_prompt: The system instructions.
            user_message: The question/task (should request JSON output).
            model: Model override.
            temperature: Creativity level.
            max_tokens: Max response length.

        Returns:
            Parsed JSON as a dictionary.

        Raises:
            ValueError: If Claude's response cannot be parsed as JSON.
        """
        enhanced_system = (
            system_prompt
            + "\n\nIMPORTANT: Respond ONLY with valid JSON. "
            "No markdown, no explanation, just the JSON object."
        )

        text = await self.ask(
            system_prompt=enhanced_system,
            user_message=user_message,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Try to extract JSON from the response
        text = text.strip()

        # Remove markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Try to find JSON within the text
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            if json_start != -1 and json_end > json_start:
                try:
                    return json.loads(text[json_start:json_end])
                except json.JSONDecodeError:
                    pass

            # Try array
            json_start = text.find("[")
            json_end = text.rfind("]") + 1
            if json_start != -1 and json_end > json_start:
                try:
                    return {"items": json.loads(text[json_start:json_end])}
                except json.JSONDecodeError:
                    pass

            logger.error(f"Failed to parse JSON from response: {text[:200]}...")
            raise ValueError(f"Could not parse JSON from Claude's response: {text[:200]}")

    async def ask_with_context(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        """Send a multi-turn conversation to Claude.

        Useful when you need to provide examples or have a back-and-forth.

        Args:
            system_prompt: The system instructions.
            messages: List of {"role": "user"/"assistant", "content": "..."} dicts.
            model: Model override.
            temperature: Creativity level.
            max_tokens: Max response length.

        Returns:
            Claude's text response.
        """
        if not self.client:
            raise RuntimeError(
                "LLM Service not initialized. Set ANTHROPIC_API_KEY in .env"
            )

        response = await self.client.messages.create(
            model=model or self.default_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=messages,
        )

        return response.content[0].text
