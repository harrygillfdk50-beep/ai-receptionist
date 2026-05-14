"""Claude API wrapper for the receptionist conversation engine.

Supports two modes:
  - ``generate_reply``: simple text-in/text-out (kept for backwards compatibility
    and the existing tests).
  - ``generate_reply_with_tools``: tool-use loop where Claude can call into
    Python functions (e.g. ``book_appointment``) mid-conversation.

The voice handler in ``modal_app.py`` uses the tools variant — the simple
one stays here in case we want a tools-free quick path later.
"""

import os
from typing import Callable
from anthropic import Anthropic

# Haiku 4.5 instead of Sonnet 4.5 — phone calls reward speed over maximum
# nuance, and Haiku is roughly 2x faster on the first-token latency that
# the caller actually perceives. Tool use (book_appointment) works on Haiku.
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
# Short token cap = faster end-to-end latency. Phone replies are 1-2 sentences;
# 200 tokens is plenty even when one of the assistant blocks is a tool_use call.
MAX_TOKENS = 200

# How many tool-call round trips we'll do for a single user turn before
# giving up. In practice, real bookings need 1 round trip. The cap is a
# defensive guard against runaway loops.
MAX_TOOL_ITERATIONS = 4


def generate_reply(
    system_prompt: str,
    history: list[dict],
    new_message: str,
) -> str:
    """Single-turn text reply, no tools.

    Args:
        system_prompt: The business-specific system prompt.
        history: List of {"role": "user"|"assistant", "content": str} dicts.
        new_message: The latest user message (caller's transcribed speech).

    Returns:
        The assistant's reply text.
    """
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    messages = list(history) + [{"role": "user", "content": new_message}]

    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=messages,
    )

    return response.content[0].text


def generate_reply_with_tools(
    system_prompt: str,
    history: list[dict],
    new_message: str,
    tools: list[dict],
    tool_dispatcher: Callable[[str, dict], dict],
) -> tuple[str, list[dict]]:
    """Generate a reply, allowing Claude to invoke tools mid-conversation.

    Loops until Claude returns a final text response (no more tool calls).

    Args:
        system_prompt: The business-specific system prompt.
        history: Prior conversation. Items are either ``{"role", "content"}``
            (text) or the richer dicts Claude returns when tools are involved.
        new_message: The latest transcribed user utterance.
        tools: Anthropic tool definitions (JSON schema list).
        tool_dispatcher: Callable ``(tool_name, tool_input_dict) -> result_dict``
            that the host environment uses to actually run a tool.

    Returns:
        Tuple of:
          - final text reply (str)
          - updated history including all tool-use round-trips, suitable
            for storing back into the ``CONVERSATIONS`` dict.
    """
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    messages = list(history) + [{"role": "user", "content": new_message}]

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            tools=tools,
            messages=messages,
        )

        # Append the assistant turn (may include tool_use blocks) to history.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            # Plain text reply — we're done. Grab the first text block.
            reply_text = next(
                (block.text for block in response.content if block.type == "text"),
                "",
            )
            return reply_text, messages

        # Run every tool_use block, accumulate results.
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = tool_dispatcher(block.name, block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": str(result),
                })

        messages.append({"role": "user", "content": tool_results})

    # Hit the iteration cap — fall back to a safe response.
    return (
        "Sorry, I'm having trouble with that. Let me have Harry follow up "
        "with you by email instead.",
        messages,
    )
