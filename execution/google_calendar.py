"""Google Calendar wrapper for booking appointments.

This module exposes one function — ``book_appointment`` — that the Claude
conversation engine can call as a tool when a caller agrees to a time.

Authentication: OAuth2 with a refresh token. Harry runs
``setup_google_oauth.py`` once locally to obtain the refresh token, then
stores it in the Modal secret alongside the OAuth client id + secret.

Why not service account: Personal Gmail accounts can't issue domain-wide
delegation. Refresh token is the simplest path for a single-user calendar.
"""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"


def _build_calendar_service():
    """Construct an authenticated Google Calendar API client.

    Reads OAuth credentials from environment:
      - GOOGLE_OAUTH_CLIENT_ID
      - GOOGLE_OAUTH_CLIENT_SECRET
      - GOOGLE_OAUTH_REFRESH_TOKEN
    """
    creds = Credentials(
        token=None,  # will be refreshed automatically on first call
        refresh_token=os.environ["GOOGLE_OAUTH_REFRESH_TOKEN"],
        token_uri=GOOGLE_TOKEN_URI,
        client_id=os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
        scopes=CALENDAR_SCOPES,
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def book_appointment(
    customer_name: str,
    customer_email: str,
    start_iso: str,
    duration_minutes: int = 30,
    purpose: str = "Discovery call",
    timezone: str = "America/Toronto",
) -> dict:
    """Create a Google Calendar event for a booked discovery call.

    Args:
        customer_name: Caller's full name.
        customer_email: Caller's email — used as the attendee on the invite.
        start_iso: Start time in ISO 8601 format (e.g. ``"2026-05-15T14:00:00"``).
            Local time in the given ``timezone``. No offset suffix needed.
        duration_minutes: Length of the meeting. Default 30.
        purpose: Short summary shown on the calendar event.
        timezone: IANA timezone name. Defaults to Harry's (America/Toronto).

    Returns:
        Dict with keys:
          - ``status``: ``"booked"`` on success, ``"error"`` on failure
          - ``event_id``: Google Calendar event id (success only)
          - ``html_link``: URL to view the event in Google Calendar (success only)
          - ``error``: human-readable message (error only)
    """
    try:
        tz = ZoneInfo(timezone)
        start_dt = datetime.fromisoformat(start_iso).replace(tzinfo=tz)
        end_dt = start_dt + timedelta(minutes=duration_minutes)

        event = {
            "summary": f"{purpose} with {customer_name}",
            "description": (
                f"Booked by AI receptionist (Alisa) on a phone call.\n\n"
                f"Customer: {customer_name}\n"
                f"Email: {customer_email}\n"
                f"Purpose: {purpose}"
            ),
            "start": {"dateTime": start_dt.isoformat(), "timeZone": timezone},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": timezone},
            "attendees": [{"email": customer_email, "displayName": customer_name}],
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "email", "minutes": 60},
                    {"method": "popup", "minutes": 10},
                ],
            },
        }

        service = _build_calendar_service()
        created = service.events().insert(
            calendarId="primary",
            body=event,
            sendUpdates="all",  # email the attendee an invite
        ).execute()

        return {
            "status": "booked",
            "event_id": created["id"],
            "html_link": created.get("htmlLink"),
        }

    except Exception as exc:
        return {"status": "error", "error": str(exc)}
