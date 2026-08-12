# Letting Claude write to the QA Bug Tracker

The tracker lives in a Google Sheet, but nothing in this setup could write to it —
the Drive integration reads files and does not edit cells, so every update so far
has been a TSV you paste in by hand. This wires up
[`mcp-google-sheets`](https://github.com/xing5/mcp-google-sheets) so the sheet can
be updated directly.

The `.mcp.json` entry is already committed. What is left is credentials, which
only you can create — they are tied to your Google account, not to this repo.

## Two gotchas already handled

**The package is broken on the current MCP SDK.** `mcp` 2.0.0 removed
`mcp.server.fastmcp`, which this package imports, so a plain
`uvx mcp-google-sheets@latest` dies at startup with `ModuleNotFoundError`. The
config pins `--with "mcp<2"` (resolves to 1.29.0), which fixes it. If a future
release of the package moves to the 2.x SDK, drop that pin.

**It ships 19 tools, ~13k tokens of context.** `ENABLED_TOOLS` trims it to the
six that matter here: `list_spreadsheets`, `list_sheets`, `get_sheet_data`,
`update_cells`, `batch_update_cells`, `add_rows`. Widen it if you want charts or
sheet management.

## Why a service account rather than OAuth

OAuth opens a browser on first run. That is fine in a terminal and bad inside a
stdio server that Claude Code launches in the background, where it can simply
hang. A service account is headless and has no interactive step, at the cost of
one extra click: the sheet has to be shared with it, exactly like sharing with a
colleague.

## Setup

1. **Google Cloud Console** → create or pick a project.
2. **Enable two APIs**: *Google Sheets API* and *Google Drive API*.
3. **Create a service account** (IAM & Admin → Service Accounts). No project role
   is needed — access comes from sharing the sheet, not from IAM.
4. **Create a JSON key** for it and download the file. Put it somewhere outside
   this repo — `C:\Users\Blutnly.ph\.config\gcloud\bluntly-sheets-sa.json` is a
   reasonable home. **Never commit it.**
5. **Share the sheet with the service account.** Open the tracker, hit Share, and
   add the service account's email (it looks like
   `something@your-project.iam.gserviceaccount.com`) as an **Editor**. This is
   the step people forget; without it every call returns a 404 that reads like
   the sheet does not exist.
6. **Set two environment variables**, then restart Claude Code:

   ```powershell
   setx GOOGLE_SHEETS_SA_KEY "C:\Users\Blutnly.ph\.config\gcloud\bluntly-sheets-sa.json"
   setx UVX_PATH "C:\Users\Blutnly.ph\AppData\Roaming\Python\Python312\Scripts\uvx.exe"
   ```

   `UVX_PATH` is only needed because `uvx` is not on PATH here — `uv` was
   installed with `python -m pip install --user uv`. Add its Scripts directory to
   PATH and you can drop the variable, since the config falls back to plain
   `uvx`.

**MCP servers load at startup**, so the tools appear only after Claude Code
restarts, not immediately.

## Checking it works

Ask for the Bug Log tab to be read back. The spreadsheet ID is in the URL:

```
1CP3qiD1YSTTtKTPWl28dr8AYXcnrV33svCx7s5T2y1s
```

If reads work but writes fail, the share in step 5 is Viewer rather than Editor.

## What to apply once it is connected

`qa/bug-log-status.tsv` — 26 rows, five columns, landing on the **Status** cell
of the BUG-001 row. `qa/bug-log-new-rows.tsv` — BUG-027 and BUG-028, appended
below BUG-026. See `qa/README.md`.
