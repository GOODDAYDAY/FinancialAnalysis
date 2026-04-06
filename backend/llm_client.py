"""
DeepSeek LLM client with structured output parsing and retry logic.

Handles DeepSeek's common failure modes:
- Markdown code fence wrapping
- Invalid JSON
- Missing/extra fields
- Truncated output
"""

import json
import re
import logging
from typing import TypeVar, Type

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from backend.config import settings

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
    return _client


def call_llm(
    user_prompt: str,
    system_prompt: str = "",
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    """Raw LLM call. Returns string response."""
    client = _get_client()
    temp = temperature if temperature is not None else settings.llm_temperature
    tokens = max_tokens if max_tokens is not None else settings.llm_max_tokens

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    logger.info("LLM call: model=%s, temp=%.1f", settings.deepseek_model, temp)
    response = client.chat.completions.create(
        model=settings.deepseek_model,
        messages=messages,
        temperature=temp,
        max_tokens=tokens,
    )
    content = response.choices[0].message.content or ""
    logger.info("LLM response: %d chars, tokens=%s", len(content), response.usage)
    return content


def _extract_json(text: str) -> str:
    """Extract JSON from LLM response, handling markdown fences and noise."""
    # Remove markdown code fences
    text = re.sub(r"```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?\s*```", "", text)
    text = text.strip()

    # Find the JSON object or array
    brace_start = text.find("{")
    bracket_start = text.find("[")

    if brace_start == -1 and bracket_start == -1:
        return text

    if brace_start == -1:
        start = bracket_start
    elif bracket_start == -1:
        start = brace_start
    else:
        start = min(brace_start, bracket_start)

    # Find matching closing bracket
    open_char = text[start]
    close_char = "}" if open_char == "{" else "]"
    depth = 0
    for i in range(start, len(text)):
        if text[i] == open_char:
            depth += 1
        elif text[i] == close_char:
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    # If no matching close found, return from start to end
    return text[start:]


def call_llm_structured(
    user_prompt: str,
    response_model: Type[T],
    system_prompt: str = "",
    max_retries: int = 2,
    temperature: float | None = None,
) -> T:
    """
    Call LLM and parse response into a Pydantic model.
    Retries with reprompt on parse failure.
    """
    schema_hint = (
        f"\n\nYou MUST respond with ONLY valid JSON (no markdown, no explanation) "
        f"matching this schema:\n{json.dumps(response_model.model_json_schema(), indent=2)}"
    )
    full_system = (system_prompt + schema_hint) if system_prompt else schema_hint.strip()

    raw = ""
    last_error = None

    for attempt in range(max_retries + 1):
        if attempt == 0:
            raw = call_llm(user_prompt, system_prompt=full_system, temperature=temperature)
        else:
            # Retry with error context
            retry_prompt = (
                f"Your previous response was not valid JSON.\n"
                f"Error: {last_error}\n\n"
                f"Original request: {user_prompt}\n\n"
                f"Respond with ONLY valid JSON, no markdown fences, no explanation."
            )
            raw = call_llm(retry_prompt, system_prompt=full_system, temperature=temperature)

        try:
            cleaned = _extract_json(raw)
            data = json.loads(cleaned)
            return response_model.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            last_error = str(e)[:500]
            logger.warning(
                "LLM parse attempt %d/%d failed: %s",
                attempt + 1, max_retries + 1, last_error
            )

    # All retries exhausted — return a default instance if possible
    logger.error("LLM structured output failed after %d attempts. Raw: %s", max_retries + 1, raw[:500])
    try:
        return response_model.model_validate({})
    except ValidationError:
        raise ValueError(f"Failed to parse LLM output: {last_error}\nRaw: {raw[:500]}")
