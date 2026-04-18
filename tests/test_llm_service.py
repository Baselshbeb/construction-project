"""
Tests for LLMService._extract_json — verifies JSON extraction logic
without making any API calls.

These tests cover the various response formats Claude may return:
clean JSON, markdown-fenced JSON, JSON embedded in surrounding text,
nested braces, array responses, and invalid inputs.
"""

import pytest

from src.services.llm_service import LLMService


class TestExtractJson:
    """Tests for LLMService._extract_json static method."""

    def test_clean_json_parsed_correctly(self):
        """Clean JSON object is parsed directly."""
        text = '{"name": "Concrete", "quantity": 45.2}'
        result = LLMService._extract_json(text)
        assert result is not None
        assert result["name"] == "Concrete"
        assert result["quantity"] == 45.2

    def test_markdown_fenced_json_parsed_correctly(self):
        """JSON wrapped in markdown code fences is extracted."""
        text = '```json\n{"material": "Steel", "unit": "kg"}\n```'
        result = LLMService._extract_json(text)
        assert result is not None
        assert result["material"] == "Steel"
        assert result["unit"] == "kg"

    def test_markdown_fenced_no_language_tag(self):
        """JSON wrapped in plain ``` fences (no language tag) is extracted."""
        text = '```\n{"value": 100}\n```'
        result = LLMService._extract_json(text)
        assert result is not None
        assert result["value"] == 100

    def test_json_with_surrounding_text(self):
        """JSON embedded in surrounding text is extracted via balanced brace matching."""
        text = 'Here is the result:\n{"category": "frame", "confidence": 0.9}\nEnd of response.'
        result = LLMService._extract_json(text)
        assert result is not None
        assert result["category"] == "frame"
        assert result["confidence"] == 0.9

    def test_nested_braces(self):
        """JSON with nested objects is correctly extracted."""
        text = '{"outer": {"inner": {"deep": 42}}, "list": [1, 2, 3]}'
        result = LLMService._extract_json(text)
        assert result is not None
        assert result["outer"]["inner"]["deep"] == 42
        assert result["list"] == [1, 2, 3]

    def test_deeply_nested_braces_with_surrounding_text(self):
        """Deeply nested JSON with surrounding text uses balanced brace extraction."""
        text = 'Response: {"a": {"b": {"c": {"d": "value"}}}} done.'
        result = LLMService._extract_json(text)
        assert result is not None
        assert result["a"]["b"]["c"]["d"] == "value"

    def test_array_response_wrapped_as_items(self):
        """A JSON array response is wrapped in {"items": [...]}."""
        text = '[{"id": 1}, {"id": 2}, {"id": 3}]'
        result = LLMService._extract_json(text)
        assert result is not None
        assert "items" in result
        assert len(result["items"]) == 3
        assert result["items"][0]["id"] == 1

    def test_array_in_surrounding_text_wrapped(self):
        """Array embedded in text is extracted and wrapped."""
        text = 'The elements are: [{"type": "wall"}, {"type": "slab"}] as shown.'
        result = LLMService._extract_json(text)
        assert result is not None
        assert "items" in result
        assert len(result["items"]) == 2

    def test_invalid_text_returns_none(self):
        """Completely invalid text returns None."""
        result = LLMService._extract_json("This is not JSON at all.")
        assert result is None

    def test_empty_string_returns_none(self):
        """Empty string returns None."""
        result = LLMService._extract_json("")
        assert result is None

    def test_whitespace_only_returns_none(self):
        """Whitespace-only string returns None."""
        result = LLMService._extract_json("   \n\t  ")
        assert result is None

    def test_multiple_json_fragments_first_extracted(self):
        """When multiple JSON objects appear, the first valid one is extracted."""
        text = 'First: {"a": 1} Second: {"b": 2}'
        result = LLMService._extract_json(text)
        assert result is not None
        assert result["a"] == 1

    def test_json_with_string_containing_braces(self):
        """JSON with braces inside string values is handled correctly."""
        text = '{"message": "Use {x} for variables", "count": 5}'
        result = LLMService._extract_json(text)
        assert result is not None
        assert result["count"] == 5

    def test_json_with_unicode(self):
        """JSON with unicode characters is parsed correctly."""
        text = '{"name": "Beton C25/30", "description": "Yap\u0131 betonu"}'
        result = LLMService._extract_json(text)
        assert result is not None
        assert result["name"] == "Beton C25/30"

    def test_markdown_fence_with_extra_content(self):
        """Markdown fence with content before and after is handled."""
        text = 'Here is the JSON:\n```json\n{"key": "value"}\n```\nThat was the output.'
        result = LLMService._extract_json(text)
        assert result is not None
        assert result["key"] == "value"
