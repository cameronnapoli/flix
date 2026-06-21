"""Thin wrapper around the Anthropic API"""

from __future__ import annotations

import os

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "claude-haiku-4-5-20251001"

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def complete(prompt: str, system: str | None = None, model: str = DEFAULT_MODEL, max_tokens: int = 1024) -> str:
    """Send a single prompt to Claude and return its text response."""
    response = _get_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system or "",
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


def complete_structured(
    prompt: str,
    schema: dict,
    system: str | None = None,
    model: str = DEFAULT_MODEL,
    max_tokens: int = 1024,
) -> dict:
    """Ask Claude for a response matching a JSON schema, via forced tool use."""
    response = _get_client().messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system or "",
        tools=[{"name": "respond", "description": "Provide the structured response.", "input_schema": schema}],
        tool_choice={"type": "tool", "name": "respond"},
        messages=[{"role": "user", "content": prompt}],
    )
    for block in response.content:
        if block.type == "tool_use":
            return block.input
    raise RuntimeError("Claude did not return a tool_use block")
