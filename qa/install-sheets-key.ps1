# Move a downloaded service account key out of Downloads and wire it up.
#
#     powershell -ExecutionPolicy Bypass -File "qa/install-sheets-key.ps1"
#
# Downloads is the wrong home for a credential: it is readable by anything
# running as you, it is what browsers and installers rummage through, and it is
# frequently cloud-synced. This moves the key (moves, not copies - one copy, in
# one known place), locks it to your account, and sets the environment variable
# the MCP server reads.
#
# Deliberately ASCII-only. Windows PowerShell 5.1 reads a .ps1 that has no byte
# order mark using the system ANSI codepage, so any UTF-8 punctuation in here
# (an em dash, a curly quote) decodes into bytes that can end a string early and
# produce parser errors hundreds of lines from the real cause. An earlier
# version of this script did exactly that, and the symptom was a valid key being
# reported as empty.

param(
    [string]$Source = "$env:USERPROFILE\Downloads\bluntly-sheets-sa.json",
    [string]$Destination = "$env:USERPROFILE\.config\gcloud\bluntly-sheets-sa.json"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $Source)) {
    Write-Host "No key at $Source" -ForegroundColor Red
    Write-Host "Download it from Cloud Shell first:"
    Write-Host "    cloudshell download ~/bluntly-sheets-sa.json"
    exit 1
}

# A silently-failed download arrives as a 0-byte file. Catch it here rather than
# as an authentication error later that looks like a permissions problem.
$size = (Get-Item $Source).Length
if ($size -eq 0) {
    Write-Host "$Source is 0 bytes - the download did not complete." -ForegroundColor Red
    Write-Host "Re-run it and check 'ls -l' in Cloud Shell shows about 2.3 KB."
    exit 1
}

$raw = Get-Content $Source -Raw
try { $key = $raw | ConvertFrom-Json }
catch {
    Write-Host "$Source is not valid JSON - not a usable key." -ForegroundColor Red
    exit 1
}

# Substring checks rather than a regex character class: '[^"]' inside a quoted
# pattern is where the previous rewrite broke the 5.1 parser outright.
if (-not $raw.Contains('"private_key"') -or -not $raw.Contains('"client_email"')) {
    Write-Host "$Source parses but carries no private_key/client_email." -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Path (Split-Path $Destination) -Force | Out-Null
Move-Item -Path $Source -Destination $Destination -Force

# Strip inherited permissions and grant only this user. Without this the file
# keeps whatever Downloads had, which is broader than a private key deserves.
$acl = "$($env:USERNAME):(R,W)"
icacls $Destination /inheritance:r /grant:r $acl | Out-Null

[Environment]::SetEnvironmentVariable("GOOGLE_SHEETS_SA_KEY", $Destination, "User")

Write-Host ""
Write-Host "  Installed        : $Destination" -ForegroundColor Green
Write-Host "  Service account  : $($key.client_email)"
Write-Host "  Project          : $($key.project_id)"
Write-Host "  Size             : $size bytes"
Write-Host "  Permissions      : $env:USERNAME only, inheritance removed"
Write-Host "  GOOGLE_SHEETS_SA_KEY set for your user account."
Write-Host ""
Write-Host "  Restart Claude Code so the MCP server picks up the variable." -ForegroundColor Yellow
Write-Host "  The sheet must also be shared with the address above as an Editor."
