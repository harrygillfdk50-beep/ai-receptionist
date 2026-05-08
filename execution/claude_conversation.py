"""Claude API wrapper for the receptionist conversation engine."""

import os
from anthropic import Anthropic

CLAUDE_MODEL = "claude-sonnet-4-5-20250929"
MAX_TOKENS = 300  # phone replies should be short


def generate_reply(
    system_prompt: str,
    history: list[dict],
    new_message: str,
) -> str:
    """Generate an assistant reply.

    Args:
        system_prompt: The business-specific system prompt.
        history: List of {"role": "user"|"assistant", "content": str} dicts.
        new_message: The latest user message (caller's transcribed speech).

    Returns:
        The assistant's reply text.
    """
    client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    messages = list(history) + [{"role": "user", "content": new_message}]

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    )

    return response.content[0].text
