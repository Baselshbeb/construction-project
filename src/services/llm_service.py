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

        # Use structured system message with cache_control for prompt caching.
        # Repeated calls with the same system prompt (e.g. material mapper
        # batches) get a ~90% discount on cached input tokens.
        response = await self.client.messages.create(
            model=model or self.default_model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=[{
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_message}],
        )

        text = response.content[0].text
        usage = response.usage
        cache_info = ""
        if hasattr(usage, "cache_creation_input_tokens"):
            cache_info = (
                f", cache_create={usage.cache_creation_input_tokens}, "
                f"cache_read={usage.cache_read_input_tokens}"
            )
        logger.debug(
            f"Response received: {usage.input_tokens} in, "
            f"{usage.output_tokens} out{cache_info}"
        )
        return text

    async def ask_json(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        max_retries: int = 2,
    ) -> dict[str, Any]:
        """Send a message to Claude and parse the response as JSON.

        The prompt is enhanced to request JSON output. Claude's response
        is parsed and returned as a Python dictionary. On parse failure,
        retries up to ``max_retries`` times with explicit error feedback.

        Args:
            system_prompt: The system instructions.
            user_message: The question/task (should request JSON output).
            model: Model override.
            temperature: Creativity level.
            max_tokens: Max response length.
            max_retries: Number of retries on JSON parse failure.

        Returns:
            Parsed JSON as a dictionary.

        Raises:
            ValueError: If Claude's response cannot be parsed as JSON
                        after all retries.
        """
        enhanced_system = (
            system_prompt
            + "\n\nIMPORTANT: Respond ONLY with valid JSON. "
            "No markdown, no explanation, just the JSON object."
        )

        last_error = ""
        for attempt in range(1 + max_retries):
            # On retry, append the parse error so Claude can self-correct
            if attempt == 0:
                msg = user_message
            else:
                msg = (
                    f"{user_message}\n\n"
                    f"[RETRY {attempt}/{max_retries}] Your previous response "
                    f"was not valid JSON. Error: {last_error}\n"
                    "Please respond with ONLY a valid JSON object."
                )

            text = await self.ask(
                system_prompt=enhanced_system,
                user_message=msg,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            parsed = self._extract_json(text)
            if parsed is not None:
                return parsed

            last_error = f"Could not parse JSON from: {text[:150]}..."
            logger.warning(f"JSON parse failed (attempt {attempt + 1}): {last_error}")

        logger.error(f"Failed to parse JSON after {1 + max_retries} attempts")
        raise ValueError(f"Could not parse JSON from Claude after retries: {last_error}")

    @staticmethod
    def _extract_json(text: str) -> Optional[dict[str, Any]]:
        """Try to extract a JSON object from Claude's response text.

        Uses a careful approach: first try direct parse, then strip markdown
        fences, then find the outermost balanced braces.
        """
        text = text.strip()

        # Remove markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Only remove lines that are purely code fence markers
            cleaned = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("```"):
                    continue
                cleaned.append(line)
            text = "\n".join(cleaned).strip()

        # Attempt 1: direct parse
        try:
            result = json.loads(text)
            if isinstance(result, dict):
                return result
            if isinstance(result, list):
                return {"items": result}
        except json.JSONDecodeError:
            pass

        # Attempt 2: find outermost balanced braces
        brace_start = text.find("{")
        if brace_start != -1:
            depth = 0
            for i in range(brace_start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[brace_start:i + 1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            break

        # Attempt 3: find outermost array (wrap as dict)
        bracket_start = text.find("[")
        if bracket_start != -1:
            depth = 0
            for i in range(bracket_start, len(text)):
                if text[i] == "[":
                    depth += 1
                elif text[i] == "]":
                    depth -= 1
                    if depth == 0:
                        candidate = text[bracket_start:i + 1]
                        try:
                            return {"items": json.loads(candidate)}
                        except json.JSONDecodeError:
                            break

        return None

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
            system=[{
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=messages,
        )

        return response.content[0].text
