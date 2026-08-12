#!/usr/bin/env bash
# Create the service account that lets Claude write to the QA Bug Tracker.
#
# Run this in Google Cloud Shell (https://shell.cloud.google.com) — it is free,
# needs no card, and is already signed in as you, so there is nothing to
# authenticate. Paste the whole file in, or upload it and `bash setup-sheets-sa.sh`.
#
# Everything here is free: creating a project, enabling the Sheets API, and
# creating a service account and key are all no-cost operations that never
# prompt for a payment method.
#
# It is safe to re-run. Each step checks for what it would create first, so a
# second run repairs a half-finished setup rather than erroring or duplicating.

set -euo pipefail

PROJECT_ID="${PROJECT_ID:-bluntly-qa-sheets}"
SA_NAME="bluntly-sheets-writer"
KEY_FILE="bluntly-sheets-sa.json"
SHEET_ID="1CP3qiD1YSTTtKTPWl28dr8AYXcnrV33svCx7s5T2y1s"

say() { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }

# --- project ---------------------------------------------------------------
# Project IDs are globally unique across all of Google Cloud, so a plain name
# is very likely taken by someone else. Fall back to a suffixed one rather than
# failing, and report which was actually used.
say "Project"
if gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1; then
  echo "    already exists: $PROJECT_ID"
else
  if ! gcloud projects create "$PROJECT_ID" --name="Bluntly QA Sheets" 2>/dev/null; then
    PROJECT_ID="${PROJECT_ID}-$(tr -dc 'a-z0-9' </dev/urandom | head -c6)"
    echo "    name was taken; using $PROJECT_ID instead"
    gcloud projects create "$PROJECT_ID" --name="Bluntly QA Sheets"
  fi
  echo "    created: $PROJECT_ID"
fi
gcloud config set project "$PROJECT_ID" >/dev/null

# --- API -------------------------------------------------------------------
# Sheets only. The Drive API would additionally be needed to *find* or create
# spreadsheets, but we address this one by ID, so it is left off.
say "Enabling the Google Sheets API (free, no billing account required)"
gcloud services enable sheets.googleapis.com

# --- service account -------------------------------------------------------
say "Service account"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if gcloud iam service-accounts describe "$SA_EMAIL" >/dev/null 2>&1; then
  echo "    already exists: $SA_EMAIL"
else
  # No IAM role is granted on purpose. This account needs no permissions on the
  # project at all — its access to the tracker comes from you sharing the sheet
  # with it, exactly as you would share with a colleague.
  gcloud iam service-accounts create "$SA_NAME" \
    --display-name="Bluntly QA tracker writer"
  echo "    created: $SA_EMAIL"
fi

# --- key -------------------------------------------------------------------
say "Key"
if [ -f "$HOME/$KEY_FILE" ]; then
  echo "    $KEY_FILE already in your home directory; keeping it."
  echo "    Delete it and re-run if you want a fresh key."
else
  gcloud iam service-accounts keys create "$HOME/$KEY_FILE" --iam-account="$SA_EMAIL"
  echo "    written to ~/$KEY_FILE"
fi

# --- what is left for you --------------------------------------------------
cat <<EOF

────────────────────────────────────────────────────────────────────────────
Done in the cloud. Two things left, both on your side.

1. SHARE THE SHEET — this is the step that people miss, and skipping it fails
   later as a 404 that reads like the spreadsheet does not exist.

   Open the tracker, click Share, and add this address as an EDITOR:

       $SA_EMAIL

   https://docs.google.com/spreadsheets/d/$SHEET_ID/edit

   Untick "Notify people" — it is a robot.

2. GET THE KEY ONTO YOUR PC. Run:

       cloudshell download ~/$KEY_FILE

   (or use the three-dot More > Download menu). Save it somewhere outside the
   git repo, then in PowerShell:

       setx GOOGLE_SHEETS_SA_KEY "C:\\Users\\Blutnly.ph\\.config\\gcloud\\$KEY_FILE"

   and restart Claude Code so the MCP server picks it up.

TREAT THAT FILE AS A PASSWORD. Anyone holding it can act as this account on
every sheet it has been shared with. Never commit it. If it leaks, revoke it:

    gcloud iam service-accounts keys list --iam-account=$SA_EMAIL
    gcloud iam service-accounts keys delete KEY_ID --iam-account=$SA_EMAIL
────────────────────────────────────────────────────────────────────────────
EOF
