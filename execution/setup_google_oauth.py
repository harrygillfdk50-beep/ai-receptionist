"""One-time script to obtain a Google Calendar OAuth refresh token.

Run this LOCALLY (not on Modal) after you've created an OAuth Client ID
in Google Cloud Console and downloaded the credentials JSON file.

Usage:
    1. Put ``google_credentials.json`` in this folder (same dir as modal_app.py)
    2. Activate venv: .\\venv\\Scripts\\Activate.ps1
    3. Run: python execution/setup_google_oauth.py
    4. A browser window opens — sign in with the Gmail account whose
       calendar you want appointments booked into. Approve the scopes.
    5. Script prints three values:
         GOOGLE_OAUTH_CLIENT_ID
         GOOGLE_OAUTH_CLIENT_SECRET
         GOOGLE_OAUTH_REFRESH_TOKEN
    6. Paste those into deploy_helper.ps1 alongside the other secrets,
       then run .\\deploy_helper.ps1 to push them to Modal and redeploy.

The refresh token does not expire under normal circumstances. You only
need to run this script again if you revoke access in your Google
account, rotate the OAuth client, or change the requested scopes.
"""

import json
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
CREDENTIALS_PATH = Path(__file__).resolve().parent.parent / "google_credentials.json"


def main() -> None:
    if not CREDENTIALS_PATH.exists():
        print(f"ERROR: {CREDENTIALS_PATH} not found.")
        print("Download it from Google Cloud Console → APIs & Services → "
              "Credentials → your OAuth client → Download JSON, "
              "then save it at the path above.")
        sys.exit(1)

    print(f"Loading OAuth client config from {CREDENTIALS_PATH}")
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)

    # Opens browser; ``access_type='offline'`` is what makes Google issue
    # a refresh_token (without it you'd only get a short-lived access token).
    creds = flow.run_local_server(
        port=0,
        prompt="consent",
        access_type="offline",
    )

    if not creds.refresh_token:
        print("ERROR: no refresh_token returned. Try revoking access at "
              "https://myaccount.google.com/permissions and rerunning.")
        sys.exit(1)

    # Pull client_id and client_secret out of the credentials file so we
    # have the full triple ready to paste into the Modal secret.
    with CREDENTIALS_PATH.open() as f:
        client_config = json.load(f)
    client_info = client_config.get("installed", client_config.get("web", {}))

    print()
    print("=" * 70)
    print("SUCCESS — copy these into deploy_helper.ps1 (next to the other keys):")
    print("=" * 70)
    print(f"  GOOGLE_OAUTH_CLIENT_ID={client_info['client_id']}")
    print(f"  GOOGLE_OAUTH_CLIENT_SECRET={client_info['client_secret']}")
    print(f"  GOOGLE_OAUTH_REFRESH_TOKEN={creds.refresh_token}")
    print("=" * 70)
    print()
    print("Then run .\\deploy_helper.ps1 to push them to Modal + redeploy.")


if __name__ == "__main__":
    main()
