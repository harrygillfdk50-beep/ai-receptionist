"""Tests for execution/google_calendar.py — booking flow.

These tests mock the Google API client entirely so we don't make real
network calls or need OAuth credentials during CI.
"""

from unittest.mock import MagicMock, patch

from execution.google_calendar import book_appointment


@patch("execution.google_calendar._build_calendar_service")
def test_book_appointment_returns_booked_on_success(mock_build_service, monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "fake-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "fake-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_REFRESH_TOKEN", "fake-refresh")

    mock_service = MagicMock()
    mock_service.events().insert().execute.return_value = {
        "id": "evt_abc123",
        "htmlLink": "https://calendar.google.com/event?eid=abc123",
    }
    mock_build_service.return_value = mock_service

    result = book_appointment(
        customer_name="Jane Doe",
        customer_email="jane@example.com",
        start_iso="2026-05-15T14:00:00",
    )

    assert result["status"] == "booked"
    assert result["event_id"] == "evt_abc123"
    assert "calendar.google.com" in result["html_link"]


@patch("execution.google_calendar._build_calendar_service")
def test_book_appointment_returns_error_on_api_failure(mock_build_service, monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "fake-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "fake-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_REFRESH_TOKEN", "fake-refresh")

    mock_service = MagicMock()
    mock_service.events().insert().execute.side_effect = RuntimeError("API down")
    mock_build_service.return_value = mock_service

    result = book_appointment(
        customer_name="John",
        customer_email="john@example.com",
        start_iso="2026-05-15T14:00:00",
    )

    assert result["status"] == "error"
    assert "API down" in result["error"]


@patch("execution.google_calendar._build_calendar_service")
def test_book_appointment_passes_attendee_email_to_calendar(mock_build_service, monkeypatch):
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "fake-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "fake-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_REFRESH_TOKEN", "fake-refresh")

    mock_service = MagicMock()
    mock_service.events().insert().execute.return_value = {"id": "x", "htmlLink": "x"}
    mock_build_service.return_value = mock_service

    book_appointment(
        customer_name="Alex",
        customer_email="alex@example.com",
        start_iso="2026-05-15T14:00:00",
    )

    # Find the actual insert(...) call (last one, since MagicMock chains).
    insert_calls = mock_service.events().insert.call_args_list
    # The last call is the real one with kwargs body=...
    body = insert_calls[-1].kwargs["body"]
    assert body["attendees"][0]["email"] == "alex@example.com"
    assert body["attendees"][0]["displayName"] == "Alex"
    # Default 30-minute meeting + Eastern Time timezone
    assert body["start"]["timeZone"] == "America/Toronto"


@patch("execution.google_calendar._build_calendar_service")
def test_book_appointment_sends_email_invite(mock_build_service, monkeypatch):
    """``sendUpdates='all'`` is what triggers the email invite to attendees."""
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_ID", "fake-id")
    monkeypatch.setenv("GOOGLE_OAUTH_CLIENT_SECRET", "fake-secret")
    monkeypatch.setenv("GOOGLE_OAUTH_REFRESH_TOKEN", "fake-refresh")

    mock_service = MagicMock()
    mock_service.events().insert().execute.return_value = {"id": "x", "htmlLink": "x"}
    mock_build_service.return_value = mock_service

    book_appointment(
        customer_name="Sam",
        customer_email="sam@example.com",
        start_iso="2026-05-15T14:00:00",
    )

    insert_kwargs = mock_service.events().insert.call_args_list[-1].kwargs
    assert insert_kwargs["sendUpdates"] == "all"
