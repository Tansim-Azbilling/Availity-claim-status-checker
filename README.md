# Availity Claim Status Checker

Tkinter + Playwright desktop automation tool for checking claim status in Availity from a CSV file and exporting enriched results.

## What this app does

- Loads a CSV of claims to process.
- Opens the Availity claim search flow for a selected payer.
- Searches each row by member/patient/date criteria.
- Matches claim rows by `InvoiceNumber`.
- Extracts claim details (status, amounts, denial reason, finalized/check data).
- Saves timestamped progress files and a final results file.

The app currently supports:
- `Healthfirst`
- `Integra`
- `SWHNY`
- `Villagecaremax`

## Requirements

- Python 3.10+ recommended
- Google Chrome installed
- Availity session accessible in Chrome
- Python packages:
  - `pandas`
  - `playwright`

## Setup

1. Create and activate a virtual environment (recommended).
2. Install dependencies:

```bash
pip install pandas playwright
python -m playwright install chromium
```

3. Start Chrome with remote debugging enabled (required):

```bash
chrome.exe --remote-debugging-port=9222
```

If `chrome.exe` is not on PATH, run it using your Chrome install path.

## Input CSV format

The following columns are required:

- `AltPatientID`
- `PatientName` (expected format: `LastName, FirstName`)
- `DOB`
- `StartDate`
- `EndDate`
- `InvoiceNumber`
- `VisitDate`

Notes:
- `PatientName` is split internally into `Last_Name` and `First_Name`.
- Date values are normalized by the app for matching.
- If `InvoiceNumber` is empty, that row is skipped with an error status.

## Run the app

From project root:

```bash
python Availity_Automation.py
```

In the GUI:

1. Select **Collection File** (input CSV).
2. Select **Output Folder**.
3. Enter **Batch Size** (positive integer).
4. Choose **Payer**.
5. Click **Start**.

Use **Stop** to request a graceful stop after the current row.

## Output files

The app writes timestamped CSV files to your output folder:

- Progress-style saves while processing (`progress_*.csv`)
- Final output at end (`FINAL_results_*.csv`)

Added output columns include:

- `Claim ID`
- `Billed Amount`
- `Paid Amount`
- `Claim Status`
- `Denial Reason`
- `Finalized Date`
- `Check Number`
- `Check Date`

## Common statuses and error handling

Rows can be marked with statuses such as:

- `No claims found. Advised to search manually`
- `Claim not found. Search manually`
- `Navigation failed`
- `Form error`
- `Missing InvoiceNumber`
- `Critical error`

The app is designed to continue processing subsequent rows even if one row fails.

## Payer behavior

Payer-specific behavior is configured in `PAYER_CONFIG` inside `availity_app/constants.py`, including:

- Target URL
- Whether HIPAA tab selection is needed
- Whether line-level extraction is used
- Whether remittance-based denial extraction is used

To add a payer, add one config entry with these flags and URL.

## Troubleshooting

- **Browser connection fails**  
  Ensure Chrome is running with `--remote-debugging-port=9222`.

- **No page loaded / selectors time out**  
  Confirm you are logged into Availity and can access the payer page manually.

- **Missing columns error**  
  Verify CSV headers match required names exactly.

- **Playwright errors on first setup**  
  Re-run:
  - `python -m playwright install chromium`

## Project structure

- `Availity_Automation.py` — entry point
- `availity_app/` — GUI + automation logic
- `README.md` — this guide

## Disclaimer

This tool automates interactions with payer portals. Use it in compliance with your organization's security, privacy, and portal usage policies.