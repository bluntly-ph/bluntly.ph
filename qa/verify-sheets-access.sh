#!/usr/bin/env bash
# Prove the service account can actually reach the QA tracker.
#
# Run in Cloud Shell AFTER sharing the sheet with the service account. This is
# worth doing before touching anything locally: the "forgot to share" mistake
# surfaces as a 404 that reads like the spreadsheet does not exist, and chasing
# that from inside a restarted MCP server is far more work than catching it here.
#
#     bash verify-sheets-access.sh
#
# Reads only. It fetches the sheet's title and tab names and writes nothing.

set -euo pipefail

KEY="${KEY:-$HOME/bluntly-sheets-sa.json}"
SHEET_ID="${SHEET_ID:-1CP3qiD1YSTTtKTPWl28dr8AYXcnrV33svCx7s5T2y1s}"

[ -f "$KEY" ] || { echo "No key at $KEY — run setup-sheets-sa.sh first."; exit 1; }

# google-auth ships with gcloud, so it is always present in Cloud Shell. The
# request itself uses stdlib rather than google-api-python-client, which is not
# guaranteed to be installed.
python3 - "$KEY" "$SHEET_ID" <<'PY'
import json, sys, urllib.error, urllib.request

from google.oauth2 import service_account
from google.auth.transport.requests import Request

key_path, sheet_id = sys.argv[1], sys.argv[2]

with open(key_path) as fh:
    client_email = json.load(fh).get("client_email", "?")

# The Sheets API needs a spreadsheets scope specifically — a default
# cloud-platform token is not accepted, which is a confusing way to fail.
creds = service_account.Credentials.from_service_account_file(
    key_path, scopes=["https://www.googleapis.com/auth/spreadsheets"])
creds.refresh(Request())

req = urllib.request.Request(
    f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}"
    "?fields=properties.title,sheets.properties.title",
    headers={"Authorization": f"Bearer {creds.token}"})

try:
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
except urllib.error.HTTPError as e:
    body = e.read().decode(errors="replace")
    print(f"\n  FAILED — HTTP {e.code}\n")
    if e.code in (403, 404):
        print("  This is almost certainly the sharing step. Open the sheet,")
        print("  click Share, and add this address as an Editor:\n")
        print(f"      {client_email}\n")
        print("  A sheet that has not been shared returns 404 rather than 403,")
        print("  because to this account it genuinely does not exist yet.")
    else:
        print(f"  {body[:400]}")
    sys.exit(1)

print(f"\n  Authenticated as : {client_email}")
print(f"  Spreadsheet      : {data['properties']['title']}")
print("  Tabs             : " + ", ".join(
    s["properties"]["title"] for s in data.get("sheets", [])))
print("\n  READ ACCESS CONFIRMED.")
print("  Note this only proves reading. If the share was set to Viewer rather")
print("  than Editor, this still passes and writes will fail later.")
PY
