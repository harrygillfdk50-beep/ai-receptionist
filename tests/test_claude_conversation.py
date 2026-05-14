from unittest.mock import MagicMock, patch
from execution.claude_conversation import generate_reply


@patch("execution.claude_conversation.Anthropic")
def test_generate_reply_returns_assistant_text(mock_anthropic_cls, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Hello! How can I help you today?")]
    )

    reply = generate_reply(
        system_prompt="You are a receptionist.",
        history=[],
        new_message="Hi",
    )

    assert reply == "Hello! How can I help you today?"


@patch("execution.claude_conversation.Anthropic")
def test_generate_reply_passes_history_to_claude(mock_anthropic_cls, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="Sure, what time?")]
    )

    history = [
        {"role": "user", "content": "I want to book an appointment."},
        {"role": "assistant", "content": "Of course! What day works for you?"},
    ]
    generate_reply(
        system_prompt="You are a receptionist.",
        history=history,
        new_message="Tomorrow",
    )

    call_args = mock_client.messages.create.call_args
    messages = call_args.kwargs["messages"]
    # history (2) + new user message (1) = 3
    assert len(messages) == 3
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[2]["content"] == "Tomorrow"


@patch("execution.claude_conversation.Anthropic")
def test_generate_reply_uses_sonnet_model(mock_anthropic_cls, monkeypatch):
    """Sonnet 4.6 is the balance of smart-enough for booking flows and fast-enough for phone."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="ok")]
    )

    generate_reply(system_prompt="x", history=[], new_message="y")

    model = mock_client.messages.create.call_args.kwargs["model"]
    assert "claude" in model
    assert "sonnet" in model
